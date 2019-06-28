# coding: utf-8
#

from __future__ import print_function

import datetime
import os
import re
import socket
import stat
import struct
import subprocess
from collections import namedtuple
from contextlib import contextmanager
from typing import Union

import pkg_resources
import six
import whichcraft
from deprecation import deprecated

from adbutils.extras import ExtraUtilsMixin, LogcatManager

_OKAY = "OKAY"
_FAIL = "FAIL"
_DENT = "DENT"  # Directory Entity
_DONE = "DONE"

DeviceItem = namedtuple("Device", ["serial", "status"])
ForwardItem = namedtuple("ForwardItem", ["serial", "local", "remote"])
FileInfo = namedtuple("FileInfo", ['mode', 'size', 'mtime', 'name'])

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


def adb_path():
    path = whichcraft.which("adb")
    if path is None:
        raise EnvironmentError(
            "Can't find the adb, please install adb on your PC")
    return path


class AdbError(Exception):
    """ adb error """


class AdbInstallError(AdbError):
    def __init__(self, output: str):
        """
        Errors examples:
        Failure [INSTALL_FAILED_ALREADY_EXISTS: Attempt to re-install io.appium.android.apis without first uninstalling.]
        Error: Failed to parse APK file: android.content.pm.PackageParser$PackageParserException: Failed to parse /data/local/tmp/tmp-29649242.apk

        Reference: https://github.com/mzlogin/awesome-adb
        """
        m = re.search(r"Failure \[([\w_]+)", output)
        self.reason = m.group(1) if m else "Unknown"
        self.output = output

    def __str__(self):
        return self.output


class _AdbStreamConnection(object):
    def __init__(self, host=None, port=None):
        self.__host = host
        self.__port = port
        self.__conn = None

        self._connect()

    def _connect(self):
        adb_host = self.__host or os.environ.get("ANDROID_ADB_SERVER_HOST",
                                                 "127.0.0.1")
        adb_port = self.__port or int(
            os.environ.get("ANDROID_ADB_SERVER_PORT", 5037))
        s = self.__conn = socket.socket()
        s.connect((adb_host, adb_port))
        return self

    def close(self):
        self.conn.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        self.close()

    @property
    def conn(self):
        return self.__conn

    def send(self, cmd: str):
        self.conn.send("{:04x}{}".format(len(cmd), cmd).encode("utf-8"))

    def read(self, n: int) -> str:
        return self.conn.recv(n).decode()

    def read_raw(self, n: int) -> bytes:
        t = n
        buffer = b''
        while t > 0:
            chunk = self.conn.recv(t)
            if not chunk:
                break
            buffer += chunk
            t = n - len(buffer)
        return buffer

    def read_string(self) -> str:
        size = int(self.read(4), 16)
        return self.read(size)

    def read_until_close(self) -> str:
        content = ""
        while True:
            chunk = self.read(4096)
            if not chunk:
                break
            content += chunk
        return content

    def check_okay(self):
        data = self.read(4)
        if data == _FAIL:
            raise AdbError(self.read_string())
        elif data == _OKAY:
            return
        raise AdbError("Unknown data: %s" % data)


class AdbClient(object):
    def __init__(self, host=None, port=None):
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

    def shell(self, serial, command: Union[str, list, tuple]) -> str:
        """Run shell in android and return output
        Args:
            serial (str)
            command: list, tuple or str

        Returns:
            str
        """
        assert isinstance(serial, six.string_types)
        if isinstance(command, (list, tuple)):
            command = subprocess.list2cmdline(command)
        assert isinstance(command, six.string_types)
        with self._connect() as c:
            c.send("host:transport:" + serial)
            c.check_okay()
            c.send("shell:" + command)
            c.check_okay()
            return c.read_until_close()

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
            list of DeviceItem
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

    def devices(self) -> list:
        return list(self.iter_device())

    def must_one_device(self):
        ds = self.devices()
        if len(ds) == 0:
            raise RuntimeError("Can't find any android device/emulator")
        if len(ds) > 1:
            raise RuntimeError(
                "more than one device/emulator, please specify the serial number"
            )
        return ds[0]

    @deprecated(
        deprecated_in="0.2.1",
        removed_in="0.3.0",
        current_version=__version__,
        details="use device(serial=serial) instead")
    def device_with_serial(self, serial=None) -> 'AdbDevice':
        if not serial:
            return self.must_one_device()
        return AdbDevice(self, serial)

    def device(self, serial=None) -> 'AdbDevice':
        if not serial:
            return self.must_one_device()
        return AdbDevice(self, serial)

    def sync(self, serial) -> 'Sync':
        return Sync(self, serial)


