import datetime
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QListView, 
                             QTextEdit, QPushButton, QStyledItemDelegate, 
                             QAbstractItemView, QLabel, QSplitter)  # [修复] 补上 QLabel, QSplitter
from PyQt5.QtCore import (Qt, QAbstractListModel, QModelIndex, QSize, 
                          QRect)
from PyQt5.QtGui import QPainter, QColor, QFontMetrics, QBrush

# --- 1. 数据模型 (Model) ---
class ChatModel(QAbstractListModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.messages = []

    def rowCount(self, parent=QModelIndex()):
        return len(self.messages)

    # [修复] 加上默认参数 role=Qt.DisplayRole
    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid() or role != Qt.DisplayRole:
            return None
        return self.messages[index.row()]

    def add_message(self, msg_data):
        self.beginInsertRows(QModelIndex(), len(self.messages), len(self.messages))
        self.messages.append(msg_data)
        self.endInsertRows()

# --- 2. 绘图代理 (Delegate) ---
class ChatDelegate(QStyledItemDelegate):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.padding = 10
        self.bubble_padding = 10
        self.max_width = 400

    def sizeHint(self, option, index):
        data = index.data(Qt.DisplayRole)
        if not data: return QSize(0, 0)
        
        font_metrics = option.fontMetrics
        rect = font_metrics.boundingRect(
            0, 0, self.max_width, 0, 
            int(Qt.TextWordWrap), data['text'] # [修复] 显式转 int
        )
        
        total_height = rect.height() + (self.padding * 3) + 20 
        return QSize(option.rect.width(), total_height)

    def paint(self, painter, option, index):
        data = index.data(Qt.DisplayRole)
        if not data: return

        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)
        
        rect = option.rect
        is_me = data['is_me']
        text = data['text']
        user = data['user']
        
        # 1. 绘制名字
        painter.setPen(QColor("#888888"))
        font = painter.font()
        font.setPointSize(9)
        painter.setFont(font)
        
        name_rect = QRect(rect)
        name_rect.setTop(rect.top() + 5)
        name_rect.setHeight(20)
        
        if is_me:
            # [修复] 显式转 int 解决 Pylance 报错
            align = int(Qt.AlignRight | Qt.AlignVCenter)
            painter.drawText(name_rect.adjusted(0,0,-10,0), align, user)
        else:
            align = int(Qt.AlignLeft | Qt.AlignVCenter)
            painter.drawText(name_rect.adjusted(10,0,0,0), align, user)

        # 2. 计算气泡
        font.setPointSize(11)
        painter.setFont(font)
        fm = QFontMetrics(font)
        # [修复] 显式转 int
        text_rect = fm.boundingRect(0, 0, self.max_width, 0, int(Qt.TextWordWrap), text)
        
        bubble_w = text_rect.width() + (self.bubble_padding * 2)
        bubble_h = text_rect.height() + (self.bubble_padding * 2)
        bubble_y = rect.top() + 25
        
        if is_me:
            bubble_x = rect.right() - bubble_w - 10
            bg_color = QColor("#95EC69")
        else:
            bubble_x = rect.left() + 10
            bg_color = QColor("#FFFFFF")

        bubble_rect = QRect(bubble_x, bubble_y, bubble_w, bubble_h)

        # 3. 画气泡
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(bg_color))
        painter.drawRoundedRect(bubble_rect, 6, 6)
        
        # 4. 画文字
        painter.setPen(QColor("#000000"))
        t_rect = bubble_rect.adjusted(self.bubble_padding, self.bubble_padding, -self.bubble_padding, -self.bubble_padding)
        # [修复] 显式转 int
        painter.drawText(t_rect, int(Qt.TextWordWrap | Qt.AlignLeft), text)

        painter.restore()

