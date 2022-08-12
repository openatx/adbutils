#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Created on Fri Aug 12 2022 14:25:35 by codeskyblue
"""

import typing
import usb
import adbutils


def main():
    offline_map: typing.Dict[str, bool] = {}
    c = adbutils.AdbClient()
    for info in c.list():
        if info.state == "offline":
            offline_map[info.serial] = True

    for d in usb.core.find(find_all=True):
        if d.serial_number in offline_map:
            print("Reset", d.serial_number)
            try:
                d.reset()
            except usb.USBError:
                pass


if __name__ == "__main__":
    main()