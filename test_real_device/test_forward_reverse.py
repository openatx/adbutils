# coding: utf-8
#
import pytest

from adbutils import AdbDevice


def test_forward(device: AdbDevice):
    """
    Test commands:
    
        adb forward --list
        adb -s xxxxx forward --list
    """
    device.forward("tcp:11221", "tcp:7912")
    exists = False
    for item in device.forward_list():
        if item.local == "tcp:11221" and item.remote == "tcp:7912":
            assert item.serial == device.serial
            exists = True
    assert exists

    lport = device.forward_port("tcp:7912")
    assert isinstance(lport, int)


def test_reverse(device: AdbDevice):
    """
    Test commands:
    
        adb reverse --list
        adb -s xxxxx reverse --list
    """
    device.reverse("tcp:12345", "tcp:4000")
    exists = False
    for item in device.reverse_list():
        if item.remote == "tcp:12345" and item.local == "tcp:4000":
            exists = True
    assert exists
