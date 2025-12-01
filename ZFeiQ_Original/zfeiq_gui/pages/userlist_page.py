from __future__ import annotations

from typing import Dict, List, Tuple

from PyQt5 import QtCore, QtWidgets

from ..widgets import NavigationButton


class UserListPage(QtWidgets.QWidget):
    """Sidebar listing peers with quick filtering and discover-by-IP."""

    targetPicked = QtCore.pyqtSignal(str)
    sigDiscover = QtCore.pyqtSignal(str)

    def __init__(self, lang: str = "zhCN"):
        super().__init__()
        from zfeiq_gui.lang import get_translations
        self._translations = get_translations(lang)
        self._info_cache: Dict = {}
        self._info_templates: Dict[str, str] = {
            "local": self._translations.get("local_label", "本机：{local} / {prefix}"),
            "broadcast": self._translations.get("broadcast_label", "广播：{bcast}"),
            "mask": self._translations.get("mask_label", "掩码：{mask}"),
            "nodes": self._translations.get("nodes_label", "在线节点: {count}"),
        }
        self._focus_chat = None
        self._build()

    def set_focus_handler(self, handler) -> None:
        self._focus_chat = handler

    def _build(self) -> None:
        t = self._translations
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        search_row = QtWidgets.QHBoxLayout()
        self.search_edit = QtWidgets.QLineEdit()
        self.search_edit.setPlaceholderText(t.get("search_ph", "搜索 用户/组/IP"))
        self.search_edit.textChanged.connect(self._apply_filter)
        search_row.addWidget(self.search_edit, 1)

        self.list = QtWidgets.QListWidget()
        self.list.itemDoubleClicked.connect(self._on_user_double_clicked)

        layout.addLayout(search_row)
        layout.addWidget(self.list, 1)

        info_box = QtWidgets.QVBoxLayout()
        info_box.setSpacing(6)
        self.lbl_local = QtWidgets.QLabel(self._info_templates["local"].format(local="-", prefix="-"))
        self.lbl_bcast = QtWidgets.QLabel(self._info_templates["broadcast"].format(bcast="-"))
        row = QtWidgets.QHBoxLayout()
        self.disc_ip = QtWidgets.QLineEdit()
        self.disc_ip.setPlaceholderText(t.get("discover_ph", "指定 IP 发现"))
        self.btn_discover_ip = NavigationButton(t.get("discover", "发现"))
        row.addWidget(self.disc_ip, 1)
        row.addWidget(self.btn_discover_ip)
        self.lbl_mask = QtWidgets.QLabel(self._info_templates["mask"].format(mask="-"))
        self.lbl_count = QtWidgets.QLabel(self._info_templates["nodes"].format(count=0))
        info_box.addWidget(self.lbl_local)
        info_box.addWidget(self.lbl_bcast)
        info_box.addLayout(row)
        info_box.addWidget(self.lbl_mask)
        info_box.addWidget(self.lbl_count)
        layout.addLayout(info_box)

        self.btn_discover_ip.clicked.connect(lambda: self.sigDiscover.emit(self.disc_ip.text().strip()))

    def _on_user_double_clicked(self, item: QtWidgets.QListWidgetItem) -> None:
        meta = item.data(QtCore.Qt.UserRole)
        if not meta:
            return
        kind, obj = meta
        if kind == "user":
            target = f"ip:{getattr(obj, 'ip', '')}"
        elif kind == "group":
            target = f"group:{obj}"
        else:
            return
        if callable(self._focus_chat):
            self._focus_chat(target)
        else:
            self.targetPicked.emit(target)

    def update_nodes(self, nodes, groups=None, local_ip: str = "") -> None:
        self.list.clear()
        items: List[Tuple[str, Tuple[str, object]]] = []
        status_emojis = {"online": "🟢", "busy": "🟠", "away": "⚪"}
        for node in nodes:
            host = getattr(node, "hostname", "")
            ip = getattr(node, "ip", "")
            status_code = getattr(node, "status", "online")
            light = status_emojis.get(status_code, "🟢")
            is_local = bool(local_ip and ip == local_ip)
            if is_local:
                text_block = f"{light} [LOCAL] {node.username} @ {ip}"
            else:
                line1 = f"{light} {node.username}"
                line2 = f"@ {ip}"
                line3 = f"[{host}]" if host else ""
                text_block = f"{line1}\n{line2}" + (f"\n{line3}" if line3 else "")
            items.append((text_block, ("user", node)))
        if groups:
            for group_name, members in sorted(groups.items()):
                items.append((f"[组] {group_name} ({len(members)})", ("group", group_name)))

        for text, meta in items:
            item = QtWidgets.QListWidgetItem(text)
            item.setData(QtCore.Qt.UserRole, meta)
            item.setData(QtCore.Qt.UserRole + 1, text.lower())  # 用于过滤
            try:
                font = item.font()
                font.setPointSize(max(8, font.pointSize()))
                item.setFont(font)
            except Exception:
                pass
            self.list.addItem(item)
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
            prefix_value = info.get("iface_prefix", "")
            if isinstance(prefix_value, str) and "/" in prefix_value:
                try:
                    bits = int(prefix_value.split("/", 1)[1])
                    if 0 <= bits <= 32:
                        mask_int = (0xFFFFFFFF << (32 - bits)) & 0xFFFFFFFF
                        mask = ".".join(str((mask_int >> (8 * i)) & 0xFF) for i in [3, 2, 1, 0])
                except Exception:
                    mask = None
        self.lbl_mask.setText(self._info_templates.get("mask", "掩码：{mask}").format(mask=mask or "-"))

    def _apply_filter(self) -> None:
        query = (self.search_edit.text() or "").strip().lower()
        for i in range(self.list.count()):
            item = self.list.item(i)
            key = item.data(QtCore.Qt.UserRole + 1) or ""
            item.setHidden(bool(query and query not in key))
