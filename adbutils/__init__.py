# coding: utf-8
#

from __future__ import print_function

import datetime
import json
import os
import re
import socket
import stat
import struct
import subprocess
from collections import namedtuple
from contextlib import contextmanager
from typing import Union, Iterator, Optional

import pkg_resources
import six
import whichcraft
from adbutils._utils import get_adb_exe
from adbutils.errors import AdbError, AdbTimeout
from adbutils.mixin import ShellMixin
from deprecation import deprecated

_OKAY = "OKAY"
_FAIL = "FAIL"
_DENT = "DENT"  # Directory Entity
_DONE = "DONE"
_DATA = "DATA"

_DISPLAY_RE = re.compile(
    r'.*DisplayViewport{valid=true, .*orientation=(?P<orientation>\d+), .*deviceWidth=(?P<width>\d+), deviceHeight=(?P<height>\d+).*'
)

DeviceEvent = namedtuple('DeviceEvent', ['present', 'serial', 'status'])
ForwardItem = namedtuple("ForwardItem", ["serial", "local", "remote"])
FileInfo = namedtuple("FileInfo", ['mode', 'size', 'mtime', 'name'])
WindowSize = namedtuple("WindowSize", ['width', 'height'])

try:
    __version__ = pkg_resources.get_distribution("adbutils").version
except pkg_resources.DistributionNotFound:
    __version__ = "0.0.1"


def get_free_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(('localhost', 0))
    try:
        return s.getsockname()[1]
    finally:
        s.close()


def _check_server(host: str, port: int) -> bool:
    """ Returns if server is running """
    s = socket.socket()
    try:
        s.connect((host, port))
        return True
    except socket.error as e:
        return False
    finally:
        s.close()


def adb_path():
    return get_adb_exe()


class _AdbStreamConnection(object):
    def __init__(self, host: str, port: int):
        self.__host = host
        self.__port = port
        self.__conn = None

        self._connect()

    def _create_socket(self):
        adb_host = self.__host
        adb_port = self.__port
        s = socket.socket()
        try:
            s.connect((adb_host, adb_port))
            return s
        except:
            s.close()
            raise

    def _connect(self):
        try:
            self.__conn = self._create_socket()
        except ConnectionRefusedError:
            subprocess.run([adb_path(), "start-server"], timeout=20.0) # 20s should enough for adb start
            self.__conn = self._create_socket()
        return self

    def close(self):
        self.__conn.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        self.close()

    @property
    def conn(self):
        return self.__conn

    def send(self, cmd: str):
        self.conn.send("{:04x}{}".format(len(cmd), cmd).encode("utf-8"))

    def read_raw(self, n: int) -> bytes:
        """ read fully 
        """
        t = n
        buffer = b''
        while t > 0:
            chunk = self.conn.recv(t)
            if not chunk:
                break
            buffer += chunk
            t = n - len(buffer)
        return buffer

    def read(self, n: int) -> str:
        data = self.read_raw(n).decode()
        return data

    def read_string(self) -> str:
        """
        Raises:
            AdbError
        """
        length = self.read(4)
        if not length:
            raise AdbError("connection closed")
        size = int(length, 16)
        return self.read(size)

    def read_until_close(self) -> str:
        content = b""
        while True:
            chunk = self.read_raw(4096)
            if not chunk:
                break
            content += chunk
        return content.decode('utf-8', errors='ignore')

    def check_okay(self):
        data = self.read(4)
        if data == _FAIL:
            raise AdbError(self.read_string())
        elif data == _OKAY:
            return
        raise AdbError("Unknown data: %s" % data)


