from PyQt5 import QtCore, QtGui, QtWidgets
import os
import time
from zfeiq_gui.lang import get_translations, get_current_language

# 导入我们之前写好的核心 OCR 引擎
try:
    from cli.ocr import ZFeiQOcr
except ImportError:
    ZFeiQOcr = None

class OcrWorker(QtCore.QThread):
    """
    后台工作线程：负责执行 OCR 推理，防止 GUI 界面卡死
    """
    sigDone = QtCore.pyqtSignal(str)  # 信号：任务完成，传回结果文本

    def __init__(self, img_path):
        super().__init__()
        self.img_path = img_path

    def run(self):
        if not ZFeiQOcr:
            self.sigDone.emit("错误：无法导入 zfeiq_cli.ocr 模块，请检查代码完整性。")
            return

        # 获取引擎单例（如果尚未初始化，这里会触发加载，可能耗时几秒）
        # 注意：第一次运行会慢一点，因为要加载模型
        engine = ZFeiQOcr.get_instance()
        
        if not engine.ready:
            self.sigDone.emit("OCR 引擎初始化失败。\n请检查控制台日志 (ONNX/NPU 依赖是否缺失)。")
            return

        # 执行识别
        try:
            start_t = time.time()
            text = engine.run(self.img_path)
            cost = time.time() - start_t
            
            # 附加一点调试信息（可选）
            mode = "NPU (RK3566)" if engine.use_npu else "CPU (ONNX)"
            header = f"=== 识别成功 ({mode}, {cost:.2f}s) ===\n"
            
            self.sigDone.emit(header + text)
        except Exception as e:
            self.sigDone.emit(f"识别过程发生异常:\n{str(e)}")

