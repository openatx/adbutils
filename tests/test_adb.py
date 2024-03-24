# coding: utf-8
#


import adbutils

def test_server_version(adb: adbutils.AdbClient):
    assert adb.server_version() == 1234