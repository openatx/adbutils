# coding: utf-8
#

import logging
import threading
from unittest import mock
import adbutils
import pytest
import time
import socket
from adb_server import run_adb_server


def check_port(port) -> bool:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.1)
            s.connect(('127.0.0.1', port))
        return True
    except (ConnectionRefusedError, OSError, socket.timeout):
        return False
    

def wait_for_port(port, timeout:float=3, ready: bool = True):
    start_time = time.time()
    while True:
        if time.time() - start_time > timeout:
            raise TimeoutError(f"Port {port} is not being listened to within {timeout} seconds")
        if check_port(port) == ready:
            return
        time.sleep(0.1)


@pytest.fixture(scope='function')
def adb_server_fixture():
    th = threading.Thread(target=run_adb_server, name='mock-adb-server')
    th.daemon = True
    th.start()
    wait_for_port(7305)
    yield
    adbutils.AdbClient(port=7305).server_kill()



@pytest.fixture
def adb(adb_server_fixture) -> adbutils.AdbClient:
    logging.basicConfig(level=logging.DEBUG)
    return adbutils.AdbClient(port=7305)