import datetime
import os
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QListView, 
                             QTextEdit, QPushButton, QStyledItemDelegate, 
                             QAbstractItemView, QLabel, QSplitter, QFrame,
                             QStyle, QFileDialog, QApplication)
from PyQt5.QtCore import (Qt, QAbstractListModel, QModelIndex, QSize, 
                          QRect, QTimer, pyqtSignal, QEvent)
from PyQt5.QtGui import QPainter, QColor, QFontMetrics, QBrush, QPen, QFont, QKeyEvent

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
            'type': 'all', 'name': '所有人 (广播)', 'ip': 'all', 
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
            'type': 'all', 'name': '所有人 (广播)', 'ip': 'all', 
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
        
        painter.setPen(QColor("#333"))
        font.setPointSize(11)
        font.setBold(False)
        painter.setFont(font)
        painter.drawText(text_x, name_y, name)
        
        ip_y = rect.top() + 42
        ip_str = data.get('ip', '')
        if data.get('type') == 'group':
            ip_str = f"群组 ({data.get('count',0)}人)"
        
        painter.setPen(QColor("#888"))
        font.setPointSize(9)
        painter.setFont(font)
        painter.drawText(text_x, ip_y, ip_str)

        status = data.get('status', 'offline')
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
        painter.setRenderHint(QPainter.Antialiasing)
        
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
        
        if is_me:
            bubble_x = rect.right() - bubble_w - 15
            bg_color = QColor("#95EC69") 
            border_color = QColor("#85D659")
        else:
            bubble_x = rect.left() + 15
            bg_color = QColor("#FFFFFF")
            border_color = QColor("#E0E0E0")

        bubble_rect = QRect(bubble_x, bubble_y, bubble_w, bubble_h)

        # 绘制背景
        painter.setPen(QPen(border_color))
        painter.setBrush(QBrush(bg_color))
        painter.drawRoundedRect(bubble_rect, 6, 6)
        
        # 绘制文本
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
        
        if is_me:
            bubble_x = rect.right() - bubble_w - 15
            bg_color = QColor("#FFFFFF") # 发送文件通常也是白色底，或者稍微区分
            border_color = QColor("#E0E0E0")
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
        painter.setBrush(QColor("#f39c12")) # 橙色文件图标
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

        # === 顶部导航栏 ===
        top_bar = QWidget()
        top_bar.setFixedHeight(50)
        top_bar.setStyleSheet("background-color: #f5f5f5; border-bottom: 1px solid #dcdcdc;")
        top_layout = QHBoxLayout(top_bar)
        top_layout.setContentsMargins(15, 0, 15, 0)
        
        self.lbl_title = QLabel("群聊大厅 (广播)")
        self.lbl_title.setStyleSheet("font-size: 16px; font-weight: 600; color: #333;")
        top_layout.addWidget(self.lbl_title)
        
        top_layout.addStretch()
        
        self.btn_settings = QPushButton("⚙️ 设置")
        self.btn_settings.setFixedSize(80, 30)
        self.btn_settings.setCursor(Qt.PointingHandCursor)
        self.btn_settings.clicked.connect(self._open_settings)
        top_layout.addWidget(self.btn_settings)
        
        main_layout.addWidget(top_bar)

        # === 核心区域 ===
        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(1)
        splitter.setStyleSheet("QSplitter::handle { background: #dcdcdc; }")
        
        # --- 左侧：用户列表 ---
        self.user_list = QListView()
        self.user_model = UserListModel()
        self.user_delegate = UserDelegate()
        self.user_list.setModel(self.user_model)
        self.user_list.setItemDelegate(self.user_delegate)
        self.user_list.setFrameShape(QFrame.NoFrame)
        self.user_list.setStyleSheet("background: #fdfdfd;")
        self.user_list.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.user_list.clicked.connect(self._on_user_clicked)
        
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0,0,0,0)
        left_layout.addWidget(self.user_list)
        left_panel.setMinimumWidth(200)
        left_panel.setMaximumWidth(350)
        
        splitter.addWidget(left_panel)

        # --- 右侧：聊天区域 ---
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0,0,0,0)
        right_layout.setSpacing(0)

        self.chat_list = QListView()
        self.chat_model = ChatModel()
        self.chat_delegate = ChatDelegate()
        self.chat_list.setModel(self.chat_model)
        self.chat_list.setItemDelegate(self.chat_delegate)
        self.chat_list.setFrameShape(QFrame.NoFrame)
        self.chat_list.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.chat_list.setSelectionMode(QAbstractItemView.NoSelection)
        self.chat_list.setStyleSheet("background: #f5f5f5;")
        
        right_layout.addWidget(self.chat_list, 1)

        input_container = QWidget()
        input_container.setFixedHeight(120)
        input_container.setStyleSheet("background: #ffffff; border-top: 1px solid #dcdcdc;")
        input_layout = QVBoxLayout(input_container)
        input_layout.setContentsMargins(10, 5, 10, 5)
        
        toolbar = QHBoxLayout()
        toolbar.setSpacing(8) # 按钮间距
        toolbar.setContentsMargins(0, 0, 0, 5)

        # 辅助函数：快速创建统一样式的按钮
        def _create_tool_btn(text, slot=None):
            btn = QPushButton(text)
            btn.setFixedSize(85, 32) # 加宽，加高，方便触控或鼠标点击
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet("""
                QPushButton { 
                    background-color: #f0f0f0; 
                    border: 1px solid #dcdcdc; 
                    border-radius: 4px; 
                    color: #444; 
                    font-size: 12px;
                }
                QPushButton:hover { 
                    background-color: #e6e6e6; 
                    border-color: #bbbbbb;
                    color: #000;
                }
                QPushButton:pressed { background-color: #d0d0d0; }
            """)
            if slot: btn.clicked.connect(slot)
            return btn

        self.btn_emoji = _create_tool_btn("😊 表情", self._on_btn_emoji)
        self.btn_screen = _create_tool_btn("✂️ 截图", self._on_btn_screen)
        self.btn_quick = _create_tool_btn("💬 常用语", self._on_btn_quick)
        self.btn_file = _create_tool_btn("📎 文件", self._send_file_action)
        self.btn_ocr = _create_tool_btn("🔍 识字", self._on_btn_ocr)
        
        toolbar.addWidget(self.btn_emoji)
        toolbar.addWidget(self.btn_screen)
        toolbar.addWidget(self.btn_quick)
        toolbar.addWidget(self.btn_file)
        toolbar.addWidget(self.btn_ocr)
        
        toolbar.addStretch()
        input_layout.addLayout(toolbar)
        
        self.input_edit = QTextEdit()
        self.input_edit.setPlaceholderText("发送消息... (Enter 发送，Ctrl+Enter 换行)")
        self.input_edit.setFrameShape(QFrame.NoFrame)
        # [关键] 安装事件过滤器
        self.input_edit.installEventFilter(self)
        
        input_layout.addWidget(self.input_edit)
        
        send_bar = QHBoxLayout()
        send_bar.addStretch()
        self.btn_send = QPushButton("发送(S)")
        self.btn_send.setFixedSize(80, 30)
        self.btn_send.setStyleSheet("""
            QPushButton { background-color: #f5f5f5; border: 1px solid #dcdcdc; border-radius: 4px; color: #666; }
            QPushButton:hover { background-color: #129611; color: white; border: none; }
        """)
        self.btn_send.setCursor(Qt.PointingHandCursor)
        self.btn_send.clicked.connect(self._do_send)
        send_bar.addWidget(self.btn_send)
        input_layout.addLayout(send_bar)
        
        right_layout.addWidget(input_container)
        splitter.addWidget(right_panel)
        
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)
        
        main_layout.addWidget(splitter)

    def eventFilter(self, watched, event):
        # 只处理输入框的按键事件
        if watched == self.input_edit and event.type() == QEvent.KeyPress:
            e: QKeyEvent = event

            # Shift+Enter → 换行
            if e.key() in (Qt.Key_Return, Qt.Key_Enter) and (e.modifiers() & Qt.ShiftModifier):
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

    def _refresh_users(self):
        user_list = self.bridge.get_user_list()
        self.user_model.update_data(user_list)

    def _on_user_clicked(self, index):
        data = self.user_model.data(index)
        if not data: return
        
        self.current_target = data
        
        name = data.get('name')
        ip = data.get('ip')
        if data.get('type') == 'all':
            self.lbl_title.setText("群聊大厅 (广播)")
        elif data.get('type') == 'group':
            self.lbl_title.setText(f"群组: {name}")
        else:
            self.lbl_title.setText(f"{name} ({ip})")

    def _do_send(self):
        text = self.input_edit.toPlainText().strip()
        if not text: return
        
        target = self.current_target['ip']
        if self.current_target['type'] == 'group':
            target = f"group:{self.current_target['name']}"
            
        self.bridge.send_text(target, text)
        self.input_edit.clear()

    def _send_file_action(self):
        path, _ = QFileDialog.getOpenFileName(self, "选择文件")
        if path and self.current_target['ip'] != 'all':
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

    # --- 工具栏槽函数 ---
    def _on_btn_emoji(self):
        self._append_sys_msg("功能开发中：表情选择")

    def _on_btn_screen(self):
        # 截图逻辑通常涉及: 隐藏主窗口 -> 截取全屏 -> 弹出裁剪框 -> 恢复窗口
        self._append_sys_msg("功能开发中：屏幕截图")

    def _on_btn_quick(self):
        # 常用语菜单
        self._append_sys_msg("功能开发中：常用语")

    def _on_btn_ocr(self):
        # 调用 OCR (选择图片 -> 识别 -> 填入输入框)
        path, _ = QFileDialog.getOpenFileName(self, "选择图片进行OCR", "", "Images (*.png *.jpg *.bmp)")
        if path:
            self._append_sys_msg(f"正在识别: {os.path.basename(path)} ...")
            # 这里的 bridge.run_ocr 需要自行实现回调或信号来获取结果
            # 暂时演示：
            self.bridge.run_ocr(path) 

    def _append_sys_msg(self, text):
        """在聊天框临时插入一条系统提示（仅自己可见，不通过网络）"""
        msg_data = {
            'type': 'text', 'user': '系统', 'text': text,
            'is_me': False, 'time': datetime.datetime.now().strftime("%H:%M")
        }
        self.chat_model.add_message(msg_data)
        self.chat_list.scrollToBottom()