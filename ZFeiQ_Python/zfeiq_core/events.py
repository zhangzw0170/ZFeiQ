from typing import Callable, Dict, List, Any


class EventBus:
    """A minimal in-process pub/sub event bus.

    - subscribe(topic, callback)
    - publish(topic, payload)
    - unsubscribe(topic, callback)
    """

    def __init__(self):
        self._subs: Dict[str, List[Callable[[Any], None]]] = {}

    def subscribe(self, topic: str, callback: Callable[[Any], None]) -> None:
        self._subs.setdefault(topic, []).append(callback)

    def unsubscribe(self, topic: str, callback: Callable[[Any], None]) -> None:
        if topic in self._subs:
            try:
                self._subs[topic].remove(callback)
            except ValueError:
                pass

    def publish(self, topic: str, payload: Any) -> None:
        for cb in list(self._subs.get(topic, [])):
            try:
                cb(payload)
            except Exception:
                # swallow exceptions in callbacks to keep bus stable
                pass


# Common topics
TOPIC_MSG_INCOMING = "msg.incoming"
TOPIC_MSG_SENT = "msg.sent"
TOPIC_USER_ONLINE = "user.online"
TOPIC_FILE_OFFER = "file.offer"
TOPIC_UDP_RECEIVED = "net.udp.recv"
TOPIC_FILE_PROGRESS = "file.progress"
TOPIC_FILE_COMPLETE = "file.complete"
TOPIC_NET_REBIND = "net.rebind"
TOPIC_USER_OFFLINE = "user.offline"
