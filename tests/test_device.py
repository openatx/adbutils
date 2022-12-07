"""
extra functions test

效果生效与否不好判定（例如屏幕亮暗），部分用例仅作冒烟测试
"""

import io
import pathlib
import re
import time

import pytest

import adbutils
from adbutils import AdbDevice, Network


def test_shell(device: AdbDevice):
    for text in ("foo", "?", "&", "but    123"):
        output = device.shell(['echo', '-n', text])
        assert output == text

    output = device.shell("pwd", rstrip=False)
    assert output in ["/\n", "/\r\n"]

def test_shell_stream(device: AdbDevice):
    c = device.shell(["echo", "-n", "hello world"], stream=True)
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


def test_keyevent(device: AdbDevice):
    # make sure no error raised
    device.keyevent(4)


def test_switch_screen(device: AdbDevice):
    device.switch_screen(False)
    device.switch_screen(True)


def test_switch_airplane(device: AdbDevice):
    device.switch_airplane(True)
    device.switch_airplane(False)


def test_switch_wifi(device: AdbDevice):
    device.switch_wifi(False)
    device.switch_wifi(True)


def test_swipe(device: AdbDevice):
    device.swipe(100, 100, 400, 400)


def test_click(device: AdbDevice):
    device.click(100, 100)


def test_send_keys(device: AdbDevice):
    device.send_keys("1234")


def test_wlan_ip(device: AdbDevice):
    device.switch_airplane(False)
    device.switch_wifi(True)
    time.sleep(3)
    ip = device.wlan_ip()
    assert ip, 'ip is empty'


def test_app_start_stop(device: AdbDevice):
    d = device
    package_name = "io.appium.android.apis"
    if package_name not in d.list_packages():
        pytest.skip(package_name + " should be installed, to start test")
    d.app_start(package_name)
    time.sleep(1)
    assert device.app_current().package == package_name
    d.app_stop(package_name)
    time.sleep(.5)
    assert device.app_current().package != package_name


def test_sync_pull_push(device: AdbDevice, device_tmp_path, tmp_path: pathlib.Path):
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


def test_screenshot(device: AdbDevice):
    im = device.screenshot()
    assert im.mode == "RGB"


@pytest.mark.skip("huawei is not supported")
def test_screenrecord(device: AdbDevice, tmp_path: pathlib.Path):
    r = device.screenrecord()
    time.sleep(5)
    target_path = tmp_path.joinpath("video.mp4")
    r.stop_and_pull(target_path)
    assert target_path.exists()
    

def test_app_info(device: AdbDevice):
    pinfo = device.app_current()
    app_info = device.app_info(pinfo.package)
    assert app_info.package_name is not None


def test_window_size(device: AdbDevice):
    w, h = device.window_size()
    assert isinstance(w, int)
    assert isinstance(h, int)


def test_is_screen_on(device: AdbDevice):
    bool_result = device.is_screen_on()
    assert isinstance(bool_result, bool)


def test_open_browser(device: AdbDevice):
    device.open_browser("https://example.org")


def test_dump_hierarchy(device: AdbDevice):
    output = device.dump_hierarchy()
    assert output.startswith("<?xml")
    assert output.rstrip().endswith("</hierarchy>")


def test_remove(device: AdbDevice):
    remove_path = "/data/local/tmp/touch.txt"
    device.shell(["touch", remove_path])
    assert device.sync.exists(remove_path)
    device.remove(remove_path)
    assert not device.sync.exists(remove_path)


# def test_create_connection(device: AdbDevice, device_tmp_path: str):
#     device.sync.push(b"hello", device_tmp_path)
#     device.create_connection(Network.LOCAL_FILESYSTEM, device_tmp_path)

def test_logcat(device: AdbDevice, tmp_path: pathlib.Path):
    logcat_path = tmp_path / "logcat.txt"
    logcat = device.logcat(logcat_path, clear=True, command="logcat -v time", re_filter="I/TAG")
    device.shell(["log", "-p", "i", "-t", "TAG", "hello"])
    time.sleep(.1)
    logcat.stop()
    assert logcat_path.exists()
    assert re.compile(r"I/TAG.*hello").search(logcat_path.read_text(encoding="utf-8"))