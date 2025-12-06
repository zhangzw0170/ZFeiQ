import sys
import os
import time
from PyQt5.QtCore import QThread, pyqtSignal

# 确保能导入 core 模块 (假设 gui 目录在 NZFeiQ/gui)
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.engine import ZFeiQCore
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
                self.sig_msg.emit(data.get('sender', '?'), data['ip'], data['text'], False, False)
                
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
                self.sig_log.emit("INFO", data['msg'])
            elif evt_type == EV_LOG_ERR:
                self.sig_log.emit("ERROR", data['msg'])
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
        for gname, members in self.core.groups.items():
            nodes.append({
                "type": "group",
                "name": gname,
                "count": len(members)
            })
        return nodes

    def get_my_info(self):
        return {
            "name": self.core.username,
            "ip": self.core.local_ip,
            "status": self.core.status
        }
    
    def get_quick_texts(self):
        """获取常用语列表"""
        return self.core.get_quick_texts()