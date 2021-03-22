# coding: utf-8
#
import time
import adbutils


def test_reverse(device: adbutils.AdbDevice):
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
