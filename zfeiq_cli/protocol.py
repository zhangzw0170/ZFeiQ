import time
import random
from typing import Tuple, Dict, Any

# IPMSG core commands
IPMSG_BR_ENTRY = 0x00000001
IPMSG_BR_EXIT = 0x00000002
IPMSG_ANSENTRY = 0x00000003
IPMSG_BR_ABSENCE = 0x00000004
IPMSG_SENDMSG = 0x00000020
IPMSG_RECVMSG = 0x00000021
IPMSG_GETFILEDATA = 0x00000060
IPMSG_RELEASEFILES = 0x00000061

# options
IPMSG_SENDCHECKOPT = 0x00000100  # request recv ack
# Best-effort guess for file-attach option flag (upper bits beyond CMD_MASK)
# This value aligns with common implementations using high-bit options.
# Per IPMSG spec, file-attach option uses high-bit flag 0x00200000
IPMSG_FILEATTACHOPT = 0x00200000

VERSION = "1"

# NOTE: The following are provisional values for list retrieval commands
# used intra-implementation. They may be adjusted to match official IPMSG
# constants in a future iteration after cross-compat validation.
IPMSG_GETLIST = 0x00000018
IPMSG_ANSLIST = 0x00000019

# provisional: public key exchange (align with common IPMSG usage)
IPMSG_GETPUBKEY = 0x00000016
IPMSG_ANSPUBKEY = 0x00000017


def now_ms() -> int:
    return int(time.time() * 1000)


def gen_packet_no() -> int:
    # millisecond timestamp + small random to avoid collision in fast sends
    return (now_ms() & 0x7FFFFFFF) + random.randint(1, 999)


def build_packet(username: str, hostname: str, command: int, extension: str = "", encoding: str = "utf-8") -> bytes:
    packet_no = gen_packet_no()
    # IPMSG packet: ver:packetNo:username:hostname:command:extension
    # extension text is raw UTF-8 string; fields beyond can be separated by \0 if needed
    base = f"{VERSION}:{packet_no}:{username}:{hostname}:{command}:"
    return (base + (extension or "")).encode(encoding, errors="ignore")


def build_packet_with_no(packet_no: int, username: str, hostname: str, command: int, extension: str = "", encoding: str = "utf-8") -> bytes:
    base = f"{VERSION}:{packet_no}:{username}:{hostname}:{command}:"
    return (base + (extension or "")).encode(encoding, errors="ignore")


def parse_packet(data: bytes) -> Tuple[Dict[str, Any], str]:
    # Try utf-8 first, fallback to gbk to improve interop with FeiQ
    try:
        text = data.decode("utf-8")
    except Exception:
        try:
            text = data.decode("gbk", errors="replace")
        except Exception:
            text = data.decode("latin-1", errors="replace")
    # split into first 5 colons, rest is extension
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
    except ValueError:
        command = 0
    return ({
        "ver": ver,
        "packet_no": packet_no,
        "username": username,
        "hostname": hostname,
        "command": command,
    }, extension)


CMD_MASK = 0x000000ff


def base_command(cmd: int) -> int:
    return cmd & CMD_MASK


def encode_list_entries(entries: list) -> str:
    """Encode host list entries into extension text.

    Format: one entry per line: username\tip\thostname
    """
    lines = []
    for e in entries:
        lines.append(f"{e['username']}\t{e['ip']}\t{e['hostname']}")
    return "\n".join(lines)


def encode_fileattach_lines(files: list) -> str:
    """Encode IPMSG file-attach lines for SENDMSG extension.

    Each element in files should be a dict with keys: id (int), name (str), size (int), mtime (int epoch), attr (int)
    Lines are separated by BEL (\a) to align with common IPMSG practice.
    Format per line: id:filename:size:mtime:attr
    """
    segs = []
    for f in files:
        fid = f.get("id", 0)
        name = f.get("name", "file")
        size = int(f.get("size", 0))
        mtime = int(f.get("mtime", int(time.time())))
        attr = int(f.get("attr", 0))
        segs.append(f"{fid}:{name}:{size}:{mtime}:{attr}")
    # Use BEL as separator; some clients also accept newlines, but BEL is safer for interop
    return "\a".join(segs)


def decode_fileattach_lines(ext: str) -> list:
    """Decode file-attach lines from SENDMSG extension.

    Accept both BEL (\a) and newline separators.
    Return list of dicts: {id, name, size, mtime, attr}
    """
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


def decode_list_entries(ext: str) -> list:
    """Decode extension text into host list entries.

    Returns list of dicts with keys: username, ip, hostname
    """
    out = []
    for ln in (ext or "").splitlines():
        if not ln.strip():
            continue
        parts = ln.split("\t")
        if len(parts) >= 3:
            out.append({"username": parts[0], "ip": parts[1], "hostname": parts[2]})
    return out
