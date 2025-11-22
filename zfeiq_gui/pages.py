from PyQt5 import QtCore, QtGui, QtWidgets
from typing import Dict, Optional, List
import os
import shutil

from .widgets import NavigationButton


class LoginPage(QtWidgets.QWidget):
    sigLogin = QtCore.pyqtSignal(str, str)

    def __init__(self):
        super().__init__()
        self._build()

    def _build(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(60, 60, 60, 60)
        layout.setSpacing(12)
        top_row = QtWidgets.QHBoxLayout()
        top_row.addStretch()
        btn_help = QtWidgets.QPushButton("帮助")
        btn_help.setFixedHeight(btn_help.fontMetrics().height() + 10)
        top_row.addWidget(btn_help)
        layout.addLayout(top_row)
        lbl = QtWidgets.QLabel("欢迎使用 ZFeiQ，请先登录")
        lbl.setAlignment(QtCore.Qt.AlignCenter)
        font = lbl.font()
        font.setPointSize(14)
        lbl.setFont(font)
        self.name_edit = QtWidgets.QLineEdit()
        self.name_edit.setPlaceholderText("输入用户名…")
        ip_row = QtWidgets.QHBoxLayout()
        self.ip_combo = QtWidgets.QComboBox()
        self.ip_combo.setEditable(False)
        ip_row.addWidget(QtWidgets.QLabel("选择IP"))
        ip_row.addWidget(self.ip_combo, 1)
        self.login_btn = QtWidgets.QPushButton("登录")
        self.login_btn.setFixedHeight(self.login_btn.fontMetrics().height() + 12)
        layout.addStretch()
        layout.addWidget(lbl)
        layout.addWidget(self.name_edit)
        layout.addLayout(ip_row)
        layout.addWidget(self.login_btn)
        layout.addStretch()
        self.login_btn.clicked.connect(self._on_login)
        try:
            self.name_edit.returnPressed.connect(self._on_login)
        except Exception:
            pass

        def _show_help():
            QtWidgets.QMessageBox.information(
                self,
                "帮助",
                (
                    "1) 输入用户名并选择 IP\n"
                    "2) 登录后在用户/组页面选择聊天对象\n"
                    "3) 聊天：Enter 发送，Shift+Enter 换行；Ctrl+V 可粘贴文件加入待发送。\n"
                    "   表情：点击‘表情’打开对话框，含 Emoji 与自定义表情。\n"
                    "   截图：支持框选区域，按 ESC 取消。\n"
                    "4) 设置：语言/状态/编码/主题、下载与截图目录、头像；编码自检位于 设置-通用。\n"
                ),
            )

        btn_help.clicked.connect(_show_help)

    def _on_login(self):
        name = self.name_edit.text().strip()
        ip = self.ip_combo.currentText().strip()
        if name:
            self.sigLogin.emit(name, ip)


class UsersListPage(QtWidgets.QWidget):
    targetPicked = QtCore.pyqtSignal(str)
    sigDiscover = QtCore.pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self._build()
        self._all_items = []
        self._focus_chat = None
        self._info_templates = {
            "local": "本机：{local} / {prefix}",
            "broadcast": "广播：{bcast}",
            "mask": "掩码：{mask}",
            "nodes": "在线节点: {count}",
        }
        self._info_cache = {}

    def set_focus_handler(self, handler):
        self._focus_chat = handler

    def _build(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)
        search_row = QtWidgets.QHBoxLayout()
        self.search_edit = QtWidgets.QLineEdit()
        self.search_edit.setPlaceholderText("搜索用户名或IP…")
        self.search_edit.textChanged.connect(self._apply_filter)
        self.discover_btn = NavigationButton("发现")
        self.discover_btn.setToolTip("在指定 IP 或广播发现在线用户（留空则广播）")
        search_row.addWidget(self.search_edit, 1)
        search_row.addWidget(self.discover_btn)
        self.list = QtWidgets.QListWidget()
        self.list.itemDoubleClicked.connect(self._on_user_double_clicked)
        layout.addLayout(search_row)
        layout.addWidget(self.list, 1)
        info_box = QtWidgets.QVBoxLayout()
        info_box.setSpacing(6)
        self.lbl_local = QtWidgets.QLabel("本机：-")
        self.lbl_bcast = QtWidgets.QLabel("广播：-")
        row = QtWidgets.QHBoxLayout()
        self.disc_ip = QtWidgets.QLineEdit()
        self.disc_ip.setPlaceholderText("ip: 例如 192.168.1.10，可留空广播")
        btn_disc = NavigationButton("发现")
        row.addWidget(self.disc_ip, 1)
        row.addWidget(btn_disc)
        self.lbl_mask = QtWidgets.QLabel("掩码：-")
        self.lbl_count = QtWidgets.QLabel("在线节点: 0")
        info_box.addWidget(self.lbl_local)
        info_box.addWidget(self.lbl_bcast)
        info_box.addLayout(row)
        info_box.addWidget(self.lbl_mask)
        info_box.addWidget(self.lbl_count)
        layout.addLayout(info_box)
        self.discover_btn.clicked.connect(lambda: self.sigDiscover.emit(self.search_edit.text().strip()))
        btn_disc.clicked.connect(lambda: self.sigDiscover.emit(self.disc_ip.text().strip()))

    def _on_user_double_clicked(self, item: QtWidgets.QListWidgetItem):
        meta = item.data(QtCore.Qt.UserRole)
        if not meta:
            return
        kind, obj = meta
        if kind == "user":
            target = f"ip:{obj.ip}"
        elif kind == "group":
            target = f"group:{obj}"
        else:
            return
        if callable(self._focus_chat):
            self._focus_chat(target)
        else:
            self.targetPicked.emit(target)

    def update_nodes(self, nodes, groups=None, local_ip: str = ""):
        self.list.clear()
        items = []
        for n in nodes:
            host = getattr(n, "hostname", "")
            local_tag = "[LOCAL] " if local_ip and getattr(n, "ip", None) == local_ip else ""
            st = f" [{n.status}]" if getattr(n, "status", "online") != "online" else ""
            items.append((f"{local_tag}{n.username} @ {n.ip} ({host}){st}", ("user", n)))
        if groups:
            for g, members in sorted(groups.items()):
                items.append((f"[组] {g} ({len(members)})", ("group", g)))
        self._all_items = [t for t, _ in items]
        for text, meta in items:
            it = QtWidgets.QListWidgetItem(text)
            it.setData(QtCore.Qt.UserRole, meta)
            try:
                f = it.font()
                f.setPointSize(f.pointSize() + 1)
                it.setFont(f)
            except Exception:
                pass
            self.list.addItem(it)
        self._apply_filter()
        try:
            self.lbl_count.setText(self._info_templates.get("nodes", "在线节点: {count}").format(count=len(nodes)))
        except Exception:
            pass

    def set_net_info(self, info: Dict) -> None:
        self._info_cache = dict(info or {})
        local_ip = info.get("local_ip", "-")
        prefix = info.get("iface_prefix", "-")
        self.lbl_local.setText(self._info_templates.get("local", "本机：{local} / {prefix}").format(local=local_ip, prefix=prefix))
        self.lbl_bcast.setText(self._info_templates.get("broadcast", "广播：{bcast}").format(bcast=info.get("broadcast", "-")))
        mask = info.get("subnet_mask")
        if not mask:
            pre = info.get("iface_prefix", "")
            if isinstance(pre, str) and "/" in pre:
                try:
                    bits = int(pre.split("/", 1)[1])
                    if 0 <= bits <= 32:
                        m = (0xFFFFFFFF << (32 - bits)) & 0xFFFFFFFF
                        mask = ".".join(str((m >> (8 * i)) & 0xFF) for i in [3, 2, 1, 0])
                except Exception:
                    mask = None
        self.lbl_mask.setText(self._info_templates.get("mask", "掩码：{mask}").format(mask=mask or "-"))

    def _apply_filter(self):
        q = self.search_edit.text().strip().lower()
        for i in range(self.list.count()):
            it = self.list.item(i)
            if it is None:
                continue
            txt = it.text() if hasattr(it, "text") else ""
            visible = (q in txt.lower()) if q else True
            if hasattr(it, "setHidden"):
                it.setHidden(!visible)

    def apply_language(self, t: Dict[str, str]) -> None:
        try:
            self.search_edit.setPlaceholderText(t['search_ph'])
            self.disc_ip.setPlaceholderText(t['discover_ph'])
            self.discover_btn.setText(t['discover'])
            self._info_templates.update(
                {
                    "local": t['local_label'],
                    "broadcast": t['broadcast_label'],
                    "mask": t['mask_label'],
                    "nodes": t['nodes_label'],
                }
            )
            self.set_net_info(self._info_cache)
        except Exception:
            pass


class GroupsPage(QtWidgets.QWidget):
    sigAdd = QtCore.pyqtSignal(str, str)
    sigRemove = QtCore.pyqtSignal(str, str)
    sigEnterChat = QtCore.pyqtSignal(str)
    sigRename = QtCore.pyqtSignal(str, str)

    def __init__(self):
        super().__init__()
        self._cached_groups = {}
        self._build()

    def _build(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)
        top_row = QtWidgets.QHBoxLayout()
        self.member_filter = QtWidgets.QLineEdit()
        self.member_filter.setPlaceholderText("搜索组名/成员…")

        def _mk_nav_btn(text: str) -> NavigationButton:
            btn = NavigationButton(text)
            btn.setSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Fixed)
            return btn

        self.btn_new_group = _mk_nav_btn("新建分组")
        self.btn_rename = _mk_nav_btn("重命名")
        top_row.addWidget(self.member_filter, 1)
        top_row.addWidget(self.btn_new_group)
        top_row.addWidget(self.btn_rename)
        layout.addLayout(top_row)
        self.group_cards = QtWidgets.QListWidget()
        self.group_cards.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.group_cards.setVerticalScrollMode(QtWidgets.QAbstractItemView.ScrollPerPixel)
        layout.addWidget(self.group_cards, 3)
        bottom = QtWidgets.QVBoxLayout()
        bottom.setSpacing(6)
        self.members_list = QtWidgets.QListWidget()
        self.members_list.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        bottom.addWidget(self.members_list, 2)
        self.member_edit = QtWidgets.QLineEdit()
        self.member_edit.setPlaceholderText("添加/移除成员…")
        bottom.addWidget(self.member_edit)
        ctrl = QtWidgets.QHBoxLayout()
        btn_add = NavigationButton("+")
        btn_del = NavigationButton("-")
        self.btn_enter_chat = NavigationButton("=>")
        ctrl.addStretch(1)
        ctrl.addWidget(btn_add)
        ctrl.addWidget(btn_del)
        ctrl.addWidget(self.btn_enter_chat)
        bottom.addLayout(ctrl)
        layout.addLayout(bottom, 2)
        try:
            self.group_cards.itemDoubleClicked.connect(lambda it: self.sigEnterChat.emit(it.data(QtCore.Qt.UserRole)))
        except Exception:
            pass
        try:
            self.btn_enter_chat.clicked.connect(lambda: (self.sigEnterChat.emit(self._current_group() or "")))
        except Exception:
            pass

        def _create_group():
            base = "New Group "
            n = 1
            names = set((self._cached_groups or {}).keys())
            while f"{base}{n}" in names:
                n += 1
            g = f"{base}{n}"
            self._cached_groups = self._cached_groups or {}
            self._cached_groups[g] = set()
            self.update_groups(self._cached_groups)
            try:
                for i in range(self.group_cards.count()):
                    it = self.group_cards.item(i)
                    if it and it.data(QtCore.Qt.UserRole) == g:
                        self.group_cards.setCurrentRow(i)
                        break
            except Exception:
                pass

        self.btn_new_group.clicked.connect(_create_group)

    def apply_language(self, t: Dict[str, str]) -> None:
        try:
            self.member_filter.setPlaceholderText(t['group_search_ph'])
            self.member_edit.setPlaceholderText(t['member_ph'])
            self.btn_new_group.setText(t['group_new'])
            self.btn_rename.setText(t['group_rename'])
        except Exception:
            pass

        def _rename_group():
            old = self._current_group()
            if not old:
                return
            new, ok = QtWidgets.QInputDialog.getText(self, "重命名分组", "新名称：", text=old)
            new = (new or "").strip()
            if ok and new and new != old:
                self.sigRename.emit(old, new)

        self.btn_rename.clicked.connect(_rename_group)

    def update_groups(self, groups: dict):
        local = getattr(self, "_cached_groups", {}) or {}
        merged = dict(local)
        for g, m in (groups or {}).items():
            merged[g] = set(m)
        self._cached_groups = merged
        current = self._current_group()
        self.group_cards.blockSignals(True)
        self.group_cards.clear()
        for g in sorted(self._cached_groups.keys()):
            members = list(self._cached_groups.get(g, []))
            online = len(members)
            header = f"{g} ({online}/{len(members)})"
            lines = [header]
            for idx, u in enumerate(members):
                prefix = "┣" if idx < len(members) - 1 else "┗"
                lines.append(f"{prefix} {u}")
            text = "\n".join(lines)
            it = QtWidgets.QListWidgetItem(text)
            it.setData(QtCore.Qt.UserRole, g)
            it.setTextAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
            try:
                f = it.font()
                f.setPointSize(f.pointSize() + 1)
                it.setFont(f)
            except Exception:
                pass
            self.group_cards.addItem(it)
        if current:
            for i in range(self.group_cards.count()):
                it = self.group_cards.item(i)
                if it and it.data(QtCore.Qt.UserRole) == current:
                    self.group_cards.setCurrentRow(i)
                    break
        self.group_cards.blockSignals(False)
        self._update_members()

    def _update_members(self):
        g = self._current_group()
        members = sorted(list(self._cached_groups.get(g, []))) if g else []
        self.members_list.clear()
        for u in members:
            it = QtWidgets.QListWidgetItem(u)
            try:
                f = it.font()
                f.setPointSize(f.pointSize() + 1)
                it.setFont(f)
            except Exception:
                pass
            self.members_list.addItem(it)

    def _current_group(self) -> str:
        it = self.group_cards.currentItem()
        if it:
            return it.data(QtCore.Qt.UserRole)
        return ""


