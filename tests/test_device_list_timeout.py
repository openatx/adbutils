# coding: utf-8
#

import contextlib
import socket
import threading
import time

import pytest

import adbutils


@contextlib.contextmanager
def silent_server():
    """A TCP server that accepts a connection but never replies.

    This mimics an unresponsive adb-server (or a non-adb service listening on
    the configured host/port), which used to make device_list() block forever.
    """
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    port = server.getsockname()[1]
    conns = []

    def accept_once():
        try:
            conn, _ = server.accept()
            conns.append(conn)
        except OSError:
            pass

    thread = threading.Thread(target=accept_once, daemon=True)
    thread.start()
    try:
        yield port
    finally:
        for conn in conns:
            conn.close()
        server.close()
        thread.join(timeout=1)


def test_device_list_default_timeout(monkeypatch):
    monkeypatch.setattr(adbutils, "_DEFAULT_HOST_TIMEOUT", 0.2)
    with silent_server() as port:
        client = adbutils.AdbClient(host="127.0.0.1", port=port)
        started = time.monotonic()
        with pytest.raises(adbutils.AdbTimeout):
            client.device_list()
        assert time.monotonic() - started < 5


def test_device_list_explicit_timeout():
    with silent_server() as port:
        client = adbutils.AdbClient(host="127.0.0.1", port=port)
        with pytest.raises(adbutils.AdbTimeout):
            client.device_list(timeout=0.2)
