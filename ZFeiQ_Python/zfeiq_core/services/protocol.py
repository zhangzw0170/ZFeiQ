from typing import Tuple, Dict, Any, List
import time

# Minimal compatible parser inspired by original CLI implementation
VERSION = "1"
CMD_MASK = 0x000000ff


def now_ms() -> int:
    return int(time.time() * 1000)


def parse_packet(data: bytes) -> Tuple[Dict[str, Any], str]:
    # Try utf-8 first, fallback to gbk/latin-1 for interop
    try:
        text = data.decode("utf-8")
    except Exception:
        try:
            text = data.decode("gbk", errors="replace")
        except Exception:
            text = data.decode("latin-1", errors="replace")
    parts = text.split(":", 5)
    if len(parts) < 5:
        raise ValueError("invalid ipmsg packet: not enough parts")
    ver = parts[0]
    packet_no = int(parts[1]) if parts[1].isdigit() else 0
    username = parts[2]
    hostname = parts[3]
    cmd_str = parts[4]
    extension = parts[5] if len(parts) > 5 else ""
    try:
        command = int(cmd_str)
    except Exception:
        command = 0
    return ({
        "ver": ver,
        "packet_no": packet_no,
        "username": username,
        "hostname": hostname,
        "command": command,
    }, extension)


def base_command(cmd: int) -> int:
    return cmd & CMD_MASK


def decode_fileattach_lines(ext: str) -> List[Dict[str, Any]]:
    if not ext:
        return []
    parts = []
    for seg in ext.split("\a"):
        parts.extend(seg.splitlines())
    out = []
    for ln in parts:
        if not ln:
            continue
        cols = ln.split(":", 4)
        if len(cols) >= 5 and cols[0].isdigit():
            try:
                out.append({
                    "id": int(cols[0]),
                    "name": cols[1],
                    "size": int(cols[2]) if cols[2].isdigit() else 0,
                    "mtime": int(cols[3]) if cols[3].isdigit() else 0,
                    "attr": int(cols[4]) if cols[4].isdigit() else 0,
                })
            except Exception:
                continue
    return out


class ProtocolService:
    """Converts raw UDP payloads into core entities and emits events via bus.

    Usage: instantiate and call `handle_raw_packet(payload, bus, entities_module)`
    where `payload` is dict {data, addr}, `bus` is EventBus and
    `entities_module` contains `Message` and `FileOffer` classes (importable).
    """

    def __init__(self):
        pass

    def handle_raw_packet(self, payload: Dict[str, Any], bus, entities_module):
        data = payload.get("data")
        addr = payload.get("addr")
        if not data:
            return
        try:
            pkt, ext = parse_packet(data)
        except Exception:
            # fallback: publish raw as incoming text
            try:
                text = data.decode("utf-8", errors="replace")
            except Exception:
                text = str(data)
            # create Message entity
            msg = entities_module.Message(from_user=addr[0], to="all", text=text)
            bus.publish("msg.incoming", msg.dict())
            return
        cmd = pkt.get("command", 0)
        bc = base_command(cmd)
        username = pkt.get("username") or addr[0]
        # handle SENDMSG with optional file attach
        if bc == 0x20:  # IPMSG_SENDMSG
            # check ext for file attachments
            files = decode_fileattach_lines(ext)
            if files:
                # publish a file offer event per attachment
                for f in files:
                    fo = entities_module.FileOffer(
                        filename=f.get("name", ""),
                        size=f.get("size", 0),
                        from_user=username,
                        to="all",
                        ts=time.time(),
                    )
                    bus.publish("file.offer", fo.dict())
            # also publish text message if extension contains other text
            # Some clients send message body before fileattach; conservative: if ext contains non-fileattach text, treat as text
            # For now publish ext as message text when no fileattach or ext contains extra text
            # If ext equals fileattach serialization, message may be empty — it's acceptable
            if ext and not files:
                msg = entities_module.Message(from_user=username, to="all", text=ext)
                bus.publish("msg.incoming", msg.dict())
            return
        # other commands: BR_ENTRY/EXIT -> user online/offline events
        if bc in (0x01, 0x03):  # BR_ENTRY or ANSENTRY
            bus.publish("user.online", {"username": username, "ip": addr[0]})
            return
        if bc == 0x02:  # BR_EXIT
            from ..events import TOPIC_USER_OFFLINE
            bus.publish(TOPIC_USER_OFFLINE, {"username": username, "ip": addr[0]})
            return
        # fallback: publish raw text as message
        try:
            text = ext if ext else data.decode("utf-8", errors="replace")
        except Exception:
            text = str(data)
        msg = entities_module.Message(from_user=username, to="all", text=text)
        bus.publish("msg.incoming", msg.dict())
        return
