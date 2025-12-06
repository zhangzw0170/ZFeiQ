import os
import glob
from functools import lru_cache
from typing import List

from PyQt5.QtCore import QAbstractListModel, Qt, QModelIndex, QSize, QRect, QPoint
from PyQt5.QtWidgets import (QListView, QMenu, QWidgetAction)
from PyQt5.QtGui import QPixmap, QImageReader
from PyQt5.QtGui import QCursor
from PyQt5.QtGui import QFontDatabase, QFont


class EmoteModel(QAbstractListModel):
    """Model that holds only path strings or unicode emote chars."""
    def __init__(self, emote_paths: List[str], parent=None):
        super().__init__(parent)
        self._data = list(emote_paths)

    def rowCount(self, parent=QModelIndex()):
        return len(self._data)

    def data(self, index: QModelIndex, role=Qt.DisplayRole):
        if not index.isValid() or role != Qt.DisplayRole:
            return None
        return self._data[index.row()]


@lru_cache(maxsize=64)
def load_scaled_pixmap(path: str, size: int) -> QPixmap:
    """
    Use QImageReader.setScaledSize to scale-on-load to reduce memory.
    Cached via LRU to limit memory usage.
    """
    if not os.path.isfile(path):
        return QPixmap()

    try:
        reader = QImageReader(path)
        reader.setAutoTransform(True)
        reader.setScaledSize(QSize(size, size))
        image = reader.read()
        if image.isNull():
            return QPixmap()
        return QPixmap.fromImage(image)
    except Exception:
        return QPixmap()


from PyQt5.QtWidgets import QStyledItemDelegate
from PyQt5.QtGui import QPainter, QColor
from PyQt5.QtWidgets import QStyle

