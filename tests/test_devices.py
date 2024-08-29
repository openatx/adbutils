# coding: utf-8
#


import pytest
import adbutils
from adbutils._proto import AdbDeviceInfo

def test_host_devices(adb: adbutils.AdbClient):
    _dev = adb.device("any")
    assert _dev.shell(cmdargs="enable-devices") == 'debug command executed'
    devices = adb.list(extended=False)
    assert devices == [AdbDeviceInfo(serial="dummydevice", state="device", tags={})]


def test_host_devices_invalid(adb: adbutils.AdbClient):
    _dev = adb.device("any")
    assert _dev.shell(cmdargs="invalidate-devices") == 'debug command executed'
    devices = adb.list(extended=False)
    assert devices == []


def test_host_devices_extended(adb: adbutils.AdbClient):
    _dev = adb.device("any")
    assert _dev.shell(cmdargs="enable-devices") == 'debug command executed'
    devices = adb.list(extended=True)
    assert devices == [AdbDeviceInfo(serial="dummydevice", state="device", tags={"product": "test_emu", "model": "test_model", "device": "test_device"})]


def test_host_devices_extended_invalid(adb: adbutils.AdbClient):
    _dev = adb.device("any")
    assert _dev.shell(cmdargs="invalidate-devices") == 'debug command executed'
    devices = adb.list(extended=True)
    assert devices == []