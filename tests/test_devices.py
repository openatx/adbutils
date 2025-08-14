# coding: utf-8
#


import pytest
from unittest.mock import Mock
import adbutils
from adbutils._proto import AdbDeviceInfo
from adbutils._device_base import BaseDevice
from adbutils._adb import BaseClient

def test_host_devices(adb: adbutils.AdbClient):
    _dev = adb.device("any")
    assert _dev.shell(cmdargs="enable-devices") == 'debug command executed'
    devices = adb.list(extended=False)
    assert devices == [AdbDeviceInfo(serial="dummydevice", state="device", tags={})]


def test_host_devices_invalid(adb: adbutils.AdbClient):
    _dev = adb.device("any")
    assert _dev.shell(cmdargs="invalidate-devices") == 'debug command executed'
    devices = adb.list(extended=False)
    assert devices == []


def test_host_devices_extended(adb: adbutils.AdbClient):
    _dev = adb.device("any")
    assert _dev.shell(cmdargs="enable-devices") == 'debug command executed'
    devices = adb.list(extended=True)
    assert devices == [AdbDeviceInfo(serial="dummydevice", state="device", tags={"product": "test_emu", "model": "test_model", "device": "test_device"})]


def test_host_devices_extended_invalid(adb: adbutils.AdbClient):
    _dev = adb.device("any")
    assert _dev.shell(cmdargs="invalidate-devices") == 'debug command executed'
    devices = adb.list(extended=True)
    assert devices == []


def test_reverse_list_empty_output():
    """Test that reverse_list returns empty list when no reverse forwards are configured
    
    This test ensures that the UnboundLocalError bug in reverse_list is fixed.
    """
    # Create mock objects
    mock_client = Mock(spec=BaseClient)
    mock_connection = Mock()
    
    # Mock the read_string_block to return empty content
    mock_connection.read_string_block.return_value = ""
    mock_connection.__enter__ = Mock(return_value=mock_connection)
    mock_connection.__exit__ = Mock(return_value=None)
    
    # Create a device instance with mocked dependencies
    device = BaseDevice(mock_client, serial="test_device")
    device.open_transport = Mock(return_value=mock_connection)
    
    # Should return empty list without error (previously would throw UnboundLocalError)
    result = device.reverse_list()
    assert result == []


def test_reverse_list_invalid_lines():
    """Test that reverse_list handles lines with incorrect format gracefully"""
    # Create mock objects
    mock_client = Mock(spec=BaseClient)
    mock_connection = Mock()
    
    # Mock the read_string_block to return content with invalid lines
    mock_connection.read_string_block.return_value = "invalid line\nanother\n"
    mock_connection.__enter__ = Mock(return_value=mock_connection)
    mock_connection.__exit__ = Mock(return_value=None)
    
    # Create a device instance with mocked dependencies  
    device = BaseDevice(mock_client, serial="test_device")
    device.open_transport = Mock(return_value=mock_connection)
    
    # Should return empty list without error
    result = device.reverse_list()
    assert result == []