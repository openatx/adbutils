#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Created on Fri May 06 2022 10:33:39 by codeskyblue
"""

from __future__ import annotations

from typing import Optional

from adbutils._adb import BaseClient
from adbutils._deprecated import DeprecatedExtension
from adbutils._device_base import BaseDevice
from adbutils._proto import *
from adbutils._version import __version__
from adbutils.install import InstallExtension
from adbutils.screenrecord import ScreenrecordExtension
from adbutils.screenshot import ScreenshotExtesion
from adbutils.shell import ShellExtension
from adbutils.sync import Sync


class AdbDevice(
    BaseDevice,
    ShellExtension,
    ScreenrecordExtension,
    ScreenshotExtesion,
    InstallExtension,
    DeprecatedExtension,
):
    """provide custom functions for some complex operations"""

    def __init__(
        self, client: BaseClient, serial: Optional[str] = None, transport_id: Optional[int] = None
    ):
        BaseDevice.__init__(self, client, serial, transport_id)
        ScreenrecordExtension.__init__(self)
    
    @property
    def sync(self) -> Sync:
        return Sync(self)
