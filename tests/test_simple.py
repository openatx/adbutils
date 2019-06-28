# coding: utf-8
#
import adbutils
import pytest
from adbutils import adb


def test_server_version():
    client = adbutils.AdbClient("127.0.0.1", 5037)
    version = client.server_version()
    assert isinstance(version, int)


def test_shell(device):
    output = device.shell("pwd")
    assert output == "/"

    output = device.shell("pwd", rstrip=False)
    assert output in ["/\n", "/\r\n"]


def test_adb_connect():
    ret = adb.connect("1270.0.0.1:1234")
    assert isinstance(ret, str)