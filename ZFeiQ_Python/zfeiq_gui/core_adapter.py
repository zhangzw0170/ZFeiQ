from PyQt5 import QtCore
from typing import Any, Dict, List, Tuple


class CoreAdapter(QtCore.QObject):
    """Adapter that exposes a backend-like Qt API by delegating to a CoreBridge.

    It maps the in-process EventBus topics to Qt signals expected by the original GUI
    and implements a handful of methods the GUI calls (best-effort delegations).
    """

    message_signal = QtCore.pyqtSignal(str, str, str)  # sender, ip, text
    file_offer_signal = QtCore.pyqtSignal(str, str, int)  # sender, name, size
    offers_updated = QtCore.pyqtSignal()
    file_progress = QtCore.pyqtSignal(str, int)  # oid, bytes
    file_saved = QtCore.pyqtSignal(str, str)  # oid, path

    def __init__(self, core_bridge):
        super().__init__()
        self._bridge = core_bridge
        self._core = getattr(core_bridge, 'core', None)
        self._bus = getattr(core_bridge, 'bus', None)
        # subscribe to topics if EventBus present
        try:
            if self._bus:
                from zfeiq_core.events import TOPIC_MSG_INCOMING, TOPIC_FILE_OFFER, TOPIC_FILE_PROGRESS, TOPIC_FILE_COMPLETE

                def _on_msg(payload):
                    try:
                        if isinstance(payload, dict):
                            sender = payload.get('from_user') or payload.get('from') or ''
                            text = payload.get('text') or ''
                            ip = sender
                        else:
                            sender = str(payload)
                            text = str(payload)
                            ip = sender
                        # emit (sender, ip, text)
                        self.message_signal.emit(sender, ip, text)
                    except Exception:
                        pass

                def _on_offer(payload):
                    try:
                        if isinstance(payload, dict):
                            sender = payload.get('uname') or payload.get('from_user') or payload.get('ip') or ''
                            name = payload.get('name') or payload.get('file_name') or ''
                            size = int(payload.get('size', 0) or 0)
                            self.file_offer_signal.emit(sender, name, size)
                    except Exception:
                        pass

                def _on_progress(payload):
                    try:
                        if isinstance(payload, dict):
                            oid = str(payload.get('oid') or payload.get('id') or '')
                            done = int(payload.get('done', 0) or 0)
                            self.file_progress.emit(oid, done)
                    except Exception:
                        pass

                def _on_complete(payload):
                    try:
                        if isinstance(payload, dict):
                            oid = str(payload.get('oid') or payload.get('id') or '')
                            path = payload.get('path') or payload.get('saved_to') or ''
                            self.file_saved.emit(oid, path)
                    except Exception:
                        pass

                try:
                    self._bus.subscribe(TOPIC_MSG_INCOMING, _on_msg)
                except Exception:
                    pass
                try:
                    self._bus.subscribe(TOPIC_FILE_OFFER, _on_offer)
                except Exception:
                    pass
                try:
                    self._bus.subscribe(TOPIC_FILE_PROGRESS, _on_progress)
                except Exception:
                    pass
                try:
                    self._bus.subscribe(TOPIC_FILE_COMPLETE, _on_complete)
                except Exception:
                    pass
        except Exception:
            pass

    # Lifecycle
    def start(self):
        # GUI expects a start method; nothing to start for adapter
        return None

    # Incoming offers list (best-effort; core may not implement)
    def list_incoming_offers(self) -> Dict[str, Dict[str, Any]]:
        try:
            fn = getattr(self._core, 'list_incoming_offers', None)
            if callable(fn):
                return fn()
        except Exception:
            pass
        return {}

    # Offer actions (no-op fallback)
    def accept_offer(self, oid: str, dest: str):
        try:
            fn = getattr(self._core, 'accept_offer', None)
            if callable(fn):
                return fn(oid, dest)
        except Exception:
            pass

    def cancel_offer(self, oid: str):
        try:
            fn = getattr(self._core, 'cancel_offer', None)
            if callable(fn):
                return fn(oid)
        except Exception:
            pass

    # Basic getters used by GUI (best-effort delegations)
    def get_ui_theme(self) -> str:
        try:
            return getattr(self._core, 'get_config', lambda k, d=None: d)('ui_theme', 'light') or 'light'
        except Exception:
            return 'light'

    def get_screenshot_dir(self) -> str:
        try:
            return getattr(self._core, 'get_config', lambda k, d=None: d)('screenshot_dir', '') or ''
        except Exception:
            return ''

    def get_nodes(self) -> List[Any]:
        # Try core._nodes structure
        try:
            nodes = getattr(self._core, '_nodes', {})
            return [type('N', (), {'ip': k, 'username': v.get('username', ''), 'hostname': '', 'status': 'online'})() for k, v in nodes.items()]
        except Exception:
            return []

    def list_groups(self):
        try:
            return getattr(self._core, 'get_config', lambda k, d=None: d)('groups', {}) or {}
        except Exception:
            return {}

    def get_net_info(self) -> Dict[str, Any]:
        try:
            return getattr(self._core, 'get_config', lambda k, d=None: d)('net_info', {}) or {}
        except Exception:
            return {}

    def get_local_ifaces(self) -> List[Tuple[str, str]]:
        # best-effort: return empty
        return []

    def get_ui_avatar(self) -> str:
        return getattr(self._core, 'get_config', lambda k, d=None: d)('ui_avatar', '') or ''

    # Group / user operations
    def group_add(self, group: str, user: str):
        # store in config for demo
        try:
            groups = self.list_groups() or {}
            groups.setdefault(group, set()).add(user)
            self._core.set_config('groups', {k: list(v) for k, v in groups.items()})
        except Exception:
            pass

    def group_remove(self, group: str, user: str = None):
        try:
            groups = self.list_groups() or {}
            if group in groups:
                if user is None:
                    groups.pop(group, None)
                else:
                    members = set(groups.get(group, []))
                    members.discard(user)
                    groups[group] = list(members)
                self._core.set_config('groups', groups)
        except Exception:
            pass

    # Send operations
    def send_text(self, target: str, text: str):
        try:
            # CoreBridge exposes send_message(to, text)
            if hasattr(self._bridge, 'send_message'):
                # normalize target if startswith ip:
                tgt = target
                if isinstance(target, str) and target.startswith('ip:'):
                    tgt = target[3:]
                self._bridge.send_message(tgt, text)
                return True
        except Exception:
            pass
        return False

    def send_file(self, target: str, path: str):
        try:
            fn = getattr(self._core, 'register_file', None)
            if callable(fn):
                # best-effort: no-op registration
                return True
        except Exception:
            pass
        return False

    # State / config
    def set_ui_avatar(self, path: str):
        try:
            self._core.set_config('ui_avatar', path)
        except Exception:
            pass

    def save_state(self):
        # persistence handled in core; nothing extra
        return None

    def login(self, name: str):
        try:
            if hasattr(self._bridge, 'login'):
                self._bridge.login(name)
                return True
            if hasattr(self._core, 'login'):
                self._core.login(name)
                return True
        except Exception:
            pass
        return False

    def logout(self):
        try:
            # publish user.offline
            if self._bus:
                self._bus.publish('user.offline', {'username': ''})
        except Exception:
            pass

    # Key / crypto helpers
    def regenerate_keys(self):
        try:
            fn = getattr(self._core, 'ensure_keys', None)
            if callable(fn):
                fn()
                return True
        except Exception:
            pass
        return False

    def export_pubkey(self, path: str):
        try:
            pub = getattr(self._core, 'get_public_key', lambda: None)()
            if pub:
                with open(path, 'wb') as f:
                    f.write(pub)
                return path
        except Exception:
            pass
        return None
