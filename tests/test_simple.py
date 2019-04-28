# coding: utf-8
#
import adbutils
import pytest
from adbutils import adb


def test_connect_adb_server():
    client = adbutils.AdbClient("127.0.0.1", 5037)
    version = client.server_version()
    assert isinstance(version, int)


def test_shell(device):
    output = device.shell("pwd")
    assert output.strip() == "/"
