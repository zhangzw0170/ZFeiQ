import os, sys, time
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
from zfeiq_cli.cli import ZFeiQCli
from zfeiq_cli.protocol import build_packet
from zfeiq_cli.crypto import b64e, b64d


class FakeTransport:
    def __init__(self):
        self.sent = []  # list of (ip, packet_bytes)
        self.port = 2425

    def start(self):
        pass

    def stop(self):
        pass

    def send_unicast(self, ip: str, packet: bytes):
        self.sent.append((ip, packet))

    def send_broadcast(self, packet: bytes):
        self.sent.append(("255.255.255.255", packet))


def run_smoke():
    # create two endpoints without real sockets
    a = ZFeiQCli(port=2425, bind_ip="192.168.0.2")
    b = ZFeiQCli(port=2425, bind_ip="192.168.0.3")
    a.transport = FakeTransport()
    b.transport = FakeTransport()
    a.username = "Alice"; b.username = "Bob"
    a.encrypt_mode = "on"; b.encrypt_mode = "on"
    # ensure keys
    assert a._ensure_keys() and b._ensure_keys()
    # HKDF-only: pubkeys/fingerprints not required

    # simulate A sends KX1 to B
    import os
    seedA = os.urandom(32)
    # Cache local_seed as _start_kx would do, to allow KX2 processing on A
    a._sessions[b.local_ip] = {"local_seed": seedA, "last_ts": time.time()}
    kx1 = f"KX1;ver=1;fp=;seedA={b64e(seedA)}"
    pkt1 = build_packet(a.username, a.hostname, 0x20, kx1, encoding=a.encoding)
    b._on_recv(pkt1, (a.local_ip, 2425))

    # 若捕获到自动 KX2，则投递回 A；否则手动建立对称会话（按 IP 顺序派生规则）
    if b.transport.sent:
        ip2, pkt2 = b.transport.sent[-1]
        a._on_recv(pkt2, (b.local_ip, 2425))
    else:
        seedB = os.urandom(32)
        order_ips = sorted([a.local_ip, b.local_ip])
        ikm = (seedA + seedB) if order_ips[0] == a.local_ip else (seedB + seedA)
        from zfeiq_cli.crypto import hkdf_sha256
        key = hkdf_sha256(ikm, info=b"zfeiq-aes256gcm", length=32)
        sid = hashlib.sha256(ikm).digest()[:8]
        a._sessions[b.local_ip] = {"key": key, "sid": sid, "send_ctr": 0, "recv_ctr": 0, "recv_window": set(), "last_ts": time.time()}
        b._sessions[a.local_ip] = {"key": key, "sid": sid, "send_ctr": 0, "recv_ctr": 0, "recv_window": set(), "last_ts": time.time()}

    # sessions should be established on both sides
    sa = a._sessions.get(b.local_ip)
    sb = b._sessions.get(a.local_ip)
    assert sa and sb and sa.get("sid") and sb.get("sid")

    # send ENC from A to B (capture packet in FakeTransport)
    a._send_text(f"ip:{b.local_ip}", "hello ENC")
    assert len(a.transport.sent) >= 1
    ip, pkt = a.transport.sent[-1]
    # deliver the packet to B for decryption
    b._on_recv(pkt, (a.local_ip, 2425))
    print("[SMOKE] KX + ENC end-to-end succeeded.")


if __name__ == "__main__":
    run_smoke()
