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
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

            search_row = QtWidgets.QHBoxLayout()  # 顶部仅保留搜索框并占满宽度，不放“发现”按钮
            self.search_edit = QtWidgets.QLineEdit()
            self.search_edit.setPlaceholderText(t["search_ph"])
            self.search_edit.textChanged.connect(self._apply_filter)
            search_row.addWidget(self.search_edit, 1)

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

            # 发现功能仅保留下方按 IP 指定的入口
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
        # 状态指示灯：使用彩色圆形 Emoji，避免富文本与委托复杂度
        status_emojis = {
            "online": "🟢",  # 绿色
            "busy": "🟠",    # 橙色
            "away": "⚪",    # 灰色近似（白圆）
        }
        for node in nodes:
            host = getattr(node, "hostname", "")
            local_tag = "[LOCAL] " if local_ip and getattr(node, "ip", None) == local_ip else ""
            status_code = getattr(node, "status", "online")
            light = status_emojis.get(status_code, status_emojis["online"])
            # 第一行：状态灯 + [LOCAL] + 用户名
            line1 = f"{light} {local_tag}{node.username}".rstrip()
            # 第二行：@ IP 地址（LOCAL 仅显示第一行）
            line2 = f"@ {node.ip}"
            # 第三行：单独一行显示主机名（方括号），若无主机名则省略（LOCAL 省略）
            line3 = f"[{host}]" if host else ""
            if local_ip and getattr(node, "ip", None) == local_ip:
                text_block = f"{line1}"
            else:
                text_block = f"{line1}\n{line2}" + (f"\n{line3}" if line3 else "")
            items.append((text_block, ("user", node)))
        if groups:
            for group_name, members in sorted(groups.items()):
                items.append((f"[组] {group_name} ({len(members)})", ("group", group_name)))
        self._all_items = [text for text, _ in items]
        for text, meta in items:
            item = QtWidgets.QListWidgetItem(text)
            item.setData(QtCore.Qt.UserRole, meta)
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
            # 状态文案映射（本地化）
            try:
                from zfeiq_gui.lang import t as _t
                status_text = {
                    'online': _t['online'],
                    'busy': _t['busy'],
                    'away': _t['away'],
                }
            except Exception:
                status_text = {'online':'在线','busy':'忙碌','away':'离开'}
                except Exception:
                    mask = None
        self.lbl_mask.setText(self._info_templates.get("mask", "掩码：{mask}").format(mask=mask or "-"))

    def _apply_filter(self) -> None:
        query = self.search_edit.text().strip().lower()
                is_local = bool(local_ip and getattr(node, "ip", None) == local_ip)
                st_txt = status_text.get(status_code, status_code)
                if is_local:
                    # 单行：状态灯 + [LOCAL] + 用户名 + 状态；IP 同行右侧近似右对齐
                    left = f"{light} [LOCAL] {node.username} {st_txt}"
                    # 通过空格拉齐，简化实现（受字体影响可能不完全右对齐）
                    spacer = " " * 4
                    right = f"@ {node.ip}"
                    text_block = f"{left}{spacer}{right}"
                else:
                    # 非本机：三行显示（用户名/状态灯、@IP、[主机名]）
                    line1 = f"{light} {node.username}"
                    line2 = f"@ {node.ip}"
                    line3 = f"[{host}]" if host else ""
                    text_block = f"{line1}\n{line2}" + (f"\n{line3}" if line3 else "")
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
