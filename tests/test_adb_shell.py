#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Created on Mon May 06 2024 14:41:10 by codeskyblue
"""

from unittest import mock
from adbutils._proto import ShellReturn
import pytest
import adbutils
from adbutils.errors import AdbError


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
        if encoding is None:
            return b""
        if cmd == "wm size":
            return "Physical size: 1080x1920"
        return b""

    d.shell = mock_shell
    d.rotation = lambda: 0

    with pytest.raises(AdbError):
        d.screenshot(error_ok=False)
    pil_img = d.screenshot(error_ok=True)
    assert pil_img.size == (1080, 1920)
    
    # assert pixel is blank
    pixel = pil_img.getpixel((0, 0))
    assert pixel[:3] == (0, 0, 0)


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
    