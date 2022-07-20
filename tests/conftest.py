# coding: utf-8

import pytest
from adbutils import adb, AdbDevice


@pytest.fixture(scope="session")
def device():
    print("Fixture device")
    return adb.device()


@pytest.fixture
def device_tmp_path(device: AdbDevice):
    tmp_path = "/data/local/tmp/Hi-世界.txt"
    yield tmp_path
    device.remove(tmp_path)
