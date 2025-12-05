# NZFeiQ/core/engine.py
import time
import os
import socket
import threading
import json
import subprocess
import re
import ipaddress
from typing import Optional, Callable, Dict, List, Set, Tuple

# 同级模块引入
from .events import *
from .transport import UdpTransport, DEFAULT_PORT
from .protocol import (
    build_packet, build_packet_with_no, parse_packet, gen_packet_no,
    IPMSG_BR_ENTRY, IPMSG_BR_EXIT, IPMSG_ANSENTRY, IPMSG_BR_ABSENCE,
    IPMSG_SENDMSG, IPMSG_RECVMSG, IPMSG_GETLIST, IPMSG_ANSLIST,
    IPMSG_FILEATTACHOPT, IPMSG_SENDCHECKOPT, IPMSG_RELEASEFILES,
    encode_list_entries, decode_fileattach_lines, encode_fileattach_lines,
    base_command
)
from .state import NodeRegistry, ChatHistory, PendingAck
from .session import Session, SessionState
from .filetransfer import IPMsgFileServer, ipmsg_download_file
from .ocr import ZFeiQOcr
from .crypto import generate_rsa_keypair

# [修改] 路径配置：使用 common 目录
CONFIG_DIR = "common"
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")
KEYS_DIR = os.path.join(CONFIG_DIR, "keys")
DOWNLOAD_DIR_DEFAULT = os.path.join(os.getcwd(), "common", "downloads")

