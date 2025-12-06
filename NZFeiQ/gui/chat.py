import datetime
import os
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QListView, 
                             QTextEdit, QPushButton, QStyledItemDelegate, 
                             QAbstractItemView, QLabel, QSplitter, QFrame,
                             QStyle, QFileDialog, QApplication, QMenu, QAction,
                             QSizePolicy, QToolButton, QLineEdit)
from PyQt5.QtCore import (Qt, QAbstractListModel, QModelIndex, QSize, 
                          QRect, QTimer, pyqtSignal, QEvent)
import shutil
import subprocess
from PyQt5.QtGui import QPainter, QColor, QFontMetrics, QBrush, QPen, QFont, QKeyEvent, QCursor, QDesktopServices
from PyQt5.QtCore import QUrl
from gui.lang import L
from gui.styles import CHAT_COLOR_ME_ENC, CHAT_COLOR_RX_ENC, CHAT_COLOR_UNENC_BG, CHAT_COLOR_UNENC_BORDER, get_color


def _hex_to_rgb(hex_str: str):
    """Convert '#RRGGBB' or 'RRGGBB' to (r,g,b) ints. Returns (0,0,0) on error."""
    if not hex_str:
        return (0, 0, 0)
    s = hex_str.lstrip('#')
    try:
        if len(s) == 6:
            r = int(s[0:2], 16)
            g = int(s[2:4], 16)
            b = int(s[4:6], 16)
            return (r, g, b)
    except Exception:
        pass
    return (0, 0, 0)

# 常量定义
MSG_TYPE_TEXT = 'text'
MSG_TYPE_FILE = 'file'

# ==========================================
#   Part 1: 左侧用户列表 (User List)
# ==========================================

class UserListModel(QAbstractListModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.users = [{
            'type': 'all', 'name': L('broadcast_hall'), 'ip': 'all', 
            'host': '', 'status': 'online'
        }]

    def rowCount(self, parent=QModelIndex()):
        return len(self.users)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid(): return None
        if role == Qt.DisplayRole:
            return self.users[index.row()]
        return None

    def update_data(self, new_list):
        self.beginResetModel()
        self.users = [{
            'type': 'all', 'name': L('broadcast_hall'), 'ip': 'all', 
            'host': '', 'status': 'online'
        }] + new_list
        self.endResetModel()

class UserDelegate(QStyledItemDelegate):
    def sizeHint(self, option, index):
        return QSize(option.rect.width(), 60)

    def paint(self, painter, option, index):
        data = index.data(Qt.DisplayRole)
        if not data: return

        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)
        
        rect = option.rect
        # theme-aware background for selection / hover
        try:
            theme_code = option.widget.property('theme') if option and option.widget is not None else None
            if not theme_code:
                theme_code = 'light'
        except Exception:
            theme_code = 'light'

        try:
            if (option.state & QStyle.State_Selected) != 0:
                painter.fillRect(rect, QColor(get_color('HIGHLIGHT', theme_code)))
            elif (option.state & QStyle.State_MouseOver) != 0:
                painter.fillRect(rect, QColor(get_color('HOVER_BG', theme_code)))
        except Exception:
            if (option.state & QStyle.State_Selected) != 0:
                painter.fillRect(rect, QColor("#e6e6e6"))
            elif (option.state & QStyle.State_MouseOver) != 0:
                painter.fillRect(rect, QColor("#f2f2f2"))

        name = data.get('name', '?')
        if not name: name = "?"
        
        bg_hue = (hash(name) % 360) 
        avatar_color = QColor.fromHsv(bg_hue, 150, 200)
        
        avatar_size = 40
        avatar_x = rect.left() + 10
        avatar_y = rect.top() + (rect.height() - avatar_size) // 2
        avatar_rect = QRect(avatar_x, avatar_y, avatar_size, avatar_size)
        
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(avatar_color))
        painter.drawEllipse(avatar_rect)
        
        painter.setPen(Qt.white)
        font = painter.font()
        font.setBold(True)
        font.setPointSize(14)
        painter.setFont(font)
        painter.drawText(avatar_rect, int(Qt.AlignCenter), name[0].upper())

        text_x = avatar_rect.right() + 12
        name_y = rect.top() + 22
        
        try:
            painter.setPen(QColor(get_color('PRIMARY_TEXT', theme_code)))
        except Exception:
            painter.setPen(QColor("#333"))
        font.setPointSize(11)
        font.setBold(False)
        painter.setFont(font)
        painter.drawText(text_x, name_y, name)
        
        ip_y = rect.top() + 42
        ip_str = data.get('ip', '')
        if data.get('type') == 'group':
            ip_str = f"群组 ({data.get('count',0)}人)"
        
        try:
            painter.setPen(QColor(get_color('SECONDARY_TEXT', theme_code)))
        except Exception:
            painter.setPen(QColor("#888"))
        font.setPointSize(9)
        painter.setFont(font)
        painter.drawText(text_x, ip_y, ip_str)

        status = data.get('status', 'offline')
        try:
            status_color = QColor(get_color('STATUS_OFFLINE', theme_code))
            if status == 'online':
                status_color = QColor(get_color('STATUS_ONLINE', theme_code))
            elif status == 'busy':
                status_color = QColor(get_color('STATUS_BUSY', theme_code))
            elif status == 'away':
                status_color = QColor(get_color('STATUS_AWAY', theme_code))
        except Exception:
            status_color = QColor("#999")
            if status == 'online': status_color = QColor("#2ecc71")
            elif status == 'busy': status_color = QColor("#e74c3c")
            elif status == 'away': status_color = QColor("#f39c12")
        
        status_size = 12
        s_rect = QRect(avatar_rect.right() - 8, avatar_rect.bottom() - 8, status_size, status_size)
        
        painter.setPen(QPen(Qt.white, 2))
        painter.setBrush(QBrush(status_color))
        painter.drawEllipse(s_rect)

        painter.restore()


class LightUserDelegate(QStyledItemDelegate):
    """轻量级用户委托：用于搜索结果显示，只绘制一行简洁信息以减小渲染成本。"""
    def sizeHint(self, option, index):
        return QSize(option.rect.width(), 28)

    def paint(self, painter, option, index):
        data = index.data(Qt.DisplayRole)
        if not data: return
        painter.save()
        rect = option.rect
        # theme-aware selection background
        try:
            theme_code = option.widget.property('theme') if option and option.widget is not None else None
            if not theme_code:
                theme_code = 'light'
        except Exception:
            theme_code = 'light'
        try:
            if (option.state & QStyle.State_Selected) != 0:
                painter.fillRect(rect, QColor(get_color('HIGHLIGHT', theme_code)))
        except Exception:
            if (option.state & QStyle.State_Selected) != 0:
                painter.fillRect(rect, QColor("#e6e6e6"))
        name = data.get('name', '')
        ip = data.get('ip', '')
        try:
            painter.setPen(QColor(get_color('PRIMARY_TEXT', theme_code)))
        except Exception:
            painter.setPen(QColor("#333"))
        font = painter.font()
        font.setPointSize(10)
        painter.setFont(font)
        painter.drawText(rect.adjusted(8, 0, -8, 0), int(Qt.AlignLeft | Qt.AlignVCenter), f"{name}    {ip}")
        painter.restore()

