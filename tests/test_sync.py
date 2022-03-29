# coding: utf-8
#
import io
import pathlib
import adbutils

def test_sync_pull_push(device: adbutils.AdbDevice, device_tmp_path, tmp_path: pathlib.Path):
    src = io.BytesIO(b"Hello 1")
    device.sync.push(src, device_tmp_path)
    assert b"Hello 1" == device.sync.read_bytes(device_tmp_path)

    device.sync.push(b"Hello 12", device_tmp_path)
    assert "Hello 12" == device.sync.read_text(device_tmp_path)

    target_path = tmp_path / "hi.txt"
    target_path.write_text("Hello Android")
    dst_path = tmp_path / "dst.txt"
    dst_path.unlink(missing_ok=True)
    
    device.sync.push(target_path, device_tmp_path)
    assert "Hello Android" == device.sync.read_text(device_tmp_path)
    device.sync.pull(device_tmp_path, dst_path)
    assert "Hello Android" == dst_path.read_text(encoding="utf-8")

    data = b""
    for chunk in device.sync.iter_content(device_tmp_path):
        data += chunk
    assert b"Hello Android" == data