class ZFeiQCore:
    def __init__(self, port: int = DEFAULT_PORT, bind_ip: Optional[str] = None):
        # --- 基础组件 ---
        self.registry = NodeRegistry()
        self.history = ChatHistory()
        self.pending = PendingAck() # [新增] 重传队列
        self.event_handler: Optional[Callable[[Event], None]] = None
        
        # --- 配置状态 ---
        self.username: Optional[str] = None
        self.hostname: str = socket.gethostname()
        self.status: str = "online"
        self.encrypt_mode: str = "on"
        self.encoding: str = "utf-8"
        self.download_dir: str = DOWNLOAD_DIR_DEFAULT
        
        # 加载配置
        self._load_config()
        
        # --- 网络与传输 ---
        self.local_ip: str = bind_ip or self._detect_best_ip()
        listen_ip = self.local_ip if os.name == "nt" else "0.0.0.0"
        
        self.transport = UdpTransport(
            bind_ip=listen_ip,
            port=port,
            iface_ip=self.local_ip,
            recv_callback=self._on_recv
        )
        
        # --- 密钥与安全 ---
        self.rsa_priv: Optional[bytes] = None
        self.rsa_pub: Optional[bytes] = None
        self.sessions: Dict[str, Session] = {}
        self._ensure_keys()
        
        # --- 功能模块 ---
        self._incoming_offers: Dict[str, dict] = {} # offer_id -> meta
        self._attach_map: Dict[Tuple[int, int], str] = {} # (pkt, aid) -> path
        self._ipmsg_srv: Optional[IPMsgFileServer] = None
        self.ocr_engine: Optional[ZFeiQOcr] = None
        
        # --- 后台任务 ---
        self._stop_event = threading.Event()
        self._maint_thread: Optional[threading.Thread] = None
        self._retrans_thread: Optional[threading.Thread] = None # [新增] 重传线程

    def set_event_handler(self, handler: Callable[[Event], None]):
        self.event_handler = handler

    def _emit(self, type: str, **kwargs):
        if self.event_handler:
            self.event_handler(Event(type, kwargs))

    def start(self):
        self.transport.start()
        self._start_background_tasks()
        self._emit(EV_LOG_INFO, msg=f"Core started on {self.local_ip}:{self.transport.port}")
        if self.username:
            self.login(self.username)

    def stop(self):
        self._save_config()
        if self.username:
            self._broadcast_presence(is_exit=True)
        
        self._stop_event.set()
        
        # 等待线程结束
        if self._maint_thread: self._maint_thread.join(timeout=1.0)
        if self._retrans_thread: self._retrans_thread.join(timeout=1.0)
        
        self.transport.stop()
        if self._ipmsg_srv:
            self._ipmsg_srv.stop()

    # ================= 业务命令 API =================

    def login(self, username: str):
        self.username = username
        self._broadcast_presence(is_login=True)
        self._emit(EV_LOG_INFO, msg=f"Logged in as {username}")
        # 自我注册
        self.registry.upsert(self.local_ip, self.username, self.hostname, self.status)

    def logout(self):
        if not self.username: return
        self._broadcast_presence(is_exit=True)
        self.username = None
        self._emit(EV_LOG_INFO, msg="Logged out")

    def run_ocr(self, image_path: str, send_target: Optional[str] = None):
        if not os.path.isfile(image_path):
            self._emit(EV_LOG_ERR, msg=f"Image not found: {image_path}")
            return

        def _worker():
            try:
                self._emit(EV_LOG_INFO, msg="OCR processing...")
                if not self.ocr_engine:
                    self.ocr_engine = ZFeiQOcr.get_instance()
                
                text = self.ocr_engine.run(image_path)
                self._emit(EV_LOG_INFO, msg=f"OCR Result:\n{text}")
                
                if send_target and text and "Error" not in text:
                    header = f"[OCR Result: {os.path.basename(image_path)}]\n"
                    self.send_text(send_target, header + text)
            except Exception as e:
                self._emit(EV_LOG_ERR, msg=f"OCR Error: {e}")

        threading.Thread(target=_worker, daemon=True).start()

    def send_text(self, target_ip: str, text: str):
        if not self.username: return
        
        final_text = text
        is_encrypted = False

        if self.encrypt_mode != "off":
            sess = self._get_session(target_ip)
            if sess.state == SessionState.ESTABLISHED:
                try:
                    final_text = sess.encrypt_msg(text)
                    is_encrypted = True
                except Exception as e:
                    self._emit(EV_LOG_ERR, msg=f"Encrypt fail: {e}")
                    if self.encrypt_mode == "strict": return
            else:
                self._start_handshake(target_ip)
                if self.encrypt_mode == "strict": 
                    self._emit(EV_LOG_WARN, msg="Strict mode: Handshaking...")
                    return

        # [修改] 使用 build_packet_with_no 以获取 pkt_no 用于重传追踪
        pkt_no = gen_packet_no()
        pkt = build_packet_with_no(
            pkt_no, self.username, self.hostname,
            IPMSG_SENDMSG | IPMSG_SENDCHECKOPT, # 强制要求 ACK
            final_text, self.encoding
        )
        self.transport.send_unicast(target_ip, pkt)
        
        # [新增] 加入重传队列
        self.pending.add(pkt_no, target_ip, final_text) # 注意存的是发送出去的文本(可能是密文)
        
        self.history.add(target_ip, "out", text) # 历史存明文
        self._emit(EV_MSG_SENT, target=target_ip, text=text, encrypted=is_encrypted)

    def discover(self, target_ip: Optional[str] = None):
        if not self.username: return
        pkt_entry = self._build_packet(IPMSG_BR_ENTRY if self.status != "away" else IPMSG_BR_ABSENCE, self._build_ext())
        pkt_list = self._build_packet(IPMSG_GETLIST)
        
        if target_ip:
            self.transport.send_unicast(target_ip, pkt_entry)
            self.transport.send_unicast(target_ip, pkt_list)
        else:
            self.transport.send_broadcast(pkt_entry)
            self.transport.send_broadcast(pkt_list)

    def send_file(self, target_ip: str, filepath: str):
        if not os.path.isfile(filepath):
            self._emit(EV_LOG_ERR, msg=f"File not found: {filepath}")
            return
        try:
            filename = os.path.basename(filepath)
            size = os.path.getsize(filepath)
            mtime = int(os.path.getmtime(filepath))
            file_id = int(time.time()) & 0xfffffff
            
            pkt_no = gen_packet_no()
            self._attach_map[(pkt_no, file_id)] = filepath
            self._ensure_ipmsg_server()

            attach_line = encode_fileattach_lines([{
                "id": file_id, "name": filename, "size": size, "mtime": mtime, "attr": 0
            }])
            ext_payload = f"\0{attach_line}\0"

            pkt = build_packet_with_no(
                pkt_no, self.username or "?", self.hostname, 
                IPMSG_SENDMSG | IPMSG_FILEATTACHOPT, 
                ext_payload, self.encoding
            )
            self.transport.send_unicast(target_ip, pkt)
            
            # [新增] 记录到 pending 以便重传 UDP 包
            # 注意：文件 Offer 本身也是一个 SENDMSG，也应该重传直到对方 ACK
            self.pending.add(pkt_no, target_ip, ext_payload, cmd_override=(IPMSG_SENDMSG | IPMSG_FILEATTACHOPT))
            
            self._emit(EV_LOG_INFO, msg=f"Offered file {filename} to {target_ip}")
        except Exception as e:
            self._emit(EV_LOG_ERR, msg=f"Send file failed: {e}")

    def accept_file(self, offer_id: str, save_dir: Optional[str] = None):
        offer = self._incoming_offers.get(offer_id)
        if not offer:
            self._emit(EV_LOG_ERR, msg="Offer not found")
            return

        target_dir = save_dir or self.download_dir
        self._ensure_dir(target_dir)
        
        ip = offer['ip']
        pkt = offer['pkt']
        aid = offer['aid']
        filename = offer['name']
        save_path = os.path.join(target_dir, filename)

        def _worker():
            try:
                def _prog_cb(current):
                    self._emit(EV_FILE_PROG, offer_id=offer_id, current=current, total=offer['size'])
                
                ipmsg_download_file(
                    ip, pkt, aid, save_path, 
                    self.username or "?", self.hostname, 
                    on_progress=_prog_cb
                )
                self._emit(EV_FILE_DONE, offer_id=offer_id, path=save_path)
                
                # 下载完成后发送 Release 报文
                rel_payload = f"{pkt}:{aid}"
                rel_pkt = self._build_packet(IPMSG_RELEASEFILES, rel_payload)
                self.transport.send_unicast(ip, rel_pkt)
                
                # 移除 offer
                self._incoming_offers.pop(offer_id, None)
                
            except Exception as e:
                self._emit(EV_FILE_ERR, offer_id=offer_id, error=str(e))

        threading.Thread(target=_worker, daemon=True).start()

    # ================= 内部逻辑 =================

    def _ensure_dir(self, path):
        if not os.path.exists(path):
            os.makedirs(path, exist_ok=True)

    def _load_config(self):
        try:
            if os.path.exists(CONFIG_FILE):
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    d = json.load(f)
                    self.username = d.get('username')
                    self.status = d.get('status', 'online')
                    self.encrypt_mode = d.get('encrypt_mode', 'on')
                    self.download_dir = d.get('download_dir', self.download_dir)
        except: pass

    def _save_config(self):
        try:
            self._ensure_dir(CONFIG_DIR)
            d = {
                'username': self.username, 'status': self.status,
                'encrypt_mode': self.encrypt_mode, 'download_dir': self.download_dir
            }
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(d, f, indent=2)
        except: pass

    def _ensure_keys(self):
        try:
            priv = os.path.join(KEYS_DIR, "priv.pem")
            pub = os.path.join(KEYS_DIR, "pub.pem")
            if os.path.exists(priv) and os.path.exists(pub):
                with open(priv, "rb") as f: self.rsa_priv = f.read()
                with open(pub, "rb") as f: self.rsa_pub = f.read()
            else:
                self._ensure_dir(KEYS_DIR)
                self.rsa_priv, self.rsa_pub = generate_rsa_keypair()
                with open(priv, "wb") as f: f.write(self.rsa_priv)
                with open(pub, "wb") as f: f.write(self.rsa_pub)
        except Exception as e:
            self._emit(EV_LOG_ERR, msg=f"Key Error: {e}")

    def _build_ext(self):
        caps = ["cap=ack"]
        if self.encrypt_mode != "off":
            caps.append("cap=enc")
            if self.rsa_pub:
                import hashlib
                fp = hashlib.sha256(self.rsa_pub).hexdigest()
                caps.append(f"fp={fp}")
        
        status_str = f"status={self.status};" + ";".join(caps)
        return f"{self.username}\0\0{status_str}"

    def _broadcast_presence(self, is_login=False, is_exit=False):
        cmd = IPMSG_BR_ENTRY
        if is_exit: cmd = IPMSG_BR_EXIT
        elif self.status == "away": cmd = IPMSG_BR_ABSENCE
        pkt = self._build_packet(cmd, self._build_ext())
        self.transport.send_broadcast(pkt)

    def _start_handshake(self, ip):
        sess = self._get_session(ip)
        payload = sess.initiate_handshake()
        if payload:
            pkt = self._build_packet(IPMSG_SENDMSG, payload)
            self.transport.send_unicast(ip, pkt)

    def _get_session(self, ip) -> Session:
        if ip not in self.sessions:
            self.sessions[ip] = Session(
                self.local_ip, ip, 
                debug_logger=lambda m: self._emit(EV_LOG_DEBUG, msg=m)
            )
        return self.sessions[ip]

    def _build_packet(self, cmd, ext=""):
        return build_packet(self.username or "?", self.hostname, cmd, ext, self.encoding)

    def _on_recv(self, data: bytes, addr: Tuple[str, int]):
        src_ip = addr[0]
        try:
            head, ext = parse_packet(data)
            cmd = head['command']
            base = base_command(cmd)
            
            # 更新列表
            ext_status = self._parse_status(ext)
            self.registry.upsert(src_ip, head['username'], head['hostname'], status=ext_status)
            
            if base == IPMSG_BR_ENTRY or base == IPMSG_ANSENTRY:
                if self.username and base == IPMSG_BR_ENTRY:
                    reply = self._build_packet(IPMSG_ANSENTRY, self._build_ext())
                    self.transport.send_unicast(src_ip, reply)
                self._emit(EV_NODE_UPD)
                
            elif base == IPMSG_BR_EXIT:
                self.registry.remove(src_ip)
                self._emit(EV_NODE_UPD)

            elif base == IPMSG_SENDMSG:
                text = ext.split('\0', 1)[0]
                
                # 1. 尝试加密处理 (Handshake/Decrypt)
                handled = False
                if self.encrypt_mode != "off":
                    sess = self._get_session(src_ip)
                    if sess.process_packet(text, lambda t: self.transport.send_unicast(src_ip, self._build_packet(IPMSG_SENDMSG, t))):
                        self._emit(EV_ENC_STATE, peer=src_ip, state="ESTABLISHED")
                        handled = True
                    elif text.startswith("ENC;") or text.startswith("ENC2;"):
                        try:
                            text = sess.decrypt_msg(text)
                        except Exception as e:
                            text = "[Decrypt Failed]"
                            self._emit(EV_LOG_ERR, msg=str(e))
                
                if handled: 
                    # 握手包也需要 ACK
                    if (cmd & IPMSG_SENDCHECKOPT):
                        ack = self._build_packet(IPMSG_RECVMSG, str(head['packet_no']))
                        self.transport.send_unicast(src_ip, ack)
                    return

                # 2. 处理附件
                if (cmd & IPMSG_FILEATTACHOPT):
                    try:
                        parts = ext.split('\0', 2)
                        if len(parts) > 1:
                            attach_text = parts[1]
                            files = decode_fileattach_lines(attach_text)
                            for f in files:
                                offer_id = f"{head['packet_no']}:{f['id']}"
                                self._incoming_offers[offer_id] = {
                                    "ip": src_ip, "name": f['name'], "size": f['size'], 
                                    "pkt": head['packet_no'], "aid": f['id']
                                }
                                self._emit(EV_FILE_OFFER, offer_id=offer_id, sender=head['username'], 
                                           filename=f['name'], size=f['size'])
                    except Exception as e:
                        self._emit(EV_LOG_ERR, msg=f"Attach parse error: {e}")

                # 3. 显示消息
                # 如果只有附件没有文本，text 可能为空，此时不应显示空消息
                has_attach = (cmd & IPMSG_FILEATTACHOPT)
                is_file_offer = text.startswith("FILE_OFFER;")
                if text and not (has_attach and text == "") and not is_file_offer:
                    self.history.add(src_ip, "in", text)
                    self._emit(EV_MSG_RECV, sender=head['username'], ip=src_ip, text=text)
                
                # 4. 发送回执
                if (cmd & IPMSG_SENDCHECKOPT):
                    ack = self._build_packet(IPMSG_RECVMSG, str(head['packet_no']))
                    self.transport.send_unicast(src_ip, ack)

            elif base == IPMSG_RECVMSG:
                # [新增] 收到 ACK，从重传队列移除
                try:
                    ack_no = int(ext.strip() or "0")
                    if ack_no:
                        self.pending.remove(ack_no)
                except: pass

            elif base == IPMSG_GETLIST:
                self._send_anslist(src_ip)
            
            elif base == IPMSG_RELEASEFILES:
                # 对方取消下载或下载完成，释放资源
                try:
                    lines = ext.split('\a')
                    for ln in lines:
                        if ':' in ln:
                            p, a = ln.split(':')[:2]
                            self._attach_map.pop((int(p), int(a)), None)
                except: pass

        except Exception as e:
            self._emit(EV_LOG_DEBUG, msg=f"Packet Err: {e}")

    # [新增] 完整的后台任务启动
    def _start_background_tasks(self):
        self._stop_event.clear()
        self._maint_thread = threading.Thread(target=self._maint_loop, daemon=True)
        self._maint_thread.start()
        self._retrans_thread = threading.Thread(target=self._retrans_loop, daemon=True)
        self._retrans_thread.start()

    def _maint_loop(self):
        last_ka = 0
        while not self._stop_event.is_set():
            now = time.time()
            if self.username and (now - last_ka > 30):
                self._broadcast_presence()
                last_ka = now
            if self.registry.purge(90):
                self._emit(EV_NODE_UPD)
            time.sleep(1)

    # [新增] 重传循环
    def _retrans_loop(self):
        while not self._stop_event.is_set():
            time.sleep(1.0)
            now = time.time()
            for pkt_no, (ip, text, attempts, last_ts, cmd_override) in list(self.pending.items()):
                if now - last_ts >= 3.0:
                    if attempts >= 3:
                        # 超过次数放弃
                        self.pending.remove(pkt_no)
                        self._emit(EV_LOG_WARN, msg=f"Msg {pkt_no} to {ip} failed (No ACK)")
                        continue
                    
                    # 重发
                    try:
                        # 使用原 cmd 或者默认 SENDMSG
                        cmd = cmd_override if cmd_override else (IPMSG_SENDMSG | IPMSG_SENDCHECKOPT)
                        pkt = build_packet_with_no(pkt_no, self.username or "?", self.hostname, cmd, text, self.encoding)
                        self.transport.send_unicast(ip, pkt)
                        self.pending.update_attempt(pkt_no)
                        # self._emit(EV_LOG_DEBUG, msg=f"Retrying {pkt_no} to {ip} ({attempts+1})")
                    except Exception as e:
                        print(f"Retrans error: {e}")

    def _ensure_ipmsg_server(self):
        if not self._ipmsg_srv:
            self._ipmsg_srv = IPMsgFileServer(
                bind_ip=(self.local_ip if os.name == "nt" else "0.0.0.0"),
                # [修改] 这里改用 lambda 包装一下，或者直接使用 self._release_file_mapping
                # 为了解决 Pylance 报错 "returns str | None incompatible with None"，
                # 我们显式定义一个不返回值的 lambda，或者使用已有的方法：
                resolver=self._resolve_file_path,
                releaser=self._release_file_mapping  # 直接引用已定义的方法
            )
            self._ipmsg_srv.start()

    def _resolve_file_path(self, pid: int, aid: int) -> Optional[str]:
        return self._attach_map.get((pid, aid))

    def _release_file_mapping(self, pid: int, aid: int) -> None:
        self._attach_map.pop((pid, aid), None)

    def _send_anslist(self, target_ip):
        entries = []
        for node in self.registry.list_nodes():
            entries.append({"username": node.username, "ip": node.ip, "hostname": node.hostname})
        payload = encode_list_entries(entries)
        pkt = self._build_packet(IPMSG_ANSLIST, payload)
        self.transport.send_unicast(target_ip, pkt)

    def _parse_status(self, ext):
        if not ext: return "online"
        if "status=busy" in ext: return "busy"
        if "status=away" in ext: return "away"
        return "online"

    # [补全] 完整的 IP 探测逻辑
    def _detect_best_ip(self):
        # 1. 尝试利用 Windows/Linux 命令获取所有 IP 并评估
        candidates = []
        try:
            if os.name == "nt":
                out = subprocess.check_output(["ipconfig"], stderr=subprocess.STDOUT).decode("gbk", errors="ignore")
                for line in out.splitlines():
                    m = re.search(r"IPv4[^:]*:\s*([0-9.]+)", line)
                    if m: candidates.append(m.group(1))
            else:
                out = subprocess.check_output(["ip", "-4", "addr"]).decode("utf-8", errors="ignore")
                for line in out.splitlines():
                    m = re.search(r"inet\s+([0-9.]+)/", line)
                    if m: candidates.append(m.group(1))
        except: pass

        # 评分：优先取常见的局域网段
        best = None
        best_score = -1
        for ip in candidates:
            if ip.startswith("127."): continue
            score = 0
            if ip.startswith("192.168."): score = 10
            elif ip.startswith("10."): score = 9
            elif ip.startswith("172."): score = 8
            if score > best_score:
                best_score = score
                best = ip
        
        if best: return best

        # 2. 回退方案：UDP 探测
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except:
            return "127.0.0.1"
