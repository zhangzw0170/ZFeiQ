from zfeiq_core.events import EventBus
from zfeiq_core.api import ZFeiQCore
from zfeiq_cli.adapter import CLIAdapter


def test_bind_lock_and_unlock(tmp_path):
    bus = EventBus()
    core = ZFeiQCore(bus)
    adapter = CLIAdapter(username='tester', core=core)

    # set bind and ensure it's persisted and locked
    adapter.cmd_set_bind('127.0.0.1')
    assert core.get_config('bind') == '127.0.0.1'
    assert core.get_config('bind_locked') is True

    # now unlock
    adapter.cmd_unset_bind()
    # unlocked: bind_locked False and bind cleared (None or falsy)
    assert core.get_config('bind_locked') is False or core.get_config('bind_locked') == False
    b = core.get_config('bind')
    assert not b or b is None


if __name__ == '__main__':
    test_bind_lock_and_unlock(None)
    print('test_bind_unlock: PASS')
