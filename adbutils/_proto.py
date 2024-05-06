#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Created on Fri May 06 2022 11:39:40 by codeskyblue
"""
from __future__ import annotations

__all__ = [
    "Network", "DeviceEvent", "ForwardItem", "ReverseItem", "FileInfo",
    "WindowSize", "RunningAppInfo", "ShellReturn", "AdbDeviceInfo", "AppInfo"
]

import enum
import datetime
import pathlib
from typing import List, NamedTuple, Optional, Union
from dataclasses import dataclass


class Network(str, enum.Enum):
    TCP = "tcp"
    UNIX = "unix"

    DEV = "dev"
    LOCAL = "local"
    LOCAL_RESERVED = "localreserved"
    LOCAL_FILESYSTEM = "localfilesystem"
    LOCAL_ABSTRACT = "localabstract"  # same as UNIX


@dataclass(frozen=True)
class DeviceEvent:
    present: bool
    serial: str
    status: str


@dataclass
class ForwardItem:
    serial: str
    local: str
    remote: str


@dataclass
class ReverseItem:
    remote: str
    local: str


@dataclass
class FileInfo:
    mode: int
    size: int
    mtime: datetime.datetime
    path: str


@dataclass
class AppInfo:
    package_name: str
    version_name: Optional[str]
    version_code: Optional[int]
    flags: Union[str, list]
    first_install_time: datetime.datetime
    last_update_time: datetime.datetime
    signature: str
    path: str
    sub_apk_paths: List[str]


@dataclass
class BatteryInfo:
    ac_powered: bool
    usb_powered: bool
    wireless_powered: Optional[bool]
    dock_powered: Optional[bool]
    max_charging_current: Optional[int]
    max_charging_voltage: Optional[int]
    charge_counter: Optional[int]
    status: Optional[int]
    health: Optional[int]
    present: Optional[bool]
    level: Optional[int]
    scale: Optional[int]
    voltage: Optional[int] # mV
    temperature: Optional[float] # e.g. 25.0
    technology: Optional[str]


class WindowSize(NamedTuple):
    width: int
    height: int


@dataclass
class RunningAppInfo:
    package: str
    activity: str
    pid: int = 0


@dataclass
class ShellReturn:
    """
    Attributes:
        command: The str command passed to run().
        returncode: The exit code of the process, negative for signals.
        output: the output
    """
    command: str
    returncode: int
    output: str | bytes


@dataclass
class AdbDeviceInfo:
    serial: str
    state: str


StrOrPathLike = Union[str, pathlib.Path]
