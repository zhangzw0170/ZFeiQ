import os
from zfeiq_core.events import EventBus
from zfeiq_core.api import ZFeiQCore
from zfeiq_cli.adapter import CLIAdapter


def test_download_dir_used_by_adapter(tmp_path):
    # prepare core with persisted download_dir
    bus = EventBus()
    core = ZFeiQCore(bus)
    dd = str(tmp_path / 'mydownloads')
    core.set_config('download_dir', dd)

    # create adapter using injected core
    adapter = CLIAdapter(username='tester', core=core)
    assert adapter.download_dir == dd
    # directory should exist or be creatable when adapter starts
    # adapter initialization doesn't force-create injected path, ensure core value respected
    print('adapter.download_dir =', adapter.download_dir)


if __name__ == '__main__':
    test_download_dir_used_by_adapter(__import__('pathlib').Path('.').resolve())
    print('test_download_dir_integration: PASS')
