#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Created on Mon May 09 2022 17:31:25 by codeskyblue
"""

import pytest
from adbutils import AdbDevice, adb


def test_package_info(device: AdbDevice):
    pinfo = device.app_current()
    pinfo = device.package_info(pinfo.package)
    assert pinfo is not None
    assert 'version_name' in pinfo


@pytest.mark.skip("current_app is removed")
def test_current_app(device: AdbDevice):
    info = device.current_app()
    assert 'package' in info
    assert 'activity' in info


def test_client_shell():
    ds = adb.device_list()
    serial = ds[0].serial
    assert adb.shell(serial, 'pwd').rstrip() == "/"