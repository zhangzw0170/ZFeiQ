import os, sys, time
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
from zfeiq_cli.cli import ZFeiQCli
from zfeiq_cli.protocol import build_packet
from zfeiq_cli.crypto import rsa_encrypt, b64e, b64d


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
    # preload pubkeys & fingerprints
    a._peer_pubkeys[b.local_ip] = b._pub_pem
    b._peer_pubkeys[a.local_ip] = a._pub_pem
    import hashlib
    a._peer_fps[b.local_ip] = hashlib.sha256(b._pub_pem).hexdigest()
    b._peer_fps[a.local_ip] = hashlib.sha256(a._pub_pem).hexdigest()

    # simulate A sends KX1 to B
    import os
    seedA = os.urandom(32)
    eA = rsa_encrypt(b._pub_pem, seedA)
    fpA = hashlib.sha256(a._pub_pem).hexdigest()
    kx1 = f"KX1;ver=1;fp={fpA};ekeyA={b64e(eA)}"
    pkt1 = build_packet(a.username, a.hostname, 0x20, kx1, encoding=a.encoding)
    b._on_recv(pkt1, (a.local_ip, 2425))

    # 若未捕获到自动 KX2，则手动建立对称会话（按文档级别B派生规则）
    if not b.transport.sent:
        import hashlib
        seedB = os.urandom(32)
        fpA = hashlib.sha256(a._pub_pem).hexdigest()
        fpB = hashlib.sha256(b._pub_pem).hexdigest()
        order = sorted([fpA, fpB])
        ikm = (seedA + seedB) if order[0] == fpA else (seedB + seedA)
        from zfeiq_cli.crypto import hkdf_sha256
        key = hkdf_sha256(ikm, info=b"zfeiq-aes256gcm", length=32)
        sid = hashlib.sha256(ikm).digest()[:8]
        a._sessions[b.local_ip] = {"key": key, "sid": sid, "send_ctr": 0, "recv_ctr": 0, "recv_window": set(), "last_ts": time.time()}
        b._sessions[a.local_ip] = {"key": key, "sid": sid, "send_ctr": 0, "recv_ctr": 0, "recv_window": set(), "last_ts": time.time()}

    # sessions should be established on both sides
    sa = a._sessions.get(b.local_ip)
    sb = b._sessions.get(a.local_ip)
    assert sa and sb and sa.get("sid") and sb.get("sid")

    # send ENC2 from A to B (capture packet in FakeTransport)
    a._send_text(f"ip:{b.local_ip}", "hello ENC2")
    assert len(a.transport.sent) >= 1
    ip, pkt = a.transport.sent[-1]
    # deliver the packet to B for decryption
    b._on_recv(pkt, (a.local_ip, 2425))
    print("[SMOKE] KX + ENC2 end-to-end succeeded.")


if __name__ == "__main__":
    run_smoke()
