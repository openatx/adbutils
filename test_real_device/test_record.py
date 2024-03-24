#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Created on Sun May 15 2022 22:12:45 by codeskyblue
"""

import time
import adbutils


def test_scrcpyrecord(device: adbutils.AdbDevice):
    device.start_recording("output.mp4")
    time.sleep(2.0)
    device.stop_recording()