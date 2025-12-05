# zfeiq_core/engine.py
import time
import os
import socket
import threading
import ipaddress
import subprocess
import re
from typing import Optional, Callable, Dict, List, Set, Tuple

# 引入同级模块
from .events import *
from .transport import UdpTransport, DEFAULT_PORT
from .protocol import (
    build_packet, build_packet_with_no, parse_packet, gen_packet_no,
    IPMSG_BR_ENTRY, IPMSG_BR_EXIT, IPMSG_ANSENTRY, IPMSG_BR_ABSENCE,
    IPMSG_SENDMSG, IPMSG_RECVMSG, IPMSG_GETLIST, IPMSG_ANSLIST,
    IPMSG_GETFILEDATA, IPMSG_RELEASEFILES, IPMSG_FILEATTACHOPT,
    encode_list_entries, decode_list_entries,
    encode_fileattach_lines, decode_fileattach_lines,
    base_command
)
from .state import NodeRegistry, ChatHistory
from .session import Session, SessionState
from .filetransfer import create_offer, download_file, IPMsgFileServer, ipmsg_download_file

class ZFeiQCore:
    def __init__(self, port: int = DEFAULT_PORT, bind_ip: Optional[str] = None):
        # --- 基础组件 ---
        self.registry = NodeRegistry()
        self.history = ChatHistory()
        self.event_handler: Optional[Callable[[Event], None]] = None
        
        # --- 配置状态 ---
        self.username: Optional[str] = None
        self.hostname: str = socket.gethostname()
        self.status: str = "online"  # online|busy|away
        self.encrypt_mode: str = "on"  # off|on|strict
        self.encoding: str = "utf-8"
        self.download_dir: str = os.getcwd()
        
        # --- 网络与传输 ---
        self.local_ip: str = bind_ip or self._detect_best_ip()
        # Linux 绑定 0.0.0.0 以接收广播，Windows 绑定具体 IP
        listen_ip = self.local_ip if os.name == "nt" else "0.0.0.0"
        
        self.transport = UdpTransport(
            bind_ip=listen_ip,
            port=port,
            iface_ip=self.local_ip,
            recv_callback=self._on_recv
        )
        
        # --- 加密会话 (IP -> Session) ---
        self.sessions: Dict[str, Session] = {}
        
        # --- 文件传输 ---
        self._incoming_offers: Dict[str, dict] = {} # offer_id -> meta
        self._outgoing_offers: Dict[str, dict] = {}
        self._attach_map: Dict[Tuple[int, int], str] = {} # (pkt, aid) -> path
        self._ipmsg_srv: Optional[IPMsgFileServer] = None
        
        # --- 后台任务 ---
        self._stop_event = threading.Event()
        self._maint_thread: Optional[threading.Thread] = None

    def set_event_handler(self, handler: Callable[[Event], None]):
        """设置外部事件回调，用于接收 Core 的输出"""
        self.event_handler = handler

    def _emit(self, type: str, **kwargs):
        """内部发射事件的辅助方法"""
        if self.event_handler:
            self.event_handler(Event(type, kwargs))

    def start(self):
        """启动核心引擎"""
        self.transport.start()
        self._start_maintenance()
        self._emit(EV_LOG_INFO, msg=f"Core started. IP: {self.local_ip}, Port: {self.transport.port}")
        self._emit(EV_NET_INFO, ip=self.local_ip, port=self.transport.port)

    def stop(self):
        """停止核心引擎"""
        if self.username:
            self.logout()
        self._stop_event.set()
        if self._maint_thread:
            self._maint_thread.join(timeout=1.0)
        self.transport.stop()
        if self._ipmsg_srv:
            self._ipmsg_srv.stop()

    # ================= 业务命令 API =================

    def login(self, username: str):
        if not username: return
        self.username = username
        self._broadcast_presence(is_login=True)
        self._emit(EV_LOG_INFO, msg=f"Logged in as {username}")
        # 登录后立即把自己加入列表（避免依赖回环）
        self.registry.upsert(self.local_ip, self.username, self.hostname, self.status)
        self._emit(EV_NODE_UPD)

    def logout(self):
        if not self.username: return
        self._broadcast_presence(is_exit=True)
        self.registry.remove(self.local_ip)
        self.username = None
        self._emit(EV_LOG_INFO, msg="Logged out")
        self._emit(EV_NODE_UPD)

    def discover(self, target_ip: Optional[str] = None):
        """发送发现报文。target_ip 为空则广播，否则单播"""
        if not self.username: return
        
        # 1. 发送 BR_ENTRY (带扩展信息)
        pkt_entry = self._build_packet(
            IPMSG_BR_ENTRY if self.status != "away" else IPMSG_BR_ABSENCE,
            self._build_ext()
        )
        # 2. 发送 GETLIST (请求列表)
        pkt_list = self._build_packet(IPMSG_GETLIST)

        if target_ip:
            self.transport.send_unicast(target_ip, pkt_entry)
            self.transport.send_unicast(target_ip, pkt_list)
            self._emit(EV_LOG_INFO, msg=f"Unicast discover to {target_ip}")
        else:
            self.transport.send_broadcast(pkt_entry)
            self.transport.send_broadcast(pkt_list)
            self._emit(EV_LOG_INFO, msg="Broadcast discover sent")

    def send_text(self, target_ip: str, text: str):
        """发送文本消息（自动处理加密/握手）"""
        if not self.username:
            self._emit(EV_LOG_WARN, msg="Please login first.")
            return

        final_text = text
        is_encrypted = False

        # --- 加密逻辑 ---
        if self.encrypt_mode != "off":
            sess = self._get_session(target_ip)
            
            # 情况A: 会话已建立 -> 直接加密
            if sess.state == SessionState.ESTABLISHED:
                try:
                    final_text = sess.encrypt_msg(text)
                    is_encrypted = True
                except Exception as e:
                    self._emit(EV_LOG_ERR, msg=f"Encrypt error: {e}")
                    if self.encrypt_mode == "strict": return
            
            # 情况B: 会话未建立 -> 尝试握手
            else:
                self._emit(EV_LOG_INFO, msg=f"Initiating handshake with {target_ip}...")
                kx_payload = sess.initiate_handshake()
                if kx_payload:
                    pkt = self._build_packet(IPMSG_SENDMSG, kx_payload)
                    self.transport.send_unicast(target_ip, pkt)
                
                # Strict 模式下，握手未完成前禁止发送
                if self.encrypt_mode == "strict":
                    self._emit(EV_LOG_WARN, msg="Strict mode: Message buffered until handshake completes.")
                    return 

        # --- 发送逻辑 ---
        # 始终带上 SENDCHECK (请求回执)
        pkt = self._build_packet(IPMSG_SENDMSG | IPMSG_SENDCHECKOPT, final_text)
        self.transport.send_unicast(target_ip, pkt)
        
        # 记录历史 (存明文)
        self.history.add(target_ip, "out", text)
        self._emit(EV_MSG_SENT, target=target_ip, text=text, encrypted=is_encrypted)

    def send_file(self, target_ip: str, filepath: str):
        """发送文件请求"""
        if not os.path.isfile(filepath):
            self._emit(EV_LOG_ERR, msg=f"File not found: {filepath}")
            return

        try:
            # 1. 准备元数据
            filename = os.path.basename(filepath)
            size = os.path.getsize(filepath)
            mtime = int(os.path.getmtime(filepath))
            file_id = int(time.time()) & 0xfffffff
            
            # 2. 登记到 IPMSG 文件服务映射表
            pkt_no = gen_packet_no()
            self._attach_map[(pkt_no, file_id)] = filepath
            self._ensure_ipmsg_server() # 确保 TCP 2425 监听中

            # 3. 构造扩展字段 (以 \0 分隔文本和附件)
            # 格式: 文本\0附件元数据
            attach_line = encode_fileattach_lines([{
                "id": file_id, "name": filename, "size": size, "mtime": mtime, "attr": 0
            }])
            ext_payload = f"\0{attach_line}\0"

            # 4. 发送 UDP 包
            # 注意：这里使用 build_packet_with_no 以便我们知道 pkt_no
            pkt = build_packet_with_no(
                pkt_no, self.username, self.hostname, 
                IPMSG_SENDMSG | IPMSG_FILEATTACHOPT, 
                ext_payload, self.encoding
            )
            self.transport.send_unicast(target_ip, pkt)
            
            # 5. 记录出站 Offer (用于 UI 显示或取消)
            offer_key = f"{pkt_no}:{file_id}"
            self._emit(EV_LOG_INFO, msg=f"Offered file {filename} to {target_ip}")
            
        except Exception as e:
            self._emit(EV_LOG_ERR, msg=f"Send file failed: {e}")

    # ================= 内部逻辑 =================

    def _on_recv(self, data: bytes, addr: Tuple[str, int]):
        src_ip = addr[0]
        try:
            head, ext = parse_packet(data)
            cmd = head['command']
            base = base_command(cmd)
            user = head['username']
            host = head['hostname']
            
            # 1. 更新节点状态
            # 解析 status=xxx, cap=xxx
            ext_status = self._parse_status(ext)
            self.registry.upsert(src_ip, user, host, status=ext_status)
            
            # 2. 路由处理
            if base == IPMSG_BR_ENTRY or base == IPMSG_ANSENTRY:
                if self.username: # 如果我也在线，回复 ANSENTRY
                    if base == IPMSG_BR_ENTRY: # 只回 BR_ENTRY，不回 ANSENTRY (防风暴)
                        reply = self._build_packet(IPMSG_ANSENTRY, self._build_ext())
                        self.transport.send_unicast(src_ip, reply)
                self._emit(EV_NODE_UPD)
                
            elif base == IPMSG_BR_EXIT:
                self.registry.remove(src_ip)
                self._emit(EV_NODE_UPD)
                self._emit(EV_LOG_INFO, msg=f"{user}@{src_ip} logged out")

            elif base == IPMSG_SENDMSG:
                # 提取文本 (第一个 \0 之前)
                text_part = ext.split('\0', 1)[0]
                
                # A. 优先处理加密协议 (KX/ENC)
                handled = False
                if self.encrypt_mode != "off":
                    sess = self._get_session(src_ip)
                    # 交给 Session 状态机处理握手包
                    if sess.handle_packet(text_part, lambda t: self._send_raw(src_ip, t)):
                        self._emit(EV_ENC_STATE, peer=src_ip, state=sess.state.name)
                        handled = True # 这是一个控制包，不作为消息显示
                    # 或者是加密消息 ENC
                    elif text_part.startswith("ENC;") or text_part.startswith("ENC2;"):
                        try:
                            decrypted = sess.decrypt_msg(text_part)
                            text_part = decrypted # 替换为明文
                        except Exception as e:
                            text_part = "[Decryption Failed]"
                            self._emit(EV_LOG_ERR, msg=f"Decrypt fail from {src_ip}: {e}")
                
                if handled: return

                # B. 处理附件 (IPMSG FILEATTACH)
                if (cmd & IPMSG_FILEATTACHOPT):
                    try:
                        # 附件元数据在第一个 \0 之后
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
                                self._emit(EV_FILE_OFFER, offer_id=offer_id, sender=user, 
                                           filename=f['name'], size=f['size'])
                    except Exception as e:
                        self._emit(EV_LOG_ERR, msg=f"Attach parse error: {e}")

                # C. 正常消息展示 (如果非空且非内部协议)
                if text_part:
                    self.history.add(src_ip, "in", text_part)
                    self._emit(EV_MSG_RECV, sender=user, ip=src_ip, text=text_part)
                
                # D. 发送回执 (ACK)
                if (cmd & IPMSG_SENDCHECKOPT):
                    ack = self._build_packet(IPMSG_RECVMSG, str(head['packet_no']))
                    self.transport.send_unicast(src_ip, ack)

            elif base == IPMSG_GETLIST:
                # 对方请求列表 -> 回复 ANSLIST
                self._send_anslist(src_ip)

            elif base == IPMSG_GETFILEDATA:
                # 理论上应该由 IPMsgFileServer (TCP) 处理，但部分客户端可能会发 UDP 试探
                pass

        except Exception as e:
            self._emit(EV_LOG_DEBUG, msg=f"Packet error: {e}")

    # --- 辅助方法 ---

    def _send_raw(self, ip, text):
        """Session 状态机回调专用的发送接口"""
        pkt = self._build_packet(IPMSG_SENDMSG, text)
        self.transport.send_unicast(ip, pkt)

    def _build_packet(self, cmd, ext=""):
        return build_packet(self.username or "unknown", self.hostname, cmd, ext, self.encoding)

    def _build_ext(self):
        """构造状态扩展字段: username\0\0status=...;cap=..."""
        # 兼容性: 飞秋/IPMSG 习惯在 username 后加 \0\0 再跟扩展键值对
        caps = ["cap=ack"]
        if self.encrypt_mode != "off":
            caps.append("cap=enc") # 宣告支持加密
        
        status_str = f"status={self.status};" + ";".join(caps)
        # 注意：build_packet 会自动把 username 放在包头，
        # 这里 ext 只需放 username 之后的附加信息（如果有显示需求）或者直接放键值对
        # 标准做法：username\0\0<group>\0\0... 我们简化处理
        return f"{self.username}\0\0{status_str}"

    def _parse_status(self, ext):
        if not ext: return "online"
        if "status=busy" in ext: return "busy"
        if "status=away" in ext: return "away"
        return "online"

    def _get_session(self, ip) -> Session:
        if ip not in self.sessions:
            # 传入 _log_func 以便 Session 内部也能输出日志到事件总线
            self.sessions[ip] = Session(
                self.local_ip, ip, 
                debug_logger=lambda m: self._emit(EV_LOG_DEBUG, msg=m)
            )
        return self.sessions[ip]

    def _ensure_ipmsg_server(self):
        if not self._ipmsg_srv:
            # 延迟启动文件服务器
            self._ipmsg_srv = IPMsgFileServer(
                bind_ip=(self.local_ip if os.name == "nt" else "0.0.0.0"),
                resolver=self._resolve_file_path,
                releaser=self._release_file_mapping
            )
            self._ipmsg_srv.start()

    def _resolve_file_path(self, pid: int, aid: int) -> Optional[str]:
        return self._attach_map.get((pid, aid))

    def _release_file_mapping(self, pid: int, aid: int):
        self._attach_map.pop((pid, aid), None)

    def accept_file(self, offer_id: str, save_dir: str):
        """接受文件请求，开始下载"""
        offer = self._incoming_offers.get(offer_id)
        if not offer:
            self._emit(EV_LOG_ERR, msg="Offer not found")
            return

        ip = offer['ip']
        pkt = offer['pkt']
        aid = offer['aid']
        filename = offer['name']
        save_path = os.path.join(save_dir, filename)

        def _worker():
            try:
                def _prog_cb(current):
                    self._emit(EV_FILE_PROG, offer_id=offer_id, current=current, total=offer['size'])
                
                # 调用 filetransfer.py 中的下载逻辑
                ipmsg_download_file(
                    ip, pkt, aid, save_path, 
                    self.username, self.hostname, 
                    on_progress=_prog_cb
                )
                self._emit(EV_FILE_DONE, offer_id=offer_id, path=save_path)
            except Exception as e:
                self._emit(EV_FILE_ERR, offer_id=offer_id, error=str(e))

        t = threading.Thread(target=_worker, daemon=True)
        t.start()

    def _broadcast_presence(self, is_login=False, is_exit=False):
        cmd = IPMSG_BR_ENTRY
        if is_exit: cmd = IPMSG_BR_EXIT
        elif self.status == "away": cmd = IPMSG_BR_ABSENCE
        
        pkt = self._build_packet(cmd, self._build_ext())
        self.transport.send_broadcast(pkt)

    def _send_anslist(self, target_ip):
        # 构造 ANSLIST: 用户名\tIP\t主机名 (每行一个)
        entries = []
        for node in self.registry.list_nodes():
            entries.append({"username": node.username, "ip": node.ip, "hostname": node.hostname})
        
        payload = encode_list_entries(entries)
        pkt = self._build_packet(IPMSG_ANSLIST, payload)
        self.transport.send_unicast(target_ip, pkt)

    def _start_maintenance(self):
        """启动后台保活线程"""
        self._stop_event.clear()
        self._maint_thread = threading.Thread(target=self._maint_loop, daemon=True)
        self._maint_thread.start()

    def _maint_loop(self):
        last_keepalive = 0
        while not self._stop_event.is_set():
            now = time.time()
            # 1. 发送心跳 (每30秒)
            if self.username and (now - last_keepalive > 30):
                self._broadcast_presence()
                last_keepalive = now
            
            # 2. 清理超时节点 (90秒无响应)
            removed = self.registry.purge(90)
            if removed:
                self._emit(EV_NODE_UPD)
                for n in removed:
                    self._emit(EV_LOG_INFO, msg=f"Node {n.username}@{n.ip} timeout")
            
            time.sleep(1)

    def _detect_best_ip(self):
        # 简化版 IP 探测，优先取内网 IP
        # 实际代码可复用原 cli.py 中的 _get_best_local_ip 逻辑
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except:
            return "127.0.0.1"
