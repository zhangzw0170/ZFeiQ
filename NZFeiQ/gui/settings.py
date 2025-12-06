import sys
import os
import platform
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QTabWidget, QWidget, 
                             QFormLayout, QLineEdit, QComboBox, QPushButton, 
                             QMessageBox, QLabel, QGroupBox, QHBoxLayout, 
                             QFileDialog, QCheckBox, QTextBrowser)
from PyQt5.QtCore import Qt, QUrl
from PyQt5.QtGui import QDesktopServices, QPixmap

# 尝试导入版本号
try:
    from core import __version__ as CORE_VERSION
except ImportError:
    CORE_VERSION = "Unknown"

class SettingsDialog(QDialog):
    def __init__(self, bridge, parent=None):
        super().__init__(parent)
        self.bridge = bridge
        self.setWindowTitle("ZFeiQ 设置")
        self.resize(550, 420) # 稍微宽一点以容纳路径选择
        
        self.my_info = self.bridge.get_my_info()
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)
        
        # --- Tab 1: 基础设置 (用户、网络、文件) ---
        self.tab_basic = QWidget()
        self._init_basic(self.tab_basic)
        self.tabs.addTab(self.tab_basic, "基础设置")
        
        # --- Tab 2: 安全与调试 ---
        self.tab_security = QWidget()
        self._init_security(self.tab_security)
        self.tabs.addTab(self.tab_security, "安全与调试")
        
        # --- Tab 3: 关于 ---
        self.tab_about = QWidget()
        self._init_about(self.tab_about)
        self.tabs.addTab(self.tab_about, "关于")
        
        # 底部按钮
        btn_box = QHBoxLayout()
        btn_box.addStretch()
        
        self.btn_save = QPushButton("保存配置")
        self.btn_save.setFixedSize(100, 35)
        self.btn_save.setStyleSheet("background-color: #0078d7; color: white; font-weight: bold; border-radius: 4px;")
        self.btn_save.clicked.connect(self._save_and_close)
        
        btn_box.addWidget(self.btn_save)
        layout.addLayout(btn_box)

    def _init_basic(self, parent):
        layout = QVBoxLayout(parent)
        layout.setSpacing(10)
        
        # Group 1: 个人信息
        grp_user = QGroupBox("个人与状态")
        fl_user = QFormLayout(grp_user)
        
        self.inp_name = QLineEdit(self.my_info.get('name', ''))
        fl_user.addRow("用户昵称:", self.inp_name)
        
        self.cmb_status = QComboBox()
        self.cmb_status.addItems(["在线 (online)", "忙碌 (busy)", "离开 (away)"])
        # 状态回显
        curr = self.my_info.get('status', 'online')
        idx = 0
        if 'busy' in curr: idx = 1
        elif 'away' in curr: idx = 2
        self.cmb_status.setCurrentIndex(idx)
        fl_user.addRow("当前状态:", self.cmb_status)
        
        fl_user.addRow("绑定 IP:", QLabel(self.my_info.get('ip', 'Unknown')))
        layout.addWidget(grp_user)
        
        # Group 2: 文件路径
        grp_file = QGroupBox("文件存储")
        fl_file = QFormLayout(grp_file)
        
        # 下载目录
        self.path_down = self._create_path_selector("./common/downloads")
        fl_file.addRow("下载目录:", self.path_down)
        
        # 截图目录
        self.path_shot = self._create_path_selector("./common/screenshots")
        fl_file.addRow("截图目录:", self.path_shot)
        
        layout.addWidget(grp_file)
        layout.addStretch()

    def _create_path_selector(self, default_path):
        # 容器 widget
        w = QWidget()
        h = QHBoxLayout(w)
        h.setContentsMargins(0,0,0,0)
        
        inp = QLineEdit(os.path.abspath(default_path)) # 这里应从配置读取，暂用默认
        inp.setReadOnly(True)
        btn = QPushButton("...")
        btn.setFixedWidth(30)
        btn.clicked.connect(lambda: self._choose_dir(inp))
        
        h.addWidget(inp)
        h.addWidget(btn)
        return w

    def _choose_dir(self, line_edit):
        d = QFileDialog.getExistingDirectory(self, "选择目录", line_edit.text())
        if d:
            line_edit.setText(d)

    def _init_security(self, parent):
        layout = QVBoxLayout(parent)
        
        # Group 1: 加密信息
        grp_sec = QGroupBox("加密指纹 (X25519)")
        v_sec = QVBoxLayout(grp_sec)
        
        fp = "Unknown"
        if hasattr(self.bridge.core, 'identity_pub_bytes'):
            import hashlib
            raw = self.bridge.core.identity_pub_bytes
            if raw:
                fp = hashlib.sha256(raw).hexdigest()
        
        lbl_fp = QLabel(fp)
        lbl_fp.setWordWrap(True)
        lbl_fp.setStyleSheet("font-family: Consolas; color: #555; background: #eee; padding: 5px; border-radius: 3px;")
        v_sec.addWidget(lbl_fp)
        
        btn_regen = QPushButton("⚠️ 重生成密钥对")
        btn_regen.setFixedWidth(120)
        btn_regen.clicked.connect(self._regen_keys)
        v_sec.addWidget(btn_regen)
        layout.addWidget(grp_sec)
        
        # Group 2: 调试
        grp_dbg = QGroupBox("调试选项")
        v_dbg = QVBoxLayout(grp_dbg)
        
        self.chk_raw = QCheckBox("在控制台显示原始密文 (Raw Crypto Data)")
        self.chk_log_debug = QCheckBox("开启详细日志 (Debug Level)")
        
        v_dbg.addWidget(self.chk_raw)
        v_dbg.addWidget(self.chk_log_debug)
        layout.addWidget(grp_dbg)
        
        layout.addStretch()

    def _init_about(self, parent):
        layout = QVBoxLayout(parent)
        layout.setAlignment(Qt.AlignTop)
        
        # 简单的 Logo 区域
        lbl_logo = QLabel("ZFeiQ")
        lbl_logo.setAlignment(Qt.AlignCenter)
        lbl_logo.setStyleSheet("font-size: 24px; font-weight: bold; color: #0078d7; margin: 20px;")
        layout.addWidget(lbl_logo)
        
        form = QFormLayout()
        form.setSpacing(10)
        form.addRow("核心版本:", QLabel(CORE_VERSION))
        form.addRow("最后更新:", QLabel("2025-12-05"))
        
        sys_info = f"{platform.system()} {platform.release()} ({platform.machine()})"
        form.addRow("系统平台:", QLabel(sys_info))
        
        python_info = f"{platform.python_version()} (Qt 5)"
        form.addRow("运行环境:", QLabel(python_info))
        
        layout.addLayout(form)
        
        layout.addSpacing(20)
        btn_link = QPushButton("打开源码仓库 (GitHub)")
        btn_link.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://github.com/YourRepo/NZFeiQ")))
        layout.addWidget(btn_link)

    def _regen_keys(self):
        ret = QMessageBox.warning(self, "警告", "重生成密钥将导致之前的加密会话失效，且无法解密历史加密消息。\n确定要继续吗？", 
                                  QMessageBox.Yes | QMessageBox.No)
        if ret == QMessageBox.Yes:
            # 模拟调用
            QMessageBox.information(self, "提示", "密钥已重置 (需重启生效)")

    def _save_and_close(self):
        name = self.inp_name.text().strip()
        status_map = ["online", "busy", "away"]
        status = status_map[self.cmb_status.currentIndex()]
        
        # 这里应该保存路径配置到 config.json
        # path_dl = self.path_down.findChild(QLineEdit).text()
        
        if not name:
            QMessageBox.warning(self, "错误", "昵称不能为空")
            return
            
        self.bridge.core.username = name
        self.bridge.core.status = status
        # self.bridge.core.save_config(...) 
        
        self.bridge.sig_log.emit("INFO", f"设置已保存: {name}")
        self.accept()