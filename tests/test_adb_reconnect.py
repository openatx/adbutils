# -*- coding: utf-8 -*-
#

"""Regression tests for a restarted adb server (#131).

A reset used to be retried inside AdbConnection, which reconnected without
replaying the transport selection and without restoring the socket timeout, so
reads never returned. These tests pin the command-level behaviour: a complete
request is replayed at most once and every other reset reaches the caller as an
AdbError.
"""

from __future__ import annotations

import threading
import time

import pytest

import adbutils
from adbutils._adb import AdbConnection
from adbutils.errors import AdbConnectionError

from adb_server import RESET_COUNTERS


def call_with_deadline(fn, timeout: float = 2.0):
    """Run fn in a thread and fail instead of hanging the whole test suite."""
    outcome = {}

    def target():
        try:
            outcome["result"] = fn()
        except BaseException as e:  # re-raised in the test thread
            outcome["error"] = e

    thread = threading.Thread(target=target, daemon=True)
    thread.start()
    thread.join(timeout)
    assert not thread.is_alive(), f"adb call did not return within {timeout}s"
    if "error" in outcome:
        raise outcome["error"]
    return outcome.get("result")


class _BrokenSocket:
    def __init__(self, send_error, recv_error):
        self._send_error = send_error
        self._recv_error = recv_error

    def send(self, data):
        raise self._send_error

    def recv(self, n):
        raise self._recv_error

    def shutdown(self, how):
        pass

    def close(self):
        pass


@pytest.fixture(autouse=True)
def clear_reset_counters():
    RESET_COUNTERS.clear()
    yield
    RESET_COUNTERS.clear()


def test_complete_command_is_replayed_after_reset(adb: adbutils.AdbClient):
    RESET_COUNTERS["host:version"] = 1
    assert call_with_deadline(adb.server_version) == 1234


def test_forward_list_is_replayed_after_reset(adb: adbutils.AdbClient):
    RESET_COUNTERS["host:list-forward"] = 1
    items = call_with_deadline(adb.forward_list)
    assert [(i.serial, i.local, i.remote) for i in items] == [
        ("123456", "tcp:1234", "tcp:4321")
    ]


def test_device_query_is_replayed_after_reset(adb: adbutils.AdbClient):
    RESET_COUNTERS["host-serial:123456:features"] = 1
    device = adb.device(serial="123456")
    assert "shell_v2" in call_with_deadline(device.get_features)


def test_track_devices_reconnects_after_reset(adb: adbutils.AdbClient):
    it = adb.track_devices()
    try:
        event = call_with_deadline(lambda: next(it))
        assert (event.serial, event.status) == ("dummydevice", "device")
        event = call_with_deadline(lambda: next(it))
        assert (event.serial, event.status) == ("otherdevice", "device")
    finally:
        it.close()


def test_reconnect_is_bounded(adb: adbutils.AdbClient):
    RESET_COUNTERS["host:version"] = 100
    started = time.monotonic()
    with pytest.raises(adbutils.AdbError):
        call_with_deadline(adb.server_version)
    assert time.monotonic() - started < 2.0


def test_command_replay_keeps_configured_timeout(adb: adbutils.AdbClient, monkeypatch):
    client = adbutils.AdbClient(port=adb.port, socket_timeout=0.5)
    timeouts = []
    original = client.make_connection

    def make_connection(timeout=None):
        conn = original(timeout=timeout)
        timeouts.append(conn.conn.gettimeout())
        return conn

    monkeypatch.setattr(client, "make_connection", make_connection)
    RESET_COUNTERS["host:version"] = 1
    assert client.server_version() == 1234
    assert timeouts == [0.5, 0.5]


def test_reset_while_reading_raises_adb_error(adb: adbutils.AdbClient):
    device = adb.device(serial="123456")
    with pytest.raises(AdbConnectionError):
        call_with_deadline(
            lambda: device.shell("reset-after-output", timeout=0.5)
        )


def test_shell_timeout_is_not_lost(adb: adbutils.AdbClient):
    device = adb.device(serial="123456")
    started = time.monotonic()
    with pytest.raises(adbutils.AdbTimeout):
        call_with_deadline(lambda: device.shell("hang", timeout=0.5))
    assert time.monotonic() - started < 2.0


def test_sync_reset_raises_adb_error(adb: adbutils.AdbClient):
    device = adb.device(serial="123456")
    with pytest.raises(AdbConnectionError):
        call_with_deadline(lambda: device.sync.stat("/sdcard/file"))


def test_reset_is_not_retried_inside_connection(adb: adbutils.AdbClient):
    conn = adb.make_connection(timeout=0.5)
    RESET_COUNTERS["host:version"] = 1
    try:
        conn.send_command("host:version")
        with pytest.raises(AdbConnectionError):
            call_with_deadline(conn.check_okay)
        assert conn.conn.gettimeout() == 0.5
    finally:
        conn.close()


@pytest.mark.parametrize(
    "send_error,recv_error",
    [
        (
            BrokenPipeError(32, "Broken pipe"),
            ConnectionResetError(54, "Connection reset by peer"),
        ),
        (
            ConnectionAbortedError(103, "Software caused connection abort"),
            ConnectionAbortedError(103, "Software caused connection abort"),
        ),
    ],
)
def test_platform_connection_errors_become_adb_errors(
    adb: adbutils.AdbClient, monkeypatch, send_error, recv_error
):
    conn = AdbConnection(adb.host, adb.port)
    monkeypatch.setattr(
        conn, "_AdbConnection__conn", _BrokenSocket(send_error, recv_error)
    )
    try:
        with pytest.raises(AdbConnectionError):
            conn.send(b"0009host:version")
        with pytest.raises(AdbConnectionError):
            conn.recv(4)
    finally:
        conn.close()
