from typing import Optional
from PyQt5 import QtCore, QtGui, QtWidgets


class NavigationButton(QtWidgets.QToolButton):
	"""Unified look-and-feel button used throughout the sidebar and toolbars."""

	def __init__(self, text: str, icon: Optional[QtGui.QIcon] = None, parent=None):
		super().__init__(parent)
		self.setText(text)
		if icon:
			self.setIcon(icon)
			self.setIconSize(QtCore.QSize(16, 16))
			self.setToolButtonStyle(QtCore.Qt.ToolButtonTextBesideIcon)
		else:
			self.setToolButtonStyle(QtCore.Qt.ToolButtonTextOnly)
		self.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
		# Use a flexible vertical policy instead of forcing a fixed height so the
		# sidebar buttons can shrink on small screens.
		self.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Preferred)


class ExpandableSection(QtWidgets.QWidget):
	"""Simple collapsible container with a toggleable header button."""

	def __init__(self, title: str, content: QtWidgets.QWidget, parent=None, default_expanded: bool = False):
		super().__init__(parent)
		self._content = content
		self._btn = QtWidgets.QToolButton()
		self._btn.setText(title)
		self._btn.setToolButtonStyle(QtCore.Qt.ToolButtonTextOnly)
		self._btn.setCheckable(True)
		self._btn.setChecked(default_expanded)
		self._btn.setArrowType(QtCore.Qt.DownArrow if default_expanded else QtCore.Qt.RightArrow)
		self._btn.clicked.connect(self._toggle)
		layout = QtWidgets.QVBoxLayout(self)
		layout.setContentsMargins(0, 0, 0, 0)
		layout.setSpacing(4)
		layout.addWidget(self._btn)
		layout.addWidget(self._content)
		self._content.setVisible(default_expanded)

	def _toggle(self):
		expanded = self._btn.isChecked()
		self._content.setVisible(expanded)
		self._btn.setArrowType(QtCore.Qt.DownArrow if expanded else QtCore.Qt.RightArrow)

