#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Created on Fri May 06 2022 11:39:40 by codeskyblue
"""

__all__ = [
    "Network", "DeviceEvent", "ForwardItem", "ReverseItem", "FileInfo",
    "WindowSize", "RunningAppInfo", "ShellReturn", "AdbDeviceInfo"
]

import enum
import datetime
import pathlib
import typing
from dataclasses import dataclass


class Network(str, enum.Enum):
    TCP = "tcp"
    UNIX = "unix"

    DEV = "dev"
    LOCAL = "local"
    LOCAL_RESERVED = "localreserved"
    LOCAL_FILESYSTEM = "localfilesystem"
    LOCAL_ABSTRACT = "localabstract"  # same as UNIX


class DeviceEvent(typing.NamedTuple):
    present: bool
    serial: str
    status: str


class ForwardItem(typing.NamedTuple):
    serial: str
    local: str
    remote: str


class ReverseItem(typing.NamedTuple):
    remote: str
    local: str


class FileInfo(typing.NamedTuple):
    mode: int
    size: int
    mtime: datetime.datetime
    path: str


class AppInfo(typing.NamedTuple):
    package_name: str
    version_name: str
    version_code: int
    flags: str
    first_install_time: datetime.datetime
    last_update_time: datetime.datetime
    signature: str


class WindowSize(typing.NamedTuple):
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
    output: str


@dataclass
class AdbDeviceInfo:
    serial: str
    state: str


StrOrPathLike = typing.Union[str, pathlib.Path]