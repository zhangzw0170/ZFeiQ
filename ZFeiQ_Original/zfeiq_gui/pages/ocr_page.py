from PyQt5 import QtCore, QtGui, QtWidgets
import os

class OcrPage(QtWidgets.QWidget):
    """OCR 文字识别页面：顶栏选文件，左图右文布局，API接口预留"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        # 顶栏：文件选择
        top_bar = QtWidgets.QHBoxLayout()
        self.file_path_edit = QtWidgets.QLineEdit()
        self.file_path_edit.setPlaceholderText("选择图片文件...")
        self.file_path_edit.setMinimumWidth(320)
        self.browse_btn = QtWidgets.QPushButton("浏览")
        self.file_path_edit.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        self.browse_btn.setSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Fixed)
        top_bar.addWidget(self.file_path_edit, 1)
        top_bar.addWidget(self.browse_btn, 0)
        root.addLayout(top_bar)

        # 主体：左图右文
        main_split = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        # 左侧图片预览
        left_box = QtWidgets.QWidget()
        left_layout = QtWidgets.QVBoxLayout(left_box)
        left_layout.setContentsMargins(8, 8, 8, 8)
        left_layout.setSpacing(8)
        self.img_label = QtWidgets.QLabel("图片预览")
        self.img_label.setAlignment(QtCore.Qt.AlignCenter)
        self.img_label.setStyleSheet("background:#f5f5f5; border:1px solid #ddd; border-radius:8px;")
        self.img_label.setMinimumSize(320, 320)
        left_layout.addWidget(self.img_label, 1)
        main_split.addWidget(left_box)
        # 右侧识别结果
        right_box = QtWidgets.QWidget()
        right_layout = QtWidgets.QVBoxLayout(right_box)
        right_layout.setContentsMargins(8, 8, 8, 8)
        right_layout.setSpacing(8)
        self.result_text = QtWidgets.QTextEdit()
        self.result_text.setReadOnly(True)
        self.result_text.setPlaceholderText("识别结果将在此显示...")
        right_layout.addWidget(QtWidgets.QLabel("识别到的文字："))
        right_layout.addWidget(self.result_text, 1)
        main_split.addWidget(right_box)
        main_split.setSizes([360, 360])
        root.addWidget(main_split, 1)

        # 连接文件选择
        self.browse_btn.clicked.connect(self._on_browse)
        self.file_path_edit.textChanged.connect(self._on_path_changed)

    def _on_browse(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "选择图片", "", "图片文件 (*.png *.jpg *.jpeg *.bmp)")
        if path:
            self.file_path_edit.setText(path)

    def _on_path_changed(self, path):
        if not path or not os.path.isfile(path):
            self.img_label.setText("图片预览")
            self.img_label.setPixmap(QtGui.QPixmap())
            self.result_text.clear()
            return
        pm = QtGui.QPixmap(path)
        if pm.isNull():
            self.img_label.setText("无法加载图片")
            self.img_label.setPixmap(QtGui.QPixmap())
            self.result_text.clear()
            return
        self.img_label.setPixmap(pm.scaled(320, 320, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation))
        # 预留：API识别接口
        self.result_text.setPlainText("(识别结果 API 待接入)")
