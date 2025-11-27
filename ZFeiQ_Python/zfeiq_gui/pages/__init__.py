"""Pages package for refactored GUI.

This module re-exports the page classes so callers can use:
    from zfeiq_gui.pages import ChatPage, LoginPage, ...
which matches the original GUI's import style.
"""

from .chat_page import ChatPage
from .login_page import LoginPage
from .userlist_page import UserListPage
from .groups_page import GroupsPage
from .settings_page import SettingsPage
from .info_page import InfoPage
from .files_page import FilesPage
from .emotes_page import EmotesPage
from .key_page import KeyPage

__all__ = [
    'ChatPage', 'LoginPage', 'UserListPage', 'GroupsPage', 'SettingsPage',
    'InfoPage', 'FilesPage', 'EmotesPage', 'KeyPage',
]
