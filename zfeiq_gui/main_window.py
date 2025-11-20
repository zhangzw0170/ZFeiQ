from PyQt5 import QtCore, QtGui, QtWidgets
from typing import Dict, Optional
import os
import datetime

from .pages import ChatPage, LoginPage, UserListPage, GroupsPage, SettingsPage
from .widgets import NavigationButton, ExpandableSection
from .lang import get_translations


## ChatPage 已重构至 pages/chat_page.py
## LoginPage 已重构至 pages/login_page.py


class MainWindow(QtWidgets.QMainWindow):
    mw_width = 800
    mw_height = 800

    def __init__(self):
        super().__init__()
        self.setWindowTitle("ZFeiQ")
        self.resize(self.mw_width, self.mw_height)
        self._build_ui()
        self._current_theme = "light"
        self._current_language = "zhCN"
        self._current_translations = {}

    def _build_ui(self) -> None:
        # 使用 QSplitter 允许用户调整侧边栏与聊天区域宽度
        self.content_panel = self._build_content_panel()
        self.nav_panel = self._build_nav_panel()
        
        splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        splitter.addWidget(self.nav_panel)
        splitter.addWidget(self.content_panel)
        splitter.setCollapsible(0, True)
        splitter.setCollapsible(1, False)
        
        # 设置最小宽度，避免拖得过小
        self.nav_panel.setMinimumWidth(150)  # 侧边栏最小宽度
        self.content_panel.setMinimumWidth(400)  # 内容区最小宽度
        
        # 正确设置初始比例：使用 setSizes 而不是 setStretchFactor
        total_width = self.mw_width
        left_width = total_width * 3 // 8   # 3/8 给侧边栏
        right_width = total_width * 5 // 8  # 5/8 给内容区
        splitter.setSizes([left_width, right_width])
        
        # 保留 splitter 为成员，避免后续切换页面时重建影响比例
        self._splitter = splitter
        self.setCentralWidget(self._splitter)
        
        # 未登录前隐藏侧边导航
        try:
            self.nav_panel.setVisible(False)
        except Exception:
            pass

    def _build_nav_panel(self) -> QtWidgets.QWidget:
        panel = QtWidgets.QWidget()
        panel.setObjectName("navPanel")
        # 不再固定宽度，交由 QSplitter 调整；设置一个合理的最小宽度
        outer = QtWidgets.QVBoxLayout(panel)
        outer.setContentsMargins(8, 8, 8, 8)
        outer.setSpacing(8)

        # 左侧采用 QTabWidget 模拟“子选项卡”切换 用户 / 组
        self.sidebar_tabs = QtWidgets.QTabWidget()
        # 去除侧边多余外边框（风格统一由主题控制）
        self.sidebar_tabs.setTabPosition(QtWidgets.QTabWidget.North)
        # 更紧凑的标签字体
        try:
            f = self.sidebar_tabs.font(); f.setPointSize(f.pointSize() - 1); self.sidebar_tabs.setFont(f)
        except Exception:
            pass
        self.sidebar_tabs.addTab(self._userlist_page, "用户")
        self.sidebar_tabs.addTab(self._groups_page, "组")
        outer.addWidget(self.sidebar_tabs, 1)
        outer.addStretch()

        # 设置按钮：若当前在设置页则返回聊天页，否则进入设置页
        self.btn_settings = NavigationButton("设置")
        def _toggle_settings():
            cur = self._stack.currentWidget()
            if cur is self._settings_page:
                self._stack.setCurrentWidget(self._chat_page)
            else:
                self._stack.setCurrentWidget(self._settings_page)
        self.btn_settings.clicked.connect(_toggle_settings)
        outer.addWidget(self.btn_settings)
        return panel

    def _build_content_panel(self) -> QtWidgets.QWidget:
        self._stack = QtWidgets.QStackedWidget()
        # 登录页（优先）
        self._login_page = LoginPage()
        self._stack.addWidget(self._login_page)
        # 聊天页（主区域保留）
        self._chat_page = ChatPage()
        self._stack.addWidget(self._chat_page)
        # 用户与组页实例用于侧边栏折叠显示（仍加入栈但无需按钮导航，便于复用现有刷新逻辑）
        self._userlist_page = UserListPage(); self._stack.addWidget(self._userlist_page)
        self._groups_page = GroupsPage(); self._stack.addWidget(self._groups_page)
        # 已移除独立表情与密钥页面（表情对话嵌入聊天；密钥集成到设置-个人）
        # 设置页
        self._settings_page = SettingsPage()
        self._stack.addWidget(self._settings_page)

        # 默认进入登录页
        self._stack.setCurrentWidget(self._login_page)
        return self._stack

    def bind_backend(self, backend):
        # backend: instance of GuiBackend
        try:
            backend.message_signal.connect(self._chat_page.append_message)
            backend.file_offer_signal.connect(lambda sender, name, size: self._chat_page.append_file_notice(sender, name))
            backend.start()
            # ---- 文件要约整合到聊天页 ----
            self._known_offers = set()
            def _refresh_offers():
                try:
                    offers = backend.list_incoming_offers() or {}
                except Exception:
                    offers = {}
                for oid, meta in offers.items():
                    if oid not in self._known_offers:
                        self._known_offers.add(oid)
                        self._chat_page.append_incoming_offer(
                            oid,
                            meta.get('uname') or meta.get('ip','?'),
                            meta.get('ip','?'),
                            meta.get('name','file'),
                            int(meta.get('size',0))
                        )
            _refresh_offers()
            try:
                backend.offers_updated.connect(_refresh_offers)
            except Exception:
                pass
            def _on_file_progress(oid: str, bytes_done: int):
                try:
                    meta = backend.list_incoming_offers().get(oid, {})
                except Exception:
                    meta = {}
                name = meta.get('name','file')
                total = int(meta.get('size',0))
                self._chat_page.append_offer_progress(oid, name, bytes_done, total)
            try:
                backend.file_progress.connect(_on_file_progress)
            except Exception:
                pass
            def _on_file_saved(oid: str, path: str):
                try:
                    meta = backend.list_incoming_offers().get(oid, {})
                except Exception:
                    meta = {}
                name = meta.get('name','file')
                self._chat_page.append_offer_saved(name, path)
                self._stack.setCurrentWidget(self._chat_page)
            try:
                backend.file_saved.connect(_on_file_saved)
            except Exception:
                pass
            def _on_anchor(href: str):
                try:
                    if href.startswith('accept:'):
                        oid = href.split(':',1)[1]
                        try:
                            dl_dir = getattr(getattr(backend,'zcli',None),'download_dir','')
                            if not dl_dir:
                                dl_dir = os.path.join(os.getcwd(), 'downloads')
                        except Exception:
                            dl_dir = os.path.join(os.getcwd(), 'downloads')
                        backend.accept_offer(oid, dl_dir)
                    elif href.startswith('cancel:'):
                        oid = href.split(':',1)[1]
                        backend.cancel_offer(oid)
                except Exception:
                    pass
            try:
                self._chat_page.sigAnchor.connect(_on_anchor)
            except Exception:
                pass
            # 初始同步设置页 UI 与后端配置
            try:
                z = getattr(backend, 'zcli', None)
                if z:
                    self._settings_page.cmb_lang.setCurrentText(getattr(z, 'language', 'zhCN'))
                    self._settings_page.cmb_status.setCurrentText(getattr(z, 'status', 'online'))
                    self._settings_page.cmb_enc.setCurrentText(getattr(z, 'encoding', 'utf-8'))
                    try:
                        dld = getattr(z, 'download_dir', '') or ''
                        if dld:
                            self._settings_page.edit_dir.setText(dld)
                    except Exception:
                        pass
                self._settings_page.cmb_theme.setCurrentText(backend.get_ui_theme())
                try:
                    ss = backend.get_screenshot_dir() or ''
                    if ss:
                        self._settings_page.edit_ss_dir.setText(ss)
                except Exception:
                    pass
                try:
                    av = backend.get_ui_avatar() if hasattr(backend, 'get_ui_avatar') else ''
                    if av:
                        self._settings_page.edit_avatar.setText(av)
                except Exception:
                    pass
            except Exception:
                pass
            # 聊天目标由子选项卡驱动
            def _find_node_by_ip(ip: str):
                for n in backend.get_nodes():
                    if getattr(n, 'ip', None) == ip:
                        return n
                return None

            def _tab_label_for_target(target_id: str) -> str:
                if not target_id:
                    return ""
                if target_id == "all":
                    return self._current_translations.get("all_tab", "全部")
                if target_id.startswith("ip:"):
                    ip = target_id[3:]
                    node = _find_node_by_ip(ip)
                    name = getattr(node, 'username', ip)
                    return f"{name}@{ip}"
                if target_id.startswith("group:"):
                    g = target_id[6:]
                    return f"群:{g}"
                return target_id

            def _display_for_target(target_id: str) -> str:
                if not target_id:
                    return ""
                if target_id == "all":
                    return self._current_translations.get("all_display", "所有在线")
                if target_id.startswith("ip:"):
                    ip = target_id[3:]
                    node = _find_node_by_ip(ip)
                    name = getattr(node, 'username', ip)
                    return f"{name}@{ip}"
                if target_id.startswith("group:"):
                    g = target_id[6:]
                    return f"群组:{g}"
                return target_id

            def _refresh_target_header(target_id: Optional[str]):
                try:
                    if not self.nav_panel.isVisible():
                        self.setWindowTitle("ZFeiQ")
                except Exception:
                    pass
                if not target_id:
                    self._chat_page.username_label.setText("聊天对象：未选择")
                    self._chat_page.ip_label.setText("IP：-.-.-.-")
                    self._chat_page.send_btn.setEnabled(False)
                    if getattr(self, 'nav_panel', None):
                        self.setWindowTitle("ZFeiQ")
                    return
                self._chat_page.send_btn.setEnabled(True)
                title = "ZFeiQ"
                if target_id.startswith("ip:"):
                    ip = target_id[3:]
                    node = _find_node_by_ip(ip)
                    name = getattr(node, 'username', ip)
                    self._chat_page.username_label.setText(name)
                    self._chat_page.ip_label.setText(f"IP：{ip}")
                    title = f"{name}[IP:{ip}] - ZFeiQ"
                elif target_id.startswith("group:"):
                    g = target_id[6:]
                    self._chat_page.username_label.setText(f"群组：{g}")
                    self._chat_page.ip_label.setText("")
                    title = f"群组:{g} - ZFeiQ"
                else:
                    self._chat_page.username_label.setText(target_id)
                    self._chat_page.ip_label.setText("")
                    title = f"{target_id} - ZFeiQ"
                self.setWindowTitle(title)

            def _on_tabs_changed(_: int):
                _refresh_target_header(self._chat_page.current_target_id())

            self._chat_page.tabs.currentChanged.connect(_on_tabs_changed)
            _refresh_target_header(self._chat_page.current_target_id())

            def _focus_target(target_id: str):
                if not target_id:
                    return
                self._chat_page.focus_chat_tab(target_id, _tab_label_for_target(target_id))
                _refresh_target_header(target_id)

            def on_send():
                target = self._chat_page.current_target_id()
                text = self._chat_page.outbox.toPlainText().strip()
                files = self._chat_page.get_pending_files()
                if not target:
                    if text or files:
                        t = self._current_translations or {}
                        QtWidgets.QMessageBox.information(
                            self,
                            t.get('no_target_warning_title', '未选择目标'),
                            t.get('no_target_warning_body', '请先在用户或组页面选择聊天对象。'),
                        )
                    return
                if not text and not files:
                    return
                tab_label = _tab_label_for_target(target)
                display = _display_for_target(target)
                try:
                    if text:
                        backend.send_text(target, text)
                        self._chat_page.append_outgoing(target, display, text, tab_label=tab_label)
                    for p in files:
                        try:
                            backend.send_file(target, p)
                            self._chat_page.append_file_sent(target, display, p, tab_label=tab_label)
                        except Exception:
                            pass
                    self._chat_page.outbox.clear()
                    self._chat_page.clear_pending_files()
                except Exception:
                    pass

            self._chat_page.send_btn.clicked.connect(on_send)
            try:
                self._chat_page.sigSend.connect(on_send)
            except Exception:
                pass

            # 监听输入框粘贴文件（类似微信）：若剪贴板中包含文件 URL，则直接按当前目标发送文件
            try:
                def _maybe_send_clipboard_files():
                    cb = QtWidgets.QApplication.clipboard()
                    md = cb.mimeData()
                    if not md or not md.hasUrls():
                        return False
                    paths = []
                    for url in md.urls():
                        p = url.toLocalFile()
                        if p:
                            paths.append(p)
                    if not paths:
                        return False
                    # 将粘贴的文件转为“待发送文件块”，不立即发送
                    for p in paths:
                        self._chat_page.add_pending_file(p)
                    return True

                # 在 outbox 的 keyRelease 上挂一个过滤器：检测 Ctrl+V 粘贴是否为文件
                # 使用独立 QObject 过滤器代替直接覆盖 eventFilter
                class _PasteFilter(QtCore.QObject):
                    def __init__(self, outer):
                        super().__init__(outer)
                        self.outer = outer
                    def eventFilter(self, a0, a1):
                        try:
                            if a0 is self.outer._chat_page.outbox and a1.type() == QtCore.QEvent.KeyRelease:
                                # 使用快捷键匹配方式：检查键与修饰键
                                get_key = getattr(a1, 'key', None)
                                k = get_key() if callable(get_key) else None
                                mods = int(QtWidgets.QApplication.keyboardModifiers())
                                if (k == QtCore.Qt.Key_V) and (mods & int(QtCore.Qt.ControlModifier)):
                                    if _maybe_send_clipboard_files():
                                        return True
                        except Exception:
                            pass
                        return False
                self._paste_filter = _PasteFilter(self)
                self._chat_page.outbox.installEventFilter(self._paste_filter)
            except Exception:
                pass

            # 聊天页“表情”对话在 ChatPage 内部实现；截图使用区域选择对话
            # 早期连接误用 _on_region_capture_send，这里移除并统一到类方法 on_region_capture_send（见后文绑定）

            def on_send_file():
                files, _ = QtWidgets.QFileDialog.getOpenFileNames(self, "选择要发送的文件")
                if not files:
                    return
                for p in files:
                    self._chat_page.add_pending_file(p)

            # 绑定 ChatPage 里预留的发送文件按钮
            try:
                self._chat_page.send_file_btn.clicked.connect(on_send_file)
            except Exception:
                pass
            # 编码自检移动至设置页：向本机 IP 发送一条包含中/英/Emoji 的测试文本
            def _enc_self_test():
                try:
                    ip = backend.get_net_info().get('local_ip','')
                    tgt = f"ip:{ip}" if ip else "all"
                    t = self._current_translations or {}
                    sample = t.get('encoding_selftest_sample', "编码自检：中文✓ English✓ Emoji😀 αßé")
                    backend.send_text(tgt, sample)
                    tab_label = _tab_label_for_target(tgt)
                    display = _display_for_target(tgt) or tgt
                    self._chat_page.append_outgoing(tgt, display, sample, tab_label=tab_label)
                    _focus_target(tgt)
                except Exception:
                    pass

            # LoginPage 登录处理：登录后显示导航并切回聊天页
            try:
                def _on_login_from_page(name: str, ip: str):
                    if not name:
                        return
                    # 先绑定选定 IP（如有），再登录与发现
                    try:
                        if ip:
                            backend.bind_ip(ip)
                    except Exception:
                        pass
                    backend.login(name)
                    backend.discover()
                    refresh_users_page()
                    # 显示左侧导航
                    try:
                        self.nav_panel.setVisible(True)
                        if hasattr(self, '_splitter') and self._splitter:
                            total = max(1, self.width())
                            left = max(200, int(total * 0.375))
                            self._splitter.setSizes([left, max(200, total - left)])
                    except Exception:
                        pass
                    # 在发送行显示当前登录用户信息
                    try:
                        local_ip = ip or getattr(backend, 'get_net_info', lambda: {}).__call__().get('local_ip','')
                        uname = getattr(getattr(backend, 'zcli', None), 'username', name)
                        status_raw = getattr(getattr(backend, 'zcli', None), 'status', 'online')
                        lang = getattr(getattr(backend, 'zcli', None), 'language', 'zhCN')
                        status_map = {
                            'zhCN': {'online':'在线','busy':'忙碌','away':'离开'},
                            'enUS': {'online':'online','busy':'busy','away':'away'},
                        }
                        status_disp = status_map.get(lang, status_map['zhCN']).get(status_raw, status_raw)
                        self._chat_page.set_local_ip(local_ip)
                        self._chat_page.set_user_status(uname, status_disp, status_raw)
                        # 设置页网卡 IP 下拉选中登录时选择的 IP
                        try:
                            if local_ip:
                                idx = self._settings_page.cmb_iface.findText(local_ip)
                                if idx >= 0:
                                    self._settings_page.cmb_iface.setCurrentIndex(idx)
                        except Exception:
                            pass
                    except Exception:
                        pass
                    # 切回聊天页
                    self._stack.setCurrentWidget(self._chat_page)
                self._login_page.sigLogin.connect(_on_login_from_page)
            except Exception:
                pass

            # discover 来自用户列表页的发现按钮
            try:
                self._userlist_page.sigDiscover.connect(lambda ip: (backend.discover(ip or None), refresh_users_page()))
            except Exception:
                pass

            # 历史查看（基于当前选中子选项卡）
            def on_show_history():
                target_raw = self._chat_page.current_target_id()
                if not target_raw:
                    t = self._current_translations or {}
                    QtWidgets.QMessageBox.information(
                        self,
                        t.get('no_target_warning_title', '未选择目标'),
                        t.get('history_no_target', t.get('no_target_warning_body', '请选择一个聊天对象后再查看历史。')),
                    )
                    return
                dlg = QtWidgets.QDialog(self)
                dlg.setWindowTitle("历史记录")
                v = QtWidgets.QVBoxLayout(dlg)
                text = QtWidgets.QTextEdit(); text.setReadOnly(True)
                v.addWidget(text)
                btn = QtWidgets.QPushButton("关闭"); btn.clicked.connect(dlg.accept)
                v.addWidget(btn)
                lines = []
                try:
                    if target_raw.startswith("user:"):
                        name = target_raw[5:]
                        items = backend.get_user_history(name)
                        for ts, d, t, ip in items:
                            arrow = ">>" if d == "out" else "<<"
                            lines.append(f"[{QtCore.QDateTime.fromSecsSinceEpoch(int(ts)).toString('yyyy-MM-dd hh:mm:ss')}] {arrow} {t}")
                    elif target_raw.startswith("group:"):
                        g = target_raw[6:]
                        items = backend.get_group_history(g)
                        for ts, d, t, uname, ip in items:
                            arrow = ">>" if d == "out" else "<<"
                            lines.append(f"[{QtCore.QDateTime.fromSecsSinceEpoch(int(ts)).toString('yyyy-MM-dd hh:mm:ss')}] {uname}@{ip} {arrow} {t}")
                    elif target_raw == "all":
                        # 聚合所有节点历史
                        for n in backend.get_nodes():
                            msgs = getattr(backend.zcli, 'history', {}).get(n.ip, [])
                            for ts, d, t in msgs:
                                arrow = ">>" if d == "out" else "<<"
                                lines.append(f"[{QtCore.QDateTime.fromSecsSinceEpoch(int(ts)).toString('yyyy-MM-dd hh:mm:ss')}] {n.username}@{n.ip} {arrow} {t}")
                    elif target_raw.startswith("ip:"):
                        ip = target_raw[3:]
                        msgs = getattr(backend.zcli, 'history', {}).get(ip, [])
                        # 找用户名
                        uname = ip
                        for n in backend.get_nodes():
                            if n.ip == ip:
                                uname = n.username; break
                        for ts, d, t in msgs:
                            arrow = ">>" if d == "out" else "<<"
                            lines.append(f"[{QtCore.QDateTime.fromSecsSinceEpoch(int(ts)).toString('yyyy-MM-dd hh:mm:ss')}] {uname}@{ip} {arrow} {t}")
                    else:
                        pass
                except Exception:
                    pass
                text.setPlainText("\n".join(lines) if lines else "(无记录)")
                dlg.resize(480, 360)
                dlg.exec_()

            self._chat_page.history_btn.clicked.connect(on_show_history)

            # 用户列表页交互
            def refresh_users_page():
                try:
                    info = backend.get_net_info()
                except Exception:
                    info = {}
                try:
                    self._userlist_page.set_net_info(info)
                except Exception:
                    pass
                try:
                    self._userlist_page.update_nodes(backend.get_nodes(), backend.list_groups(), info.get('local_ip',''))
                except Exception:
                    pass
                try:
                    mask = None
                    if hasattr(backend, 'get_subnet_mask'):
                        mask = backend.get_subnet_mask() or None
                    if not mask:
                        pre = info.get('iface_prefix','')
                        if isinstance(pre, str) and '/' in pre:
                            try:
                                bits = int(pre.split('/',1)[1])
                                if 0 <= bits <= 32:
                                    m = (0xffffffff << (32 - bits)) & 0xffffffff
                                    mask = '.'.join(str((m >> (8*i)) & 0xff) for i in [3,2,1,0])
                            except Exception:
                                pass
                    if mask:
                        self._settings_page.edit_mask.setText(mask)
                except Exception:
                    pass
                try:
                    ifaces = backend.get_local_ifaces()
                    self._settings_page.cmb_iface.blockSignals(True)
                    cur_iface = self._settings_page.cmb_iface.currentText()
                    self._settings_page.cmb_iface.clear()
                    for ip_addr, pre in ifaces:
                        self._settings_page.cmb_iface.addItem(f"{ip_addr}")
                    if cur_iface:
                        idx = self._settings_page.cmb_iface.findText(cur_iface)
                        if idx >= 0:
                            self._settings_page.cmb_iface.setCurrentIndex(idx)
                    self._settings_page.cmb_iface.blockSignals(False)
                except Exception:
                    pass
                try:
                    uname = getattr(getattr(backend, 'zcli', None), 'username', '')
                    local_ip = info.get('local_ip','')
                    status_raw = getattr(getattr(backend, 'zcli', None), 'status', 'online')
                    lang = getattr(getattr(backend, 'zcli', None), 'language', 'zhCN')
                    status_map = {
                        'zhCN': {'online':'在线','busy':'忙碌','away':'离开'},
                        'enUS': {'online':'online','busy':'busy','away':'away'},
                    }
                    status_disp = status_map.get(lang, status_map['zhCN']).get(status_raw, status_raw)
                    if uname:
                        self._chat_page.set_local_ip(local_ip)
                        self._chat_page.set_user_status(uname, status_disp, status_raw)
                        # 同步到设置页个人信息
                        try:
                            self._settings_page.update_personal_info(uname, local_ip)
                            try:
                                idx = self._settings_page.cmb_status.findData(status_raw)
                                if idx >= 0:
                                    self._settings_page.cmb_status.setCurrentIndex(idx)
                            except Exception:
                                pass
                        except Exception:
                            pass
                except Exception:
                    pass
                try:
                    ifaces = backend.get_local_ifaces()
                    self._login_page.ip_combo.blockSignals(True)
                    cur_ip = self._login_page.ip_combo.currentText()
                    self._login_page.ip_combo.clear()
                    for ip_addr, pre in ifaces:
                        self._login_page.ip_combo.addItem(f"{ip_addr}")
                    if cur_ip:
                        idx = self._login_page.ip_combo.findText(cur_ip)
                        if idx >= 0:
                            self._login_page.ip_combo.setCurrentIndex(idx)
                    self._login_page.ip_combo.blockSignals(False)
                except Exception:
                    pass

            refresh_users_page()
            timer2 = QtCore.QTimer(self)
            timer2.timeout.connect(refresh_users_page)
            timer2.start(3000)

            def on_pick_target(text: str):
                try:
                    if text:
                        _focus_target(text)
                        self._stack.setCurrentWidget(self._chat_page)
                except Exception:
                    pass

            self._userlist_page.targetPicked.connect(on_pick_target)


            # 组管理页绑定
            def refresh_groups_page():
                try:
                    self._groups_page.update_groups(backend.list_groups())
                except Exception:
                    pass

            refresh_groups_page()
            timer3 = QtCore.QTimer(self)
            timer3.timeout.connect(refresh_groups_page)
            timer3.start(3000)

            def on_group_add(group: str, user: str):
                if group and user:
                    backend.group_add(group, user)
                    refresh_groups_page()

            def on_group_remove(group: str, user: str):
                if group and user:
                    backend.group_remove(group, user)
                    refresh_groups_page()

            self._groups_page.sigAdd.connect(on_group_add)
            self._groups_page.sigRemove.connect(on_group_remove)
            def _enter_group_chat(g: str):
                if not g:
                    return
                try:
                    _focus_target(f"group:{g}")
                finally:
                    self._stack.setCurrentWidget(self._chat_page)
            self._groups_page.sigEnterChat.connect(_enter_group_chat)

            def _rename_group(old: str, new: str):
                if not old or not new or old == new:
                    return
                try:
                    groups = backend.list_groups() or {}
                    members = list(groups.get(old, []))
                    # 新建新组并迁移成员
                    for u in members:
                        try:
                            backend.group_add(new, u)
                        except Exception:
                            pass
                    # 删除旧组
                    try:
                        backend.group_remove(old, None)
                    except Exception:
                        pass
                    # 刷新分组页
                    refresh_groups_page()
                    # 刷新用户页/分组视图
                    refresh_users_page()
                    # 刷新用户页分组列表
                    if hasattr(self._userlist_page, "update_nodes"):
                        self._userlist_page.update_nodes(backend.get_nodes(), backend.list_groups(), backend.get_net_info().get('local_ip',''))
                except Exception:
                    pass
            self._groups_page.sigRename.connect(_rename_group)

            # 独立文件页已移除；文件要约逻辑已在 bind_backend 中整合到聊天页

            # 设置页绑定
            self._settings_page.sigApply.connect(lambda cfg: self._apply_settings(backend, cfg))
            try:
                self._settings_page.sigEncodingSelfTest.connect(_enc_self_test)
            except Exception:
                pass
            # 设置页登出
            try:
                self._settings_page.sigLogout.connect(lambda: self._on_logout_to_login(backend))
            except Exception:
                pass

            # 初始主题应用
            try:
                theme = backend.get_ui_theme()
                self._settings_page.cmb_theme.setCurrentText(theme)
                self._apply_theme(theme)
            except Exception:
                pass
            # 初始头像应用（若已配置）
            try:
                if hasattr(backend, 'get_ui_avatar'):
                    ap = backend.get_ui_avatar()
                    if ap:
                        self._chat_page.set_avatar(ap)
            except Exception:
                pass

            # 表情页与截图页发送绑定（按当前聊天目标发送）
            def _current_target():
                return self._chat_page.current_target_id()

            def _send_path(path: str):
                tgt = _current_target()
                if not tgt or not path:
                    return
                try:
                    backend.send_file(tgt, path)
                    # 在聊天区提示已发送文件/表情
                    me_label = (self._current_translations or {}).get('me_label', '我')
                    self._chat_page.append_file_notice(me_label, os.path.basename(path))
                    # 发送后切回聊天页
                    self._stack.setCurrentWidget(self._chat_page)
                except Exception:
                    pass

            # 已移除独立表情页面，发送逻辑通过聊天页弹出表情对话自定义表情后回调处理
            # 不使用单独截图页发送；事件改为类方法
            try:
                self._chat_page.screenshot_btn.clicked.connect(lambda: self.on_region_capture_send(backend))
            except Exception:
                pass
            # 常用语菜单
            try:
                self._chat_page.quicktext_btn.clicked.connect(self.on_quicktext_menu)
            except Exception:
                pass
            # 允许用户页/组页复用聊天标签逻辑
            try:
                self._userlist_page.set_focus_handler(_focus_target)
            except Exception:
                pass
            # 密钥管理页绑定
            try:
                try:
                    # 密钥设置已集成到设置-个人页的 key_section
                    try:
                        if hasattr(self._settings_page, 'key_section') and hasattr(self._settings_page.key_section, 'cmb_mode'):
                            self._settings_page.key_section.cmb_mode.setCurrentText(getattr(backend, 'get_encrypt_mode', lambda: 'off')())
                    except Exception:
                        pass
                except Exception:
                    pass
                def _refresh_fp():
                    try:
                        fp = getattr(backend, 'get_pubkey_fingerprint', lambda: '(n/a)')()
                        if hasattr(self._settings_page, 'key_section'):
                            self._settings_page.key_section.lbl_fp.setText(f"指纹：{fp}")
                    except Exception:
                        if hasattr(self._settings_page, 'key_section'):
                            self._settings_page.key_section.lbl_fp.setText("指纹：(error)")
                _refresh_fp()
                if hasattr(self._settings_page, 'key_section'):
                    self._settings_page.key_section.btn_refresh.clicked.connect(_refresh_fp)
                    self._settings_page.key_section.cmb_mode.currentTextChanged.connect(lambda v: (backend.set_encrypt_mode(v), backend.save_state()))
                def _on_regen():
                    ok = getattr(backend, 'regenerate_keys', lambda: False)()
                    _refresh_fp()
                    QtWidgets.QMessageBox.information(self, "密钥", "已重生成密钥" if ok else "重生成失败")
                if hasattr(self._settings_page, 'key_section'):
                    self._settings_page.key_section.btn_regen.clicked.connect(_on_regen)
                def _on_export():
                    path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "导出公钥", os.path.join(os.getcwd(), "keys", "pub_export.pem"), filter="PEM (*.pem)")
                    if not path:
                        return
                    res = getattr(backend, 'export_pubkey', lambda p: None)(path)
                    QtWidgets.QMessageBox.information(self, "导出公钥", f"已导出至:\n{res}" if res else "导出失败")
                if hasattr(self._settings_page, 'key_section'):
                    self._settings_page.key_section.btn_export.clicked.connect(_on_export)
            except Exception:
                pass
            # 独立表情页面已移除（占位 try 块避免缩进错误）
            try:
                pass
            except Exception:
                pass
        except Exception:
            pass

    def _on_logout_to_login(self, backend):
        try:
            backend.logout()
        except Exception:
            pass
        try:
            # 清空聊天页顶部与发送行显示
            self._chat_page.username_label.setText("用户名：未登录")
            self._chat_page.ip_label.setText("IP：-.-.-.-")
            self._chat_page.me_info_label.setText("")
            self.setWindowTitle("ZFeiQ")
            # 隐藏侧边导航并回到登录页
            self.nav_panel.setVisible(False)
            self._stack.setCurrentWidget(self._login_page)
        except Exception:
            pass

    def _apply_settings(self, backend, cfg: Dict):
        try:
            if "language" in cfg:
                backend.set_language(cfg["language"]) 
                self._apply_language(cfg["language"]) 
            if "status" in cfg:
                backend.set_status(cfg["status"]) 
            if "encoding" in cfg:
                backend.set_encoding(cfg["encoding"]) 
            if "ui_theme" in cfg:
                backend.set_ui_theme(cfg["ui_theme"]) 
                self._apply_theme(cfg["ui_theme"]) 
            if "debug" in cfg:
                backend.set_debug(bool(cfg["debug"]))
            if "trace" in cfg:
                backend.set_trace(bool(cfg["trace"]))
            if "keepalive" in cfg:
                backend.set_keepalive(float(cfg["keepalive"]))
            if "expire" in cfg:
                backend.set_expire(float(cfg["expire"]))
            if "bind_ip" in cfg and cfg["bind_ip"]:
                backend.bind_ip(cfg["bind_ip"]) 
            if "subnet_mask" in cfg and cfg["subnet_mask"]:
                try:
                    if hasattr(backend, 'set_subnet_mask'):
                        backend.set_subnet_mask(cfg["subnet_mask"])  # 后端支持时生效
                except Exception:
                    pass
            if "download_dir" in cfg and cfg["download_dir"]:
                backend.set_download_dir(cfg["download_dir"]) 
            if "screenshot_dir" in cfg and cfg["screenshot_dir"]:
                try:
                    backend.set_screenshot_dir(cfg["screenshot_dir"]) 
                except Exception:
                    pass
            if "ui_avatar" in cfg and cfg["ui_avatar"]:
                try:
                    backend.set_ui_avatar(cfg["ui_avatar"]) 
                    # 更新界面头像显示
                    try:
                        self._chat_page.set_avatar(cfg["ui_avatar"]) 
                    except Exception:
                        pass
                except Exception:
                    pass
            # persist after applying
            backend.save_state()
        except Exception:
            pass

    def _apply_theme(self, mode: str):
        app = QtWidgets.QApplication.instance()
        self._current_theme = mode if mode in ("light","dark") else "light"
        if self._current_theme == "dark":
            dark_qss = """
            QMainWindow, QWidget { background: #121212; color: #e0e0e0; }
                        QLineEdit, QTextEdit, QComboBox, QListWidget, QGroupBox, QSpinBox, QDoubleSpinBox {
                            background: #1e1e1e; color: #e0e0e0; border: 1px solid #2a2a2a; border-radius: 6px; padding: 6px; }
            QPushButton { background: #2d2d2d; color: #e0e0e0; border: 1px solid #3a3a3a; border-radius: 6px; padding: 6px; }
            QPushButton:hover { background: #3a3a3a; }
            QToolButton { color: #e0e0e0; border: none; padding: 6px; }
            QToolButton:hover { background: #2a2a2a; }
            #navPanel { background: #161616; }
            QProgressBar { background: #1e1e1e; color: #e0e0e0; border: 1px solid #2a2a2a; border-radius: 6px; text-align: center; }
            QProgressBar::chunk { background: #3f7cff; }
            QListWidget::item { background: #1a1a1a; }
                        QListWidget::item:hover { background: #242424; }
                        QListWidget::item:selected { background: #2f2f2f; color: #ffffff; }
            QComboBox QAbstractItemView { background: #1e1e1e; selection-background-color: #3a3a3a; }
            QGroupBox::title { subcontrol-origin: margin; left: 8px; padding: 0 4px; }
                        QTabWidget::pane { border-top: 1px solid #2a2a2a; }
                        QTabBar::tab { background: #1b1b1b; color: #bdbdbd; padding: 6px 10px; border: 1px solid #2a2a2a; border-bottom: none; border-top-left-radius: 6px; border-top-right-radius: 6px; }
                        QTabBar::tab:selected { background: #2a2a2a; color: #ffffff; }
                        QTabBar::tab:hover { background: #242424; }
                        QScrollBar:vertical { background: #1a1a1a; width: 10px; margin: 0; }
                        QScrollBar::handle:vertical { background: #3a3a3a; min-height: 20px; border-radius: 4px; }
                        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
                        QScrollBar:horizontal { background: #1a1a1a; height: 10px; margin: 0; }
                        QScrollBar::handle:horizontal { background: #3a3a3a; min-width: 20px; border-radius: 4px; }
                        QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }
                        QToolTip { background: #2a2a2a; color: #e0e0e0; border: 1px solid #3a3a3a; }
            """
            if isinstance(app, QtWidgets.QApplication):
                app.setStyleSheet(dark_qss)
        else:
            light_qss = """
            QMainWindow, QWidget { background: #ffffff; color: #222222; }
            QLineEdit, QTextEdit, QComboBox, QListWidget, QGroupBox, QSpinBox, QDoubleSpinBox {
                background: #fafafa; color: #222222; border: 1px solid #d0d0d0; border-radius: 6px; padding: 6px; }
            QPushButton { background: #f5f5f5; color: #222222; border: 1px solid #d0d0d0; border-radius: 6px; padding: 6px; }
            QPushButton:hover { background: #e0e0e0; }
            QToolButton { color: #222222; border: none; padding: 6px; }
            QToolButton:hover { background: #f0f0f0; }
            #navPanel { background: #f7f7f8; }
            QProgressBar { background: #fafafa; color: #222222; border: 1px solid #d0d0d0; border-radius: 6px; text-align: center; }
            QProgressBar::chunk { background: #3f7cff; }
            QListWidget::item { background: #f7f7f8; }
            QListWidget::item:hover { background: #e0e0e0; }
            QListWidget::item:selected { background: #e6e6e6; color: #222222; }
            QComboBox QAbstractItemView { background: #fafafa; selection-background-color: #e0e0e0; }
            QGroupBox::title { subcontrol-origin: margin; left: 8px; padding: 0 4px; }
            QTabWidget::pane { border-top: 1px solid #e6e6e6; }
            QTabBar::tab { background: #fafafa; color: #333333; padding: 6px 10px; border: 1px solid #e6e6e6; border-bottom: none; border-top-left-radius: 6px; border-top-right-radius: 6px; }
            QTabBar::tab:selected { background: #ffffff; color: #222222; }
            QTabBar::tab:hover { background: #e0e0e0; }
            QScrollBar:vertical { background: #f7f7f8; width: 10px; margin: 0; }
            QScrollBar::handle:vertical { background: #e0e0e0; min-height: 20px; border-radius: 4px; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
            QScrollBar:horizontal { background: #f7f7f8; height: 10px; margin: 0; }
            QScrollBar::handle:horizontal { background: #e0e0e0; min-width: 20px; border-radius: 4px; }
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }
            QToolTip { background: #e0e0e0; color: #222222; border: 1px solid #d0d0d0; }
            """
            if isinstance(app, QtWidgets.QApplication):
                app.setStyleSheet(light_qss)

    def _apply_language(self, lang: str):
        t = get_translations(lang)
        self._current_language = lang
        self._current_translations = t

        try:
            self.btn_settings.setText(t.get('settings', self.btn_settings.text()))
        except Exception:
            pass
        try:
            self.sidebar_tabs.setTabText(0, t.get('users_tab', t.get('users', '用户')))
            self.sidebar_tabs.setTabText(1, t.get('groups_tab', t.get('groups', '组')))
        except Exception:
            pass

        for page in (self._login_page, self._chat_page, self._userlist_page, self._groups_page, self._settings_page):
            try:
                if hasattr(page, 'apply_language'):
                    page.apply_language(t)
            except Exception:
                pass

        user_loc = {
            'status_prefix': t.get('status_prefix', '状态：'),
            'all_tab': t.get('all_tab', '全部'),
            'me_label': t.get('me_label', '我'),
            'file_sent_prefix': t.get('file_sent_prefix', '已发送文件: '),
        }
        try:
            self._chat_page.apply_localization(lang, user_loc)
        except Exception:
            pass
        try:
            self._userlist_page.search_edit.setPlaceholderText(t['search_ph'])
        except Exception:
            pass
        # 登录页占位符 & 组搜索占位符在对应页面内部处理

    # ---- class-level handlers ----
    def on_region_capture_send(self, backend):
        try:
            try:
                # 状态栏提示进入截图模式
                self.statusBar().showMessage("截图模式：拖拽选择区域，Esc 取消", 4000)
            except Exception:
                pass
            # 全屏遮罩选区
            sel = _RegionSelector(None)
            r = sel.exec_()
            if r is None or r.width() <= 0 or r.height() <= 0:
                return
            screen = QtWidgets.QApplication.primaryScreen()
            pm = None
            try:
                # 截取当前屏幕，再裁剪到选区
                geo = screen.geometry()
                # 使用 QApplication.desktop().winId() 获取根窗口 ID 进行整屏截图
                root_wid = QtWidgets.QApplication.desktop().winId()
                pm_full = screen.grabWindow(root_wid, geo.x(), geo.y(), geo.width(), geo.height())
                if pm_full and not pm_full.isNull():
                    pm = pm_full.copy(r)
            except Exception:
                pm = None
            if pm is None or pm.isNull():
                return

            # 在截图边缘绘制 5px 灰白色边框以强调区域
            painter = QtGui.QPainter(pm)
            pen = QtGui.QPen(QtGui.QColor(230, 230, 230))
            pen.setWidth(5)
            painter.setPen(pen)
            painter.drawRect(0, 0, pm.width()-1, pm.height()-1)
            painter.end()

            # 保存到截图目录
            try:
                base_dir = backend.get_screenshot_dir() or os.path.join(os.getcwd(), "screenshots")
            except Exception:
                base_dir = os.path.join(os.getcwd(), "screenshots")
            try:
                os.makedirs(base_dir, exist_ok=True)
            except Exception:
                pass
            ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"shot_{ts}.png"
            path = os.path.join(base_dir, filename)
            saved = False
            try:
                saved = pm.save(path, "PNG")
            except Exception:
                saved = False
            if saved:
                try:
                    self._chat_page.add_pending_file(path)
                except Exception:
                    pass

            # 写入剪贴板
            try:
                cb = QtWidgets.QApplication.clipboard()
                cb.setPixmap(pm)
            except Exception:
                pass

            # 状态栏提示
            try:
                extra = "，已加入待发送列表" if saved else ""
                self.statusBar().showMessage(f"截图已保存到 {path}，并复制到剪贴板{extra}", 5000)
            except Exception:
                pass
        except Exception:
            pass

    def on_quicktext_menu(self):
        try:
            # 从文件加载常用语（可选），否则使用默认
            defaults = [
                "在吗？", "收到。", "稍等一下～", "方便发个文件吗？", "辛苦了！", "谢谢！"
            ]
            items = []
            cfg_path = os.path.join(os.getcwd(), "quick_texts.txt")
            if os.path.isfile(cfg_path):
                try:
                    with open(cfg_path, "r", encoding="utf-8") as f:
                        items = [ln.strip() for ln in f.readlines() if ln.strip()]
                except Exception:
                    items = []
            if not items:
                items = defaults
            if not items:
                return
            m = QtWidgets.QMenu(self)
            acts = []
            for t in items:
                a = m.addAction(t)
                acts.append(a)
            pos = self._chat_page.quicktext_btn.mapToGlobal(self._chat_page.quicktext_btn.rect().bottomLeft())
            act = m.exec_(pos)
            if act and act.text():
                # 直接插入到输入框光标处
                self._chat_page.outbox.insertPlainText(act.text())
                self._chat_page.outbox.setFocus()
        except Exception:
            pass


