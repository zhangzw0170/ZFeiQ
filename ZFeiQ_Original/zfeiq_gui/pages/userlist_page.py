from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from PyQt5 import QtCore, QtWidgets

from ..widgets import NavigationButton


class UserListPage(QtWidgets.QWidget):
    """Sidebar view that lists discovered peers and allows quick target selection."""

    targetPicked = QtCore.pyqtSignal(str)
    sigDiscover = QtCore.pyqtSignal(str)

    def __init__(self, lang: str = "zhCN"):
        super().__init__()
        from zfeiq_gui.lang import get_translations
        self._translations = get_translations(lang)
        self._build()
        self._all_items: List[str] = []
        self._focus_chat = None
        t = self._translations
        self._info_templates = {
            "local": t["local_label"],
            "broadcast": t["broadcast_label"],
            "mask": t["mask_label"],
            "nodes": t["nodes_label"],
        }
        self._info_cache: Dict = {}

    def set_focus_handler(self, handler) -> None:
        self._focus_chat = handler

    def _build(self) -> None:
        t = self._translations
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)

        search_row = QtWidgets.QHBoxLayout()
        self.search_edit = QtWidgets.QLineEdit()
        self.search_edit.setPlaceholderText(t["search_ph"])
        self.search_edit.textChanged.connect(self._apply_filter)
        self.discover_btn = NavigationButton(t["discover"])
        self.discover_btn.setToolTip(t['discover_tip'])
        search_row.addWidget(self.search_edit, 1)
        search_row.addWidget(self.discover_btn)

        self.list = QtWidgets.QListWidget()
        self.list.itemDoubleClicked.connect(self._on_user_double_clicked)

        layout.addLayout(search_row)
        layout.addWidget(self.list, 1)

        info_box = QtWidgets.QVBoxLayout()
        info_box.setSpacing(6)
        self.lbl_local = QtWidgets.QLabel(t["local_label"].format(local="-", prefix="-"))
        self.lbl_bcast = QtWidgets.QLabel(t["broadcast_label"].format(bcast="-"))
        row = QtWidgets.QHBoxLayout()
        self.disc_ip = QtWidgets.QLineEdit()
        self.disc_ip.setPlaceholderText(t["discover_ph"])
        self.btn_discover_ip = NavigationButton(t["discover"])
        row.addWidget(self.disc_ip, 1)
        row.addWidget(self.btn_discover_ip)
        self.lbl_mask = QtWidgets.QLabel(t["mask_label"].format(mask="-"))
        self.lbl_count = QtWidgets.QLabel(t["nodes_label"].format(count=0))
        info_box.addWidget(self.lbl_local)
        info_box.addWidget(self.lbl_bcast)
        info_box.addLayout(row)
        info_box.addWidget(self.lbl_mask)
        info_box.addWidget(self.lbl_count)
        layout.addLayout(info_box)

        self.discover_btn.clicked.connect(lambda: self.sigDiscover.emit(self.search_edit.text().strip()))
        self.btn_discover_ip.clicked.connect(lambda: self.sigDiscover.emit(self.disc_ip.text().strip()))

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

    def update_nodes(self, nodes, groups=None, local_ip: str = "") -> None:
        self.list.clear()
        items: List[Tuple[str, Tuple[str, object]]] = []
        for node in nodes:
            host = getattr(node, "hostname", "")
            local_tag = "[LOCAL] " if local_ip and getattr(node, "ip", None) == local_ip else ""
            status_suffix = f" [{node.status}]" if getattr(node, "status", "online") != "online" else ""
            items.append((f"{local_tag}{node.username} @ {node.ip} ({host}){status_suffix}", ("user", node)))
        if groups:
            for group_name, members in sorted(groups.items()):
                items.append((f"[组] {group_name} ({len(members)})", ("group", group_name)))
        self._all_items = [text for text, _ in items]
        for text, meta in items:
            item = QtWidgets.QListWidgetItem(text)
            item.setData(QtCore.Qt.UserRole, meta)
            try:
                font = item.font()
                font.setPointSize(font.pointSize() + 1)
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
        query = self.search_edit.text().strip().lower()
        for i in range(self.list.count()):
            item = self.list.item(i)
            if item is None:
                continue
            text = item.text() if hasattr(item, "text") else ""
            visible = (query in text.lower()) if query else True
            if hasattr(item, "setHidden"):
                item.setHidden(not visible)

    def apply_language(self, translations: Dict[str, str]) -> None:
        self._translations = translations
        try:
            self.search_edit.setPlaceholderText(translations.get("search_ph", self.search_edit.placeholderText()))
            self.disc_ip.setPlaceholderText(translations.get("discover_ph", self.disc_ip.placeholderText()))
            text_discover = translations.get("discover", "发现")
            self.discover_btn.setText(text_discover)
            self.btn_discover_ip.setText(text_discover)
            tip = translations.get("discover_tip", self.discover_btn.toolTip())
            self.discover_btn.setToolTip(tip)
            self.btn_discover_ip.setToolTip(tip)
            self._info_templates.update(
                {
                    "local": translations.get("local_label", "本机：{local} / {prefix}"),
                    "broadcast": translations.get("broadcast_label", "广播：{bcast}"),
                    "mask": translations.get("mask_label", "掩码：{mask}"),
                    "nodes": translations.get("nodes_label", "在线节点: {count}"),
                }
            )
            self.set_net_info(self._info_cache)
        except Exception:
            pass
