from __future__ import annotations

from typing import Dict

from PyQt5 import QtCore, QtWidgets
from zfeiq_gui.lang import t


class InfoPage(QtWidgets.QWidget):
    """Network information overview page (kept for backward compatibility)."""

    sigDiscover = QtCore.pyqtSignal(str)

    def __init__(self, core=None, parent=None):
        super().__init__(parent)
        self.core = core
        self._translations = t
        self._build()

    def _build(self) -> None:
        t_local = self._translations
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)
        self.lbl_local = QtWidgets.QLabel(t_local["local_label"].format(local="-", prefix="-"))
        self.lbl_bcast = QtWidgets.QLabel(t_local["broadcast_label"].format(bcast="-"))
        self.lbl_mask = QtWidgets.QLabel(t_local["mask_label"].format(mask="-"))
        row = QtWidgets.QHBoxLayout()
        self.disc_ip = QtWidgets.QLineEdit()
        self.disc_ip.setPlaceholderText(t_local["discover_ph"])
        btn_disc = QtWidgets.QPushButton(t_local["discover"])
        btn_disc.setFixedHeight(btn_disc.fontMetrics().height() + 12)
        row.addWidget(self.disc_ip, 1)
        row.addWidget(btn_disc)
        self.nodes = QtWidgets.QListWidget()
        self.lbl_count = QtWidgets.QLabel(t_local["nodes_label"].format(count=0))
        layout.addWidget(self.lbl_local)
        layout.addWidget(self.lbl_bcast)
        layout.addLayout(row)
        layout.addWidget(self.lbl_mask)
        layout.addWidget(self.lbl_count)
        layout.addWidget(self.nodes, 1)
        btn_disc.clicked.connect(lambda: self.sigDiscover.emit(self.disc_ip.text().strip()))

    def set_net_info(self, info: Dict) -> None:
        self.lbl_local.setText(f"本机：{info.get('local_ip','-')} / {info.get('iface_prefix','-')}")
        self.lbl_bcast.setText(f"广播：{info.get('broadcast','-')}")
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
        self.lbl_mask.setText(f"掩码：{mask or '-'}")

    def update_nodes(self, nodes) -> None:
        self.nodes.clear()
        for node in nodes:
            status_suffix = f" [{node.status}]" if getattr(node, "status", "online") != "online" else ""
            self.nodes.addItem(f"{node.username}@{node.ip} ({node.hostname}){status_suffix}")
        try:
            self.lbl_count.setText(f"在线节点: {len(nodes)}")
        except Exception:
            pass