class AdbClient(object):
    def __init__(self, host: str = None, port: int = None):
        """
        Args:
            host (str): default value from env:ANDROID_ADB_SERVER_HOST
            port (int): default value from env:ANDROID_ADB_SERVER_PORT
        """
        if not host:
            host = os.environ.get("ANDROID_ADB_SERVER_HOST", "127.0.0.1")
        if not port:
            port = int(os.environ.get("ANDROID_ADB_SERVER_PORT", 5037))
        self.__host = host
        self.__port = port

    def _connect(self):
        return _AdbStreamConnection(self.__host, self.__port)

    def server_version(self):
        """ 40 will match 1.0.40
        Returns:
            int
        """
        with self._connect() as c:
            c.send("host:version")
            c.check_okay()
            return int(c.read_string(), 16)

    def server_kill(self):
        """
        adb kill-server
 
        Send host:kill if adb-server is alive
        """
        if _check_server(self.__host, self.__port):
            with self._connect() as c:
                c.send("host:kill")
                c.check_okay()

    def connect(self, addr: str) -> str:
        """ adb connect $addr
        Returns:
            content adb server returns

        Example returns:
            - "already connected to 192.168.190.101:5555"
            - "unable to connect to 192.168.190.101:5551"
        """
        with self._connect() as c:
            c.send("host:connect:" + addr)
            c.check_okay()
            return c.read_string()

    def shell(self,
              serial: str,
              command: Union[str, list, tuple],
              stream: bool = False,
              timeout: Optional[float] = None) -> str:
        """Run shell in android and return output
        Args:
            serial (str)
            command: list, tuple or str
            stream (bool): return stream instead of string output
            timeout (float or None): only works when stream is False

        Returns:
            str or socket
        
        Raises:
            AdbTimeout
        """
        assert isinstance(serial, six.string_types)
        if isinstance(command, (list, tuple)):
            command = subprocess.list2cmdline(command)
        assert isinstance(command, six.string_types)
        c = self._connect()
        try:
            c.send("host:transport:" + serial)
            c.check_okay()
            c.send("shell:" + command)
            c.check_okay()
            if stream:
                return c
            
            # when no response in timeout, socket.timeout will raise
            c.conn.settimeout(timeout)
            try:
                return c.read_until_close()
            except socket.timeout:
                raise AdbTimeout("shell exec timeout", "CMD={!r} TIMEOUT={:.1f}".format(command, timeout))
        except:
            if stream:
                c.close()
            raise
        finally:
            if not stream:
                c.close()
    
    def track_devices(self) -> Iterator[DeviceEvent]:
        """
        Report device state when changes

        Args:
            limit_status: eg, ['device', 'offline'], empty means all status

        Returns:
            Iterator[DeviceEvent], DeviceEvent.status can be one of ['device', 'offline', 'unauthorized', 'absent']
        
        Raises:
            AdbError when adb-server was killed
        """
        orig_devices = []

        with self._connect() as c:
            c.send("host:track-devices")
            c.check_okay()
            while True:
                output = c.read_string()
                curr_devices = self._output2devices(output)
                for event in self._diff_devices(orig_devices, curr_devices):
                    yield event
                orig_devices = curr_devices

    def _output2devices(self, output: str):
        devices = []
        for line in output.splitlines():
            fields = line.strip().split("\t", maxsplit=1)
            if len(fields) != 2:
                continue
            serial, status = fields
            devices.append(DeviceEvent(None, serial, status))
        return devices

    def _diff_devices(self, orig: list, curr: list):
        for d in set(orig).difference(curr):
            yield DeviceEvent(False, d.serial, 'absent')
        for d in set(curr).difference(orig):
            yield DeviceEvent(True, d.serial, d.status)

    def forward_list(self, serial: Union[None, str] = None):
        with self._connect() as c:
            list_cmd = "host:list-forward"
            if serial:
                list_cmd = "host-serial:{}:list-forward".format(serial)
            c.send(list_cmd)
            c.check_okay()
            content = c.read_string()
            for line in content.splitlines():
                parts = line.split()
                if len(parts) != 3:
                    continue
                if serial and parts[0] != serial:
                    continue
                yield ForwardItem(*parts)

    def forward(self, serial, local, remote, norebind=False):
        """
        Args:
            serial (str): device serial
            local, remote (str): tcp:<port> or localabstract:<name>
            norebind (bool): fail if already forwarded when set to true

        Raises:
            AdbError
        """
        with self._connect() as c:
            cmds = ["host-serial", serial, "forward"]
            if norebind:
                cmds.append("norebind")
            cmds.append(local + ";" + remote)
            c.send(":".join(cmds))
            c.check_okay()

    def iter_device(self):
        """
        Returns:
            iter of AdbDevice
        """
        with self._connect() as c:
            c.send("host:devices")
            c.check_okay()
            output = c.read_string()
            for line in output.splitlines():
                parts = line.strip().split("\t")
                if len(parts) != 2:
                    continue
                if parts[1] == 'device':
                    yield AdbDevice(self, parts[0])

    @deprecated(deprecated_in="0.3.0",
                removed_in="0.4.0",
                current_version=__version__,
                details="use device_list() instead")
    def devices(self) -> list:
        return list(self.iter_device())

    def device_list(self):
        return list(self.iter_device())

    @deprecated(deprecated_in="0.3.0",
                removed_in="0.4.0",
                current_version=__version__,
                details="use device() instead")
    def must_one_device(self):
        return self.device()

    def device(self, serial=None) -> 'AdbDevice':
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

    def sync(self, serial) -> 'Sync':
        return Sync(self, serial)


