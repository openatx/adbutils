# coding: utf-8
#


import pytest
import adbutils
from adb_server import encode


def test_encode():
    assert encode(1234) == b'000404d2'


def test_server_version(adb: adbutils.AdbClient):
    assert adb.server_version() == 1234


def test_server_kill(adb: adbutils.AdbClient):
    adb.server_kill()


def test_host_tport_serial(adb: adbutils.AdbClient):
    d = adb.device(serial="not-found")
    # pass
    with pytest.raises(adbutils.AdbError):
        d.open_transport()

    d = adb.device(serial="123456")
    d.open_transport()
