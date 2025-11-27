import time
from zfeiq_core import EventBus, ZFeiQCore
from zfeiq_core.services.network import NetworkService
from zfeiq_core import events


def main():
    bus = EventBus()

    def on_msg(payload):
        print("[demo-net] msg incoming:", payload)

    def on_udp(payload):
        print("[demo-net] raw udp:", payload)

    bus.subscribe(events.TOPIC_MSG_INCOMING, on_msg)
    bus.subscribe(events.TOPIC_UDP_RECEIVED, on_udp)

    core = ZFeiQCore(bus)
    net = NetworkService(bus, bind_ip="127.0.0.1", port=2425)
    core.attach_network(net)

    # send a loopback udp packet to self
    net.send_udp("127.0.0.1", 2425, b"Hello from network demo")

    # wait a moment for receive
    time.sleep(0.5)

    net.stop()


if __name__ == "__main__":
    main()
