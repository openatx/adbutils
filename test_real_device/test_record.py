#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Created on Sun May 15 2022 22:12:45 by codeskyblue
"""

import os
import time
import adbutils


def test_screenrecord(device: adbutils.AdbDevice):
    device.start_recording("output.mp4")
    time.sleep(2.0)
    device.stop_recording()
    assert os.path.exists("output.mp4")
    os.remove("output.mp4")