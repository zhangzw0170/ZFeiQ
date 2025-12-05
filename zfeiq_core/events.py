# zfeiq_core/events.py
from dataclasses import dataclass, field
from typing import Any, Dict, Optional
import time

@dataclass
class Event:
    type: str
    data: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

# --- 事件类型常量定义 ---

# 日志类事件 (UI 可选择展示在控制台或状态栏)
EV_LOG_INFO = "log.info"
EV_LOG_WARN = "log.warn"
EV_LOG_ERR = "log.error"
EV_LOG_DEBUG = "log.debug"

# 消息类事件
EV_MSG_RECV = "msg.recv"       # 收到文本消息 data={sender, ip, text}
EV_MSG_SENT = "msg.sent"       # 消息已发出 data={target, text}

# 网络与节点状态
EV_NODE_UPD = "node.update"    # 节点列表变更 (上线/下线/状态改变)
EV_NET_INFO = "net.info"       # 本机网络信息变更 (绑定IP/端口)

# 文件传输
EV_FILE_OFFER = "file.offer"   # 收到文件传输请求 data={offer_id, sender, filename, size}
EV_FILE_PROG = "file.progress" # 文件传输进度 data={offer_id, current, total}
EV_FILE_DONE = "file.done"     # 文件传输完成 data={offer_id, path}
EV_FILE_ERR  = "file.error"    # 文件传输失败 data={offer_id, error}

# 加密与安全
EV_ENC_STATE = "enc.state"     # 加密会话状态变更 (如握手成功) data={peer_ip, state}
