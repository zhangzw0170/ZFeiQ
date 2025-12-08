# NZFeiQ/core/session.py
import os
import time
import hashlib
from enum import Enum, auto
from typing import Optional, Dict, Set, Tuple, Callable

# [修改] 引入新的原语
from .crypto import (
    hkdf_sha256, 
    generate_x25519_keypair, derive_x25519_shared, 
    chacha20_encrypt, chacha20_decrypt,
    b64e, b64d
)

class SessionState(Enum):
    NONE = auto()
    KX_SENT = auto()
    ESTABLISHED = auto()

class Session:
    def __init__(self, local_ip: str, peer_ip: str, debug_logger: Optional[Callable[[str], None]] = None):
        self.local_ip = local_ip
        self.peer_ip = peer_ip
        self._log_func = debug_logger
        
        self.state = SessionState.NONE
        # 记录对端公钥指纹（或摘要），用于检测密钥变化
        self.peer_fp: Optional[str] = None
        
        # 密钥材料
        self.key: Optional[bytes] = None      # 32字节 ChaCha20 Key
        self.sid: Optional[bytes] = None      # 会话ID
        
        # [修改] 暂存 X25519 私钥对象 (不再是 seed bytes)
        self.local_ephemeral_priv = None 
        
        self.send_ctr = 0
        self.recv_window: Set[int] = set()
        self.last_active_ts = 0.0
        
        self.peer_ready = False
        self.ready_announced = False

    def log(self, msg: str):
        if self._log_func: self._log_func(f"[Session {self.peer_ip}] {msg}")

    def reset(self):
        self.state = SessionState.NONE
        self.key = None
        self.sid = None
        self.local_ephemeral_priv = None
        self.send_ctr = 0
        self.recv_window.clear()
        self.peer_ready = False
        self.ready_announced = False
        self.log("Reset to NONE")

    def initiate_handshake(self) -> Optional[str]:
        if self.state == SessionState.KX_SENT:
            if time.time() - self.last_active_ts < 3.0:
                return None
        
        self.reset()
        
        # [修改] 生成 X25519 密钥对
        priv, pub_bytes = generate_x25519_keypair()
        self.local_ephemeral_priv = priv
        
        self.state = SessionState.KX_SENT
        self.last_active_ts = time.time()
        
        # [修改] 发送 pubA 而不是 seedA
        return f"KX1;ver=2;fp=;pubA={b64e(pub_bytes)}"

    def process_packet(self, text: str, reply_sender: Callable[[str], None]) -> bool:
        self.last_active_ts = time.time()
        if text.startswith("KX1;"): return self._handle_kx1(text, reply_sender)
        elif text.startswith("KX2;"): return self._handle_kx2(text, reply_sender)
        elif text.startswith("ENCREADY;"): return self._handle_encready(text)
        return False

    def _handle_kx1(self, text: str, send_func) -> bool:
        """收到 KX1 (pubA)"""
        # 竞态仲裁
        if self.state == SessionState.KX_SENT:
            if self.local_ip > self.peer_ip:
                self.log("Race: Dominant, ignoring KX1.")
                return False
            else:
                self.log("Race: Submissive, yielding.")
                self.state = SessionState.NONE

        try:
            fields = self._parse_fields(text)
            peer_pub = b64d(fields.get("pubA", ""))
            if len(peer_pub) != 32: return False
        except: return False

        # [修改] 生成我的 X25519 密钥
        my_priv, my_pub = generate_x25519_keypair()
        
        # 回复 KX2 (pubB)
        reply_text = f"KX2;ver=2;fp=;pubB={b64e(my_pub)}"
        send_func(reply_text)
        
        # [修改] ECDH 计算共享密钥 + HKDF 派生
        shared_secret = derive_x25519_shared(my_priv, peer_pub)
        self._derive_keys(shared_secret)
        
        self._send_encready(send_func)
        return True

    def _handle_kx2(self, text: str, send_func) -> bool:
        """收到 KX2 (pubB)"""
        if self.state != SessionState.KX_SENT: return False

        try:
            fields = self._parse_fields(text)
            peer_pub = b64d(fields.get("pubB", ""))
            if len(peer_pub) != 32: return False
        except: return False

        if not self.local_ephemeral_priv:
            self.reset()
            return False

        # [修改] ECDH 计算
        shared_secret = derive_x25519_shared(self.local_ephemeral_priv, peer_pub)
        self._derive_keys(shared_secret)
        
        self._send_encready(send_func)
        return True

    def _handle_encready(self, text: str) -> bool:
        if self.state != SessionState.ESTABLISHED or not self.sid: return False
        fields = self._parse_fields(text)
        remote_sid = b64d(fields.get("sid", ""))
        if remote_sid == self.sid:
            if not self.peer_ready:
                self.peer_ready = True
                self.log("Peer confirmed ENCREADY (Secure Channel Open).")
                return True
        return False

    def encrypt_msg(self, plaintext: str) -> str:
        if self.state != SessionState.ESTABLISHED: raise RuntimeError("Not ready")

        # 显式断言，消除类型警告
        assert self.key is not None, "Key missing in ESTABLISHED state"
        assert self.sid is not None, "SID missing in ESTABLISHED state"
        
        self.send_ctr += 1
        nonce = self._derive_nonce(self.sid, self.send_ctr)
        
        # [修改] 使用 ChaCha20-Poly1305 加密
        ct, tag = chacha20_encrypt(self.key, plaintext.encode("utf-8"), nonce, aad=self.sid)
        
        return f"ENC;sid={b64e(self.sid)};ctr={self.send_ctr};tag={b64e(tag)};b64={b64e(ct)}"

    def decrypt_msg(self, text: str) -> str:
        if self.state != SessionState.ESTABLISHED: raise RuntimeError("Not ready")
        
        assert self.key is not None
        assert self.sid is not None

        fields = self._parse_fields(text)
        msg_sid = b64d(fields.get("sid", ""))
        msg_ctr = int(fields.get("ctr", "0"))
        
        if msg_sid != self.sid: raise ValueError("SID mismatch")
        if msg_ctr in self.recv_window: raise ValueError(f"Replay detected ctr={msg_ctr}")
        
        nonce = self._derive_nonce(self.sid, msg_ctr)
        ct = b64d(fields.get("b64", ""))
        tag = b64d(fields.get("tag", ""))
        
        # [修改] 使用 ChaCha20-Poly1305 解密
        pt_bytes = chacha20_decrypt(self.key, nonce, ct, tag, aad=self.sid)
        
        self.recv_window.add(msg_ctr)
        if len(self.recv_window) > 1024:
            try: self.recv_window.remove(min(self.recv_window))
            except: pass
            
        return pt_bytes.decode("utf-8", errors="ignore")

    def _derive_keys(self, shared_secret: bytes):
        """从 ECDH 共享密钥派生会话密钥 (ChaCha20 Key)"""
        # 使用 HKDF 将共享密钥扩展为 32 字节的对称密钥
        # info 字段加入协议名防篡改
        self.key = hkdf_sha256(ikm=shared_secret, info=b"zfeiq-x25519-chacha20", length=32)
        # SID 取密钥的 Hash 前 8 位 (简化)
        self.sid = hashlib.sha256(self.key).digest()[:8]
        
        self.state = SessionState.ESTABLISHED
        self.local_ephemeral_priv = None # 握手完成，销毁私钥 (PFS)
        self.log(f"Secure Connection Established. SID={b64e(self.sid)}")

    def _derive_nonce(self, sid: bytes, ctr: int) -> bytes:
        # Nonce 派生逻辑不变
        h = hashlib.sha256()
        h.update(sid)
        h.update(b"zfeiq_nonce")
        h.update(str(ctr).encode('ascii'))
        return h.digest()[:12]

    def _send_encready(self, send_func):
        if self.state == SessionState.ESTABLISHED and self.sid:
            txt = f"ENCREADY;sid={b64e(self.sid)}"
            send_func(txt)
            
    def _parse_fields(self, text: str) -> Dict[str, str]:
        return dict(x.split("=", 1) for x in text.split(";") if "=" in x)