# ==========================================
#   Part 2: 右侧聊天 (Chat View)
# ==========================================

class ChatModel(QAbstractListModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.messages = []
        # 映射 offer_id -> row index，用于快速查找
        self.offer_map = {} 

    def rowCount(self, parent=QModelIndex()):
        return len(self.messages)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid() or role != Qt.DisplayRole:
            return None
        return self.messages[index.row()]

    def add_message(self, msg_data):
        row = len(self.messages)
        self.beginInsertRows(QModelIndex(), row, row)
        self.messages.append(msg_data)
        
        # 如果是文件消息，记录 offer_id 以便后续更新进度
        if msg_data.get('type') == MSG_TYPE_FILE and 'offer_id' in msg_data:
            self.offer_map[msg_data['offer_id']] = row
            
        self.endInsertRows()

    def update_progress(self, offer_id, current, total):
        """更新文件传输进度"""
        row = self.offer_map.get(offer_id)
        if row is not None and 0 <= row < len(self.messages):
            msg = self.messages[row]
            msg['current'] = current
            msg['total'] = total
            msg['status'] = 'transferring'
            
            # 触发局部刷新
            idx = self.index(row)
            self.dataChanged.emit(idx, idx)

    def update_file_done(self, offer_id, saved_path):
        """文件传输完成"""
        row = self.offer_map.get(offer_id)
        if row is not None and 0 <= row < len(self.messages):
            msg = self.messages[row]
            msg['current'] = msg.get('total', 0)
            msg['status'] = 'done'
            msg['local_path'] = saved_path
            
            idx = self.index(row)
            self.dataChanged.emit(idx, idx)

class ChatDelegate(QStyledItemDelegate):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.padding = 10
        self.bubble_padding = 12
        self.max_width = 450
        
    def sizeHint(self, option, index):
        data = index.data(Qt.DisplayRole)
        if not data: return QSize(0, 0)
        
        if data.get('type') == MSG_TYPE_FILE:
            # 文件气泡固定高度: 顶部信息(20) + 气泡(80) + 底部padding
            return QSize(option.rect.width(), 120)
        
        # 文本消息计算高度
        font_metrics = option.fontMetrics
        rect = font_metrics.boundingRect(
            0, 0, self.max_width, 0, 
            int(Qt.TextWordWrap), data['text']
        )
        total_height = rect.height() + (self.padding * 4) + 20 
        return QSize(option.rect.width(), total_height)

    def paint(self, painter, option, index):
        data = index.data(Qt.DisplayRole)
        if not data: return

        painter.save()
        # painter.setRenderHint(QPainter.Antialiasing)
        
        # 1. 绘制通用头部 (用户名 + 时间)
        self._paint_header(painter, option.rect, data)
        
        # 2. 根据类型绘制气泡
        if data.get('type') == MSG_TYPE_FILE:
            self._paint_file_bubble(painter, option.rect, data)
        else:
            self._paint_text_bubble(painter, option.rect, data, option)

        painter.restore()

    def _paint_header(self, painter, rect, data):
        is_me = data['is_me']
        user = data['user']
        time_str = data.get('time', '')
        try:
            # header text uses secondary text color
            theme_code = getattr(self, '_theme_code', None)
            if not theme_code:
                # try to get from parent view if available
                theme_code = 'light'
        except Exception:
            theme_code = 'light'
        try:
            painter.setPen(QColor(get_color('SECONDARY_TEXT', theme_code)))
        except Exception:
            painter.setPen(QColor("#999"))
        font = painter.font()
        font.setPointSize(9)
        painter.setFont(font)
        
        header_rect = QRect(rect)
        header_rect.setTop(rect.top() + 8)
        header_rect.setHeight(20)
        
        header_text = f"{user}  {time_str}"
        
        if is_me:
            painter.drawText(header_rect.adjusted(0,0,-15,0), int(Qt.AlignRight | Qt.AlignVCenter), header_text)
        else:
            painter.drawText(header_rect.adjusted(15,0,0,0), int(Qt.AlignLeft | Qt.AlignVCenter), header_text)

    def _paint_text_bubble(self, painter, rect, data, option):
        is_me = data['is_me']
        encrypted = bool(data.get('encrypted', False))
        text = data['text']
        
        # 计算气泡大小
        font = painter.font()
        font.setPointSize(11)
        painter.setFont(font)
        fm = QFontMetrics(font)
        text_rect = fm.boundingRect(0, 0, self.max_width, 0, int(Qt.TextWordWrap), text)
        
        bubble_w = text_rect.width() + (self.bubble_padding * 2)
        bubble_h = text_rect.height() + (self.bubble_padding * 2)
        bubble_y = rect.top() + 30 
        
        if encrypted:
            if is_me:
                bubble_x = rect.right() - bubble_w - 15
                bg_color = QColor(CHAT_COLOR_ME_ENC)
                border_color = QColor(CHAT_COLOR_ME_ENC)
            else:
                bubble_x = rect.left() + 15
                bg_color = QColor(CHAT_COLOR_RX_ENC)
                border_color = QColor(CHAT_COLOR_RX_ENC)
        else:
            # 未加密消息统一白底
            if is_me:
                bubble_x = rect.right() - bubble_w - 15
            else:
                bubble_x = rect.left() + 15
            bg_color = QColor(CHAT_COLOR_UNENC_BG)
            border_color = QColor(CHAT_COLOR_UNENC_BORDER)

        bubble_rect = QRect(bubble_x, bubble_y, bubble_w, bubble_h)

        # 绘制背景
        painter.setPen(QPen(border_color))
        painter.setBrush(QBrush(bg_color))
        painter.drawRoundedRect(bubble_rect, 6, 6)
        
        # 绘制文本
        try:
            painter.setPen(QColor(get_color('PRIMARY_TEXT', getattr(self, '_theme_code', 'light'))))
        except Exception:
            painter.setPen(QColor("#000000"))
        t_rect = bubble_rect.adjusted(self.bubble_padding, self.bubble_padding, -self.bubble_padding, -self.bubble_padding)
        painter.drawText(t_rect, int(Qt.TextWordWrap | Qt.AlignLeft), text)

    def _paint_file_bubble(self, painter, rect, data):
        is_me = data['is_me']
        filename = data.get('filename', '未知文件')
        size_bytes = data.get('total', 0)
        current_bytes = data.get('current', 0)
        status = data.get('status', 'waiting') # waiting, transferring, done
        
        # 气泡固定尺寸
        bubble_w = 300
        bubble_h = 80
        bubble_y = rect.top() + 30
        
        # file bubble background/border should follow unencrypted chat bubble colors
        try:
            bubble_x = rect.right() - bubble_w - 15 if is_me else rect.left() + 15
            bg_color = QColor(CHAT_COLOR_UNENC_BG)
            border_color = QColor(CHAT_COLOR_UNENC_BORDER)
        except Exception:
            if is_me:
                bubble_x = rect.right() - bubble_w - 15
            else:
                bubble_x = rect.left() + 15
            bg_color = QColor("#FFFFFF")
            border_color = QColor("#E0E0E0")
            
        bubble_rect = QRect(bubble_x, bubble_y, bubble_w, bubble_h)

        # 绘制气泡背景
        painter.setPen(QPen(border_color))
        painter.setBrush(QBrush(bg_color))
        painter.drawRoundedRect(bubble_rect, 6, 6)
        
        # --- 内部内容 ---
        content_rect = bubble_rect.adjusted(10, 10, -10, -10)
        
        # 1. 图标 (简单的Emoji或者绘制一个矩形代表文件)
        icon_size = 40
        icon_rect = QRect(content_rect.left(), content_rect.top(), icon_size, icon_size)
        
        # 绘制文件图标背景
        painter.setPen(Qt.NoPen)
        try:
            painter.setBrush(QColor(get_color('ICON_BG', getattr(self, '_theme_code', 'light'))))
        except Exception:
            painter.setBrush(QColor("#f39c12"))
        painter.drawRoundedRect(icon_rect, 4, 4)
        # 绘制 'DOC' 简写
        painter.setPen(Qt.white)
        f = painter.font()
        f.setBold(True)
        f.setPointSize(10)
        painter.setFont(f)
        painter.drawText(icon_rect, int(Qt.AlignCenter), "FILE")
        
        # 2. 文件名
        name_x = icon_rect.right() + 10
        name_w = content_rect.width() - icon_size - 10
        name_rect = QRect(name_x, content_rect.top(), name_w, 20)
        
        try:
            painter.setPen(QColor(get_color('PRIMARY_TEXT', getattr(self, '_theme_code', 'light'))))
        except Exception:
            painter.setPen(QColor("#333"))
        f.setBold(True)
        f.setPointSize(10)
        painter.setFont(f)
        elided_name = QFontMetrics(f).elidedText(filename, Qt.ElideMiddle, name_w)
        painter.drawText(name_rect, int(Qt.AlignLeft | Qt.AlignVCenter), elided_name)
        
        # 3. 进度条区域
        progress_h = 6
        progress_y = icon_rect.bottom() - progress_h
        progress_bg_rect = QRect(name_x, progress_y, name_w, progress_h)
        
        # 绘制进度条背景
        try:
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(get_color('PROGRESS_BG', getattr(self, '_theme_code', 'light'))))
        except Exception:
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor("#eee"))
        painter.drawRoundedRect(progress_bg_rect, 3, 3)
        
        # 绘制进度前景色
        if size_bytes > 0:
            pct = min(1.0, current_bytes / size_bytes)
        else:
            pct = 0
            
            if pct > 0:
                prog_w = int(name_w * pct)
                prog_fg_rect = QRect(name_x, progress_y, prog_w, progress_h)
                try:
                    fg = get_color('PROGRESS_DONE', getattr(self, '_theme_code', 'light')) if status == 'done' else get_color('PROGRESS_ACTIVE', getattr(self, '_theme_code', 'light'))
                    painter.setBrush(QColor(fg))
                except Exception:
                    painter.setBrush(QColor("#2ecc71") if status == 'done' else QColor("#3498db"))
                painter.drawRoundedRect(prog_fg_rect, 3, 3)

        # 4. 状态文本 (大小 / 状态)
        status_rect = QRect(name_x, progress_y + 10, name_w, 15)
        painter.setPen(QColor("#888"))
        f.setBold(False)
        f.setPointSize(8)
        painter.setFont(f)
        
        size_str = self._fmt_size(size_bytes)
        if status == 'done':
            status_text = f"已完成 ({size_str})"
        elif status == 'transferring':
            curr_str = self._fmt_size(current_bytes)
            status_text = f"正在下载... {curr_str} / {size_str}"
        else:
            status_text = f"等待中... ({size_str})"
            
        painter.drawText(status_rect, int(Qt.AlignLeft | Qt.AlignVCenter), status_text)

    def _fmt_size(self, size):
        if size < 1024: return f"{size} B"
        if size < 1024*1024: return f"{size/1024:.1f} KB"
        return f"{size/(1024*1024):.1f} MB"

