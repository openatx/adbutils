#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import io
import logging
import pathlib
import re
import socket
import subprocess
import threading
import typing
from typing import List, Optional, Union

from PIL import Image, UnidentifiedImageError
from deprecation import deprecated

from adbutils._proto import ShellReturnRaw
from adbutils._adb import AdbConnection, BaseClient
from adbutils._proto import *
from adbutils._proto import StrOrPathLike
from adbutils._utils import StopEvent, adb_path, get_free_port, list2cmdline
from adbutils._version import __version__
from adbutils.errors import AdbError



_DEFAULT_SOCKET_TIMEOUT = 600  # 10 minutes

logger = logging.getLogger(__name__)

class BaseDevice:
    """Basic operation for a device"""

    def __init__(
        self, client: BaseClient, serial: Optional[str] = None, transport_id: Optional[int] = None
    ):
        """
        Args:
            client (BaseClient): AdbClient instance
            serial (str): device serial
            transport_id (int): transport_id
        """
        self._client = client
        self._serial = serial
        self._transport_id = transport_id
        self._properties = {}  # store properties data
        self._features = {}

        if not serial and not transport_id:
            raise AdbError("serial, transport_id must set atleast one")

        self._prepare()

    def _prepare(self):
        """rewrite in sub class"""

    @property
    def serial(self) -> Optional[str]:
        return self._serial

    def open_transport(
        self, command: Optional[str] = None, timeout: Optional[float] = _DEFAULT_SOCKET_TIMEOUT
    ) -> AdbConnection:
        # connect has it own timeout
        c = self._client.make_connection(timeout=timeout)

        if command:
            if self._transport_id:
                c.send_command(f"host-transport-id:{self._transport_id}:{command}")
                c.check_okay()
            elif self._serial:
                c.send_command(f"host-serial:{self._serial}:{command}")
                c.check_okay()
            else:
                raise RuntimeError("should not reach here")
        else:
            if self._transport_id:
                c.send_command(f"host:transport-id:{self._transport_id}")
                c.check_okay()
            elif self._serial:
                # compatible with old adb version
                # https://github.com/openatx/adbutils/issues/145
                if self._client.server_version() >= 41:
                    c.send_command(f"host:tport:serial:{self._serial}")
                    c.check_okay()
                    c.read(8)  # skip 8 bytes
                else: # tested on 39,40
                    # 1.0.40 https://dl.google.com/android/repository/platform-tools_r28.0.1-darwin.zip
                    # 1.0.39 https://dl.google.com/android/repository/platform-tools_r26.0.1-darwin.zip
                    c.send_command("host:transport:" + self._serial)
                    c.check_okay()
            else:
                raise RuntimeError("should not reach here")
        return c

    def _get_with_command(self, cmd: str) -> str:
        with self.open_transport(cmd) as c:
            return c.read_string_block()

    def get_state(self) -> str:
        """return device state {offline,bootloader,device}"""
        return self._get_with_command("get-state")

    def get_serialno(self) -> str:
        """return the real device id, not the connect serial"""
        return self._get_with_command("get-serialno")

    def get_devpath(self) -> str:
        """example return: usb:12345678Y"""
        return self._get_with_command("get-devpath")

    def get_features(self) -> str:
        """
        Return example:
            'abb_exec,fixed_push_symlink_timestamp,abb,stat_v2,apex,shell_v2,fixed_push_mkdir,cmd'
        """
        features = self._get_with_command("features")
        self._features = set(features.split(','))
        return features

    @property
    def info(self) -> dict:
        return {
            "serialno": self.get_serialno(),
            "devpath": self.get_devpath(),
            "state": self.get_state(),
        }

    def __repr__(self):
        return "AdbDevice(serial={})".format(self.serial)

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
        cmds = [adb_path(), "-s", self._serial] if self._serial else [adb_path()]
        cmds.extend(args)
        try:
            return subprocess.check_output(
                cmds, stdin=subprocess.DEVNULL, stderr=subprocess.STDOUT
            ).decode("utf-8")
        except subprocess.CalledProcessError as e:
            if kwargs.get("raise_error", True):
                raise EnvironmentError(
                    "subprocess", cmds, e.output.decode("utf-8", errors="ignore")
                )

    def open_shell(self, cmdargs: Union[str, list, tuple]) -> AdbConnection:
        """Open a shell connection to the device

        Args:
            cmdargs (str | list | tuple): command args

        Returns:
            AdbConnection: shell connection object
        """
        if isinstance(cmdargs, (list, tuple)):
            cmdargs = list2cmdline(cmdargs)
        c = self.open_transport()
        c.send_command("shell:" + cmdargs)
        c.check_okay()
        return c
    
    def shell(
        self,
        cmdargs: Union[str, list, tuple],
        stream: bool = False,
        timeout: Optional[float] = _DEFAULT_SOCKET_TIMEOUT,
        encoding: str | None = "utf-8",
        rstrip=True,
    ) -> typing.Union[AdbConnection, str, bytes]:
        """Run shell inside device and get it's content

        Args:
            rstrip (bool): strip the last empty line (Default: True)
            stream (bool): return stream instead of string output (Default: False)
            timeout (float): set shell timeout
            encoding (str): set output encoding (Default: utf-8), set None to make return bytes
            rstrip (bool): strip the last empty line, only work when encoding is set

        Returns:
            string of output when stream is False
            AdbConnection when stream is True

        Raises:
            AdbTimeout

        Examples:
            shell("ls -l")
            shell(["ls", "-l"])
            shell("ls | grep data")
        """
        if isinstance(cmdargs, (list, tuple)):
            cmdargs = list2cmdline(cmdargs)
        c = self.open_shell(cmdargs)
        if stream:
            return c
        if timeout:
            c.conn.settimeout(timeout)
        try:
            output = c.read_until_close(encoding=encoding)
        finally:
            # ensure the connection is closed
            # https://github.com/openatx/uiautomator2/issues/998
            c.close()
        if encoding:
            return output.rstrip() if rstrip else output
        return output

    def shell2(
        self,
        cmdargs: Union[str, list, tuple],
        timeout: Optional[float] = _DEFAULT_SOCKET_TIMEOUT,
        encoding: str | None = "utf-8",
        rstrip=False,
        v2=False,
    ) -> Union[ShellReturn, ShellReturnRaw]:
        """
        Run shell command with detail output
        Args:
            cmdargs (str | list | tuple): command args
            timeout (float): set shell timeout, seconds
            encoding (str): set output encoding (Default: utf-8), set None to make return bytes
            rstrip (bool): strip the last empty line, only work when encoding is set
            shell_v2 (bool): attempt to use the shell_v2 protocol (and fail if not supported by device)

        Returns:
            ShellOutput

        Raises:
            AdbTimeout
        """
        if isinstance(cmdargs, (list, tuple)):
            cmdargs = list2cmdline(cmdargs)

        if v2:
            if not self._features:
                self._features = set(self.get_features().split(','))
            if "shell_v2" not in self._features:
                v2 = False
                logger.warning("shell_v2 specified but not supported by device")

        if v2:
            result = self._shell_v2(cmdargs, timeout)
        else:
            result = self._shell_v1(cmdargs, timeout)

        if encoding:
            result = ShellReturn(
                command=result.command,
                returncode=result.returncode,
                output=result.output.decode(encoding, errors="replace"),
                stderr=result.stderr.decode(encoding, errors="replace"),
                stdout=result.stdout.decode(encoding, errors="replace"),
            )
            if rstrip:
                result.output = result.output.rstrip()
                result.stderr = result.stderr.rstrip()
                result.stdout = result.stdout.rstrip()
        return result
    
    def _shell_v1(self, cmdargs: str, timeout: Optional[float] = _DEFAULT_SOCKET_TIMEOUT) -> ShellReturnRaw:
        assert isinstance(cmdargs, str)
        MAGIC = "X4EXIT:"
        newcmd = cmdargs + f"; echo {MAGIC}$?"
        output: bytes = self.shell(newcmd, timeout=timeout, encoding=None, rstrip=False) # type: ignore
        rindex = output.rfind(MAGIC.encode())
        if rindex == -1:  # normally will not possible
            raise AdbError("shell output invalid", newcmd, output)
        returncode = int(output[rindex + len(MAGIC) :])
        output = output[:rindex]
        return ShellReturnRaw(command=cmdargs, returncode=returncode, output=output)

    def _shell_v2(self, cmdargs: str, timeout: Optional[float] = _DEFAULT_SOCKET_TIMEOUT) -> ShellReturnRaw:
        c = self.open_transport(timeout=timeout)
        c.send_command(f"shell,v2:{cmdargs}")
        c.check_okay()
        stdout_buffer = io.BytesIO()
        stderr_buffer = io.BytesIO()
        output_buffer = io.BytesIO()
        exit_code = 255

        while True:
            header = c.read_exact(5)
            msg_id = header[0]
            length = int.from_bytes(header[1:5], byteorder="little")
            if length == 0:
                continue

            data = c.read_exact(length)
            if msg_id == 1:
                stdout_buffer.write(data)
                output_buffer.write(data)
            elif msg_id == 2:
                stderr_buffer.write(data)
                output_buffer.write(data)
            elif msg_id == 3:
                exit_code = data[0]
                break
        return ShellReturnRaw(
            command=cmdargs,
            returncode=exit_code,
            output=output_buffer.getvalue(),
            stderr=stderr_buffer.getvalue(),
            stdout=stdout_buffer.getvalue(),
        )

    def forward(self, local: str, remote: str, norebind: bool = False):
        cmd = "forward"
        if norebind:
            cmd += ":norebind"
        cmd += f':{local};{remote}'
        c = self.open_transport(cmd)
        c.close()

    def forward_port(self, remote: Union[int, str]) -> int:
        """forward remote port to local random port"""
        if isinstance(remote, int):
            remote = "tcp:" + str(remote)
        for f in self.forward_list():
            if (
                f.serial == self._serial
                and f.remote == remote
                and f.local.startswith("tcp:")
            ):  # yapf: disable
                return int(f.local[len("tcp:") :])
        local_port = get_free_port()
        self.forward("tcp:" + str(local_port), remote)
        return local_port

    def forward_list(self) -> List[ForwardItem]:
        cmd = 'list-forward'
        with self.open_transport(cmd) as c:
            content = c.read_string_block()
            items = []
            for line in content.splitlines():
                parts = line.split()
                if len(parts) != 3:
                    continue
                items.append(ForwardItem(*parts))
            return items
            
        items = self._client.forward_list()
        return [item for item in items if item.serial == self._serial]

    def reverse(self, remote: str, local: str, norebind: bool = False):
        """
        Args:
            serial (str): device serial
            remote, local (str):
                - tcp:<port>
                - localabstract:<unix domain socket name>
                - localreserved:<unix domain socket name>
                - localfilesystem:<unix domain socket name>
            norebind (bool): fail if already reversed when set to true

        Raises:
            AdbError
        """
        with self.open_transport() as c:
            args = ["reverse:forward"]
            if norebind:
                args.append("norebind")
            args.append(remote + ";" + local)
            c.send_command(":".join(args))
            c.check_okay() # this OKAY means message was received
            c.check_okay() # check reponse

    def reverse_list(self) -> List[ReverseItem]:
        with self.open_transport() as c:
            c.send_command("reverse:list-forward")
            c.check_okay()
            content = c.read_string_block()
            items = []
            for line in content.splitlines():
                parts = line.split()
                if len(parts) != 3:
                    continue
            items.append(ReverseItem(*parts[1:]))
        return items
    
    def framebuffer(self) -> Image.Image:
        """Capture device screen and return PIL.Image object (Not very stable)

        Raises:
            NotImplementedError
        """
        # Ref: https://android.googlesource.com/platform/system/core/+/android-cts-7.0_r18/adb/framebuffer_service.cpp
        # Ref: https://github.com/DeviceFarmer/adbkit/blob/c16081384ca34addbdab318bda3c76434b7538af/src/adb/command/host-transport/framebuffer.ts
        c = self.open_transport()
        c.send_command("framebuffer:")
        c.check_okay()
        
        version = c.read_uint32()
        if version == 16:
            raise NotImplementedError("Unsupported version 16")
        bpp = c.read_uint32() # bits per pixel
        if bpp != 24 and bpp != 32:
            raise NotImplementedError("Unsupported bpp(bits per pixel)", bpp)
        size = c.read_uint32()
        if size == 1:
            # FIXME: what is this?
            size = c.read_uint32()
        width = c.read_uint32()
        height = c.read_uint32()
        red_offset = c.read_uint32()
        red_length = c.read_uint32() # always 8
        blue_offset = c.read_uint32()
        blue_length = c.read_uint32() # always 8
        green_offset = c.read_uint32()
        green_length = c.read_uint32() # always 8
        alpha_offset = c.read_uint32()
        alpha_length = c.read_uint32()

        color_format = 'RGB'
        if blue_offset == 0:
            color_format = 'BGR'
        if bpp == 32 or alpha_length:
            color_format += 'A'

        if color_format != 'RGBA' and color_format != 'RGB':
            raise NotImplementedError("Unsupported color format")
        buffer = c.read(size)
        if len(buffer) != size:
            raise UnidentifiedImageError("framebuffer size not match", size, len(buffer))
        image = Image.frombytes(color_format, (width, height), buffer)
        return image

    @deprecated(deprecated_in="2.6.0", removed_in="3.0.0", current_version=__version__, details="use sync.push instead")
    def push(self, local: str, remote: str):
        """ alias for sync.push """
        return self.sync.push(local, remote)

    def create_connection(
        self, network: Network, address: Union[int, str]
    ) -> socket.socket:
        """
        Used to connect a socket (unix of tcp) on the device

        Returns:
            socket object

        Raises:
            AdbError, ValueError
        """
        def _connect(c: AdbConnection) -> socket.socket:
            if network == Network.TCP:
                assert isinstance(address, int)
                c.send_command("tcp:" + str(address))
                c.check_okay()
            elif network in [Network.UNIX, Network.LOCAL_ABSTRACT]:
                assert isinstance(address, str)
                c.send_command("localabstract:" + address)
                c.check_okay()
            elif network in [
                Network.LOCAL_FILESYSTEM,
                Network.LOCAL,
                Network.DEV,
                Network.LOCAL_RESERVED,
            ]:
                c.send_command(network + ":" + str(address))
                c.check_okay()
            else:
                raise ValueError("Unsupported network type", network)
            return c.conn
        
        c = self.open_transport()
        try:
            return _connect(c)
        except:
            c.close()
            raise

    def root(self):
        """restart adbd as root

        Return example:
            cannot run as root in production builds
        """
        # Ref: https://github.com/Swind/pure-python-adb/blob/master/ppadb/command/transport/__init__.py#L179
        with self.open_transport() as c:
            c.send_command("root:")
            c.check_okay()
            return c.read_until_close()

    def tcpip(self, port: int):
        """restart adbd listening on TCP on PORT

        Return example:
            restarting in TCP mode port: 5555
        """
        with self.open_transport() as c:
            c.send_command("tcpip:" + str(port))
            c.check_okay()
            return c.read_until_close()

    def logcat(
        self,
        file: Optional[StrOrPathLike] = None,
        clear: bool = False,
        re_filter: Optional[Union[str, re.Pattern]] = None,
        command: str = "logcat -v time",
    ) -> StopEvent:
        """
        Args:
            file (str): file path to save logcat
            clear (bool): clear logcat before start
            re_filter (str | re.Pattern): regex pattern to filter logcat
            command (str): logcat command, default is "logcat -v time"

        Example usage:
            >>> evt = device.logcat("logcat.txt", clear=True, re_filter=".*python.*")
            >>> time.sleep(10)
            >>> evt.stop()
        """
        if re_filter:
            if isinstance(re_filter, str):
                re_filter = re.compile(re_filter)
            assert isinstance(re_filter, re.Pattern)

        if clear:
            self.shell("logcat --clear")

        def _filter_func(line: str) -> bool:
            if re_filter is None:
                return True
            return re_filter.search(line) is not None

        def _copy2file(
            stream: AdbConnection,
            fdst: typing.TextIO,
            event: StopEvent,
            filter_func: typing.Callable[[str], bool],
        ):
            try:
                fsrc = stream.conn.makefile("r", encoding="UTF-8", errors="replace")
                while not event.is_stopped():
                    line = fsrc.readline()
                    if not line:
                        break
                    if filter_func(line):
                        fdst.write(line)
                        fdst.flush()
            finally:
                fsrc.close()
                stream.close()
                event.done()

        event = StopEvent()
        stream = self.shell(command, stream=True)
        fdst = pathlib.Path(file).open("w", encoding="UTF-8")
        threading.Thread(
            name="logcat",
            target=_copy2file,
            args=(stream, fdst, event, _filter_func),
            daemon=True,
        ).start()
        return event


class Property:

    def __init__(self, d: BaseDevice):
        self._d = d

    def __str__(self):
        return f"product:{self.name} model:{self.model} device:{self.device}"

    def get(self, name: str, cache=True) -> str:
        if cache and name in self._d._properties:
            return self._d._properties[name]
        value = self._d._properties[name] = self._d.shell(["getprop", name]).strip()
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

