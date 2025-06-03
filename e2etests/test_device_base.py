import pytest

import adbutils
from adbutils import AdbDevice, Network, BrightnessMode
from adbutils.errors import AdbSyncError


def test_shell(device: AdbDevice):
    for text in ("foo", "?", "&", "but    123"):
        output = device.shell(['echo', '-n', text])
        assert output == text

    output = device.shell("pwd", rstrip=False)
    assert output in ["/\n", "/\r\n"]


def test_shell_without_encoding(device: AdbDevice):
    output = device.shell("echo -n hello", encoding=None)
    assert output == b"hello"

    ret = device.shell2("echo -n hello", encoding=None)
    assert ret.output == b"hello"


def test_shell_stream(device: AdbDevice):
    # c = device.shell(["echo", "-n", "hello world"], stream=True)
    c = device.open_shell("echo -n 'hello world'")
    output = c.read_until_close()
    assert output == "hello world"


def test_adb_shell_raise_timeout(device: AdbDevice):
    with pytest.raises(adbutils.AdbTimeout):
        device.shell("sleep 10", timeout=1.0)


def test_shell2(device: AdbDevice):
    cmd = "echo -n 'hello'; false"
    res = device.shell2(cmd)
    assert res.output == "hello"
    assert res.returncode == 1
    assert res.command == cmd


def test_get_xxx(device: AdbDevice):
    assert device.get_serialno()
    assert device.get_state() == "device"
    # adb connect device devpath is "unknown"
    # assert device.get_devpath().startswith("usb:")


def test_transport(client: adbutils.AdbClient):
    infos = client.list(extended=True)
    transport_id = infos[0].transport_id
    dev = client.device(transport_id=transport_id)
    files = dev.sync.list('/data/local/tmp')
    assert isinstance(files, list)
    
    forward_list = dev.forward_list()
    assert isinstance(forward_list, list)


def test_framebuffer(device: AdbDevice):
    try:
        im = device.framebuffer()
        assert im.size
    except NotImplementedError:
        pass