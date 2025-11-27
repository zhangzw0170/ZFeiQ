from zfeiq_core.events import EventBus
from zfeiq_core.api import ZFeiQCore
from zfeiq_core.services.network import NetworkService


def test_bind_persistence():
    bus = EventBus()
    core = ZFeiQCore(bus)
    # persist a bind value
    core.set_config('bind', '127.0.0.1')

    net = NetworkService(bus)
    core.attach_network(net)

    assert net.bind_ip == '127.0.0.1', f"expected bind_ip applied, got {net.bind_ip}"
    # network should be started (best-effort)
    assert getattr(net, '_running', False) is True

    # cleanup
    try:
        net.stop()
    except Exception:
        pass


if __name__ == '__main__':
    test_bind_persistence()
    print('test_bind_persistence: PASS')
