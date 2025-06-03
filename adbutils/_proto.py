#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Created on Fri May 06 2022 11:39:40 by codeskyblue
"""
from __future__ import annotations

__all__ = [
    "Network", "BrightnessMode", "DeviceEvent", "ForwardItem", "ReverseItem", "FileInfo",
    "WindowSize", "RunningAppInfo", "ShellReturn", "AdbDeviceInfo", "AppInfo", "BatteryInfo", "RunningAppInfo"
]

import enum
import datetime
import pathlib
from typing import List, NamedTuple, Optional, Union
from dataclasses import dataclass, field


class Network(str, enum.Enum):
    TCP = "tcp"
    UNIX = "unix"

    DEV = "dev"
    LOCAL = "local"
    LOCAL_RESERVED = "localreserved"
    LOCAL_FILESYSTEM = "localfilesystem"
    LOCAL_ABSTRACT = "localabstract"  # same as UNIX


class BrightnessMode(int, enum.Enum):
    AUTO = 1
    MANUAL = 0


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
    mtime: Optional[datetime.datetime]  # None if not available
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
    voltage: Optional[int]  # mV
    temperature: Optional[float]  # e.g. 25.0
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
class ShellReturnRaw:
    command: str
    returncode: int
    stdout: bytes = b""
    stderr: bytes = b""
    output: bytes = b""


@dataclass
class ShellReturn:
    command: str
    returncode: int
    output: str = ""
    stderr: str = ""
    stdout: str = ""


@dataclass
class AdbDeviceInfo:
    serial: str
    state: str
    tags: dict[str, str] = field(default_factory=dict)
    
    @property
    def transport_id(self) -> Optional[int]:
        """Get the transport ID from tags."""
        return int(self.tags.get("transport_id", 0)) if "transport_id" in self.tags else None


StrOrPathLike = Union[str, pathlib.Path]