class OcrPage(QtWidgets.QWidget):
    """OCR 文字识别页面（支持语言包）"""

    def __init__(self, parent=None, lang: str = None):
        super().__init__(parent)
        if lang is None:
            lang = get_current_language()
        self._translations = get_translations(lang)
        self._build_ui()
        # 延迟一秒在后台预热引擎（可选，提升用户第一次点击的体验）
        QtCore.QTimer.singleShot(1000, self._warmup_engine)

    def _warmup_engine(self):
        """在后台静默初始化引擎，避免用户点按钮时才卡顿"""
        if ZFeiQOcr:
            # 只是为了触发 __init__ 加载模型，不需要跑图
            self.result_text.setPlaceholderText(self._translations.get('ocr_processing', '正在后台初始化 OCR 模型...'))
            # 触发单例但不运行识别
            try:
                QtCore.QTimer.singleShot(0, lambda: getattr(ZFeiQOcr, 'get_instance', lambda: None)())
            except Exception:
                pass

    def _build_ui(self):
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        # 1. 顶栏：文件选择 + 按钮
        top_bar = QtWidgets.QHBoxLayout()
        
        self.file_path_edit = QtWidgets.QLineEdit()
        self.file_path_edit.setPlaceholderText(self._translations.get('browse', '请选择图片文件...'))
        self.file_path_edit.setMinimumWidth(300)
        
        self.browse_btn = QtWidgets.QPushButton(self._translations.get('browse', '浏览'))
        self.run_btn = QtWidgets.QPushButton(self._translations.get('ocr', '开始识别'))
        self.run_btn.setEnabled(False) # 有图片才能点
        
        # 样式美化一下按钮
        self.run_btn.setStyleSheet("""
            QPushButton { background-color: #0078d7; color: white; font-weight: bold; padding: 5px 15px; }
            QPushButton:hover { background-color: #0063b1; }
            QPushButton:disabled { background-color: #cccccc; color: #666666; }
        """)

        top_bar.addWidget(self.file_path_edit, 1)
        top_bar.addWidget(self.browse_btn, 0)
        top_bar.addWidget(self.run_btn, 0)
        root.addLayout(top_bar)

        # 2. 主体：左图右文
        main_split = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        
        # 左侧：图片预览容器
        left_box = QtWidgets.QWidget()
        left_layout = QtWidgets.QVBoxLayout(left_box)
        left_layout.setContentsMargins(0, 0, 0, 0)
        
        self.img_label = QtWidgets.QLabel(self._translations.get('ocr_preview', '图片预览区域'))
        self.img_label.setAlignment(QtCore.Qt.AlignCenter)
        self.img_label.setStyleSheet("background:#f0f0f0; border:1px solid #ddd; border-radius:4px;")
            # 注释掉最小尺寸限制以允许在窄屏上缩放
            # self.img_label.setMinimumSize(320, 320)
        
        left_layout.addWidget(self.img_label, 1)
        main_split.addWidget(left_box)
        
        # 右侧：结果文本框
        right_box = QtWidgets.QWidget()
        right_layout = QtWidgets.QVBoxLayout(right_box)
        right_layout.setContentsMargins(0, 0, 0, 0)
        
        lbl_res = QtWidgets.QLabel(self._translations.get('ocr', '识别结果 (可复制/编辑):'))
        self.result_text = QtWidgets.QTextEdit()
        self.result_text.setReadOnly(False) # 允许用户修改识别错的字
        self.result_text.setPlaceholderText(self._translations.get('ocr_processing', '点击 "开始识别" 后，文字将显示在这里...'))
        self.result_text.setStyleSheet("font-family: Consolas, 'Microsoft YaHei'; font-size: 14px;")
        
        right_layout.addWidget(lbl_res)
        right_layout.addWidget(self.result_text, 1)
        main_split.addWidget(right_box)
        
        # 设置分割比例 1:1
        main_split.setStretchFactor(0, 1)
        main_split.setStretchFactor(1, 1)
        
        root.addWidget(main_split, 1)

        # 3. 信号连接
        self.browse_btn.clicked.connect(self._on_browse)
        self.file_path_edit.textChanged.connect(self._on_path_changed)
        self.run_btn.clicked.connect(self._on_run)

    def _on_browse(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            self._translations.get('browse_dialog_title', '选择图片'),
            "",
            self._translations.get('images_filter', '图片文件 (*.png *.jpg *.jpeg *.bmp *.gif)')
        )
        if path:
            self.file_path_edit.setText(path)

    def _on_path_changed(self, path):
        """当路径变化时，尝试加载图片预览"""
        if not path or not os.path.isfile(path):
            self.run_btn.setEnabled(False)
            self.img_label.setText(self._translations.get('avatar', '图片预览区域'))
            self.img_label.setPixmap(QtGui.QPixmap())
            return
        
        pm = QtGui.QPixmap(path)
        if pm.isNull():
            self.run_btn.setEnabled(False)
            self.img_label.setText(self._translations.get('preview', '无法读取此图片'))
            return

        # 缩放到合适大小显示 (KeepAspectRatio)
        scaled = pm.scaled(
            self.img_label.size() - QtCore.QSize(10, 10), 
            QtCore.Qt.KeepAspectRatio, 
            QtCore.Qt.SmoothTransformation
        )
        self.img_label.setPixmap(scaled)
        self.run_btn.setEnabled(True)
        # 清空旧结果
        self.result_text.clear()

    def _on_run(self):
        path = self.file_path_edit.text()
        if not path or not os.path.isfile(path):
            return
        
        # 界面状态切换
        self.run_btn.setEnabled(False)
        self.run_btn.setText(self._translations.get('ocr_processing', '识别中...'))
        self.file_path_edit.setEnabled(False)
        self.browse_btn.setEnabled(False)
        self.result_text.setPlainText(self._translations.get('ocr_processing', '正在后台进行 OCR 识别，请稍候...\n(RK3566 NPU 首次运行可能需要几秒加载模型)'))
        
        # 启动线程
        self._worker = OcrWorker(path)
        self._worker.sigDone.connect(self._on_worker_done)
        self._worker.finished.connect(self._worker.deleteLater)
        self._worker.start()

    def _on_worker_done(self, result_text):
        # 恢复界面
        self.run_btn.setEnabled(True)
        self.run_btn.setText("开始识别")
        self.file_path_edit.setEnabled(True)
        self.browse_btn.setEnabled(True)
        
        # 显示结果
        self.result_text.setPlainText(result_text)
