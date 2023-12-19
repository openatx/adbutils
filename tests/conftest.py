# coding: utf-8

import pytest
from adbutils import adb, AdbDevice
import subprocess
import pathlib


@pytest.fixture(scope="session")
def device():
    print("Fixture device")
    return adb.device()


@pytest.fixture
def device_tmp_path(device: AdbDevice):
    tmp_path = "/data/local/tmp/Hi-世界.txt"
    yield tmp_path
    device.remove(tmp_path)

@pytest.fixture
def device_tmp_dir_path(device: AdbDevice):
    tmp_dir_path = "/sdcard/test_d"
    yield tmp_dir_path
    device.remove_dir(tmp_dir_path)

@pytest.fixture
def local_src_in_dir():
    local_src_in_dir = pathlib.Path('tests/test-assets/test_s')
    yield local_src_in_dir

@pytest.fixture
def local_src_out_dir1():
    local_src_out_dir1 = pathlib.Path('tests/test-assets/test_d1')
    yield local_src_out_dir1
    subprocess.check_output(['rm', '-r', local_src_out_dir1])

@pytest.fixture
def local_src_out_dir2():
    local_src_out_dir2 = pathlib.Path('tests/test-assets/test_d2')
    yield local_src_out_dir2
    subprocess.check_output(['rm', '-r', local_src_out_dir2])