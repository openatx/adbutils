# coding: utf-8
#
import adbutils
import pytest
from adbutils import AdbClient, DeviceEvent


adb = adbutils.AdbClient("127.0.0.1", 5037)


def test_server_version():
    version = adb.server_version()
    assert isinstance(version, int)


def test_adb_disconnect():
    with pytest.raises(adbutils.AdbError):
        adb.disconnect("127.0.0.1:1234", raise_error=True)


def test_wait_for():
    adb.wait_for("127.0.0.1:1234", state="disconnect", timeout=1)
    adb.wait_for(transport="usb", state="device", timeout=1)

    with pytest.raises(adbutils.AdbTimeout):
        adb.wait_for(transport="usb", state="disconnect", timeout=.5)


def test_track_device():
    it = adb.track_devices()
    evt = next(it)
    assert isinstance(evt, DeviceEvent)