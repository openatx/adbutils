# coding: utf-8
#

from __future__ import print_function

import io
import os
import typing

from ._adb import BaseClient
from ._device import AdbDevice, Sync
from ._utils import adb_path
from .errors import *
from ._proto import *


class AdbClient(BaseClient):
    def sync(self, serial: str) -> Sync:
        return Sync(self, serial)
    
    def iter_device(self) -> typing.Iterator:
        """
        Returns:
            iter of AdbDevice
        """
        with self._connect() as c:
            c.send_command("host:devices")
            c.check_okay()
            output = c.read_string_block()
            for line in output.splitlines():
                parts = line.strip().split("\t")
                if len(parts) != 2:
                    continue
                if parts[1] == 'device':
                    yield AdbDevice(self, parts[0])
    
    def device_list(self):
        return list(self.iter_device())

    def device(self, serial: str=None) -> 'AdbDevice':
        if not serial:
            serial = os.environ.get("ANDROID_SERIAL")

        if not serial:
            ds = self.device_list()
            if len(ds) == 0:
                raise RuntimeError("Can't find any android device/emulator")
            if len(ds) > 1:
                raise RuntimeError(
                    "more than one device/emulator, please specify the serial number"
                )
            return ds[0]
        return AdbDevice(self, serial)
    


adb = AdbClient()
device = adb.device


if __name__ == "__main__":
    print("server version:", adb.server_version())
    print("devices:", adb.devices())
    d = adb.devices()[0]

    print(d.serial)
    for f in adb.sync(d.serial).iter_directory("/data/local/tmp"):
        print(f)

    finfo = adb.sync(d.serial).stat("/data/local/tmp")
    print(finfo)
    import io
    sync = adb.sync(d.serial)
    filepath = "/data/local/tmp/hi.txt"
    sync.push(io.BytesIO(b"hi5a4de5f4qa6we541fq6w1ef5a61f65ew1rf6we"),
              filepath, 0o644)

    print("FileInfo", sync.stat(filepath))
    for chunk in sync.iter_content(filepath):
        print(chunk)
    # sync.pull(filepath)
