#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Created on Wed May 08 2024 21:45:15 by codeskyblue
"""

import adbutils


def test_forward_list(adb: adbutils.AdbClient):
    items = adb.forward_list()
    assert len(items) == 1
    assert items[0].serial == "123456"
    assert items[0].local == "tcp:1234"
    assert items[0].remote == "tcp:4321"
