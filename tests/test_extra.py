"""
extra functions test

效果生效与否不好判定（例如屏幕亮暗），部分用例仅作冒烟测试
"""

import adbutils
import time
from adbutils import AdbDevice

# adb = adbutils.AdbClient(host="127.0.0.1", port=5037)
# target_device = adb.device()


def test_say_hello(device: AdbDevice):
    assert device.say_hello() == 'hello from {}'.format(device.serial)


def test_keyevent(device: AdbDevice):
    # make sure no error raised
    device.keyevent(4)


def test_switch_screen(device: AdbDevice):
    device.switch_screen(False)
    device.switch_screen(True)


def test_switch_airplane(device: AdbDevice):
    device.switch_airplane(True)
    device.switch_screen(False)


def test_switch_wifi(device: AdbDevice):
    device.switch_wifi(False)
    device.switch_wifi(True)


def test_swipe(device: AdbDevice):
    device.swipe(100, 100, 400, 400)


def test_click(device: AdbDevice):
    device.click(100, 100)


def test_set_ime(device: AdbDevice):
    # TODO need an ime package name
    pass


def test_wlan_ip(device: AdbDevice):
    device.switch_airplane(True)
    device.switch_wifi(True)
    time.sleep(3)
    ip = device.wlan_ip()
    assert ip, 'ip is empty'