class _RegionSelector(QtWidgets.QWidget):
    """Full-screen translucent overlay that lets users drag-select a region."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            QtCore.Qt.WindowStaysOnTopHint
            | QtCore.Qt.FramelessWindowHint
            | QtCore.Qt.Tool
        )
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        self._overlay_color = QtGui.QColor(0, 0, 0, 120)
        self._rubber = QtWidgets.QRubberBand(QtWidgets.QRubberBand.Rectangle, self)
        self._start = QtCore.QPoint()
        self._selected: Optional[QtCore.QRect] = None
        self._loop: Optional[QtCore.QEventLoop] = None

    def exec_(self) -> Optional[QtCore.QRect]:
        try:
            self.showFullScreen()
            self.raise_()
            self.activateWindow()
        except Exception:
            screen = QtWidgets.QApplication.primaryScreen()
            geo = screen.geometry() if screen else QtCore.QRect()
            if geo.isValid():
                self.setGeometry(geo)
            self.show()
        self._selected = None
        self._loop = QtCore.QEventLoop()
        self._loop.exec_()
        return self._selected

    def paintEvent(self, a0: QtGui.QPaintEvent) -> None:
        _ = a0
        painter = QtGui.QPainter(self)
        painter.fillRect(self.rect(), self._overlay_color)
        painter.end()

    def mousePressEvent(self, a0: QtGui.QMouseEvent) -> None:
        self._start = a0.pos()
        self._rubber.setGeometry(QtCore.QRect(self._start, QtCore.QSize()))
        self._rubber.show()

    def mouseMoveEvent(self, a0: QtGui.QMouseEvent) -> None:
        if not self._rubber.isVisible():
            return
        rect = QtCore.QRect(self._start, a0.pos()).normalized()
        self._rubber.setGeometry(rect)

    def mouseReleaseEvent(self, a0: QtGui.QMouseEvent) -> None:
        _ = a0
        if self._rubber.isVisible():
            self._selected = self._rubber.geometry()
            self._rubber.hide()
        if self._loop:
            self._loop.quit()
        self.close()

    def keyPressEvent(self, a0: QtGui.QKeyEvent) -> None:
        if a0.key() == QtCore.Qt.Key_Escape:
            if self._rubber.isVisible():
                self._rubber.hide()
            self._selected = QtCore.QRect()
            if self._loop:
                self._loop.quit()
            self.close()
            a0.accept()
            return
        super().keyPressEvent(a0)


