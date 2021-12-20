# coding: utf-8
#
import adbutils
import pytest
from adbutils import adb


def test_server_version():
    client = adbutils.AdbClient("127.0.0.1", 5037)
    version = client.server_version()
    assert isinstance(version, int)


def test_shell(device):
    output = device.shell("pwd")
    assert output == "/"

    output = device.shell("pwd", rstrip=False)
    assert output in ["/\n", "/\r\n"]


def test_adb_connect(device: adbutils.AdbDevice):
    with pytest.raises(adbutils.AdbTimeout):
        device.shell("sleep 10", timeout=1.0)


def test_adb_disconnect():
    with pytest.raises(adbutils.AdbError):
        adb.disconnect("127.0.0.1:1234", raise_error=True)


def test_wait_for():
    adb.wait_for("127.0.0.1:1234", state="disconnect", timeout=1)
    adb.wait_for(transport="usb", state="device", timeout=1)

    with pytest.raises(adbutils.AdbTimeout):
        adb.wait_for(transport="usb", state="disconnect", timeout=.5)


def test_get_xxx(device: adbutils.AdbDevice):
    assert device.get_serialno()
    assert device.get_state() == "device"
    assert device.get_devpath().startswith("usb:")