# ==========================================
#   Part 3: 整合页面 (Page)
# ==========================================

class ChatPage(QWidget):
    def __init__(self, bridge, parent=None):
        super().__init__(parent)
        self.bridge = bridge
        self.current_target = {'ip': 'all', 'name': '所有人', 'type': 'all'}
        
        self._setup_ui()
        
        self.timer_refresh = QTimer(self)
        self.timer_refresh.timeout.connect(self._refresh_users)
        self.timer_refresh.start(3000)
        
        self._connect_signals()
        
        QTimer.singleShot(100, self._refresh_users)

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # === 核心区域 ===
        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(1)
        splitter.setStyleSheet("QSplitter::handle { background: " + get_color('BORDER', 'light') + "; }")
        
        # --- 左侧：用户列表 (保持不变) ---
        # 搜索框（轻量级匹配用户 / IP / 组）
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText(L('search_placeholder'))
        self.search_box.setFixedHeight(30)
        self.search_box.setClearButtonEnabled(True)
        self.search_box.textChanged.connect(self._on_search_text)

        self.user_list = QListView()
        self.user_model = UserListModel()
        self.user_delegate = UserDelegate()
        self.light_delegate = LightUserDelegate()
        self.user_list.setModel(self.user_model)
        self.user_list.setItemDelegate(self.user_delegate)
        self.user_list.setFrameShape(QFrame.NoFrame)
        self.user_list.setStyleSheet("background: " + get_color('BACKGROUND_PANEL', 'light') + ";")
        self.user_list.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.user_list.clicked.connect(self._on_user_clicked)
        
        left_panel = QWidget()
        # 左侧面板使用与消息区相近的背景，避免白色块视觉不协调
        left_panel.setStyleSheet("background: " + get_color('BACKGROUND_PANEL', 'light') + ";")
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0,0,0,0)
        left_layout.addWidget(self.search_box)
        # 用户列表背景设为透明，让面板背景承接，避免突兀的白色块
        self.user_list.setStyleSheet("background: transparent;")
        left_layout.addWidget(self.user_list)
        left_layout.addStretch()

        # 左下角：设置 & 组管理
        left_bottom = QWidget()
        left_bottom.setStyleSheet("background: transparent;")
        lb_layout = QHBoxLayout(left_bottom)
        lb_layout.setContentsMargins(8,8,8,8)
        lb_layout.setSpacing(8)
        # 使用 QToolButton 保持与上方工具栏一致的风格
        self.btn_settings = QToolButton()
        self.btn_settings.setText(L('btn_settings'))
        self.btn_settings.setCursor(Qt.PointingHandCursor)
        self.btn_settings.setToolButtonStyle(Qt.ToolButtonTextOnly)
        self.btn_settings.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.Preferred)
        # 仅保留结构性样式，颜色/hover 由主题引擎在 _on_theme_changed 中应用
        self.btn_settings.setStyleSheet("QToolButton { border: 1px solid transparent; border-radius: 4px; padding: 4px; }")
        self.btn_settings.clicked.connect(self._open_settings)

        self.btn_group = QToolButton()
        self.btn_group.setText(L('btn_group'))
        self.btn_group.setCursor(Qt.PointingHandCursor)
        self.btn_group.setToolButtonStyle(Qt.ToolButtonTextOnly)
        self.btn_group.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.Preferred)
        # 仅保留结构性样式，颜色/hover 由主题引擎在 _on_theme_changed 中应用
        self.btn_group.setStyleSheet("QToolButton { border: 1px solid transparent; border-radius: 4px; padding: 4px; }")
        self.btn_group.clicked.connect(self._open_group_manager)

        lb_layout.addWidget(self.btn_group)
        lb_layout.addWidget(self.btn_settings)
        left_layout.addWidget(left_bottom)
        left_panel.setMinimumWidth(200)
        left_panel.setMaximumWidth(350)
        
        splitter.addWidget(left_panel)

        # --- 右侧：聊天区域 ---
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0,0,0,0)
        right_layout.setSpacing(0)

        # 右上：用户信息（当前选中目标）
        right_top = QWidget()
        self.right_top = right_top
        right_top.setFixedHeight(48)
        # 初始背景适配浅色，主题切换时更新
        right_top.setStyleSheet("background: " + get_color('BACKGROUND_PANEL', 'light') + ";")
        rt_layout = QHBoxLayout(right_top)
        rt_layout.setContentsMargins(12, 6, 12, 6)
        self.lbl_title = QLabel(L('broadcast_hall'))
        self.lbl_title.setStyleSheet("font-size: 15px; font-weight: 600; color: #333;")
        rt_layout.addWidget(self.lbl_title)
        # 会话加密状态显示：右侧显示（绿色=已加密，红色=未加密）
        self.lbl_status = QLabel("")
        self.lbl_status.setStyleSheet("font-size:12px; padding:2px 6px; border-radius:4px;")
        self.lbl_encrypt_status = QLabel("")
        self.lbl_encrypt_status.setStyleSheet("font-size:12px; padding:2px 6px; border-radius:4px;")
        rt_layout.addStretch()
        rt_layout.addWidget(self.lbl_status)
        rt_layout.addWidget(self.lbl_encrypt_status)
        right_layout.addWidget(right_top)

        self.chat_list = QListView()
        self.chat_model = ChatModel()
        self.chat_delegate = ChatDelegate()
        self.chat_list.setModel(self.chat_model)
        self.chat_list.setItemDelegate(self.chat_delegate)
        self.chat_list.setFrameShape(QFrame.NoFrame)
        self.chat_list.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.chat_list.setSelectionMode(QAbstractItemView.NoSelection)
        # 现代化的细滚动条样式，与发送框一致：细长、圆角把手，hover 加深；在不支持样式的平台上视觉上接近隐藏
        self.chat_list.setStyleSheet(
            "QListView { background: " + get_color('BACKGROUND_PANEL', 'light') + "; }"
            "QScrollBar:vertical {"
                "background: transparent;"
                "width: 8px;"
                "margin: 0px 0px 0px 0px;"
            "}"
            "QScrollBar::handle:vertical {"
                "background: rgba(0,0,0,0.18);"
                "min-height: 22px;"
                "border-radius: 4px;"
            "}"
            "QScrollBar::handle:vertical:hover { background: rgba(0,0,0,0.30); }"
            "QScrollBar::add-line, QScrollBar::sub-line { height: 0px; }"
            "QScrollBar::add-page, QScrollBar::sub-page { background: none; }"
        )
        
        # 点击聊天项（用于打开已下载的文件等交互）
        self.chat_list.clicked.connect(self._on_chat_clicked)
        
        # 聊天消息区域：相对输入区占比为 2
        right_layout.addWidget(self.chat_list, 2)

        # [修改] 底部输入容器：移除固定高度，改为自适应
        self.input_container = QWidget()
        # input_container.setFixedHeight(120) <--- 移除此行
        self.input_container.setStyleSheet("background: " + get_color('INPUT_BG', 'light') + "; border-top: 1px solid " + get_color('BORDER', 'light') + ";")
        input_layout = QVBoxLayout(self.input_container)
        input_layout.setContentsMargins(10, 5, 10, 5)
        
        # 工具栏容器，允许设置背景以适配深色模式
        toolbar_container = QWidget()
        self.toolbar_container = toolbar_container
        toolbar_container.setStyleSheet("background: " + get_color('BACKGROUND_PANEL', 'light') + "; border: none;")
        toolbar = QHBoxLayout(toolbar_container)
        toolbar.setSpacing(6)
        toolbar.setContentsMargins(0, 0, 0, 5)

        # [修改] 辅助函数：完全模仿 Legacy 的 NavigationButton 风格
        def _create_tool_btn(text, slot=None):
            # 使用 QToolButton 代替 QPushButton
            btn = QToolButton()
            btn.setText(text)
            btn.setToolButtonStyle(Qt.ToolButtonTextOnly)
            btn.setCursor(Qt.PointingHandCursor)
            
            # 关键：设置 SizePolicy 为 (MinimumExpanding, Preferred)
            # 这会让按钮在水平方向上尽可能平均分配空间，像 legacy 布局一样
            btn.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.Preferred)
            
            # 仅保留结构性样式，颜色/hover 由主题引擎在 _on_theme_changed 中应用
            btn.setStyleSheet("QToolButton { border: 1px solid transparent; border-radius: 4px; padding: 4px; }")
            
            if slot: btn.clicked.connect(slot)
            return btn

        self.btn_emoji = _create_tool_btn(L('btn_emoji'), self._on_btn_emoji)
        self.btn_screen = _create_tool_btn(L('btn_screen'), self._on_btn_screen)
        self.btn_quick = _create_tool_btn(L('btn_quick'), self._on_btn_quick)
        self.btn_file = _create_tool_btn(L('btn_file'), self._send_file_action)
        self.btn_ocr = _create_tool_btn(L('btn_ocr'), self._request_ocr) # 确保连接到正确的 request 函数
        
        toolbar.addWidget(self.btn_emoji)
        toolbar.addWidget(self.btn_screen)
        toolbar.addWidget(self.btn_quick)
        toolbar.addWidget(self.btn_file)
        toolbar.addWidget(self.btn_ocr)
        
        # toolbar.addStretch() <--- Legacy 风格通常填满，如果希望按钮紧凑可保留 stretch
        
        input_layout.addWidget(toolbar_container)
        
        self.input_edit = QTextEdit()
        self.input_edit.setPlaceholderText(L('input_placeholder'))
        self.input_edit.setFrameShape(QFrame.NoFrame)
        # [新增] 设置最小高度，防止压得太扁
        self.input_edit.setMinimumHeight(56) 
        self.input_edit.installEventFilter(self)
        # 现代化的细滚动条样式：细长、圆角把手，hover 加深；在不支持样式的平台上视觉上接近隐藏
        self.input_edit.setStyleSheet(
            "QTextEdit { background: " + get_color('INPUT_BG', 'light') + "; border: none; }"
            "QScrollBar:vertical { background: transparent; width: 8px; margin: 0px 0px 0px 0px; }"
            "QScrollBar::handle:vertical { background: rgba(0,0,0,0.18); min-height: 22px; border-radius: 4px; }"
            "QScrollBar::handle:vertical:hover { background: rgba(0,0,0,0.30); }"
            "QScrollBar::add-line, QScrollBar::sub-line { height: 0px; }"
            "QScrollBar::add-page, QScrollBar::sub-page { background: none; }"
        )
        
        input_layout.addWidget(self.input_edit)
        
        send_bar = QHBoxLayout()
        send_bar.addStretch()
        
        self.btn_send = QPushButton(L('send_button'))
        # [修改] 发送按钮也改为自适应策略，不仅限固定大小
        self.btn_send.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.Preferred)
        self.btn_send.setMinimumWidth(80)
        self.btn_send.setMaximumWidth(120)
        self.btn_send.setFixedHeight(30)
        
        self.btn_send.setStyleSheet(
            "QPushButton { background-color: " + get_color('BTN_BG', 'light') + "; border: 1px solid " + get_color('BORDER', 'light') + "; border-radius: 4px; color: " + get_color('BTN_TEXT', 'light') + "; }"
            "QPushButton:hover { background-color: " + get_color('BTN_ACCENT', 'light') + "; color: white; border: none; }"
        )
        self.btn_send.setCursor(Qt.PointingHandCursor)
        self.btn_send.clicked.connect(self._do_send)
        send_bar.addWidget(self.btn_send)
        
        input_layout.addLayout(send_bar)
        
        # 输入区域（工具栏 + 输入框 + 发送按钮）：设置为占右侧栏的 1/3
        right_layout.addWidget(self.input_container, 1)
        splitter.addWidget(right_panel)
        
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)
        
        main_layout.addWidget(splitter)

    def eventFilter(self, watched, event): # type: ignore
        # 只处理输入框的按键事件
        if watched == self.input_edit and event.type() == QEvent.KeyPress:
            e: QKeyEvent = event

            # Shift+Enter → 换行
            if e.key() in (Qt.Key_Return, Qt.Key_Enter) and (e.modifiers() & Qt.ShiftModifier): # type: ignore
                return False  # 不拦截，让 QTextEdit 默认行为执行（换行）

            # Enter → 发送消息
            if e.key() in (Qt.Key_Return, Qt.Key_Enter):
                self._do_send()
                return True  # 拦截，防止换行

        return super().eventFilter(watched, event)

    def _connect_signals(self):
        self.bridge.sig_msg.connect(self._on_msg_received)
        # 将文件 offer 连接到新逻辑
        self.bridge.sig_file_offer.connect(self._on_file_offer)
        # 连接进度和完成信号
        self.bridge.sig_file_progress.connect(self.chat_model.update_progress)
        self.bridge.sig_file_done.connect(self.chat_model.update_file_done)
        
        self.bridge.sig_nodes_changed.connect(lambda n: self._refresh_users())
        # 语言变更：立即更新界面可见文本
        try:
            self.bridge.sig_lang_changed.connect(self._on_language_changed)
        except Exception:
            pass
        try:
            self.bridge.sig_theme_changed.connect(self._on_theme_changed)
        except Exception:
            pass
        # 加密状态变更及时反映到 UI
        try:
            self.bridge.sig_enc_state.connect(self._on_enc_state)
        except Exception:
            pass
        
        # [新增] 连接 OCR 完成信号
        self.bridge.sig_ocr_done.connect(self._on_ocr_result)

        # 初始化时保持完整委托
        self._using_light_delegate = False

    def _on_search_text(self, text: str):
        """搜索框回调：接收文本后触发用户列表刷新（轻量级匹配）。"""
        # 直接调用刷新（可以在未来加入防抖）
        try:
            self._refresh_users()
        except Exception:
            pass

    def _is_encrypted_with(self, target_ip: str) -> bool:
        """尝试从 bridge 查询与 target_ip 的会话是否已建立加密通道。
        如果 bridge 未提供相关接口，则返回 False（保守不显示已加密）。"""
        try:
            fn = getattr(self.bridge, 'is_encrypted', None)
            if callable(fn):
                return bool(fn(target_ip))
        except Exception:
            pass
        # 备用尝试：bridge 可能暴露 session/registry，尝试常见属性名（防御性）
        try:
            fn2 = getattr(self.bridge, 'has_session', None)
            if callable(fn2):
                return bool(fn2(target_ip))
        except Exception:
            pass
        return False

    def _set_encrypt_label(self, encrypted: bool):
        theme_code = getattr(self, '_current_theme', 'light')
        # Use theme tokens specifically for encryption indicator colors
        try:
            if encrypted:
                self.lbl_encrypt_status.setText(L('encrypted', '已加密'))
                color_hex = get_color('ENC_GREEN', theme_code) or get_color('STATUS_ONLINE', theme_code) or '#1e7e34'
            else:
                self.lbl_encrypt_status.setText(L('unencrypted', '未加密'))
                color_hex = get_color('ENC_RED', theme_code) or get_color('STATUS_BUSY', theme_code) or '#b21b1b'

            r, g, b = _hex_to_rgb(color_hex)
            # subtle background for light theme, stronger for dark theme
            if theme_code == 'dark':
                bg_alpha = 0.16
                border_alpha = 0.28
            else:
                bg_alpha = 0.06
                border_alpha = 0.12

            bg_css = f'background: rgba({r},{g},{b},{bg_alpha});'
            border_css = f'border: 1px solid rgba({r},{g},{b},{border_alpha});'
            self.lbl_encrypt_status.setStyleSheet(f"color: {color_hex}; {bg_css} {border_css} padding:2px 6px; border-radius:4px; font-size:12px;")
        except Exception:
            # conservative fallback
            if encrypted:
                self.lbl_encrypt_status.setStyleSheet("color: #1e7e34; background: rgba(30,126,52,0.06); border: 1px solid rgba(30,126,52,0.12); padding:2px 6px; border-radius:4px; font-size:12px;")
                self.lbl_encrypt_status.setText(L('encrypted', '已加密'))
            else:
                self.lbl_encrypt_status.setStyleSheet("color: #b21b1b; background: rgba(178,27,27,0.04); border: 1px solid rgba(178,27,27,0.12); padding:2px 6px; border-radius:4px; font-size:12px;")
                self.lbl_encrypt_status.setText(L('unencrypted', '未加密'))

    def _status_to_text_and_color(self, status: str):
        theme_code = getattr(self, '_current_theme', 'light')
        if not status:
            try:
                return (L('status_offline'), get_color('SECONDARY_TEXT', theme_code))
            except Exception:
                return (L('status_offline'), "#777")
        s = status.lower()
        try:
            if s == 'online':
                return (L('status_online'), get_color('STATUS_ONLINE', theme_code))
            if s == 'busy' or s == '忙碌':
                return (L('status_busy'), get_color('STATUS_BUSY', theme_code))
            if s == 'away' or s == '离开':
                return (L('status_away'), get_color('STATUS_AWAY', theme_code))
            return (status, get_color('SECONDARY_TEXT', theme_code))
        except Exception:
            if s == 'online':
                return (L('status_online'), "#2ecc71")
            if s == 'busy' or s == '忙碌':
                return (L('status_busy'), "#e74c3c")
            if s == 'away' or s == '离开':
                return (L('status_away'), "#f39c12")
            return (status, "#777")

    def _set_status_label(self, status: str):
        text, color = self._status_to_text_and_color(status)
        self.lbl_status.setText(text)
        # 边框与轻背景以提高可读性
        self.lbl_status.setStyleSheet(f"color: {color}; background: rgba(0,0,0,0); border: 1px solid rgba(0,0,0,0); padding:2px 6px; border-radius:4px; font-size:12px;")

    def _refresh_users(self):
        user_list = self.bridge.get_user_list()
        # 如果 search box 有内容，优先进行轻量级匹配并使用轻量委托
        q = self.search_box.text().strip()
        if q:
            ql = q.lower()
            filtered = []
            for u in user_list:
                name = (u.get('name') or '').lower()
                ip = (u.get('ip') or '').lower()
                typ = (u.get('type') or '').lower()
                if ql in name or ql in ip or ql in typ:
                    # 轻量对象，减少复杂字段
                    filtered.append({'type': u.get('type'), 'name': u.get('name'), 'ip': u.get('ip'), 'status': u.get('status','offline')})
            self.user_model.update_data(filtered)
            # 切换到轻量委托
            if not self._using_light_delegate:
                self.user_list.setItemDelegate(self.light_delegate)
                self._using_light_delegate = True
            # 如果当前目标在过滤结果中，更新 current_target 的 status
            try:
                cur_ip = self.current_target.get('ip') if self.current_target else None
                if cur_ip and cur_ip != 'all':
                    for u in filtered:
                        if u.get('ip') == cur_ip:
                            # 同步最新状态
                            self.current_target.update(u)
                            self._set_status_label(u.get('status'))
                            break
            except Exception:
                pass
        else:
            # 恢复完整用户列表与委托
            # 在更新前，确保当前聊天目标不会被意外移除：
            new_list = list(user_list)
            cur_ip = None
            try:
                cur_ip = self.current_target.get('ip')
            except Exception:
                cur_ip = None

            if cur_ip and cur_ip != 'all':
                # 优先尝试用最新的列表条目覆盖 current_target，保证 status 等字段是最新的
                matched = None
                for u in new_list:
                    if u.get('ip') == cur_ip:
                        matched = u
                        break
                if matched:
                    # 使用最新对象更新 current_target 的字段
                    try:
                        # 保证保留 type/name/ip 等字段
                        self.current_target.update(matched)
                    except Exception:
                        self.current_target = matched
                else:
                    # 把当前目标保留到列表顶部（紧接广播后）
                    new_list.insert(0, self.current_target)

            self.user_model.update_data(new_list)
            if self._using_light_delegate:
                self.user_list.setItemDelegate(self.user_delegate)
                self._using_light_delegate = False

        # 更新加密状态显示（主动查询 + 事件驱动会通过 sig_enc_state 触发）
        try:
            target_ip = (self.current_target.get('ip') if self.current_target else 'all') or 'all'
            enc = False if (not target_ip or target_ip == 'all') else self._is_encrypted_with(target_ip)
            self._set_encrypt_label(enc)
            # 同步当前目标的在线状态到右上显示
            try:
                stat = (self.current_target.get('status') if self.current_target else '') or ''
                self._set_status_label(stat)
            except Exception:
                self._set_status_label('')
        except Exception:
            self._set_encrypt_label(False)

    def _on_enc_state(self, peer_ip: str, state: str):
        """Bridge 发来的加密状态变化通知，若与当前目标匹配则立即更新 UI。"""
        try:
            if not self.current_target:
                return
            cur_ip = self.current_target.get('ip')
            if cur_ip and cur_ip == peer_ip:
                # 简单逻辑：当握手建立时，将加密标签设为 True
                if isinstance(state, str) and state.upper() in ("ESTABLISHED", "1"):
                    self._set_encrypt_label(True)
                else:
                    # 其它状态认为未加密
                    self._set_encrypt_label(False)
                    # 如果是 RESET，提示状态栏
                    try:
                        if isinstance(state, str) and state.upper() == "RESET":
                            # 底栏提示：加密已重置
                            from gui.lang import L
                            self._append_sys_msg(L('enc_reset', '加密已重置，正在重新握手...'))
                    except Exception:
                        pass
        except Exception:
            pass

    def _on_language_changed(self, lang_code: str):
        """当语言更改时刷新聊天相关的可见文本。"""
        try:
            # 更新按钮/占位文本
            self.btn_emoji.setText(L('btn_emoji'))
            self.btn_screen.setText(L('btn_screen'))
            self.btn_quick.setText(L('btn_quick'))
            self.btn_file.setText(L('btn_file'))
            self.btn_ocr.setText(L('btn_ocr'))
            try:
                self.btn_settings.setText(L('btn_settings'))
            except Exception:
                pass
            try:
                self.btn_group.setText(L('btn_group'))
            except Exception:
                pass
            try:
                self.input_edit.setPlaceholderText(L('input_placeholder'))
            except Exception:
                pass
            try:
                # 发送按钮可能是一个普通按钮或 ToolButton
                if hasattr(self, 'btn_send'):
                    self.btn_send.setText(L('send_button'))
            except Exception:
                pass
            # 更新当前标题（广播/群组/用户）
            try:
                if not self.current_target or self.current_target.get('type') == 'all':
                    self.lbl_title.setText(L('broadcast_hall'))
                elif self.current_target.get('type') == 'group':
                    name = self.current_target.get('name')
                    self.lbl_title.setText(f"{L('group_prefix')}{name}")
                else:
                    name = self.current_target.get('name')
                    ip = self.current_target.get('ip')
                    self.lbl_title.setText(f"{name} ({ip})")
            except Exception:
                try:
                    self.lbl_title.setText(L('broadcast_hall'))
                except Exception:
                    pass
        except Exception:
            pass

    def _on_theme_changed(self, theme_code: str):
        """Apply simple theme adjustments when theme changes. This is a lightweight
        handler: it updates some widgets' background and logs the change. A
        full theme engine should apply QPalette/QSS across the app.
        """
        try:
            # store current theme for possible later use
            self._current_theme = theme_code
            # expose theme to delegates and list widgets so painting can read it
            try:
                self.user_delegate._theme_code = theme_code
            except Exception:
                pass
            try:
                self.light_delegate._theme_code = theme_code
            except Exception:
                pass
            try:
                self.chat_delegate._theme_code = theme_code
            except Exception:
                pass
            try:
                # allow delegates to read theme from option.widget.property('theme') as well
                self.user_list.setProperty('theme', theme_code)
            except Exception:
                pass
            try:
                self.chat_list.setProperty('theme', theme_code)
            except Exception:
                pass
            try:
                self.input_edit.setProperty('theme', theme_code)
            except Exception:
                pass
            # Use centralized style helpers when available
            try:
                from gui.styles import get_color, qss_fragment
                # Apply small qss fragment globally to some containers
                try:
                    frag = qss_fragment(theme_code)
                    # Apply to chat list and input area specifically to avoid overwriting other widgets
                    self.chat_list.setStyleSheet(f"QListView {{ background: {get_color('BACKGROUND_PANEL', theme_code)}; color: {get_color('PRIMARY_TEXT', theme_code)} }}")
                except Exception:
                    pass

                # Left column (search + user list) parent container
                try:
                    left_container = self.search_box.parentWidget()
                    if left_container is not None:
                        left_container.setStyleSheet(f"background: {get_color('BACKGROUND_PANEL', theme_code)}; color: {get_color('PRIMARY_TEXT', theme_code)};")
                except Exception:
                    pass

                # User list
                try:
                    self.user_list.setStyleSheet(f"background: transparent; color: {get_color('PRIMARY_TEXT', theme_code)}")
                except Exception:
                    pass

                # Search box
                try:
                    self.search_box.setStyleSheet(f"background: {get_color('INPUT_BG', theme_code)}; color: {get_color('PRIMARY_TEXT', theme_code)}; border: 1px solid {get_color('BORDER', theme_code)}; border-radius:4px; padding:4px;")
                except Exception:
                    pass

                # Buttons in left bar
                try:
                    self.btn_settings.setStyleSheet(f"background: transparent; color: {get_color('PRIMARY_TEXT', theme_code)}; border: none; padding:6px;")
                    self.btn_group.setStyleSheet(f"background: transparent; color: {get_color('PRIMARY_TEXT', theme_code)}; border: none; padding:6px;")
                except Exception:
                    pass

                # Toolbar buttons (emoji/screen/quick/file/ocr)
                try:
                    self.btn_emoji.setStyleSheet(f"background: transparent; color: {get_color('PRIMARY_TEXT', theme_code)}; border: none; padding:6px;")
                    self.btn_screen.setStyleSheet(f"background: transparent; color: {get_color('PRIMARY_TEXT', theme_code)}; border: none; padding:6px;")
                    self.btn_quick.setStyleSheet(f"background: transparent; color: {get_color('PRIMARY_TEXT', theme_code)}; border: none; padding:6px;")
                    self.btn_file.setStyleSheet(f"background: transparent; color: {get_color('PRIMARY_TEXT', theme_code)}; border: none; padding:6px;")
                    self.btn_ocr.setStyleSheet(f"background: transparent; color: {get_color('PRIMARY_TEXT', theme_code)}; border: none; padding:6px;")
                except Exception:
                    pass

                # Title and status labels (top bar)
                try:
                    self.lbl_title.setStyleSheet(f"font-size: 15px; font-weight: 600; color: {get_color('PRIMARY_TEXT', theme_code)};")
                    # status uses previous logic for colored dot; ensure text color consistent
                    cur_status_style = f"color: {get_color('SECONDARY_TEXT', theme_code)}; background: rgba(0,0,0,0); border: 1px solid rgba(0,0,0,0); padding:2px 6px; border-radius:4px; font-size:12px;"
                    self.lbl_status.setStyleSheet(cur_status_style)
                    # 顶栏背景
                    try:
                        if hasattr(self, 'right_top') and self.right_top is not None:
                            self.right_top.setStyleSheet(f"background: {get_color('BACKGROUND_PANEL', theme_code)};")
                    except Exception:
                        pass
                except Exception:
                    pass

                # Input area
                try:
                    self.input_edit.setStyleSheet(f"background: {get_color('INPUT_BG', theme_code)}; color: {get_color('PRIMARY_TEXT', theme_code)}; border-top: 1px solid {get_color('BORDER', theme_code)};")
                    # 工具栏容器背景
                    try:
                        if hasattr(self, 'toolbar_container') and self.toolbar_container is not None:
                            self.toolbar_container.setStyleSheet(f"background: {get_color('BACKGROUND_PANEL', theme_code)}; border: none;")
                    except Exception:
                        pass
                    # 输入容器背景（发送按钮下方的区域）
                    try:
                        if hasattr(self, 'input_container') and getattr(self, 'input_container', None) is not None:
                            self.input_container.setStyleSheet(f"background: {get_color('INPUT_BG', theme_code)}; border-top: 1px solid {get_color('BORDER', theme_code)};")
                    except Exception:
                        try:
                            if hasattr(self, 'input_container') and getattr(self, 'input_container', None) is not None:
                                self.input_container.setStyleSheet(f"background: {get_color('INPUT_BG', 'light')}; border-top: 1px solid {get_color('BORDER', 'light')};")
                        except Exception:
                            pass
                except Exception:
                    pass

            except Exception:
                # fallback: keep previous minimal behavior
                try:
                    from gui.styles import BACKGROUND_PANEL
                    bg = BACKGROUND_PANEL
                    if theme_code == 'dark':
                        bg = '#2b2b2b'
                    self.chat_list.setStyleSheet(f"QListView {{ background: {bg}; }}")
                except Exception:
                    pass

            try:
                self.bridge.sig_log.emit('INFO', f"Theme applied: {theme_code}")
            except Exception:
                pass
        except Exception:
            pass

    def _on_user_clicked(self, index):
        data = self.user_model.data(index)
        if not data: return
        
        self.current_target = data
        
        name = data.get('name')
        ip = data.get('ip')
        if data.get('type') == 'all':
            self.lbl_title.setText(L('broadcast_hall'))
        elif data.get('type') == 'group':
            # use localized group prefix
            self.lbl_title.setText(f"{L('group_prefix')}{name}")
        else:
            self.lbl_title.setText(f"{name} ({ip})")
        # 选择用户时更新加密状态
        try:
            enc = False if (not ip or ip == 'all') else self._is_encrypted_with(ip)
            self._set_encrypt_label(enc)
            # update status label when user selected
            try:
                self._set_status_label(data.get('status') or '')
            except Exception:
                self._set_status_label('')
        except Exception:
            self._set_encrypt_label(False)
            self._set_status_label('')

    def _on_chat_clicked(self, index: QModelIndex):
        """Handle clicks on chat items. If the item is a file message and the
        file has been downloaded (has 'local_path'), open it with the system
        default application. Otherwise show a short status message."""
        try:
            data = self.chat_model.data(index)
            if not data:
                return
            if data.get('type') != MSG_TYPE_FILE:
                return

            # If download completed and local_path exists, open it
            local = data.get('local_path')
            status = data.get('status')
            if local and os.path.isfile(local):
                # 首选使用 Qt 的 QDesktopServices 打开；某些 Linux 环境下该调用可能返回 False
                opened = False
                try:
                    opened = QDesktopServices.openUrl(QUrl.fromLocalFile(local))
                except Exception:
                    opened = False

                if not opened:
                    # 回退到系统的 xdg-open（大多数 Linux 桌面环境支持）
                    xdg = shutil.which('xdg-open')
                    if xdg:
                        try:
                            subprocess.Popen([xdg, local], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                            return
                        except Exception:
                            pass

                    # 仍然无法打开，给出帮助性提示
                    self._append_sys_msg(L('detect_launcher_fail'))
                    return
            else:
                # Show informative message depending on status
                if status == 'transferring':
                    self._append_sys_msg(L('file_transferring'))
                elif status == 'waiting':
                    self._append_sys_msg(L('file_waiting'))
                else:
                    self._append_sys_msg(L('file_unavailable'))
        except Exception as e:
            print(f"[Chat Click Error] {e}")

    def _do_send(self):
        text = self.input_edit.toPlainText().strip()
        if not text: return
        
        target = self.current_target['ip']
        if self.current_target['type'] == 'group':
            target = f"group:{self.current_target['name']}"
            
        self.bridge.send_text(target, text)
        self.input_edit.clear()

    def _send_file_action(self):
        path, _ = QFileDialog.getOpenFileName(self, L('select_file'))
        if not path:
            return

        # 如果目标为广播(all)，目前不支持广播文件发送；给出提示
        if self.current_target.get('ip') == 'all':
            self._append_sys_msg(L('send_file_prompt'))
            return

        # 向指定目标发送文件
        if path:
            self.bridge.send_file(self.current_target['ip'], path)
            import os
            # 发送方也显示一个文件气泡 (可选，这里先模拟成已完成状态，因为发送方不需要下载)
            filename = os.path.basename(path)
            size = os.path.getsize(path)
            msg_data = {
                'type': MSG_TYPE_FILE,
                'user': '我',
                'filename': filename,
                'total': size,
                'current': size,
                'status': 'done', # 发送方视为已完成
                'is_me': True,
                'time': datetime.datetime.now().strftime("%H:%M")
            }
            self.chat_model.add_message(msg_data)
            self.chat_list.scrollToBottom()

    def _on_msg_received(self, name, ip, text, is_me, is_enc):
        msg_data = {
            'type': MSG_TYPE_TEXT,
            'user': name,
            'text': text,
            'is_me': is_me,
            'encrypted': bool(is_enc),
            'time': datetime.datetime.now().strftime("%H:%M")
        }
        self.chat_model.add_message(msg_data)
        self.chat_list.scrollToBottom()

    def _on_file_offer(self, offer_id, sender, filename, size):
        # 创建文件消息卡片
        msg_data = {
            'type': MSG_TYPE_FILE,
            'user': sender,
            'offer_id': offer_id,
            'filename': filename,
            'total': size,
            'current': 0,
            'status': 'waiting',
            'is_me': False,
            'time': datetime.datetime.now().strftime("%H:%M")
        }
        self.chat_model.add_message(msg_data)
        self.chat_list.scrollToBottom()
        
        # 自动接受文件
        self.bridge.accept_file(offer_id)

    def _open_settings(self):
        from gui.settings import SettingsDialog
        dlg = SettingsDialog(self.bridge, self)
        dlg.exec_()
        self._refresh_users()

    def _open_group_manager(self):
        """占位：组管理界面（待实现）"""
        # 目前作为占位函数，避免 UI 按钮失效
        self._append_sys_msg(L('group_mgr_placeholder'))

    # --- 工具栏槽函数 ---
    def _on_btn_emoji(self):
        self._append_sys_msg(L('emoji_placeholder'))

    def _on_btn_screen(self):
        # 截图逻辑通常涉及: 隐藏主窗口 -> 截取全屏 -> 弹出裁剪框 -> 恢复窗口
        self._append_sys_msg(L('screen_placeholder'))

    def _on_btn_quick(self):
        """弹出常用语菜单"""
        texts = self.bridge.get_quick_texts()
        if not texts:
            self._append_sys_msg(L('no_quick_texts'))
            return

        menu = QMenu(self)
        menu.setStyleSheet(
            "QMenu { background-color: " + get_color('MENU_BG', 'light') + "; border: 1px solid " + get_color('BORDER', 'light') + "; }"
            "QMenu::item { padding: 5px 20px; }"
            "QMenu::item:selected { background-color: " + get_color('ACCENT', 'light') + "; color: " + get_color('ACCENT_TEXT', 'light') + "; }"
        )

        for text in texts:
            # 使用闭包捕获当前的 text
            action = QAction(text, self)
            action.triggered.connect(lambda checked, t=text: self._insert_quick_text(t))
            menu.addAction(action)

        # 在鼠标位置弹出
        menu.exec_(QCursor.pos())

    def _insert_quick_text(self, text):
        """将选中的常用语插入输入框"""
        self.input_edit.insertPlainText(text)
        self.input_edit.setFocus()

    def _request_ocr(self):
        path, _ = QFileDialog.getOpenFileName(self, L('ocr_select'), "", "Images (*.png *.jpg *.bmp)")
        if path:
            # 记录开始时间以便在回调时计算耗时
            try:
                self._ocr_start = datetime.datetime.now()
            except Exception:
                self._ocr_start = None

            self._append_sys_msg(L('ocr_in_progress').format(name=os.path.basename(path)))
            # 异步调用，结果将通过 sig_ocr_done 返回
            self.bridge.run_ocr(path)

    def _on_ocr_result(self, text, engine_type=None, elapsed=None):
        """OCR 识别完成回调

        Parameters passed from Bridge: (text, engine_type, elapsed)
        """
        if not text:
            self._append_sys_msg(L('ocr_no_text'))
            return
            
        if text.startswith("Error") or text.startswith("OCR Error"):
            self._append_sys_msg(L('ocr_fail').format(err=text))
        else:
            # 成功：直接回填到输入框，方便用户编辑发送
            # 如果输入框已有内容，先换行
            current_content = self.input_edit.toPlainText()
            if current_content and not current_content.endswith('\n'):
                self.input_edit.insertPlainText('\n')
            
            self.input_edit.insertPlainText(text)
            # Prefer engine-provided engine_type and elapsed (from core), fallback to local start time
            # Determine engine tag (CPU or NPU or Unknown)
            eng = engine_type or getattr(self, '_ocr_engine_type', None) or 'Unknown'
            if isinstance(eng, str) and 'NPU' in eng.upper():
                eng_tag = 'NPU'
            elif isinstance(eng, str) and 'CPU' in eng.upper():
                eng_tag = 'CPU'
            else:
                eng_tag = eng

            # elapsed priority: parameter > recorded start time > unknown
            real_elapsed = None
            try:
                if isinstance(elapsed, (int, float)) and elapsed > 0:
                    real_elapsed = float(elapsed)
                else:
                    start = getattr(self, '_ocr_start', None)
                    if start:
                        real_elapsed = (datetime.datetime.now() - start).total_seconds()
            except Exception:
                real_elapsed = None

            if real_elapsed is None:
                self._append_sys_msg(L('ocr_success_unknown').format(engine=eng_tag))
            else:
                self._append_sys_msg(L('ocr_success').format(engine=eng_tag, sec=f"{real_elapsed:.2f}"))
            self.input_edit.setFocus()
    
    def _append_sys_msg(self, text):
        """通过主窗口的状态栏显示提示信息"""
        # self.window() 获取当前控件所在的顶级窗口 (即 MainWindow)
        main_win = self.window()
        
        # 检查 main_win 是否有 statusBar 方法 (防御性编程)
        if main_win and hasattr(main_win, "statusBar"):
            # showMessage(text, timeout_ms): 显示文本，3000ms 后自动清除/恢复
            main_win.statusBar().showMessage(text, 3000) # type: ignore
        else:
            # 如果没找到状态栏 (比如独立测试时)，退化为控制台打印
            print(f"[System]: {text}")