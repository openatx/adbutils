#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Created on Fri May 06 2022 11:39:40 by codeskyblue
"""

__all__ = ["Network", "DeviceEvent", "ForwardItem", "ReverseItem", "FileInfo", "WindowSize"]


import enum
import typing
from datetime import datetime


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
    mtime: datetime
    path: str


class WindowSize(typing.NamedTuple):
    width: int
    height: int

