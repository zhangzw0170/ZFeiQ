from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QTabWidget, QWidget, 
                             QFormLayout, QLineEdit, QComboBox, QPushButton, 
                             QMessageBox, QLabel, QGroupBox, QHBoxLayout)
from PyQt5.QtCore import Qt

class SettingsDialog(QDialog):
    def __init__(self, bridge, parent=None):
        super().__init__(parent)
        self.bridge = bridge
        self.setWindowTitle("ZFeiQ 设置")
        self.resize(450, 350) # 嵌入式设备上不要太大
        
        # 获取当前配置
        self.info = self.bridge.get_my_info()
        
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        
        # 顶部选项卡
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)
        
        # --- 分页1: 常规设置 ---
        self.tab_general = QWidget()
        self._init_general() 
        self.tabs.addTab(self.tab_general, "常规")
        
        # --- 分页2: 安全/网络 ---
        self.tab_network = QWidget()
        self._init_network()
        self.tabs.addTab(self.tab_network, "安全与网络")
        
        # 底部按钮区
        btn_box = QHBoxLayout()
        btn_box.addStretch()
        
        self.btn_save = QPushButton("保存配置")
        self.btn_save.setFixedSize(100, 35)
        # 蓝色主按钮风格
        self.btn_save.setStyleSheet("background-color: #0078d7; color: white; font-weight: bold; border-radius: 4px;")
        self.btn_save.clicked.connect(self._save_and_close)
        
        btn_box.addWidget(self.btn_save)
        layout.addLayout(btn_box)

    def _init_general(self):
        form = QFormLayout(self.tab_general)
        form.setSpacing(15)
        form.setContentsMargins(20, 20, 20, 20)
        
        # 用户名
        self.inp_name = QLineEdit(self.info.get('name', ''))
        self.inp_name.setPlaceholderText("展示给他人的名称")
        form.addRow("用户昵称:", self.inp_name)
        
        # 在线状态
        self.cmb_status = QComboBox()
        self.cmb_status.addItems(["在线 (online)", "忙碌 (busy)", "离开 (away)"])
        # 简单的状态映射
        current_status = self.info.get('status', 'online')
        idx = 0
        if 'busy' in current_status: idx = 1
        elif 'away' in current_status: idx = 2
        self.cmb_status.setCurrentIndex(idx)
        form.addRow("当前状态:", self.cmb_status)

        # 软件渲染 (提示)
        lbl_tips = QLabel("提示: 如遇界面黑屏或卡顿，请在启动脚本中强制开启 QT_OPENGL=software")
        lbl_tips.setWordWrap(True)
        lbl_tips.setStyleSheet("color: #666; font-size: 12px;")
        form.addRow(lbl_tips)

    def _init_network(self):
        layout = QVBoxLayout(self.tab_network)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # 网络信息展示
        grp_net = QGroupBox("网络信息")
        v_net = QFormLayout(grp_net)
        v_net.addRow("当前绑定 IP:", QLabel(self.info.get('ip', 'Unknown')))
        v_net.addRow("主机名:", QLabel(self.bridge.core.hostname))
        layout.addWidget(grp_net)
        
        # 安全指纹
        grp_sec = QGroupBox("安全指纹 (X25519)")
        v_sec = QVBoxLayout(grp_sec)
        
        # 获取指纹 (如果 Core 支持)
        fp = "加载中..."
        if hasattr(self.bridge.core, 'identity_pub_bytes'):
            import hashlib
            raw = self.bridge.core.identity_pub_bytes
            if raw:
                fp = hashlib.sha256(raw).hexdigest()[:32] + "..."
        
        self.lbl_fp = QLabel(fp)
        self.lbl_fp.setStyleSheet("font-family: Consolas, Monospace; color: #555; background: #eee; padding: 4px;")
        self.lbl_fp.setWordWrap(True)
        v_sec.addWidget(self.lbl_fp)
        layout.addWidget(grp_sec)
        
        layout.addStretch()

    def _save_and_close(self):
        # 1. 收集数据
        new_name = self.inp_name.text().strip()
        status_map = ["online", "busy", "away"]
        new_status = status_map[self.cmb_status.currentIndex()]
        
        if not new_name:
            QMessageBox.warning(self, "错误", "昵称不能为空")
            return

        # 2. 调用 Bridge 更新 Core
        # 我们需要在 Bridge 里加一个 update_settings 方法，
        # 或者直接调用 core (如果在 bridge.py 里偷懒没写的话)
        # 这里我们假设直接操作 core 属性，虽然不完美但有效
        try:
            self.bridge.core.username = new_name
            self.bridge.core.status = new_status
            self.bridge.core._save_config() # 触发持久化
            
            # 广播状态变更
            self.bridge.core._broadcast_presence()
            
            # 刷新一下 GUI 显示 (如果需要)
            self.bridge.sig_log.emit("INFO", f"配置已更新: {new_name} ({new_status})")
            
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "保存失败", str(e))