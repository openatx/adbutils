#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Created on Mon May 06 2024 14:41:10 by codeskyblue
"""

import pathlib
from unittest import mock
from adbutils._proto import ShellReturn
import pytest
import adbutils
from adbutils.errors import AdbError
from adb_server import EXEC_OUTPUTS, SCREENCAP_PNG, SCREENCAP_PNG_SIZE


def test_shell_pwd(adb: adbutils.AdbClient):
    d = adb.device(serial="123456")
    assert d.shell("pwd") == "/"

def test_shell2_pwd(adb: adbutils.AdbClient):
    d = adb.device(serial="123456")
    assert d.shell2("pwd") == ShellReturn(
        command='pwd', 
        returncode=0, 
        output='/\n',
    )

def test_shellv2_stdout(adb: adbutils.AdbClient):
    d = adb.device(serial="123456")
    assert d.shell2("v2-stdout-only", v2=True) == ShellReturn(
        command='v2-stdout-only', 
        returncode=0, 
        output='this is stdout\n', 
        stdout='this is stdout\n',
    )

def test_shellv2_stderr(adb: adbutils.AdbClient):
    d = adb.device(serial="123456")
    assert d.shell2("v2-stdout-stderr", rstrip=True, v2=True) == ShellReturn(
        command='v2-stdout-stderr', 
        returncode=1, 
        output='this is stdout\nthis is stderr',
        stdout='this is stdout',
        stderr='this is stderr'
    )

def test_shell_screenshot(adb: adbutils.AdbClient):
    d = adb.device(serial="123456")
    
    def mock_shell(cmd: str, encoding='utf-8', **kwargs):
        if cmd == "wm size":
            return "Physical size: 1080x1920"
        return ""

    d.shell = mock_shell
    d.exec_out = lambda cmdargs: b""
    d.rotation = lambda: 0

    # Both transports fail, so screenshot() has to use its black image
    # fallback; pull is patched so the test does not need a sync server.
    with mock.patch("adbutils.sync.Sync.pull", side_effect=AdbError("no file")):
        with pytest.raises(AdbError):
            d.screenshot(error_ok=False)
        pil_img = d.screenshot(error_ok=True)
    assert pil_img.size == (1080, 1920)
    
    # assert pixel is blank
    pixel = pil_img.getpixel((0, 0))
    assert pixel[:3] == (0, 0, 0)


def test_exec_out_returns_raw_bytes(adb: adbutils.AdbClient):
    d = adb.device(serial="123456")
    # LF, CRLF and NUL bytes must survive untouched: exec: has no pty
    assert d.exec_out("raw-bytes") == EXEC_OUTPUTS["raw-bytes"]


def test_exec_out_empty_output(adb: adbutils.AdbClient):
    d = adb.device(serial="123456")
    assert d.exec_out("empty") == b""


def test_exec_out_rejects_empty_command(adb: adbutils.AdbClient):
    d = adb.device(serial="123456")
    with pytest.raises(ValueError):
        d.exec_out([])


def test_exec_out_unsupported_service(adb: adbutils.AdbClient):
    d = adb.device(serial="123456")
    with pytest.raises(AdbError, match="unknown service"):
        d.exec_out("not-mocked")


def test_screenshot_trims_display_warning(adb: adbutils.AdbClient):
    # Regression test for #133: the png arrives behind a multi-display warning
    d = adb.device(serial="123456")
    im = d.screenshot()
    assert im.size == SCREENCAP_PNG_SIZE
    assert im.getpixel((0, 0)) == (255, 0, 0)


def test_screenshot_falls_back_to_file_and_pull(adb: adbutils.AdbClient):
    # adb builds before exec-out (2016) need screencap to a file + sync pull
    d = adb.device(serial="123456")
    d.exec_out = mock.Mock(side_effect=AdbError("unknown service: exec"))
    shell_calls = []

    def mock_shell(cmd, encoding="utf-8", **kwargs):
        shell_calls.append(cmd)
        return ""

    def fake_pull(sync_self, src, dst):
        pathlib.Path(dst).write_bytes(SCREENCAP_PNG)
        return len(SCREENCAP_PNG)

    d.shell = mock_shell
    with mock.patch("adbutils.sync.Sync.pull", new=fake_pull):
        im = d.screenshot()

    assert im.size == SCREENCAP_PNG_SIZE
    assert im.getpixel((0, 0)) == (255, 0, 0)
    remote_path = shell_calls[0][-1]
    assert shell_calls[0][:2] == ["screencap", "-p"]
    assert remote_path.startswith("/data/local/tmp/adbutils-screencap-")
    assert shell_calls[-1] == ["rm", "-f", remote_path]


def test_window_size(adb: adbutils.AdbClient):
    d = adb.device(serial="123456")
    
    def mock_shell(cmd):
        if cmd == "wm size":
            return "Physical size: 1080x1920"
        if cmd == "dumpsys display":
            return "mViewports=[DisplayViewport{orientation=0]"
        return ""
    
    d.shell = mock_shell
    wsize = d.window_size()
    assert wsize.width == 1080
    assert wsize.height == 1920


def test_shell_battery(adb: adbutils.AdbClient):
    d = adb.device(serial="123456")

    _DUMPSYS_BATTERY_ = """Current Battery Service state:
    AC powered: false
    USB powered: true
    Wireless powered: false
    Dock powered: false
    Max charging current: 0
    Max charging voltage: 0
    Charge counter: 10000
    status: 4
    health: 2
    present: true
    level: 80
    scale: 100
    voltage: 5000
    temperature: 250
    technology: Li-ion"""
    d.shell = lambda cmd: _DUMPSYS_BATTERY_
    
    bat = d.battery()
    assert bat.ac_powered == False
    assert bat.wireless_powered == False
    assert bat.usb_powered == True
    assert bat.dock_powered == False
    assert bat.max_charging_current == 0
    assert bat.max_charging_voltage == 0
    assert bat.charge_counter == 10000
    assert bat.status == 4
    assert bat.health == 2
    assert bat.present == True
    assert bat.level == 80
    assert bat.scale == 100
    assert bat.voltage == 5000
    assert bat.temperature == 25.0
    assert bat.technology == "Li-ion"
    