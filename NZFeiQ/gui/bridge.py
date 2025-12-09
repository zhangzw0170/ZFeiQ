import sys
import os
import time
import threading
from PyQt5.QtCore import QThread, pyqtSignal

# 确保能导入 core 模块 (假设 gui 目录在 NZFeiQ/gui)
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.engine import ZFeiQCore
from core.session import SessionState
from core.events import (
    EV_MSG_RECV, EV_MSG_SENT, EV_NODE_UPD, 
    EV_FILE_OFFER, EV_FILE_PROG, EV_FILE_DONE, EV_FILE_ERR,
    EV_LOG_INFO, EV_LOG_WARN, EV_LOG_ERR, EV_LOG_DEBUG,
    EV_ENC_STATE, EV_OCR_DONE
)

class Bridge(QThread):
    """
    Core <-> GUI 桥梁
    利用 Core 的 set_event_handler 机制，将底层事件转发为 Qt 信号。
    """
    
    # --- 信号定义 ---
    
    # 消息: (name, ip, text, is_me, is_enc)
    sig_msg = pyqtSignal(str, str, str, bool, bool)
    
    # 节点变动: (在线人数)
    sig_nodes_changed = pyqtSignal(int)
    # 语言变更: (lang_code)
    sig_lang_changed = pyqtSignal(str)
    # 主题变更: (theme_code)
    sig_theme_changed = pyqtSignal(str)
    # 群组变更: (no payload)  GUI 可请求拉取
    sig_groups_changed = pyqtSignal()
    
    # 文件要约: (offer_id, sender_name, filename, size)
    sig_file_offer = pyqtSignal(str, str, str, int)
    
    # 文件进度: (offer_id, current, total)
    sig_file_progress = pyqtSignal(str, int, int)
    
    # 文件完成: (offer_id, saved_path)
    sig_file_done = pyqtSignal(str, str)
    
    # 日志/状态栏: (level, msg)
    sig_log = pyqtSignal(str, str)
    
    # 加密状态变更: (peer_ip, state)
    sig_enc_state = pyqtSignal(str, str)

    # OCR 识别完成信号 (text, engine_type, elapsed_seconds)
    sig_ocr_done = pyqtSignal(str, str, float)

    # Screenshot done: (path, send_target)
    sig_screenshot_done = pyqtSignal(str, str)
    # Screenshot failed: (error_msg)
    sig_screenshot_failed = pyqtSignal(str)

    def __init__(self, port=2425, bind_ip=None):
        super().__init__()
        # 初始化 Core
        self.core = ZFeiQCore(port=port, bind_ip=bind_ip)
        
        # [关键] 注册事件回调
        self.core.set_event_handler(self._on_core_event)
        
        self._running = True

    def run(self):
        """QThread 入口"""
        try:
            # 启动核心服务
            self.core.start()
            self.sig_log.emit("INFO", f"Core 服务已启动 (Port: {self.core.transport.port})")
            
            # 保持线程运行，同时做一些简单的看门狗工作（如有必要）
            while self._running:
                time.sleep(1)
                
        except Exception as e:
            self.sig_log.emit("ERROR", f"Core 异常退出: {e}")

    def capture_screen(self, send_target: str = "", region: bool = False):
        """
        异步触发核心截图命令，完成后通过信号通知 GUI。

        send_target: 可选的目标 IP（为空或 'all' 表示不发送）。
        """
        def _worker(target_ip: str, region_flag: bool):
            try:
                # Only capture and return path; do NOT auto-send (BC: user requested save-then-ask)
                path = self.core.capture_screen(region=region_flag)
                if path:
                    # Emit screenshot done with no automatic send target
                    try:
                        self.sig_screenshot_done.emit(path, '')
                    except Exception:
                        pass
                else:
                    try:
                        self.sig_screenshot_failed.emit('Screenshot failed')
                    except Exception:
                        pass
            except Exception as e:
                try:
                    self.sig_screenshot_failed.emit(str(e))
                except Exception:
                    pass

        t = threading.Thread(target=_worker, args=(send_target or '', region), daemon=True)
        t.start()

    def stop(self):
        """优雅关闭"""
        self._running = False
        self.core.stop()
        self.quit()
        self.wait()

    # --- 事件处理 (Core -> GUI) ---
    def _on_core_event(self, event):
        """
        处理来自 Core 线程的事件，转发为信号。
        注意：此方法运行在 Core 的线程中，emit 是线程安全的。
        """
        evt_type = event.type
        data = event.data
        
        try:
            if evt_type == EV_MSG_RECV:
                # 收到消息
                # 尝试判断该消息是否通过已建立的加密会话到达
                try:
                    sess = self.core._get_session(data['ip'])
                    is_enc = (sess is not None and getattr(sess, 'state', None) == SessionState.ESTABLISHED)
                except Exception:
                    is_enc = False
                self.sig_msg.emit(data.get('sender', '?'), data['ip'], data['text'], False, bool(is_enc))
                
            elif evt_type == EV_MSG_SENT:
                # 自己发送的消息 (Core 发送成功后才通知，比乐观更新更可靠)
                target = data['target']
                # 如果是广播或者特定IP，转换显示文本
                display_ip = target if target != 'all' else 'Broadcast'
                self.sig_msg.emit("我", display_ip, data['text'], True, data.get('encrypted', False))
                
            elif evt_type == EV_NODE_UPD:
                # 节点列表更新
                count = len(self.core.registry.list_nodes())
                self.sig_nodes_changed.emit(count)
                
            elif evt_type == EV_FILE_OFFER:
                # 收到文件请求
                self.sig_file_offer.emit(
                    data['offer_id'], 
                    data.get('sender', '?'), 
                    data['filename'], 
                    data['size']
                )
                
            elif evt_type == EV_FILE_PROG:
                # 文件传输进度
                self.sig_file_progress.emit(data['offer_id'], data['current'], data['total'])
                
            elif evt_type == EV_FILE_DONE:
                # 文件传输完成
                self.sig_file_done.emit(data['offer_id'], data['path'])
                
            elif evt_type == EV_ENC_STATE:
                # 加密会话建立
                self.sig_enc_state.emit(data['peer'], data['state'])
            

            elif evt_type == EV_OCR_DONE:
                # EV_OCR_DONE now includes optional 'engine_type' and 'elapsed'
                txt = data.get('text', '')
                eng = data.get('engine_type', 'Unknown')
                el = float(data.get('elapsed', 0.0) or 0.0)
                self.sig_ocr_done.emit(txt, eng, el)

            # 日志类事件
            elif evt_type == EV_LOG_INFO:
                msg = data.get('msg', '')
                self.sig_log.emit("INFO", msg)
                # Back-compat: some codepaths (CLI/legacy) print "Screenshot saved: {path}" as log
                try:
                    if isinstance(msg, str) and "Screenshot saved" in msg:
                        # Try to extract path
                        parts = msg.split("Screenshot saved:")
                        path = parts[-1].strip() if len(parts) > 1 else ''
                        if path:
                            # Emit screenshot done for backward compatibility (no send target)
                            try:
                                self.sig_screenshot_done.emit(path, '')
                            except Exception:
                                pass
                except Exception:
                    pass
            elif evt_type == EV_LOG_ERR:
                msg = data.get('msg', '')
                self.sig_log.emit("ERROR", msg)
                # Back-compat: map log error containing screenshot failure to screenshot_failed
                try:
                    if isinstance(msg, str) and ("Screenshot failed" in msg or "Screenshot error" in msg):
                        try:
                            self.sig_screenshot_failed.emit(msg)
                        except Exception:
                            pass
                except Exception:
                    pass
            elif evt_type == EV_LOG_WARN:
                self.sig_log.emit("WARN", data['msg'])

        except Exception as e:
            print(f"[Bridge Dispatch Error] {e}")

    # --- 前端调用接口 (GUI -> Core) ---
    
    def login(self, username):
        self.core.login(username)
        # 登录后立即刷新一次列表
        self.sig_nodes_changed.emit(0)

    def logout(self):
        self.core.logout()

    def send_text(self, target, text):
        """
        target: '192.168.1.x' or 'all' or 'group:Name'
        """
        if target.startswith("group:"):
            self.core.send_group_msg(target[6:], text)
        else:
            self.core.send_text(target, text)

    def send_file(self, target_ip, file_path):
        self.core.send_file(target_ip, file_path)

    def accept_file(self, offer_id, save_dir=None):
        self.core.accept_file(offer_id, save_dir)
    
    def discover(self, target_ip=None):
        self.core.discover(target_ip)
        
    def run_ocr(self, image_path, send_target=None):
        self.core.run_ocr(image_path, send_target)

    # --- 数据获取 (供 GUI 轮询/渲染使用) ---
    
    def get_user_list(self):
        """返回简单的字典列表供 GUI 渲染"""
        nodes = []
        # 普通用户
        for n in self.core.registry.list_nodes():
            nodes.append({
                "type": "user",
                "name": n.username,
                "ip": n.ip,
                "host": n.hostname,
                "status": n.status
            })
        # 群组 (从 Core 的 groups 字典读取)
        # Respect visibility preference if present (core.visible_groups)
        try:
            visible = getattr(self.core, 'visible_groups', None)
            for gname, members in self.core.groups.items():
                if visible is None or (gname in visible):
                    nodes.append({
                        "type": "group",
                        "name": gname,
                        "count": len(members)
                    })
        except Exception:
            for gname, members in self.core.groups.items():
                nodes.append({"type": "group", "name": gname, "count": len(members)})
        return nodes

    # --- Group management helpers (GUI -> Core) ---
    def get_groups(self):
        """返回 core.groups 的快照，格式为 list of (name, count)"""
        try:
            return [(gname, len(members)) for gname, members in self.core.groups.items()]
        except Exception:
            return []

    def set_group_visibility(self, group_name: str, visible: bool):
        """设置某个群组是否在用户列表中可见（持久化到 core config）"""
        try:
            vg = getattr(self.core, 'visible_groups', None)
            if vg is None:
                vg = set(self.core.groups.keys())
            if visible:
                vg.add(group_name)
            else:
                vg.discard(group_name)
            self.core.visible_groups = vg
            # persist
            try:
                self.core._save_config()
            except Exception:
                pass
            try:
                self.sig_groups_changed.emit()
            except Exception:
                pass
            return True
        except Exception:
            return False

    def get_group_members(self, group_name: str):
        try:
            return list(self.core.groups.get(group_name, []))
        except Exception:
            return []

    def create_group(self, name: str):
        try:
            self.core.create_group(name)
            # emit change signal so GUI can refresh
            try:
                self.sig_groups_changed.emit()
            except Exception:
                pass
            return True
        except Exception:
            return False

    def add_to_group(self, group_name: str, username: str):
        try:
            self.core.add_to_group(group_name, username)
            try:
                self.sig_groups_changed.emit()
            except Exception:
                pass
            return True
        except Exception:
            return False

    def remove_from_group(self, group_name: str, username: str):
        try:
            ok = False
            # Prefer core API if available
            if hasattr(self.core, 'remove_from_group'):
                ok = self.core.remove_from_group(group_name, username)
            else:
                if group_name in self.core.groups and username in self.core.groups[group_name]:
                    self.core.groups[group_name].remove(username)
                    ok = True
            if ok:
                try:
                    self.sig_groups_changed.emit()
                except Exception:
                    pass
            return bool(ok)
        except Exception:
            return False

    def rename_group(self, old: str, new: str) -> bool:
        try:
            if hasattr(self.core, 'rename_group'):
                ok = self.core.rename_group(old, new)
            else:
                # fallback: naive dict rename
                if old in self.core.groups and new not in self.core.groups:
                    self.core.groups[new] = self.core.groups.pop(old)
                    ok = True
                else:
                    ok = False
            if ok:
                try:
                    self.sig_groups_changed.emit()
                except Exception:
                    pass
            return bool(ok)
        except Exception:
            return False

    def delete_group(self, name: str) -> bool:
        try:
            if hasattr(self.core, 'delete_group'):
                ok = self.core.delete_group(name)
            else:
                ok = False
            if ok:
                try:
                    self.sig_groups_changed.emit()
                except Exception:
                    pass
            return bool(ok)
        except Exception:
            return False

    def get_my_info(self):
        return {
            "name": self.core.username,
            "ip": self.core.local_ip,
            "status": self.core.status
        }
    
    def get_quick_texts(self):
        """获取常用语列表"""
        return self.core.get_quick_texts()

    # --- 额外的查询接口，供 GUI 主动查询会话/加密状态（向后兼容 chat.py 的防御性调用） ---
    def is_encrypted(self, ip: str) -> bool:
        try:
            sess = self.core._get_session(ip)
            return getattr(sess, 'state', None) == SessionState.ESTABLISHED
        except Exception:
            return False

    def has_session(self, ip: str) -> bool:
        try:
            return ip in getattr(self.core, 'sessions', {})
        except Exception:
            return False