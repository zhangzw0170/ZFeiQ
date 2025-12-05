# zfeiq_core/session.py
import os
import time
import hashlib
from enum import Enum, auto
from typing import Optional, Dict, Set, Tuple, Callable

# 引用同级目录下的 crypto 模块
from .crypto import hkdf_sha256, aes_gcm_encrypt, aes_gcm_decrypt, b64e, b64d

class SessionState(Enum):
    NONE = auto()          # 无会话 / 初始状态
    KX_SENT = auto()       # 我主动发起了 KX1，正在等待 KX2
    ESTABLISHED = auto()   # 密钥已派生，会话已建立，可以收发 ENC

class Session:
    """
    管理与单个 IP 的加密会话状态机。
    负责：握手状态流转、密钥派生、消息加解密、防重放窗口。
    不负责：网络 IO (由上层传入回调处理)。
    """
    def __init__(self, local_ip: str, peer_ip: str, debug_logger: Optional[Callable[[str], None]] = None):
        self.local_ip = local_ip
        self.peer_ip = peer_ip
        self._log_func = debug_logger
        
        self.state = SessionState.NONE
        
        # 密钥材料
        self.key: Optional[bytes] = None      # 32字节会话密钥 (AES-256)
        self.sid: Optional[bytes] = None      # 8字节会话ID
        self.local_seed: Optional[bytes] = None # 我生成的随机种子 (暂存)
        
        # 计数器与防重放
        self.send_ctr = 0
        self.recv_window: Set[int] = set()
        self.last_active_ts = 0.0
        
        # 状态标记 (用于 UI 显示或逻辑判断)
        self.peer_ready = False      # 对方是否发送了 ENCREADY
        self.ready_announced = False # 是否已向上层报告过“加密就绪”

    def log(self, msg: str):
        if self._log_func:
            self._log_func(f"[Session {self.peer_ip}] {msg}")

    def reset(self):
        """重置会话到初始状态 (用于清理或重新握手)"""
        self.state = SessionState.NONE
        self.key = None
        self.sid = None
        self.local_seed = None
        self.send_ctr = 0
        self.recv_window.clear()
        self.peer_ready = False
        self.ready_announced = False
        self.log("Reset to NONE")

    def initiate_handshake(self) -> Optional[str]:
        """
        (主动) 生成 KX1 报文内容。
        返回: 报文文本 (e.g. "KX1;...")，若因防抖未生成则返回 None。
        """
        # 防抖：如果已经在握手中且时间很短，不要重复生成
        if self.state == SessionState.KX_SENT:
            if time.time() - self.last_active_ts < 3.0:
                self.log("Handshake debounce: ignoring duplicate init")
                return None
        
        self.reset() # 重新开始
        self.local_seed = os.urandom(32)
        self.state = SessionState.KX_SENT
        self.last_active_ts = time.time()
        
        # Level B: 明文交换种子
        return f"KX1;ver=1;fp=;seedA={b64e(self.local_seed)}"

    def process_packet(self, text: str, reply_sender: Callable[[str], None]) -> bool:
        """
        处理入站的加密控制包 (KX1/KX2/ENCREADY)。
        :param text: 消息内容 (去除了命令头)
        :param reply_sender: 回调函数，用于发送回复包 func(text) -> None
        :return: True 表示握手状态有重要变更 (如建立完成)
        """
        self.last_active_ts = time.time()
        
        if text.startswith("KX1;"):
            return self._handle_kx1(text, reply_sender)
        elif text.startswith("KX2;"):
            return self._handle_kx2(text, reply_sender)
        elif text.startswith("ENCREADY;"):
            return self._handle_encready(text)
        return False

    def _handle_kx1(self, text: str, send_func) -> bool:
        """收到 KX1：作为响应方"""
        # 竞态仲裁 (Simultaneous Open)
        if self.state == SessionState.KX_SENT:
            # 双方同时发起，IP 大者为主 (Dominant)，小者退让 (Submissive)
            if self.local_ip > self.peer_ip:
                self.log(f"Race: I am dominant ({self.local_ip} > {self.peer_ip}), ignoring peer's KX1.")
                return False # 坚持我的 KX1，忽略对方
            else:
                self.log("Race: I am submissive, yielding to peer's KX1.")
                self.state = SessionState.NONE # 放弃我的主动状态，转为响应对方

        try:
            fields = self._parse_fields(text)
            seed_a = b64d(fields.get("seedA", ""))
            if len(seed_a) != 32:
                return False
        except Exception:
            return False

        # 生成我的种子，回复 KX2
        my_seed = os.urandom(32)
        reply_text = f"KX2;ver=1;fp=;seedB={b64e(my_seed)}"
        send_func(reply_text)
        
        # 立即派生密钥，进入 ESTABLISHED
        # 注意：这里我们不仅是响应者，同时也拥有了全部材料
        self._derive_keys(local_seed=my_seed, peer_seed=seed_a)
        
        # 发送 ENCREADY 通知对方我已就绪
        self._send_encready(send_func)
        return True

    def _handle_kx2(self, text: str, send_func) -> bool:
        """收到 KX2：作为发起方"""
        if self.state != SessionState.KX_SENT:
            return False

        try:
            fields = self._parse_fields(text)
            seed_b = b64d(fields.get("seedB", ""))
            if len(seed_b) != 32:
                return False
        except Exception:
            return False

        if not self.local_seed:
            self.reset()
            return False

        # 派生密钥
        self._derive_keys(local_seed=self.local_seed, peer_seed=seed_b)
        
        # 发送 ENCREADY
        self._send_encready(send_func)
        return True

    def _handle_encready(self, text: str) -> bool:
        if self.state != SessionState.ESTABLISHED or not self.sid:
            return False
            
        fields = self._parse_fields(text)
        remote_sid = b64d(fields.get("sid", ""))
        
        # 只有 SID 匹配才确认
        if remote_sid == self.sid:
            if not self.peer_ready:
                self.peer_ready = True
                self.log("Peer confirmed ENCREADY.")
                return True # 状态变更：完全握手
        return False

    def encrypt_msg(self, plaintext: str) -> str:
        """加密文本，返回 ENC 格式字符串"""
        if self.state != SessionState.ESTABLISHED or not self.key or not self.sid:
            raise RuntimeError("Session not ready for encryption")
        
        self.send_ctr += 1
        nonce = self._derive_nonce(self.sid, self.send_ctr)
        
        # AES-GCM 加密
        # 注意：crypto.py 的 aes_gcm_encrypt 返回 (nonce, ciphertext, tag)
        # 但我们要用自己派生的 nonce，所以传进去
        _, ct, tag = aes_gcm_encrypt(self.key, plaintext.encode("utf-8"), aad=self.sid, nonce=nonce)
        
        # 构造报文: ENC;sid=...;ctr=...;tag=...;b64=...
        b64_sid = b64e(self.sid)
        b64_tag = b64e(tag)
        b64_ct = b64e(ct)
        return f"ENC;sid={b64_sid};ctr={self.send_ctr};tag={b64_tag};b64={b64_ct}"

    def decrypt_msg(self, text: str) -> str:
        """解密 ENC 报文，返回明文。失败抛出异常"""
        if self.state != SessionState.ESTABLISHED or not self.key or not self.sid:
            raise RuntimeError("Session not ready for decryption")
            
        fields = self._parse_fields(text)
        msg_sid = b64d(fields.get("sid", ""))
        msg_ctr = int(fields.get("ctr", "0"))
        
        # 1. 检查 SID
        if msg_sid != self.sid:
            raise ValueError("SID mismatch")
            
        # 2. 防重放窗口检查
        if msg_ctr in self.recv_window:
            raise ValueError(f"Replayed packet ctr={msg_ctr}")
            
        # 3. 派生 Nonce 并解密
        nonce = self._derive_nonce(self.sid, msg_ctr)
        ct = b64d(fields.get("b64", ""))
        tag = b64d(fields.get("tag", ""))
        
        pt_bytes = aes_gcm_decrypt(self.key, nonce, ct, tag, aad=self.sid)
        
        # 4. 更新窗口 (简单的滑动窗口实现)
        self.recv_window.add(msg_ctr)
        if len(self.recv_window) > 1024:
            try:
                self.recv_window.remove(min(self.recv_window))
            except: pass
            
        return pt_bytes.decode("utf-8", errors="ignore")

    def _derive_keys(self, local_seed: bytes, peer_seed: bytes):
        # 确定性 IKM 排序：(Small_IP_Seed) + (Large_IP_Seed)
        # 保证双方算出的 IKM 一致
        l_ip, p_ip = self.local_ip, self.peer_ip
        if l_ip < p_ip:
            ikm = local_seed + peer_seed
        else:
            ikm = peer_seed + local_seed
            
        # HKDF-SHA256 派生 32 字节 Key
        self.key = hkdf_sha256(ikm, info=b"zfeiq-aes256gcm", length=32)
        # SID 取 IKM 哈希的前 8 字节
        self.sid = hashlib.sha256(ikm).digest()[:8]
        
        self.state = SessionState.ESTABLISHED
        self.log(f"Keys derived. SID={b64e(self.sid)}")

    def _derive_nonce(self, sid: bytes, ctr: int) -> bytes:
        # Nonce = SHA256(sid + "zfeiq_msg" + ctr)[0:12]
        # 确定性派生，不需要在网络上传输 Nonce
        h = hashlib.sha256()
        h.update(sid)
        h.update(b"zfeiq_msg") # 固定盐
        h.update(str(ctr).encode('ascii'))
        return h.digest()[:12]

    def _send_encready(self, send_func):
        if self.state == SessionState.ESTABLISHED and self.sid:
            txt = f"ENCREADY;sid={b64e(self.sid)}"
            send_func(txt)
            
    def _parse_fields(self, text: str) -> Dict[str, str]:
        return dict(x.split("=", 1) for x in text.split(";") if "=" in x)
