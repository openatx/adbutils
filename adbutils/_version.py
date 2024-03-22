#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Created on Fri May 06 2022 10:54:04 by codeskyblue
"""


from importlib.metadata import version, PackageNotFoundError

try:
    __version__ = version("adbutils")
except PackageNotFoundError:
    __version__ = "unknown"