class AdbDevice(ShellMixin):
    def __init__(self, client: AdbClient, serial: str):
        self._client = client
        self._serial = serial
        self._properties = {} # store properties data

    @property
    def serial(self):
        return self._serial

    def __repr__(self):
        return "AdbDevice(serial={})".format(self.serial)

    @property
    def sync(self) -> 'Sync':
        return Sync(self._client, self.serial)

    @property
    def prop(self) -> "Property":
        return Property(self)

    def adb_output(self, *args, **kwargs):
        """Run adb command use subprocess and get its content

        Returns:
            string of output

        Raises:
            EnvironmentError
        """

        cmds = [adb_path(), '-s', self._serial
                ] if self._serial else [adb_path()]
        cmds.extend(args)
        cmdline = subprocess.list2cmdline(map(str, cmds))
        try:
            return subprocess.check_output(cmdline,
                                           stderr=subprocess.STDOUT,
                                           shell=True).decode('utf-8')
        except subprocess.CalledProcessError as e:
            if kwargs.get('raise_error', True):
                raise EnvironmentError(
                    "subprocess", cmdline,
                    e.output.decode('utf-8', errors='ignore'))

    def shell(self,
              cmdargs: Union[str, list, tuple],
              stream: bool = False,
              timeout: Optional[float] = None,
              rstrip=True) -> str:
        """Run shell inside device and get it's content

        Args:
            rstrip (bool): strip the last empty line (Default: True)
            stream (bool): return stream instead of string output (Default: False)
            timeout (float): set shell timeout

        Returns:
            string of output

        Raises:

        Examples:
            shell("ls -l")
            shell(["ls", "-l"])
            shell("ls | grep data")
        """
        if isinstance(cmdargs, (list, tuple)):
            cmdargs = subprocess.list2cmdline(cmdargs)
        ret = self._client.shell(self._serial, cmdargs, stream=stream, timeout=timeout)
        if stream:
            return ret
        return ret.rstrip() if rstrip else ret

    @deprecated(deprecated_in="0.2.4",
                removed_in="0.3.0",
                current_version=__version__,
                details="use shell function instead, eg shell(\"ls -l\")")
    def shell_output(self, *args) -> str:
        return self._client.shell(self._serial, subprocess.list2cmdline(args))

    def forward(self, local: str, remote: str):
        return self._client.forward(self._serial, local, remote)

    def forward_port(self, remote: Union[int, str]) -> int:
        """ forward remote port to local random port """
        if isinstance(remote, int):
            remote = "tcp:" + str(remote)
        for f in self.forward_list():
            if f.serial == self._serial and f.remote == remote and f.local.startswith(
                    "tcp:"):
                return int(f.local[len("tcp:"):])
        local_port = get_free_port()
        self._client.forward(self._serial, "tcp:" + str(local_port), remote)
        return local_port

    def forward_list(self):
        return self._client.forward_list(self._serial)

    def push(self, local: str, remote: str):
        self.adb_output("push", local, remote)