class EmoteDelegate(QStyledItemDelegate):
    def __init__(self, icon_size=48, parent=None):
        super().__init__(parent)
        self.icon_size = icon_size
        self.padding = 6
        # Try to register repo-level emote font (resource/NotoColorEmoji.ttf)
        self.emote_font_family = None
        try:
            repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
            font_path = os.path.join(repo_root, 'resource', 'NotoColorEmoji.ttf')
            if os.path.isfile(font_path):
                fid = QFontDatabase.addApplicationFont(font_path)
                families = QFontDatabase.applicationFontFamilies(fid) if fid != -1 else []
                if families:
                    self.emote_font_family = families[0]
        except Exception:
            self.emote_font_family = None

    def paint(self, painter: QPainter, option, index: QModelIndex):
        data = index.data(Qt.DisplayRole)
        rect = option.rect

        painter.save()
        # hover / selected backgrounds
        try:
            if option.state & QStyle.State_Selected:
                painter.fillRect(rect, QColor("#e6f7ff"))
            elif option.state & QStyle.State_MouseOver:
                painter.fillRect(rect, QColor("#f5f5f5"))
        except Exception:
            pass

        # Draw content: special manager marker, unicode emote (short string) or image path
        if data == "__EMOTES_MANAGER__":
            # draw a rounded gray background box and a gear glyph centered
            bg_size = int(self.icon_size * 0.9)
            x = rect.x() + (rect.width() - bg_size) // 2
            y = rect.y() + (rect.height() - bg_size) // 2
            bg_rect = QRect(x, y, bg_size, bg_size)
            painter.save()
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor("#dddddd"))
            painter.drawRoundedRect(bg_rect, 6, 6)
            # gear glyph
            font = painter.font()
            font.setPixelSize(max(10, bg_size // 2))
            painter.setFont(font)
            painter.setPen(QColor("#333333"))
            painter.drawText(bg_rect, Qt.AlignCenter, "⚙")
            painter.restore()
        elif isinstance(data, str) and len(data) < 8 and not os.path.exists(data):
            # text emote
            if self.emote_font_family:
                font = QFont(self.emote_font_family)
                font.setPixelSize(self.icon_size - 8)
                painter.setFont(font)
            else:
                font = painter.font()
                font.setPixelSize(self.icon_size - 8)
                painter.setFont(font)
            painter.setPen(QColor("#000000"))
            painter.drawText(rect, Qt.AlignCenter, data)
        else:
            pixmap = load_scaled_pixmap(data, self.icon_size)
            if not pixmap.isNull():
                x = rect.x() + (rect.width() - self.icon_size) // 2
                y = rect.y() + (rect.height() - self.icon_size) // 2
                painter.drawPixmap(x, y, pixmap)

        painter.restore()

    def sizeHint(self, option, index):
        s = self.icon_size + self.padding * 2
        return QSize(s, s)


def show_emote_popup(parent, emote_list: List[str], on_select, icon_size=48, cols=8, rows=4, anchor_widget=None):
    """
    Show a popup menu containing a QListView (IconMode) backed by EmoteModel/EmoteDelegate.
    on_select: callback(data_str)
    emote_list: list of unicode strings and/or image paths
    """
    lv = QListView(parent)
    lv.setViewMode(QListView.IconMode)
    lv.setMovement(QListView.Static)
    lv.setResizeMode(QListView.Adjust)
    lv.setUniformItemSizes(True)
    lv.setSpacing(6)
    lv.setIconSize(QSize(icon_size, icon_size))
    grid_w = icon_size + 12
    lv.setGridSize(QSize(grid_w, grid_w))
    lv.setFlow(QListView.LeftToRight)

    model = EmoteModel(emote_list, parent)
    delegate = EmoteDelegate(icon_size=icon_size, parent=parent)
    lv.setModel(model)
    lv.setItemDelegate(delegate)

    def _on_clicked(index: QModelIndex):
        data = index.data(Qt.DisplayRole)
        try:
            on_select(data)
        except Exception:
            pass
        try:
            popup.close()
        except Exception:
            pass

    lv.clicked.connect(_on_clicked)

    width = (grid_w) * cols + 20
    height = (grid_w) * rows + 10
    lv.setFixedSize(width, height)

    popup = QMenu(parent)
    wa = QWidgetAction(popup)
    wa.setDefaultWidget(lv)
    popup.addAction(wa)

    # Prefer anchoring to provided widget's bottom-left so popup appears stable
    try:
        if anchor_widget is not None:
            try:
                gp = anchor_widget.mapToGlobal(QPoint(0, anchor_widget.height()))
                popup.exec_(gp)
                return
            except Exception:
                pass
        popup.exec_(QCursor.pos())
    except Exception:
        popup.exec_()


def build_emote_list(default_unicode: List[str], custom_dir: str = None, include_manager: bool = False) -> List[str]:
    """Return combined emote list (unicode first, then image paths from custom_dir).

    If include_manager is True, insert a special marker string at the beginning which
    represents the settings/manager entry (displayed as a gear in the UI).
    """
    res = list(default_unicode)
    if custom_dir and os.path.isdir(custom_dir):
        patterns = ['*.png', '*.jpg', '*.jpeg', '*.webp', '*.svg']
        for pat in patterns:
            res.extend(sorted(glob.glob(os.path.join(custom_dir, pat))))

    if include_manager:
        res.insert(0, "__EMOTES_MANAGER__")

    return res


from PyQt5.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QListWidget, QPushButton, QMessageBox, QFileDialog, QLabel
from gui.lang import L
import shutil


class EmotesManagerDialog(QDialog):
    """Simple dialog to add/remove image files in the custom emotes directory.

    Operations are destructive (copy/delete) on the target directory (custom_dir).
    The dialog returns True from exec_ if the contents were modified.
    """
    def __init__(self, parent, custom_dir: str):
        super().__init__(parent)
        self.setWindowTitle(L('emotes_manager_title', 'Emotes Manager'))
        self.custom_dir = custom_dir
        self.modified = False

        self.setMinimumSize(480, 320)
        layout = QVBoxLayout(self)

        self.lbl = QLabel(L('emotes_dir_label', 'Emotes directory: {dir}').format(dir=self.custom_dir))
        layout.addWidget(self.lbl)

        self.listw = QListWidget(self)
        layout.addWidget(self.listw)

        btn_layout = QHBoxLayout()
        self.btn_add = QPushButton(L('btn_add', 'Add'))
        self.btn_remove = QPushButton(L('btn_remove', 'Remove'))
        self.btn_close = QPushButton(L('btn_close', 'Close'))
        btn_layout.addWidget(self.btn_add)
        btn_layout.addWidget(self.btn_remove)
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_close)
        layout.addLayout(btn_layout)

        self.btn_add.clicked.connect(self._on_add)
        self.btn_remove.clicked.connect(self._on_remove)
        self.btn_close.clicked.connect(self.accept)

        self._ensure_dir()
        self._refresh()

    def _ensure_dir(self):
        try:
            os.makedirs(self.custom_dir, exist_ok=True)
        except Exception:
            pass

    def _refresh(self):
        self.listw.clear()
        patterns = ['*.png', '*.jpg', '*.jpeg', '*.webp', '*.svg']
        files = []
        for pat in patterns:
            files.extend(sorted(glob.glob(os.path.join(self.custom_dir, pat))))
        for p in files:
            self.listw.addItem(os.path.basename(p))

    def _on_add(self):
        paths, _ = QFileDialog.getOpenFileNames(self, L('emotes_select_images', 'Select images to add'), os.getcwd(), "Images (*.png *.jpg *.jpeg *.webp *.svg)")
        if not paths:
            return
        for p in paths:
            try:
                dst = os.path.join(self.custom_dir, os.path.basename(p))
                if os.path.exists(dst):
                    base, ext = os.path.splitext(dst)
                    i = 1
                    while os.path.exists(f"{base}_{i}{ext}"):
                        i += 1
                    dst = f"{base}_{i}{ext}"
                shutil.copy2(p, dst)
                self.modified = True
            except Exception as e:
                QMessageBox.warning(self, L('err_title', 'Error'), L('emotes_add_failed', 'Failed to add {file}: {err}').format(file=p, err=e))
        self._refresh()

    def _on_remove(self):
        items = self.listw.selectedItems()
        if not items:
            return
        ok = QMessageBox.question(self, L('warn_title', 'Warning'), L('emotes_confirm_remove', 'Delete {n} selected files from custom emotes?').format(n=len(items)), QMessageBox.Yes | QMessageBox.No)
        if ok != QMessageBox.Yes:
            return
        for it in items:
            name = it.text()
            p = os.path.join(self.custom_dir, name)
            try:
                if os.path.isfile(p):
                    os.remove(p)
                    self.modified = True
            except Exception as e:
                QMessageBox.warning(self, L('err_title', 'Error'), L('emotes_remove_failed', 'Failed to remove {file}: {err}').format(file=p, err=e))
        self._refresh()