class AdbDevice(ExtraUtilsMixin):
    def __init__(self, client: AdbClient, serial: str):
        self._client = client
        self._serial = serial
        self.logcat = LogcatManager(self)

    @property
    def serial(self):
        return self._serial

    def __repr__(self):
        return "AdbDevice(serial={})".format(self.serial)

    @property
    def sync(self) -> 'Sync':
        return Sync(self._client, self.serial)

    def adb_output(self, *args, **kwargs):
        """Run adb command and get its content

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
            return subprocess.check_output(
                cmdline, stderr=subprocess.STDOUT, shell=True).decode('utf-8')
        except subprocess.CalledProcessError as e:
            if kwargs.get('raise_error', True):
                raise EnvironmentError(
                    "subprocess", cmdline,
                    e.output.decode('utf-8', errors='ignore'))

    def shell(self, cmdargs: Union[str, list, tuple], rstrip=True) -> str:
        """Run shell inside device and get it's content

        Args:
            rstrip (bool): strip the last empty line (Default: True)

        Returns:
            string of output
        
        Examples:
            shell("ls -l")
            shell(["ls", "-l"])
            shell("ls | grep data")
        """
        if isinstance(cmdargs, (list, tuple)):
            cmdargs = subprocess.list2cmdline(cmdargs)
        output = self._client.shell(self._serial, cmdargs)
        if rstrip:
            output = output.rstrip()
        return output

    @deprecated(
        deprecated_in="0.2.4",
        removed_in="0.3.0",
        current_version=__version__,
        details="use shell function instead, eg shell(\"ls -l\")")
    def shell_output(self, *args) -> str:
        return self._client.shell(self._serial, subprocess.list2cmdline(args))

    def forward(self, local: str, remote: str):
        return self._client.forward(self._serial, local, remote)

    def forward_port(self, remote_port: int) -> int:
        """ forward remote port to local random port """
        for f in self._client.forward_list():
            if f.serial == self._serial and f.remote == 'tcp:' + str(
                    remote_port) and f.local.startswith("tcp:"):
                return int(f.local[len("tcp:"):])
        local_port = get_free_port()
        self._client.forward(self._serial, "tcp:" + str(local_port),
                             "tcp:" + str(remote_port))
        return local_port

    def forward_list(self):
        return self._client.forward_list(self._serial)

    def push(self, local: str, remote: str):
        self.adb_output("push", local, remote)

    def pull(self, local: str, remote: str):
        self.adb_output("pull", local, remote)


class Sync():
    def __init__(self, adbclient: AdbClient, serial: str):
        self._adbclient = adbclient
        self._serial = serial
        # self._path = path

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
                yield FileInfo(mode, size,
                               datetime.datetime.fromtimestamp(mtime), name)

    def list(self, path: str):
        return list(self.iter_directory(path))

    def push(self, src, dst: str, mode: int = 0o755):
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
        # print("TotalSize", total_size, self.stat(dst))

    def iter_content(self, path: str):
        with self._prepare_sync(path, "RECV") as c:
            while True:
                cmd = c.read(4)
                if cmd == "DONE":
                    break
                assert cmd == "DATA"
                chunk_size = struct.unpack("<I", c.read_raw(4))[0]
                chunk = c.read_raw(chunk_size)
                if len(chunk) != chunk_size:
                    raise RuntimeError("read chunk missing")
                yield chunk

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
    sync.push(
        io.BytesIO(b"hi5a4de5f4qa6we541fq6w1ef5a61f65ew1rf6we"), filepath,
        0o644)

    print("FileInfo", sync.stat(filepath))
    for chunk in sync.iter_content(filepath):
        print(chunk)
    # sync.pull(filepath)
