# coding: utf-8
#

import sys
from unittest.mock import Mock

from adbutils import __main__ as cli
from adbutils._proto import FileInfo
from adbutils.sync import Sync


def test_cli_push_calls_sync_push(tmp_path, monkeypatch):
    """Regression test for #138: --push must not pass unsupported arguments.

    The CLI used to call Sync.push(..., filesize=...) while that method only
    accepts (src, dst, mode, check), so every `python -m adbutils --push` run
    failed with a TypeError before any data was sent.
    """
    local = tmp_path / "local.txt"
    local.write_bytes(b"hello android")

    device = Mock()
    sync = Sync(device)
    pushed = {}

    # Keep the real Sync.push signature in play but skip the adb transport.
    monkeypatch.setattr(sync, "stat", lambda path: FileInfo(0, 0, None, path))

    def fake_push_file(src, dst, mode=0o755, check=False):
        data = b""
        while True:
            chunk = src.read(4096)
            if not chunk:
                break
            data += chunk
        pushed.update(data=data, dst=dst, mode=mode, check=check)
        return len(data)

    monkeypatch.setattr(sync, "_push_file", fake_push_file)
    device.sync = sync
    monkeypatch.setattr(cli.adbclient, "device", lambda serial=None: device)
    monkeypatch.setattr(sys, "argv",
                        ["adbutils", "--push", f"{local}:/sdcard/remote.txt"])

    cli.main()

    assert pushed == {
        "data": b"hello android",
        "dst": "/sdcard/remote.txt",
        "mode": 0o755,
        "check": False,
    }