class FilesPage(QtWidgets.QWidget):
    sigAccept = QtCore.pyqtSignal(str, str)
    sigCancel = QtCore.pyqtSignal(str)
    sigPickDir = QtCore.pyqtSignal()
    sigApplyDir = QtCore.pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self._build()
        self._offers = {}
        self._save_dir = ""
        self._prog_bars = {}

    def _build(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)
        dir_row = QtWidgets.QHBoxLayout()
        self.dir_edit = QtWidgets.QLineEdit()
        btn_pick = QtWidgets.QPushButton("选择保存目录")
        btn_apply = QtWidgets.QPushButton("设为默认")
        for b in (btn_pick, btn_apply):
            b.setFixedHeight(b.fontMetrics().height() + 12)
        dir_row.addWidget(self.dir_edit, 1)
        dir_row.addWidget(btn_pick)
        dir_row.addWidget(btn_apply)
        layout.addLayout(dir_row)
        self.list = QtWidgets.QListWidget()
        layout.addWidget(self.list, 1)
        ctrl = QtWidgets.QHBoxLayout()
        self.btn_accept = QtWidgets.QPushButton("接收")
        self.btn_cancel = QtWidgets.QPushButton("放弃")
        for b in (self.btn_accept, self.btn_cancel):
            b.setFixedHeight(b.fontMetrics().height() + 12)
        ctrl.addWidget(self.btn_accept)
        ctrl.addWidget(self.btn_cancel)
        ctrl.addStretch()
        layout.addLayout(ctrl)
        btn_pick.clicked.connect(lambda: self.sigPickDir.emit())
        btn_apply.clicked.connect(lambda: self.sigApplyDir.emit(self.dir_edit.text().strip()))
        self.btn_accept.clicked.connect(self._on_accept)
        self.btn_cancel.clicked.connect(self._on_cancel)

    def pick_dir(self):
        d = QtWidgets.QFileDialog.getExistingDirectory(self, "选择保存目录")
        if d:
            self.dir_edit.setText(d)

    def update_offers(self, offers: Dict[str, dict]):
        self._offers = offers or {}
        self.list.clear()
        self._prog_bars.clear()
        for oid, m in self._offers.items():
            name = m.get("name", "file")
            size = int(m.get("size", 0))
            src = f"{m.get('ip','?')}:{m.get('port','-')}" if m.get("method") != "ipmsg" else f"{m.get('ip','?')}:2425/ipmsg"
            uname = m.get("uname") or m.get("ip", "?")
            ts_val = m.get("ts")
            ts_txt = QtCore.QDateTime.fromSecsSinceEpoch(int(ts_val)).toString("yyyy-MM-dd hh:mm:ss") if ts_val else "--"
            ext = os.path.splitext(name)[1]
            display = (
                f"{uname}[IP:{m.get('ip','?')}] {name}{'' if ext else ''} {ts_txt} | {size} bytes | {src}"
                if uname
                else f"{oid} | {name} | {size} bytes | from {src}"
            )
            it = QtWidgets.QListWidgetItem()
            it.setData(QtCore.Qt.UserRole, oid)
            w = QtWidgets.QWidget()
            hl = QtWidgets.QHBoxLayout(w)
            hl.setContentsMargins(6, 2, 6, 2)
            hl.setSpacing(8)
            lbl = QtWidgets.QLabel(display)
            bar = QtWidgets.QProgressBar()
            bar.setMinimum(0)
            if size > 0:
                bar.setMaximum(size)
            else:
                bar.setMaximum(0)
            bar.setTextVisible(True)
            hl.addWidget(lbl, 1)
            hl.addWidget(bar, 1)
            self.list.addItem(it)
            self.list.setItemWidget(it, w)
            self._prog_bars[oid] = bar

    def _on_accept(self):
        it = self.list.currentItem()
        if not it:
            return
        oid = it.data(QtCore.Qt.UserRole)
        self.sigAccept.emit(oid, self.dir_edit.text().strip())

    def _on_cancel(self):
        it = self.list.currentItem()
        if not it:
            return
        oid = it.data(QtCore.Qt.UserRole)
        self.sigCancel.emit(oid)

    def update_progress(self, oid: str, total: int):
        bar = self._prog_bars.get(oid)
        if not bar:
            return
        m = self._offers.get(oid) or {}
        size = int(m.get("size", 0)) if m else 0
        if size > 0:
            if bar.maximum() != size:
                bar.setMaximum(size)
            bar.setValue(max(0, min(total, size)))
            pct = (total * 100 // size) if size else 0
            bar.setFormat(f"{pct}% ({total}/{size})")
        else:
            bar.setMaximum(0)
            bar.setFormat(f"{oid}: {total} bytes")

    def on_saved(self, oid: str, path: str):
        QtWidgets.QMessageBox.information(self, "保存完成", f"要约 {oid} 已保存至:\n{path}")


class InfoPage(QtWidgets.QWidget):
    sigDiscover = QtCore.pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self._build()

    def _build(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)
        self.lbl_local = QtWidgets.QLabel("本机：-")
        self.lbl_bcast = QtWidgets.QLabel("广播：-")
        self.lbl_mask = QtWidgets.QLabel("掩码：-")
        row = QtWidgets.QHBoxLayout()
        self.disc_ip = QtWidgets.QLineEdit()
        self.disc_ip.setPlaceholderText("ip: 例如 192.168.1.10，可留空广播")
        btn_disc = QtWidgets.QPushButton("发现")
        btn_disc.setFixedHeight(btn_disc.fontMetrics().height() + 12)
        row.addWidget(self.disc_ip, 1)
        row.addWidget(btn_disc)
        self.nodes = QtWidgets.QListWidget()
        self.lbl_count = QtWidgets.QLabel("在线节点: 0")
        layout.addWidget(self.lbl_local)
        layout.addWidget(self.lbl_bcast)
        layout.addLayout(row)
        layout.addWidget(self.lbl_mask)
        layout.addWidget(self.lbl_count)
        layout.addWidget(self.nodes, 1)
       btn_disc.clicked.connect(lambda: self.sigDiscover.emit(self.disc_ip.text().strip()))

    def set_net_info(self, info: Dict):
        self.lbl_local.setText(f"本机：{info.get('local_ip','-')} / {info.get('iface_prefix','-')}")
        self.lbl_bcast.setText(f"广播：{info.get('broadcast','-')}")
        mask = info.get("subnet_mask")
        if not mask:
            pre = info.get("iface_prefix", "")
            if isinstance(pre, str) and "/" in pre:
                try:
                    bits = int(pre.split("/", 1)[1])
                    if 0 <= bits <= 32:
                        m = (0xFFFFFFFF << (32 - bits)) & 0xFFFFFFFF
                        mask = ".".join(str((m >> (8 * i)) & 0xFF) for i in [3, 2, 1, 0])
                except Exception:
                    mask = None
        self.lbl_mask.setText(f"掩码：{mask or '-'}")

    def update_nodes(self, nodes):
        self.nodes.clear()
        for n in nodes:
            st = f" [{n.status}]" if getattr(n, "status", "online") != "online" else ""
            self.nodes.addItem(f"{n.username}@{n.ip} ({n.hostname}){st}")
        try:
            self.lbl_count.setText(f"在线节点: {len(nodes)}")
        except Exception:
            pass

