#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Created on Mon Apr 08 2024 12:21:30 by codeskyblue
"""

import abc
import dataclasses
from typing import Optional
from adbutils._proto import AppInfo


class AbstracctDevice(abc.ABC):
    @abc.abstractmethod
    def app_info(self, package_name: str) -> Optional[AppInfo]:
        pass


class DeprecatedExtension(AbstracctDevice):
    def package_info(self, package_name: str) -> Optional[dict]:
        """deprecated method, use app_info instead."""
        info = self.app_info(package_name)
        if info:
            return dataclasses.asdict(info)
        return None