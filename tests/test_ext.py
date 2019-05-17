"""
extra functions test

效果生效与否不好判定（例如屏幕亮暗），部分用例仅作冒烟测试
"""

import adbutils
import time

adb = adbutils.AdbClient(host="127.0.0.1", port=5037)
target_device = adb.device()


def test_say_hello():
    assert target_device.say_hello() == 'hello from {}'.format(target_device.serial)


def test_input_key_event():
    # make sure no error raised
    target_device.input_key_event(4)


def test_clean_cache():
    # TODO 需要root，且需要一个用过的app的包名
    pass


def test_switch_screen():
    target_device.switch_screen(False)
    target_device.switch_screen(True)


def test_switch_airplane():
    target_device.switch_airplane(True)
    target_device.switch_screen(False)


def test_switch_wifi():
    target_device.switch_wifi(False)
    target_device.switch_wifi(True)


def test_start_activity():
    # TODO need a app package name
    pass


def test_start_broadcast():
    # TODO need a broadcast name
    pass


def test_swipe():
    target_device.swipe((100, 100), (400, 400))


def test_click():
    target_device.click((100, 100))


def test_set_ime():
    # TODO need an ime package name
    pass


def test_make_dir():
    target_device.make_dir('/sdcard/testonly4adbutils')


def test_remove_dir():
    target_device.remove_dir('/sdcard/testonly4adbutils')


def test_get_ip_address():
    target_device.switch_airplane(True)
    target_device.switch_wifi(True)
    time.sleep(3)
    ip = target_device.get_ip_address()
    assert ip, 'ip is empty'
