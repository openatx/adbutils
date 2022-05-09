# coding: utf-8

import pytest
from adbutils import adb, AdbDevice


@pytest.fixture(scope="session")
def device():
    print("Fixture device")
    return adb.device()


@pytest.fixture
def device_tmp_path(device: AdbDevice):
    yield "/data/local/tmp/hi.txt"
    device.remove("/data/local/tmp/hi.txt")
