# coding: utf-8
#
import io


def test_sync_pull_push(device, device_tmp_path, tmp_path):
    src = io.BytesIO(b"Hello Android")
    device.sync.push(src, device_tmp_path)

    target_path = tmp_path / "hi.txt"
    device.sync.pull(device_tmp_path, target_path.as_posix())
    with target_path.open('rb') as f:
        assert b"Hello Android" == f.read()

    data = b""
    for chunk in device.sync.iter_content(device_tmp_path):
        data += chunk

    assert b"Hello Android" == data
