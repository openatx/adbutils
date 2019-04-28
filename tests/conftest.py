# coding: utf-8

import pytest
from adbutils import adb


@pytest.fixture(scope="session")
def device():
    print("Fixture device")
    return adb.device()


@pytest.fixture
def device_tmp_path(device):
    yield "/data/local/tmp/hi.txt"
    device.shell(["rm", "/data/local/tmp/hi.txt"])