class Sync():
    def __init__(self, adbclient: AdbClient, serial: str):
        self._adbclient = adbclient
        self._serial = serial

    @contextmanager
    def _prepare_sync(self, path, cmd):
        c = self._adbclient._connect()
        try:
            c.send(":".join(["host", "transport", self._serial]))
            c.check_okay()
            c.send("sync:")
            c.check_okay()
            # {COMMAND}{LittleEndianPathLength}{Path}
            c.conn.send(
                cmd.encode("utf-8") + struct.pack("<I", len(path)) +
                path.encode("utf-8"))
            yield c
        finally:
            c.close()

    def stat(self, path: str) -> FileInfo:
        with self._prepare_sync(path, "STAT") as c:
            assert "STAT" == c.read(4)
            mode, size, mtime = struct.unpack("<III", c.conn.recv(12))
            return FileInfo(mode, size, datetime.datetime.fromtimestamp(mtime),
                            path)

    def iter_directory(self, path: str):
        with self._prepare_sync(path, "LIST") as c:
            while 1:
                response = c.read(4)
                if response == _DONE:
                    break
                mode, size, mtime, namelen = struct.unpack(
                    "<IIII", c.conn.recv(16))
                name = c.read(namelen)
                try:
                    mtime = datetime.datetime.fromtimestamp(mtime)
                except OSError:  # bug in Python 3.6
                    mtime = datetime.datetime.now()
                yield FileInfo(mode, size, mtime, name)

    def list(self, path: str):
        return list(self.iter_directory(path))

    def push(self, src, dst: str, mode: int = 0o755, filesize: int = None):
        # IFREG: File Regular
        # IFDIR: File Directory
        path = dst + "," + str(stat.S_IFREG | mode)
        total_size = 0
        with self._prepare_sync(path, "SEND") as c:
            r = src if hasattr(src, "read") else open(src, "rb")
            try:
                while True:
                    chunk = r.read(4096)
                    if not chunk:
                        mtime = int(datetime.datetime.now().timestamp())
                        c.conn.send(b"DONE" + struct.pack("<I", mtime))
                        break
                    c.conn.send(b"DATA" + struct.pack("<I", len(chunk)))
                    c.conn.send(chunk)
                    total_size += len(chunk)
                assert c.read(4) == _OKAY
            finally:
                if hasattr(r, "close"):
                    r.close()
        # wait until really pushed
        # if filesize:
        #     print("Read: %d Copied: %d" % (filesize, total_size), self.stat(dst))

    def iter_content(self, path: str):
        with self._prepare_sync(path, "RECV") as c:
            while True:
                cmd = c.read(4)
                if cmd == _FAIL:
                    str_size = struct.unpack("<I", c.read_raw(4))[0]
                    error_message = c.read(str_size)
                    raise AdbError(error_message)
                elif cmd == _DONE:
                    break
                elif cmd == _DATA:
                    chunk_size = struct.unpack("<I", c.read_raw(4))[0]
                    chunk = c.read_raw(chunk_size)
                    if len(chunk) != chunk_size:
                        raise RuntimeError("read chunk missing")
                    yield chunk
                else:
                    raise AdbError("Invalid sync cmd", cmd)

    def pull(self, src: str, dst: str) -> int:
        """
        Pull file from device:src to local:dst

        Returns:
            file size
        """
        with open(dst, 'wb') as f:
            size = 0
            for chunk in self.iter_content(src):
                f.write(chunk)
                size += len(chunk)
            return size


class Property():
    def __init__(self, d: AdbDevice):
        self._d = d

    def __str__(self):
        return f"product:{self.name} model:{self.model} device:{self.device}"

    def get(self, name: str, cache=True) -> str:
        if cache and name in self._d._properties:
            return self._d._properties[name]
        value = self._d._properties[name] = self._d.shell(['getprop', name]).strip()
        return value

    @property
    def name(self):
        return self.get("ro.product.name", cache=True)

    @property
    def model(self):
        return self.get("ro.product.model", cache=True)

    @property
    def device(self):
        return self.get("ro.product.device", cache=True)


adb = AdbClient()

# device = adb.device
# devices = adb.devices

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
