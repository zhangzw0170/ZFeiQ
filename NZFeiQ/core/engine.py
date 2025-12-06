# NZFeiQ/core/engine.py
import time
import os
import socket
import threading
import json
import subprocess
import re
import ipaddress
import platform
import datetime
from typing import Optional, Callable, Dict, List, Set, Tuple

# 同级模块引入
from .events import *
from .transport import UdpTransport, DEFAULT_PORT
from .protocol import (
    build_packet, build_packet_with_no, parse_packet, gen_packet_no,
    IPMSG_BR_ENTRY, IPMSG_BR_EXIT, IPMSG_ANSENTRY, IPMSG_BR_ABSENCE,
    IPMSG_SENDMSG, IPMSG_RECVMSG, IPMSG_GETLIST, IPMSG_ANSLIST,
    IPMSG_FILEATTACHOPT, IPMSG_SENDCHECKOPT, IPMSG_RELEASEFILES,
    encode_list_entries, decode_list_entries, decode_fileattach_lines, encode_fileattach_lines,
    base_command
)
from .state import NodeRegistry, ChatHistory, PendingAck
from .session import Session, SessionState
from .filetransfer import IPMsgFileServer, ipmsg_download_file
from .ocr import ZFeiQOcr
from .crypto import (
    generate_x25519_keypair, 
    load_x25519_private_key, 
    dump_x25519_private_key
)

CONFIG_DIR = "common"
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")
GROUPS_FILE = os.path.join(CONFIG_DIR, "groups.json")
KEYS_DIR = os.path.join(CONFIG_DIR, "keys")
DOWNLOAD_DIR_DEFAULT = os.path.join(os.getcwd(), "common", "downloads")
QUICK_TEXTS_FILE = os.path.join(CONFIG_DIR, "quick_texts.txt")

