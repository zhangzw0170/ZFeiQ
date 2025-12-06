SUPPORTED_THEMES = ['light', 'dark']

# Theme dictionary design
# - centralize all commonly-used colors into THEMES
# - keys are used across the GUI: use `get_color(name, theme)` to fetch
THEMES = {
	'light': {
		'PRIMARY_TEXT': "#000000",
		'SECONDARY_TEXT': "#666666",
		'BORDER': "#E0E0E0",
		'BACKGROUND_PANEL': "#FAFAFA",
		'INPUT_BG': "#FFFFFF",
		'BTN_BG': "#0078d7",
		'BTN_TEXT': "#FFFFFF",
		# UI accents / hover / menus
		'HIGHLIGHT': "#e6e6e6",
		'HOVER_BG': "#f2f2f2",
		'ACCENT': "#0078d7",
		'ACCENT_TEXT': "#ffffff",
		'MENU_BG': "#ffffff",
		'ICON_BG': "#f39c12",
		'PROGRESS_BG': "#eeeeee",
		'PROGRESS_ACTIVE': "#3498db",
		'PROGRESS_DONE': "#2ecc71",
		'BTN_ACCENT': "#129611",
		# Encryption indicator colors (used for top-right status labels)
		'ENC_GREEN': "#1e7e34",
		'ENC_RED': "#b21b1b",
		# Chat bubble colors
		'CHAT_COLOR_ME_ENC': "#95EC69",
		'CHAT_COLOR_RX_ENC': "#D6F3FF",
		'CHAT_COLOR_UNENC_BG': "#FFFFFF",
		'CHAT_COLOR_UNENC_BORDER': "#E0E0E0",
		# Status colors
		'STATUS_ONLINE': "#2ecc71",
		'STATUS_OFFLINE': "#777777",
	},
	'dark': {
		'PRIMARY_TEXT': "#E7E7E7",
		'SECONDARY_TEXT': "#BFBFBF",
		'BORDER': "#444444",
		'BACKGROUND_PANEL': "#2b2b2b",
		'INPUT_BG': "#3a3a3a",
		'BTN_BG': "#1f6feb",
		'BTN_TEXT': "#FFFFFF",
		# UI accents / hover / menus
		'HIGHLIGHT': "#3a3a3a",
		'HOVER_BG': "#333333",
		'ACCENT': "#1f6feb",
		'ACCENT_TEXT': "#ffffff",
		'MENU_BG': "#3a3a3a",
		'ICON_BG': "#f39c12",
		'PROGRESS_BG': "#444444",
		'PROGRESS_ACTIVE': "#3498db",
		'PROGRESS_DONE': "#2ecc71",
		'BTN_ACCENT': "#2a9d3a",
		# Encryption indicator colors (bright variants for dark theme)
		'ENC_GREEN': "#76FF03",
		'ENC_RED': "#FF5252",
		# Chat bubble colors (tuned for dark backgrounds)
		'CHAT_COLOR_ME_ENC': "#6CC24A",
		'CHAT_COLOR_RX_ENC': "#2b6f81",
		'CHAT_COLOR_UNENC_BG': "#2f2f2f",
		'CHAT_COLOR_UNENC_BORDER': "#444444",
		# Status colors
		'STATUS_ONLINE': "#2ecc71",
		'STATUS_OFFLINE': "#B0B0B0",
	}
}


def _normalize_theme_code(theme_code: str) -> str:
	if not theme_code:
		return 'light'
	tc = str(theme_code).lower()
	return tc if tc in THEMES else 'light'


def get_theme(theme_code: str) -> dict:
	"""Return theme dict for `theme_code`. Falls back to 'light'."""
	return THEMES[_normalize_theme_code(theme_code)]


def get_color(name: str, theme_code: str = 'light') -> str:
	"""Fetch a color value by name from the selected theme.

	Usage: `get_color('PRIMARY_TEXT', core.theme)` or `get_color('CHAT_COLOR_ME_ENC', 'dark')`.
	If `name` already looks like a hex color (starts with '#'), it is returned as-is.
	"""
	if not name:
		return ''
	if isinstance(name, str) and name.startswith('#'):
		return name
	theme = get_theme(theme_code)
	return theme.get(name, '')


def qss_fragment(theme_code: str = 'light') -> str:
	"""Return a small, reusable QSS fragment for common containers.

	This is intentionally small: use it to seed `app.setStyleSheet()` or to
	compose larger QSS in `theme.py` later.
	"""
	t = get_theme(theme_code)
	bg = t.get('BACKGROUND_PANEL', '#ffffff')
	text = t.get('PRIMARY_TEXT', '#000000')
	input_bg = t.get('INPUT_BG', '#ffffff')
	btn_bg = t.get('BTN_BG', '#0078d7')
	btn_text = t.get('BTN_TEXT', '#ffffff')
	return (
		f"QWidget {{ background: {bg}; color: {text}; }}\n"
		f"QLineEdit, QTextEdit {{ background: {input_bg}; color: {text}; }}\n"
		f"QPushButton {{ background-color: {btn_bg}; color: {btn_text}; border-radius:4px; }}\n"
	)


# Backwards-compatible constants (small set) - prefer get_color in new code
CHAT_COLOR_ME_ENC = THEMES['light']['CHAT_COLOR_ME_ENC']
CHAT_COLOR_RX_ENC = THEMES['light']['CHAT_COLOR_RX_ENC']
CHAT_COLOR_UNENC_BG = THEMES['light']['CHAT_COLOR_UNENC_BG']
CHAT_COLOR_UNENC_BORDER = THEMES['light']['CHAT_COLOR_UNENC_BORDER']

# Example placeholders (kept for quick imports)
PRIMARY_TEXT = THEMES['light']['PRIMARY_TEXT']
SECONDARY_TEXT = THEMES['light']['SECONDARY_TEXT']
BORDER_LIGHT = THEMES['light']['BORDER']
BACKGROUND_PANEL = THEMES['light']['BACKGROUND_PANEL']
