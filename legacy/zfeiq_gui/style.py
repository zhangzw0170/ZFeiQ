"""UI 样式片段：统一 `QComboBox` 与 `QLineEdit` 的扁平、圆角风格，并美化下拉箭头。

策略：
- 统一 `QLineEdit` 与 `QComboBox` 的高度、内边距与圆角，保证它们在同一行内视觉一致。
- 使用纯 CSS 绘制小三角箭头，并适当调整右侧内边距使箭头位置更居中。
- 优化 `QAbstractItemView` 列表的行高与内边距，提高可读性。
"""

COMBOBOX_QSS_LIGHT = '''
/* 基本控件统一样式：QLineEdit 与 QComboBox */
QLineEdit, QComboBox {
  background: #ffffff;
  border: 1px solid #d6d6d6;
  border-radius: 6px;
  padding: 6px 10px; /* 上下 6px，左右 10px */
  min-height: 20px;
  color: #222222;
  selection-background-color: #e6f0ff;
}

/* 保持 QComboBox 右侧留出箭头区域 */
QComboBox { padding-right: 20px; }
QComboBox:hover { border-color: #b7b7b7; }

/* 下拉区域样式 */
QComboBox::drop-down {
  subcontrol-origin: padding;
  subcontrol-position: top right;
  width: 30px;
  border-left: none;
}

/* 现代细小三角形箭头，使用边框绘制 */
QComboBox::down-arrow {
  width: 0;
  height: 0;
  image: none;
  border: none;
}

/* 下拉列表本身 */
QComboBox QAbstractItemView {
  border: 1px solid rgba(0,0,0,0.06);
  background: #ffffff;
  selection-background-color: #e6f0ff;
  outline: none;
  padding: 4px 2px;
  border-radius: 6px;
}
QComboBox QAbstractItemView::item {
  padding: 6px 10px;
  min-height: 24px;
}

/* 小型滚动条风格，避免太粗 */
QScrollBar:vertical { width:10px; background:transparent; }
QScrollBar::handle:vertical { background: rgba(0,0,0,0.12); border-radius:5px; }

'''

COMBOBOX_QSS_DARK = '''
QLineEdit, QComboBox {
  background: #2b2b2b;
  border: 1px solid #444444;
  border-radius: 6px;
  padding: 6px 10px;
  min-height: 20px;
  color: #eaeaea;
  selection-background-color: #274b7a;
}

QComboBox { padding-right: 20px; }
QComboBox:hover { border-color: #5c5c5c; }

QComboBox::drop-down {
  subcontrol-origin: padding;
  subcontrol-position: top right;
  width: 30px;
  border-left: none;
}

QComboBox::down-arrow {
  width: 0;
  height: 0;
  image: none;
  border: none;
}

QComboBox QAbstractItemView {
  border: 1px solid rgba(255,255,255,0.06);
  background: #232323;
  selection-background-color: #274b7a;
  color: #eaeaea;
  outline: none;
  padding: 4px 2px;
  border-radius: 6px;
}
QComboBox QAbstractItemView::item {
  padding: 6px 10px;
  min-height: 24px;
}

QScrollBar:vertical { width:10px; background:transparent; }
QScrollBar::handle:vertical { background: rgba(255,255,255,0.08); border-radius:5px; }

'''

def get_combobox_qss(theme: str = 'light') -> str:
    return COMBOBOX_QSS_DARK if theme == 'dark' else COMBOBOX_QSS_LIGHT