class ZFeiQCore:
    def __init__(self, port: int = DEFAULT_PORT, bind_ip: Optional[str] = None):
        # --- 基础组件 ---
        self.registry = NodeRegistry()
        self.history = ChatHistory()
        self.pending = PendingAck()
        self.event_handler: Optional[Callable[[Event], None]] = None
        
        # --- 配置状态 ---
        self.username: Optional[str] = None
        self.hostname: str = socket.gethostname()
        self.status: str = "online"
        self.encrypt_mode: str = "on"
        self.encoding: str = "utf-8"
        self.download_dir: str = DOWNLOAD_DIR_DEFAULT
        
        self.groups: Dict[str, List[str]] = {}         
        self.quick_texts: List[str] = [] # 常用语列表缓存
        
        self._load_config()
        self._load_groups()
        self._load_quick_texts()
        
        # --- 网络与传输 ---
        self.local_ip: str = bind_ip or self._detect_best_ip()
        
        if bind_ip:
            listen_ip = bind_ip
        else:
            listen_ip = self.local_ip if os.name == "nt" else "0.0.0.0"
        
        self.transport = UdpTransport(
            bind_ip=listen_ip,
            port=port,
            iface_ip=self.local_ip,
            recv_callback=self._on_recv
        )
        self.tcp_port = port  # 记录 TCP 监听端口，通常与 UDP 端口一致
        
        # --- 密钥与安全 ---
        self.identity_priv = None
        self.identity_pub_bytes = None
        self.sessions: Dict[str, Session] = {}
        self._ensure_keys()
        
        # --- 功能模块 ---
        self._incoming_offers: Dict[str, dict] = {}
        self._attach_map: Dict[Tuple[int, int], str] = {}
        self._ipmsg_srv: Optional[IPMsgFileServer] = None
        self.ocr_engine: Optional[ZFeiQOcr] = None
        
        # --- 后台任务 ---
        self._stop_event = threading.Event()
        self._maint_thread: Optional[threading.Thread] = None
        self._retrans_thread: Optional[threading.Thread] = None
        
        self.show_cipher = False
        self.log_level = "INFO"

    def set_event_handler(self, handler: Callable[[Event], None]):
        self.event_handler = handler

    def _should_log(self, level: str) -> bool:
        levels = {"DEBUG": 0, "INFO": 1, "WARN": 2, "ERROR": 3}
        current = levels.get(self.log_level.upper(), 1)
        target = levels.get(level.upper(), 1)
        return target >= current

    def _emit(self, type: str, **kwargs):
        if type.startswith("log."):
            level = type.split(".")[1].upper()
            if not self._should_log(level):
                return
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
        self._save_groups()
        if self.username:
            self._broadcast_presence(is_exit=True)
        self._stop_event.set()
        if self._maint_thread: self._maint_thread.join(timeout=1.0)
        if self._retrans_thread: self._retrans_thread.join(timeout=1.0)
        self.transport.stop()
        if self._ipmsg_srv: self._ipmsg_srv.stop()

    # ================= 业务 API =================

    def login(self, username: str):
        self.username = username
        self._broadcast_presence(is_login=True)
        self._emit(EV_LOG_INFO, msg=f"Logged in as {username}")
        self.registry.upsert(self.local_ip, self.username, self.hostname, self.status)

    def logout(self):
        if not self.username: return
        self._broadcast_presence(is_exit=True)
        self.username = None
        self._emit(EV_LOG_INFO, msg="Logged out")

    def _load_quick_texts(self):
        self.quick_texts = [
            "收到。", "在吗？", "稍等一下。", "方便发个文件吗？", 
            "辛苦了！", "谢谢！", "👍"
        ]
        try:
            self._ensure_dir(CONFIG_DIR)
            if os.path.exists(QUICK_TEXTS_FILE):
                with open(QUICK_TEXTS_FILE, 'r', encoding='utf-8') as f:
                    lines = [line.strip() for line in f if line.strip()]
                    if lines: self.quick_texts = lines
            else:
                with open(QUICK_TEXTS_FILE, 'w', encoding='utf-8') as f:
                    f.write("\n".join(self.quick_texts))
        except Exception: pass 

    # [新增] 公开接口：获取常用语
    def get_quick_texts(self) -> List[str]:
        return self.quick_texts

    # --- 搜索 ---
    def search_nodes(self, query: str) -> List[dict]:
        result = []
        q = query.lower()
        for node in self.registry.list_nodes():
            if q in node.username.lower() or q in node.ip:
                result.append({"type": "user", "name": node.username, "ip": node.ip, "status": node.status})
        for gname in self.groups:
            if q in gname.lower():
                result.append({"type": "group", "name": gname, "count": len(self.groups[gname])})
        return result

    # --- 截图 ---
    def capture_screen(self, save_path: str = "") -> Optional[str]:
        """调用系统工具截图并保存 (CLI 使用，GUI 建议使用 SnippingTool)"""
        if not save_path:
            ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            save_dir = os.path.join(self.download_dir, "screenshots")
            self._ensure_dir(save_dir)
            save_path = os.path.join(save_dir, f"screenshot_{ts}.png")
        
        self._ensure_dir(os.path.dirname(save_path))
        try:
            sys_plat = platform.system()
            if sys_plat == "Windows":
                try:
                    from PIL import ImageGrab
                    img = ImageGrab.grab(all_screens=True)
                    img.save(save_path)
                    return save_path
                except ImportError:
                    self._emit(EV_LOG_ERR, msg="Screenshot failed: Pillow not installed")
                    return None
            elif sys_plat == "Linux":
                try:
                    subprocess.run(["scrot", save_path], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    return save_path
                except:
                    try:
                        subprocess.run(["gnome-screenshot", "-f", save_path], check=True, stdout=subprocess.DEVNULL)
                        return save_path
                    except:
                        self._emit(EV_LOG_ERR, msg="Screenshot failed: install scrot or gnome-screenshot")
                        return None
            else:
                self._emit(EV_LOG_ERR, msg=f"Screenshot not supported on {sys_plat}")
                return None
        except Exception as e:
            self._emit(EV_LOG_ERR, msg=f"Screenshot error: {e}")
            return None

    # --- 群组与消息 ---
    def create_group(self, name: str):
        if name not in self.groups:
            self.groups[name] = []
            self._save_groups()
            self._emit(EV_LOG_INFO, msg=f"Group '{name}' created")

    def add_to_group(self, group_name: str, username: str):
        if group_name not in self.groups: self.create_group(group_name)
        if username not in self.groups[group_name]:
            self.groups[group_name].append(username)
            self._save_groups()
            self._emit(EV_LOG_INFO, msg=f"Added {username} to {group_name}")

    def send_group_msg(self, group_name: str, text: str):
        if group_name not in self.groups:
            self._emit(EV_LOG_ERR, msg=f"Group '{group_name}' not found")
            return
        
        members = self.groups[group_name]
        online_nodes = self.registry.list_nodes()
        sent_count = 0
        group_text = f"[Group:{group_name}] {text}"
        
        for target_user in members:
            if target_user == self.username: continue
            target_ips = [n.ip for n in online_nodes if n.username == target_user]
            for ip in target_ips:
                self.send_text(ip, group_text)
                sent_count += 1
        
        self._emit(EV_LOG_INFO, msg=f"Sent group msg to {sent_count} nodes")

    def send_text(self, target_ip: str, text: str):
        if not self.username: return
        if target_ip == 'all':
            self._send_broadcast_msg(text)
            return

        final_text = text
        is_encrypted = False

        if self.encrypt_mode != "off":
            sess = self._get_session(target_ip)
            if sess.state == SessionState.ESTABLISHED:
                try:
                    final_text = sess.encrypt_msg(text)
                    is_encrypted = True
                    if self.show_cipher:
                        self._emit(EV_LOG_INFO, msg=f"Cipher OUT: {final_text}")
                except Exception as e:
                    self._emit(EV_LOG_ERR, msg=f"Encrypt fail: {e}")
                    if self.encrypt_mode == "strict": return
            else:
                self._start_handshake(target_ip)
                if self.encrypt_mode == "strict": return

        pkt_no = gen_packet_no()
        pkt = build_packet_with_no(
            pkt_no, self.username, self.hostname,
            IPMSG_SENDMSG | IPMSG_SENDCHECKOPT,
            final_text, self.encoding
        )
        self.transport.send_unicast(target_ip, pkt)
        self.pending.add(pkt_no, target_ip, final_text)
        self.history.add(target_ip, "out", text)
        self._emit(EV_MSG_SENT, target=target_ip, text=text, encrypted=is_encrypted)

    def _send_broadcast_msg(self, text: str):
        pkt = self._build_packet(IPMSG_SENDMSG, text)
        self.transport.send_broadcast(pkt)
        self._emit(EV_MSG_SENT, target="all", text=text, encrypted=False)

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

            flag = IPMSG_SENDMSG | IPMSG_FILEATTACHOPT | IPMSG_SENDCHECKOPT
            
            pkt = build_packet_with_no(
                pkt_no, self.username or "?", self.hostname, 
                flag, 
                ext_payload, self.encoding
            )
            self.transport.send_unicast(target_ip, pkt)
            
            self.pending.add(pkt_no, target_ip, ext_payload, cmd_override=flag)
            
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
        # 获取对方端口，默认为 2425
        ip, port, pkt, aid, filename = offer['ip'], offer.get('port', 2425), offer['pkt'], offer['aid'], offer['name']
        save_path = os.path.join(target_dir, filename)

        def _worker():
            try:
                def _prog_cb(current):
                    self._emit(EV_FILE_PROG, offer_id=offer_id, current=current, total=offer['size'])
                # 传入端口进行下载
                ipmsg_download_file(ip, pkt, aid, save_path, self.username or "?", self.hostname, encoding=self.encoding, port=port, on_progress=_prog_cb)
                self._emit(EV_FILE_DONE, offer_id=offer_id, path=save_path)
                rel_pkt = self._build_packet(IPMSG_RELEASEFILES, f"{pkt}:{aid}")
                self.transport.send_unicast(ip, rel_pkt)
                self._incoming_offers.pop(offer_id, None)
            except Exception as e:
                self._emit(EV_FILE_ERR, offer_id=offer_id, error=str(e))
        threading.Thread(target=_worker, daemon=True).start()

    def run_ocr(self, image_path: str, send_target: Optional[str] = None):
        if not os.path.isfile(image_path):
            self._emit(EV_LOG_ERR, msg=f"Image not found: {image_path}")
            return
        def _worker():
            try:
                # 初始化 OCR 引擎（懒加载）并汇报类型
                if not self.ocr_engine:
                    self.ocr_engine = ZFeiQOcr.get_instance()

                engine_type = "Unknown"
                if getattr(self.ocr_engine, 'use_npu', False):
                    engine_type = "NPU"
                elif getattr(self.ocr_engine, 'use_external_main', False):
                    engine_type = "NPU (legacy main)"
                else:
                    engine_type = "CPU"

                self._emit(EV_LOG_INFO, msg=f"OCR Engine: {engine_type}")
                self._emit(EV_LOG_INFO, msg="OCR Processing...")

                # 检查引擎是否初始化成功
                if not self.ocr_engine.ready:
                    self._emit(EV_LOG_ERR, msg="OCR engine failed to initialize")
                    return

                start = time.time()
                text = self.ocr_engine.run(image_path)
                elapsed = time.time() - start

                self._emit(EV_LOG_INFO, msg=f"Time cost: {elapsed:.2f} s")

                # 通知上层 OCR 完成（结果事件），包含引擎类型与耗时，便于上层做显示
                self._emit(EV_OCR_DONE, text=text, image_path=image_path, engine_type=engine_type, elapsed=elapsed)

                # 若指定发送目标且识别成功，则发送识别内容
                if send_target and text and "Error" not in text:
                    header = f"[OCR Result: {os.path.basename(image_path)}]\n"
                    if send_target.startswith("group:"):
                        self.send_group_msg(send_target[6:], header + text)
                    else:
                        self.send_text(send_target, header + text)
            except Exception as e:
                self._emit(EV_LOG_ERR, msg=f"OCR Error: {e}")
        threading.Thread(target=_worker, daemon=True).start()

    # ================= 内部逻辑 =================
    def _ensure_dir(self, path):
        if not os.path.exists(path):
            os.makedirs(path, exist_ok=True)

    def resolve_hostname(self, name: str):
        """Resolve a hostname to an IP address using the core's network context.

        This centralizes DNS resolution in core so CLI code doesn't perform
        low-level network operations directly.
        Returns resolved IP string or None on failure.
        """
        try:
            return socket.gethostbyname(name)
        except Exception:
            return None

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

    def _load_groups(self):
        try:
            if os.path.exists(GROUPS_FILE):
                with open(GROUPS_FILE, 'r', encoding='utf-8') as f:
                    self.groups = json.load(f)
        except: self.groups = {}

    def _save_config(self):
        try:
            self._ensure_dir(CONFIG_DIR)
            d = {'username': self.username, 'status': self.status, 'encrypt_mode': self.encrypt_mode, 'download_dir': self.download_dir}
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(d, f, indent=2)
        except: pass

    def _save_groups(self):
        try:
            self._ensure_dir(CONFIG_DIR)
            with open(GROUPS_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.groups, f, indent=2, ensure_ascii=False)
        except: pass

    def _ensure_keys(self):
        priv_path = os.path.join(KEYS_DIR, "identity.bin")
        try:
            self._ensure_dir(KEYS_DIR)
            if os.path.exists(priv_path):
                with open(priv_path, "rb") as f:
                    self.identity_priv = load_x25519_private_key(f.read())
            else:
                self._emit(EV_LOG_INFO, msg="Generating new X25519 Identity Key...")
                self.identity_priv, _ = generate_x25519_keypair()
                with open(priv_path, "wb") as f:
                    f.write(dump_x25519_private_key(self.identity_priv))
            from cryptography.hazmat.primitives import serialization
            self.identity_pub_bytes = self.identity_priv.public_key().public_bytes(
                encoding=serialization.Encoding.Raw, format=serialization.PublicFormat.Raw
            )
        except Exception as e:
            self._emit(EV_LOG_ERR, msg=f"Identity Init Failed: {e}")

    def _build_ext(self):
        caps = ["cap=ack"]
        if self.encrypt_mode != "off":
            caps.append("cap=enc")
            if self.identity_pub_bytes:
                import hashlib
                caps.append(f"fp={hashlib.sha256(self.identity_pub_bytes).hexdigest()}")
        return f"{self.username}\0\0status={self.status};{';'.join(caps)}"

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
            self.sessions[ip] = Session(self.local_ip, ip, debug_logger=lambda m: self._emit(EV_LOG_DEBUG, msg=m))
        return self.sessions[ip]

    def _build_packet(self, cmd, ext=""):
        return build_packet(self.username or "?", self.hostname, cmd, ext, self.encoding)

    def _on_recv(self, data: bytes, addr: Tuple[str, int]):
        src_ip = addr[0]
        src_port = addr[1]
        try:
            head, ext = parse_packet(data)
            cmd, base = head['command'], base_command(head['command'])
            self.registry.upsert(src_ip, head['username'], head['hostname'], status=self._parse_status(ext))
            
            if base in (IPMSG_BR_ENTRY, IPMSG_ANSENTRY):
                if self.username and base == IPMSG_BR_ENTRY:
                    self.transport.send_unicast(src_ip, self._build_packet(IPMSG_ANSENTRY, self._build_ext()))
                self._emit(EV_NODE_UPD)
                if self.encrypt_mode != "off" and self._get_session(src_ip).state == SessionState.NONE:
                    self._start_handshake(src_ip)
            elif base == IPMSG_BR_EXIT:
                self.registry.remove(src_ip); self._emit(EV_NODE_UPD)
            elif base == IPMSG_SENDMSG:
                text = ext.split('\0', 1)[0]
                handled = False
                if self.encrypt_mode != "off":
                    sess = self._get_session(src_ip)
                    if sess.process_packet(text, lambda t: self.transport.send_unicast(src_ip, self._build_packet(IPMSG_SENDMSG, t))):
                        self._emit(EV_ENC_STATE, peer=src_ip, state="ESTABLISHED"); handled = True
                    elif text.startswith("ENC;") or text.startswith("ENC2;"):
                        if self.show_cipher: self._emit(EV_LOG_INFO, msg=f"Cipher IN: {text}")
                        try: text = sess.decrypt_msg(text)
                        except Exception as e: text = "[Decrypt Failed]"; self._emit(EV_LOG_ERR, msg=str(e))
                if handled and (cmd & IPMSG_SENDCHECKOPT):
                    self.transport.send_unicast(src_ip, self._build_packet(IPMSG_RECVMSG, str(head['packet_no'])))
                    return
                if (cmd & IPMSG_FILEATTACHOPT):
                    try:
                        parts = ext.split('\0', 2)
                        if len(parts) > 1:
                            for f in decode_fileattach_lines(parts[1]):
                                oid = f"{head['packet_no']}:{f['id']}"
                                # 记录发送方端口，以便 TCP 连接
                                self._incoming_offers[oid] = {
                                    "ip": src_ip, 
                                    "port": src_port,
                                    "name": f['name'], 
                                    "size": f['size'], 
                                    "pkt": head['packet_no'], 
                                    "aid": f['id']
                                }
                                # 额外输出一条 INFO，方便自动化脚本匹配 offer id
                                self._emit(EV_LOG_INFO, msg=f"File offer: {f['name']} ({f['size']} bytes) from {src_ip} | offer={oid}")
                                self._emit(EV_FILE_OFFER, offer_id=oid, sender=head['username'], filename=f['name'], size=f['size'])
                    except Exception as e: self._emit(EV_LOG_ERR, msg=f"Attach parse error: {e}")
                if text and not (text.startswith("FILE_OFFER;") or ((cmd & IPMSG_FILEATTACHOPT) and not text)):
                    self.history.add(src_ip, "in", text)
                    self._emit(EV_MSG_RECV, sender=head['username'], ip=src_ip, text=text)
                if (cmd & IPMSG_SENDCHECKOPT):
                    self.transport.send_unicast(src_ip, self._build_packet(IPMSG_RECVMSG, str(head['packet_no'])))
            elif base == IPMSG_RECVMSG:
                try: 
                    ack = int(ext.strip() or "0")
                    if ack: self.pending.remove(ack)
                except: pass
            elif base == IPMSG_ANSLIST:
                try:
                    for e in decode_list_entries(ext):
                        if e['ip'] != self.local_ip: self.registry.upsert(e['ip'], e['username'], e['hostname'])
                    self._emit(EV_NODE_UPD)
                except: pass
            elif base == IPMSG_GETLIST:
                self._send_anslist(src_ip)
            elif base == IPMSG_RELEASEFILES:
                try:
                    for ln in ext.split('\a'):
                        if ':' in ln:
                            p, a = ln.split(':')[:2]
                            self._attach_map.pop((int(p), int(a)), None)
                except: pass
        except Exception as e:
            self._emit(EV_LOG_DEBUG, msg=f"Packet Err: {e}")

    def _start_background_tasks(self):
        self._stop_event.clear()
        self._maint_thread = threading.Thread(target=self._maint_loop, daemon=True); self._maint_thread.start()
        self._retrans_thread = threading.Thread(target=self._retrans_loop, daemon=True); self._retrans_thread.start()

    def _maint_loop(self):
        last_ka = 0
        while not self._stop_event.is_set():
            now = time.time()
            if self.username and (now - last_ka > 30):
                self._broadcast_presence(); last_ka = now
            if self.registry.purge(90): self._emit(EV_NODE_UPD)
            time.sleep(1)

    def _retrans_loop(self):
        while not self._stop_event.is_set():
            time.sleep(1.0)
            now = time.time()
            for pkt_no, (ip, text, attempts, last_ts, cmd) in list(self.pending.items()):
                if now - last_ts >= 3.0:
                    if attempts >= 3:
                        self.pending.remove(pkt_no)
                        self._emit(EV_LOG_WARN, msg=f"Msg {pkt_no} to {ip} failed (No ACK)")
                        continue
                    try:
                        cmd_val = cmd if cmd else (IPMSG_SENDMSG | IPMSG_SENDCHECKOPT)
                        self.transport.send_unicast(ip, build_packet_with_no(pkt_no, self.username or "?", self.hostname, cmd_val, text, self.encoding))
                        self.pending.update_attempt(pkt_no)
                    except: pass

    def _ensure_ipmsg_server(self):
        if not self._ipmsg_srv:
            self._ipmsg_srv = IPMsgFileServer(
                bind_ip=self.local_ip,
                port=self.tcp_port,  # 传入端口
                resolver=self._resolve_file_path,
                releaser=self._release_file_mapping
            )
            self._ipmsg_srv.start()

    def _resolve_file_path(self, pid: int, aid: int) -> Optional[str]: return self._attach_map.get((pid, aid))
    def _release_file_mapping(self, pid: int, aid: int) -> None: self._attach_map.pop((pid, aid), None)
    
    def _send_anslist(self, target_ip):
        entries = [{"username": n.username, "ip": n.ip, "hostname": n.hostname} for n in self.registry.list_nodes()]
        self.transport.send_unicast(target_ip, self._build_packet(IPMSG_ANSLIST, encode_list_entries(entries)))

    def _parse_status(self, ext):
        if not ext: return "online"
        if "status=busy" in ext: return "busy"
        if "status=away" in ext: return "away"
        return "online"

    def _detect_best_ip(self) -> str:
        candidates = []
        try:
            if os.name == "nt":
                # Windows ipconfig 解析
                out = subprocess.check_output(["ipconfig"], stderr=subprocess.STDOUT).decode("gbk", errors="ignore")
                for line in out.splitlines():
                    m = re.search(r"IPv4[^:]*:\s*([0-9.]+)", line)
                    if m: candidates.append(m.group(1))
            else:
                # Linux ip addr 解析
                out = subprocess.check_output(["ip", "-4", "addr"]).decode("utf-8", errors="ignore")
                for line in out.splitlines():
                    m = re.search(r"inet\s+([0-9.]+)/", line)
                    if m: candidates.append(m.group(1))
        except: pass

        # 过滤回环地址
        candidates = [ip for ip in candidates if not ip.startswith("127.")]

        if not candidates:
            return "127.0.0.1"

        def ip_sort_key(ip):
            # 优先级评分
            score = 0
            if ip.startswith("192.168."):
                score = 3  # 最高优先级：通常是家用路由器/Wi-Fi
            elif ip.startswith("172."):
                score = 2  # 次高优先级：通常是校园网/企业内网 (172.16.x.x - 172.31.x.x)
            elif ip.startswith("10."):
                score = 1  # 最低优先级：通常是 Docker/WSL/VPN 虚拟网卡
            
            # 将 IP 转换为整数，实现同级下“数值从大到小”的排序辅助
            # 例如 192.168.1.100 > 192.168.1.5
            try:
                ip_int = int(ipaddress.IPv4Address(ip))
            except:
                ip_int = 0
            
            return (score, ip_int)

        # 按照 (优先级, IP数值) 从大到小排序
        candidates.sort(key=ip_sort_key, reverse=True)

        return candidates[0]