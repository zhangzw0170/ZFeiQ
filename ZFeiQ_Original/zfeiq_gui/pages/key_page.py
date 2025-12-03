from __future__ import annotations

from typing import Dict

from PyQt5 import QtWidgets, QtGui


class KeyPage(QtWidgets.QWidget):
    """Embedded key-management helper hosted inside the settings page."""

    @staticmethod
    def format_fingerprint(hexstr: str) -> str:
        # Display in 16-bit groups (4 hex chars) for readability
        groups = [hexstr[i:i+4] for i in range(0, len(hexstr), 4)]
        lines = []
        # Keep 8 groups per line to maintain readable block width
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
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

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
        # 允许换行；不强制固定高度以便在小屏设备上能够收缩
        self.lbl_fp_desc.setWordWrap(True)
        self.lbl_fp_desc.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Preferred)
        layout.addWidget(self.lbl_fp_desc)

        # 指纹内容文本框（不可编辑，每两位一组，每行8组）
        self.txt_fp = QtWidgets.QTextEdit()
        self.txt_fp.setReadOnly(True)
        # 允许指纹文本框自适应，但保留最大高度避免占用过多空间
        # 使用较小字体以便 16-bit 分组能在较窄窗口内显示
        try:
            f = self.txt_fp.font()
            # reduce by 1 point if possible
            try:
                f.setPointSize(max(8, f.pointSize() - 1))
            except Exception:
                pass
            try:
                f.setStyleHint(QtGui.QFont.Monospace)
            except Exception:
                pass
            self.txt_fp.setFont(f)
        except Exception:
            pass
        self.txt_fp.setMaximumHeight(80)
        layout.addWidget(self.txt_fp)

        # 重生成密钥按钮（单独一行）
        self.btn_regen = QtWidgets.QPushButton(t["key_regen"])
        try:
            self.btn_regen.setSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Preferred)
        except Exception:
            pass
        layout.addWidget(self.btn_regen)

        # 导出公钥按钮（单独一行）
        self.btn_export = QtWidgets.QPushButton(t["key_export"])
        try:
            self.btn_export.setSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Preferred)
        except Exception:
            pass
        layout.addWidget(self.btn_export)

        # 复选框：显示原始密文 / 显示 [E-D OK] 标记
        self.chk_show_cipher = QtWidgets.QCheckBox(t.get('show_cipher', '显示原始密文'))
        self.chk_show_edtag = QtWidgets.QCheckBox(t.get('show_edtag', '显示明文旁 [E-D OK] 标记'))
        layout.addWidget(self.chk_show_cipher)
        layout.addWidget(self.chk_show_edtag)

        # 信号连接
        # 刷新按钮已移除：Key 重新生成会自动更新指纹
        self.btn_regen.clicked.connect(self.on_regen_clicked)
        self.btn_export.clicked.connect(self.on_export_clicked)
        self.chk_show_cipher.toggled.connect(self.on_toggle_cipher)
        self.chk_show_edtag.toggled.connect(self.on_toggle_edtag)

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
            self.btn_regen.setText(translations.get("key_regen", "重生成密钥"))
            self.btn_export.setText(translations.get("key_export", "导出公钥…"))
            self.chk_show_cipher.setText(translations.get('show_cipher', self.chk_show_cipher.text()))
            self.chk_show_edtag.setText(translations.get('show_edtag', self.chk_show_edtag.text()))
        except Exception:
            pass

    def on_refresh_clicked(self):
        try:
            self.refresh_fingerprint()
            title = self._translations.get('key_refresh', '刷新指纹')
            msg = self._translations.get('key_refresh_success', '指纹已刷新。')
            QtWidgets.QMessageBox.information(self, title, msg)
        except Exception as e:
            title = self._translations.get('key_refresh', '刷新指纹')
            msg = self._translations.get('key_refresh_failed', '刷新指纹失败') + f": {e}"
            QtWidgets.QMessageBox.warning(self, title, msg)

    def on_regen_clicked(self):
        try:
            if not self._backend:
                title = self._translations.get('key_regen', '重生成密钥')
                QtWidgets.QMessageBox.warning(self, title, self._translations.get('key_regen_no_backend', '未绑定后端，无法重生成密钥。'))
                return
            z = getattr(self._backend, 'zcli', None)
            if not z:
                title = self._translations.get('key_regen', '重生成密钥')
                QtWidgets.QMessageBox.warning(self, title, self._translations.get('key_regen_no_zcli', '后端内部错误：找不到 zcli 实例。'))
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
            title = self._translations.get('key_regen', '重生成密钥')
            QtWidgets.QMessageBox.information(self, title, self._translations.get('key_regen_success', '已重生成密钥并保存。'))
        except Exception as e:
            title = self._translations.get('key_regen', '重生成密钥')
            msg = self._translations.get('key_regen_failed', '重生成密钥失败') + f": {e}"
            QtWidgets.QMessageBox.warning(self, title, msg)

    def on_export_clicked(self):
        try:
            if not self._backend:
                title = self._translations.get('key_export', '导出公钥…')
                QtWidgets.QMessageBox.warning(self, title, self._translations.get('key_regen_no_backend', '未绑定后端，无法重生成密钥。'))
                return
            z = getattr(self._backend, 'zcli', None)
            if not z:
                title = self._translations.get('key_export', '导出公钥…')
                QtWidgets.QMessageBox.warning(self, title, self._translations.get('key_regen_no_zcli', '后端内部错误：找不到 zcli 实例。'))
                return
            pub = getattr(z, '_pub_pem', None)
            if not pub:
                # try ensure
                try:
                    ok = z._ensure_keys()
                except Exception:
                    ok = False
                if not ok:
                    title = self._translations.get('key_export', '导出公钥…')
                    QtWidgets.QMessageBox.warning(self, title, self._translations.get('key_export_no_pub', '不存在公钥且无法生成密钥对。'))
                    return
                pub = getattr(z, '_pub_pem', None)
            # ask user for save path
            dialog_title = self._translations.get('key_export', '导出公钥…')
            path, _ = QtWidgets.QFileDialog.getSaveFileName(self, dialog_title, "pub.pem", "PEM Files (*.pem);;All Files (*)")
            if not path:
                return
            try:
                with open(path, 'wb') as f:
                    f.write(pub)
                title = self._translations.get('key_export', '导出公钥…')
                QtWidgets.QMessageBox.information(self, title, self._translations.get('key_export_saved', '公钥已保存到: {path}').format(path=path))
            except Exception as e:
                title = self._translations.get('key_export', '导出公钥…')
                QtWidgets.QMessageBox.warning(self, title, self._translations.get('key_export_failed', '导出失败：{error}').format(error=e))
        except Exception as e:
            title = self._translations.get('key_export', '导出公钥…')
            QtWidgets.QMessageBox.warning(self, title, self._translations.get('key_export_failed', '导出失败：{error}').format(error=e))

    def on_toggle_cipher(self, checked: bool):
        try:
            if not self._backend:
                return
            z = getattr(self._backend, 'zcli', None)
            if not z:
                return
            z.encrypt_show_cipher = bool(checked)
        except Exception:
            pass

    def on_toggle_edtag(self, checked: bool):
        try:
            if not self._backend:
                return
            z = getattr(self._backend, 'zcli', None)
            if not z:
                return
            z.encrypt_edtag = bool(checked)
        except Exception:
            pass
