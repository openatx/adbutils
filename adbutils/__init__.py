# coding: utf-8
#

from __future__ import print_function

import io
import os
import typing

from typing import Iterator, List, Optional, Union
from deprecation import deprecated

from adbutils._adb import AdbConnection
from adbutils._adb import BaseClient as _BaseClient
from adbutils._device import AdbDevice, Sync
from adbutils._proto import *
from adbutils._utils import adb_path, StopEvent
from adbutils._version import __version__
from adbutils.errors import *

__all__ = [
    'AdbDevice',
    'AdbConnection', 
    'AdbClient',
    'Sync',
    'StopEvent',
    'AdbError',
    'adb_path',
    'adb',
    'device',
]

class AdbClient(_BaseClient):
    def sync(self, serial: str) -> Sync:
        return Sync(self.device(serial))

    @deprecated(deprecated_in="0.15.0",
                removed_in="1.0.0",
                current_version=__version__,
                details="use AdbDevice.shell instead")
    def shell(self,
              serial: str,
              command: Union[str, list, tuple],
              stream: bool = False,
              timeout: Optional[float] = None) -> Union[str, AdbConnection]:
        return self.device(serial).shell(command, stream=stream, timeout=timeout, encoding='utf-8')

    def list(self, extended=False) -> List[AdbDeviceInfo]:
        """
        Returns:
            list of device info, including offline
        """
        infos = []
        with self.make_connection() as c:
            if extended:
                c.send_command("host:devices-l")
            else:
                c.send_command("host:devices")
            c.check_okay()
            output = c.read_string_block()
            for line in output.splitlines():
                parts = line.split()
                tags = {}
                num_required_fields = 2 # serial and state
                if len(parts) < num_required_fields:
                    continue
                if extended:
                    for part in parts[num_required_fields:]:
                        fields = part.split(':', 1)
                        if len(fields) != 2:
                            continue
                        tags[fields[0]] = fields[1]
                infos.append(AdbDeviceInfo(serial=parts[0], state=parts[1], tags=tags))
        return infos

    def iter_device(self) -> Iterator[AdbDevice]:
        """
        Returns:
            iter only AdbDevice with state:device
        """
        for info in self.list():
            if info.state != "device":
                continue
            yield AdbDevice(self, serial=info.serial)

    def device_list(self) -> typing.List[AdbDevice]:
        return list(self.iter_device())

    def device(self,
               serial: Optional[str] = None,
               transport_id: Optional[int] = None) -> AdbDevice:
        if serial:
            return AdbDevice(self, serial=serial)
        
        if transport_id:
            return AdbDevice(self, transport_id=transport_id)

        serial = os.environ.get("ANDROID_SERIAL")
        if not serial:
            ds = self.device_list()
            if len(ds) == 0:
                raise AdbError("Can't find any android device/emulator")
            if len(ds) > 1:
                raise AdbError(
                    "more than one device/emulator, please specify the serial number"
                )
            return ds[0]
        return AdbDevice(self, serial)



adb = AdbClient()
device = adb.device


if __name__ == "__main__":
    print("server version:", adb.server_version())
    print("devices:", adb.device_list())
    d = adb.device_list()[0]

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
