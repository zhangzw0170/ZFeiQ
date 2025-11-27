from __future__ import annotations

from typing import Dict

from PyQt5 import QtWidgets


class KeyPage(QtWidgets.QWidget):
    """Embedded key-management helper hosted inside the settings page."""

    @staticmethod
    def format_fingerprint(hexstr: str) -> str:
        groups = [hexstr[i:i+2] for i in range(0, len(hexstr), 2)]
        lines = []
        for i in range(0, len(groups), 8):
            lines.append(' '.join(groups[i:i+8]))
        return '\n'.join(lines)

    def __init__(self, lang: str = "zhCN"):
        super().__init__()
        from zfeiq_gui.lang import get_translations
        self._translations = get_translations(lang)
        self._backend = None
        self._build()

    def _build(self) -> None:
        t = self._translations
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        # 加密模式下拉选择框（与说明同一行）
        enc_mode_row = QtWidgets.QHBoxLayout()
        self.lbl_enc_mode = QtWidgets.QLabel(t['enc_mode'])
        self.cmb_mode = QtWidgets.QComboBox()
        self.cmb_mode.addItems(["off", "on", "strict"])
        enc_mode_row.addWidget(self.lbl_enc_mode)
        enc_mode_row.addWidget(self.cmb_mode)
        enc_mode_row.addStretch()
        layout.addLayout(enc_mode_row)

        # 指纹说明文本（单独一行）
        self.lbl_fp_desc = QtWidgets.QLabel(t['key_fp'])
        layout.addWidget(self.lbl_fp_desc)

        # 指纹内容文本框（不可编辑，每两位一组，每行8组）
        self.txt_fp = QtWidgets.QTextEdit()
        self.txt_fp.setReadOnly(True)
        self.txt_fp.setMinimumHeight(60)
        self.txt_fp.setMaximumHeight(120)
        layout.addWidget(self.txt_fp)

        # 刷新指纹按钮（单独一行）
        self.btn_refresh = QtWidgets.QPushButton(t["key_refresh"])
        self.btn_refresh.setFixedHeight(self.btn_refresh.fontMetrics().height() + 12)
        layout.addWidget(self.btn_refresh)

        # 重生成密钥按钮（单独一行）
        self.btn_regen = QtWidgets.QPushButton(t["key_regen"])
        self.btn_regen.setFixedHeight(self.btn_regen.fontMetrics().height() + 12)
        layout.addWidget(self.btn_regen)

        # 导出公钥按钮（单独一行）
        self.btn_export = QtWidgets.QPushButton(t["key_export"])
        self.btn_export.setFixedHeight(self.btn_export.fontMetrics().height() + 12)
        layout.addWidget(self.btn_export)

        # 信号连接
        self.btn_refresh.clicked.connect(self.on_refresh_clicked)
        self.btn_regen.clicked.connect(self.on_regen_clicked)
        self.btn_export.clicked.connect(self.on_export_clicked)

    def set_fingerprint(self, hexstr: str) -> None:
        formatted = self.format_fingerprint(hexstr)
        self.txt_fp.setPlainText(formatted)

    def set_backend(self, backend) -> None:
        """Attach GuiBackend (or object exposing `zcli`) to this widget."""
        self._backend = backend

    def refresh_fingerprint(self) -> None:
        """Load/ensure keys via backend and update fingerprint display."""
        try:
            if not self._backend:
                return
            z = getattr(self._backend, 'zcli', None)
            if not z:
                return
            # ensure keys exist
            try:
                ok = z._ensure_keys()
            except Exception:
                ok = False
            if not ok:
                return
            pub = getattr(z, '_pub_pem', None) or b''
            import hashlib
            h = hashlib.sha256(pub).hexdigest()
            self.set_fingerprint(h)
        except Exception:
            pass

    def apply_language(self, translations: Dict[str, str]) -> None:
        self._translations = translations
        try:
            self.lbl_enc_mode.setText(translations.get("enc_mode", self.lbl_enc_mode.text()))
            self.lbl_fp_desc.setText(translations.get("key_fp", self.lbl_fp_desc.text()))
            self.btn_refresh.setText(translations.get("key_refresh", "刷新指纹"))
            self.btn_regen.setText(translations.get("key_regen", "重生成密钥"))
            self.btn_export.setText(translations.get("key_export", "导出公钥…"))
        except Exception:
            pass

    def on_refresh_clicked(self):
        try:
            self.refresh_fingerprint()
            QtWidgets.QMessageBox.information(self, "刷新指纹", "指纹已刷新。")
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "刷新指纹失败", f"刷新指纹失败：{e}")

    def on_regen_clicked(self):
        try:
            if not self._backend:
                QtWidgets.QMessageBox.warning(self, "重生成密钥", "未绑定后端，无法重生成密钥。")
                return
            z = getattr(self._backend, 'zcli', None)
            if not z:
                QtWidgets.QMessageBox.warning(self, "重生成密钥", "后端内部错误：找不到 zcli 实例。")
                return
            # 生成新密钥对并保存
            from zfeiq_cli.crypto import generate_rsa_keypair
            prv, pub = generate_rsa_keypair(3072)
            z._priv_pem, z._pub_pem = prv, pub
            try:
                z._save_keys()
            except Exception:
                pass
            self.refresh_fingerprint()
            QtWidgets.QMessageBox.information(self, "重生成密钥", "已重生成密钥并保存。")
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "重生成密钥失败", f"重生成密钥失败：{e}")

    def on_export_clicked(self):
        try:
            if not self._backend:
                QtWidgets.QMessageBox.warning(self, "导出公钥", "未绑定后端，无法导出公钥。")
                return
            z = getattr(self._backend, 'zcli', None)
            if not z:
                QtWidgets.QMessageBox.warning(self, "导出公钥", "后端内部错误：找不到 zcli 实例。")
                return
            pub = getattr(z, '_pub_pem', None)
            if not pub:
                # try ensure
                try:
                    ok = z._ensure_keys()
                except Exception:
                    ok = False
                if not ok:
                    QtWidgets.QMessageBox.warning(self, "导出公钥", "不存在公钥且无法生成密钥对。")
                    return
                pub = getattr(z, '_pub_pem', None)
            # ask user for save path
            path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "导出公钥", "pub.pem", "PEM Files (*.pem);;All Files (*)")
            if not path:
                return
            try:
                with open(path, 'wb') as f:
                    f.write(pub)
                QtWidgets.QMessageBox.information(self, "导出公钥", f"公钥已保存到: {path}")
            except Exception as e:
                QtWidgets.QMessageBox.warning(self, "导出公钥失败", f"导出失败：{e}")
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "导出公钥失败", f"导出失败：{e}")
