from zfeiq_core.events import EventBus, TOPIC_UDP_RECEIVED
from zfeiq_core.api import ZFeiQCore

class FakeNetworkService:
    def __init__(self, bus, bind_ip='0.0.0.0', port=2425, local_addrs=None):
        self._bus = bus
        self.bind_ip = bind_ip
        self.port = port
        self._running = False
        self._local_addrs = local_addrs or []
    def start(self):
        self._running = True
    def stop(self):
        self._running = False
    def get_bind_info(self):
        return {'bind_ip': self.bind_ip, 'port': self.port, 'local_addrs': self._local_addrs}

b = EventBus()
core = ZFeiQCore(b)
core.set_config('bind_locked', True)
fake = FakeNetworkService(b, bind_ip='0.0.0.0', local_addrs=['192.168.1.5'])
core.attach_network(fake)
print('before publish, bind_locked:', core.get_config('bind_locked'), 'fake.bind_ip:', fake.bind_ip)
b.publish(TOPIC_UDP_RECEIVED, {'data':b'hi','addr':('192.168.1.100',12345)})
print('after publish, fake.bind_ip:', fake.bind_ip)
