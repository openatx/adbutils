# coding: utf-8
#

import logging
import threading
import adbutils
from adbutils.server import run_adb_server
import pytest
import time
import socket


def wait_for_port(port, timeout=10):
    start_time = time.time()
    while True:
        if time.time() - start_time > timeout:
            raise TimeoutError(f"Port {port} is not being listened to within {timeout} seconds")
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(0.1)
                s.connect(('localhost', port))
            return
        except (ConnectionRefusedError, OSError, socket.timeout):
            time.sleep(0.1)


@pytest.fixture(scope='session')
def adb_server_fixture():
    th = threading.Thread(target=run_adb_server, name='mock-adb-server')
    th.daemon = True
    th.start()
    wait_for_port(7305)



@pytest.fixture
def adb(adb_server_fixture) -> adbutils.AdbClient:
    logging.basicConfig(level=logging.DEBUG)
    return adbutils.AdbClient(port=7305)