# --- 3. 聊天页面 (Page) ---
class ChatPage(QWidget):
    def __init__(self, bridge, parent=None):
        super().__init__(parent)
        self.bridge = bridge
        self.current_target_ip = "all"
        
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # === 顶部导航栏 ===
        top_bar = QWidget()
        top_bar.setFixedHeight(50)
        top_bar.setStyleSheet("background-color: #f7f7f7; border-bottom: 1px solid #e0e0e0;")
        top_layout = QHBoxLayout(top_bar)
        top_layout.setContentsMargins(15, 0, 15, 0)
        
        self.lbl_title = QLabel("ZFeiQ 群聊大厅 (广播)")
        self.lbl_title.setStyleSheet("font-size: 16px; font-weight: bold; color: #333;")
        top_layout.addWidget(self.lbl_title)
        
        top_layout.addStretch()
        
        self.btn_settings = QPushButton("⚙️ 设置")
        self.btn_settings.setFixedSize(80, 30)
        self.btn_settings.setCursor(Qt.PointingHandCursor)
        self.btn_settings.setStyleSheet("""
            QPushButton { background: white; border: 1px solid #ccc; border-radius: 4px; }
            QPushButton:hover { background: #e6e6e6; }
        """)
        self.btn_settings.clicked.connect(self._open_settings)
        top_layout.addWidget(self.btn_settings)
        
        main_layout.addWidget(top_bar)

        # === 核心区域：Splitter (左侧列表 | 右侧聊天) ===
        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(1)
        splitter.setStyleSheet("QSplitter::handle { background: #e0e0e0; }")
        
        # [TODO] 左侧用户列表 (暂时留空，下一次填这里)
        # self.user_list = ...
        # splitter.addWidget(self.user_list) 

        # 右侧：聊天容器
        chat_container = QWidget()
        chat_layout = QVBoxLayout(chat_container)
        chat_layout.setContentsMargins(0,0,0,0)
        chat_layout.setSpacing(0)

        # 消息列表
        self.list_view = QListView()
        self.model = ChatModel()
        self.delegate = ChatDelegate()
        self.list_view.setModel(self.model)
        self.list_view.setItemDelegate(self.delegate)
        self.list_view.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.list_view.setSelectionMode(QAbstractItemView.NoSelection)
        self.list_view.setStyleSheet("QListView { background: #F5F5F5; border: none; }")
        chat_layout.addWidget(self.list_view, 1)

        # 底部输入区
        input_container = QWidget()
        input_container.setFixedHeight(60)
        input_container.setStyleSheet("background: #FFFFFF; border-top: 1px solid #E0E0E0;")
        h_layout = QHBoxLayout(input_container)
        h_layout.setContentsMargins(10, 8, 10, 8)
        
        self.input_edit = QTextEdit()
        self.input_edit.setPlaceholderText("发送消息... (Enter换行, Ctrl+Enter发送)")
        self.input_edit.setStyleSheet("border: none; background: transparent;")
        
        self.btn_send = QPushButton("发送")
        self.btn_send.setFixedSize(60, 32)
        self.btn_send.setCursor(Qt.PointingHandCursor)
        self.btn_send.clicked.connect(self._do_send)
        
        h_layout.addWidget(self.input_edit, 1)
        h_layout.addWidget(self.btn_send)
        
        chat_layout.addWidget(input_container)
        
        # 将聊天容器加入 splitter
        splitter.addWidget(chat_container)
        
        main_layout.addWidget(splitter)

    def _connect_signals(self):
        self.bridge.sig_msg.connect(self._on_msg_received)
        self.bridge.sig_file_offer.connect(self._on_file_offer)

    def _do_send(self):
        text = self.input_edit.toPlainText().strip()
        if not text: return
        self.bridge.send_text(self.current_target_ip, text)
        self.input_edit.clear()

    def _on_msg_received(self, name, ip, text, is_me, is_enc):
        msg_data = {
            'user': name,
            'text': text,
            'is_me': is_me,
            'time': datetime.datetime.now().strftime("%H:%M")
        }
        self.model.add_message(msg_data)
        self.list_view.scrollToBottom()

    def _on_file_offer(self, offer_id, sender, filename, size):
        msg = f"[文件请求]\n文件名: {filename}\n大小: {size} Bytes"
        self._on_msg_received(sender, "", msg, False, False)

    def _open_settings(self):
        from gui.settings import SettingsDialog
        dlg = SettingsDialog(self.bridge, self)
        dlg.exec_()
        # 刷新信息
        info = self.bridge.get_my_info()