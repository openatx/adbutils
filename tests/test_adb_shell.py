#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Created on Mon May 06 2024 14:41:10 by codeskyblue
"""

import adbutils


def test_shell_pwd(adb: adbutils.AdbClient):
    d = adb.device(serial="123456")
    assert d.shell("pwd") == "/"


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