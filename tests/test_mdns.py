# coding: utf-8
#
# Tests for the mDNS helpers, the mock server speaks the same protocol as
# `adb mdns services`: TAB separated instance, service type and ip:port.
#

import adbutils
import adb_server
import pytest
from unittest.mock import Mock
from adbutils._proto import AdbMdnsService


@pytest.fixture(autouse=True)
def mdns_state():
    adb_server.reset_mdns_state()
    yield
    adb_server.reset_mdns_state()


def test_mdns_services(adb: adbutils.AdbClient):
    adb_server.MDNS_SERVICES.extend([
        "adb-1234abcd-xyz\t_adb-tls-connect._tcp.\t192.168.1.2:6666",
        "adb-aaaabbbb-xyz\t_adb-tls-pairing._tcp.\t192.168.1.2:6667",
    ])

    services = adb.mdns_services()

    assert services == [
        AdbMdnsService("adb-1234abcd-xyz", "_adb-tls-connect._tcp", "192.168.1.2:6666"),
        AdbMdnsService("adb-aaaabbbb-xyz", "_adb-tls-pairing._tcp", "192.168.1.2:6667"),
    ]
    # adb names the transport "<instance>.<service>", the same serial mDNS
    # auto-connect would create.
    assert services[0].serial == "adb-1234abcd-xyz._adb-tls-connect._tcp"


def test_mdns_services_skips_malformed_lines(adb: adbutils.AdbClient):
    adb_server.MDNS_SERVICES.extend([
        "",
        "no-separator",
        "adb-0000-xyz\t_adb-tls-connect._tcp.",
        "adb-0000-xyz\t_adb-tls-connect._tcp.\t192.168.1.9:6666\textra",
        "\t_adb-tls-connect._tcp.\t192.168.1.9:6666",
        "adb-1234abcd-xyz\t_adb-tls-connect._tcp.\t192.168.1.2:6666",
    ])

    assert adb.mdns_services() == [
        AdbMdnsService("adb-1234abcd-xyz", "_adb-tls-connect._tcp", "192.168.1.2:6666"),
    ]


def test_mdns_services_empty(adb: adbutils.AdbClient):
    assert adb.mdns_services() == []


def test_mdns_services_disabled(adb: adbutils.AdbClient):
    adb_server.MDNS_ERROR = "ERROR: mdns discovery disabled"

    with pytest.raises(adbutils.AdbError) as excinfo:
        adb.mdns_services()
    assert "mdns discovery disabled" in str(excinfo.value)


def test_mdns_services_unsupported_server():
    # Old servers answer FAIL, check_okay turns it into AdbError with the raw
    # server message, which is more useful than an empty service list.
    client = adbutils.AdbClient(port=1)
    conn = Mock()
    conn.__enter__ = Mock(return_value=conn)
    conn.__exit__ = Mock(return_value=None)
    conn.check_okay.side_effect = adbutils.AdbError("Unknown command: host:mdns:services")
    client.make_connection = Mock(return_value=conn)

    with pytest.raises(adbutils.AdbError) as excinfo:
        client.mdns_services()
    assert "Unknown command: host:mdns:services" in str(excinfo.value)


def test_connect_mdns(adb: adbutils.AdbClient):
    adb_server.MDNS_SERVICES.extend([
        "adb-1234abcd-xyz\t_adb-tls-connect._tcp.\t192.168.1.2:6666",
        "adb-aaaabbbb-xyz\t_adb-tls-pairing._tcp.\t192.168.1.2:6667",
        "adb-ccccdddd-xyz\t_adb-tls-connect._tcp.\t192.168.1.4:6666",
    ])
    adb_server.MDNS_CONNECT["adb-ccccdddd-xyz"] = (
        "failed to resolve host: 'adb-ccccdddd-xyz'")

    connected = adb.connect_mdns()

    assert connected == [
        AdbMdnsService("adb-1234abcd-xyz", "_adb-tls-connect._tcp", "192.168.1.2:6666"),
    ]
    # pairing services are left alone, failed devices are skipped
    assert adb_server.MDNS_CONNECTED == ["adb-1234abcd-xyz", "adb-ccccdddd-xyz"]


def test_connect_mdns_already_connected(adb: adbutils.AdbClient):
    adb_server.MDNS_SERVICES.append(
        "adb-1234abcd-xyz\t_adb-tls-connect._tcp.\t192.168.1.2:6666")
    adb_server.MDNS_CONNECT["adb-1234abcd-xyz"] = (
        "already connected to adb-1234abcd-xyz._adb-tls-connect._tcp")

    assert adb.connect_mdns() == [
        AdbMdnsService("adb-1234abcd-xyz", "_adb-tls-connect._tcp", "192.168.1.2:6666"),
    ]


def test_connect_mdns_duplicate_services(adb: adbutils.AdbClient):
    service = "adb-1234abcd-xyz\t_adb-tls-connect._tcp.\t192.168.1.2:6666"
    adb_server.MDNS_SERVICES.extend([service, service])

    assert len(adb.connect_mdns()) == 1
    assert adb_server.MDNS_CONNECTED == ["adb-1234abcd-xyz", "adb-1234abcd-xyz"]


def test_connect_mdns_no_devices(adb: adbutils.AdbClient):
    assert adb.connect_mdns() == []
    assert adb_server.MDNS_CONNECTED == []
