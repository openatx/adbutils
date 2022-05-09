#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Created on Mon May 09 2022 17:31:25 by codeskyblue
"""

from adbutils import AdbDevice, adb


def test_current_app(device: AdbDevice):
    info = device.current_app()
    assert 'package' in info
    assert 'activity' in info


def test_client_shell():
    ds = adb.device_list()
    serial = ds[0].serial
    assert adb.shell(serial, 'pwd').rstrip() == "/"