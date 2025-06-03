#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Created on Sun Apr 07 2024 19:29:55 by codeskyblue
"""

import abc
import os
import pathlib
import shutil
import signal
import socket
import subprocess
import textwrap
import threading
import time
import typing
import weakref

from retry import retry

from adbutils.errors import AdbError
from adbutils._utils import adb_path
from adbutils._adb import AdbConnection, Network
from adbutils._interfaces import AbstractDevice


class AbstractScreenrecord(abc.ABC):
    @abc.abstractmethod
    def is_recording(self) -> bool:
        """return whether recording"""

    @abc.abstractmethod
    def check_env(self) -> bool:
        """check if environment if valid"""

    @abc.abstractmethod
    def _start(self, filename: str):
        pass

    @abc.abstractmethod
    def _stop(self):
        pass

    def start_recording(self, filename: str):
        if self.is_recording():
            print("recording already running")
            return
        self._start(filename)

    def stop_recording(self):
        if not self.is_recording():
            print("recording alreay stopped")
            return
        self._stop()


class ScreenrecordExtension(AbstractDevice):
    def __init__(self):
        self._record_client = None

    def start_recording(self, filename: str):
        """start video recording

        Raises:
            AdbError (when no record client)
        """
        self.__get_screenrecord_impl().start_recording(filename)

    def stop_recording(self):
        """stop video recording"""
        return self.__get_screenrecord_impl().stop_recording()

    def is_recording(self) -> bool:
        """is recording"""
        return self.__get_screenrecord_impl().is_recording()

    def __get_screenrecord_impl(self) -> AbstractScreenrecord:
        if self._record_client:
            return self._record_client
        r1 = _ScrcpyScreenRecord(self)
        if r1.check_env():
            self._record_client = r1
            return r1
        r2 = _AdbScreenRecord(self)
        if r2.check_env():
            self._record_client = r2
            return r2
        raise AdbError("no valid screenrecord client")


class _ScrcpyScreenRecord(AbstractScreenrecord):

    def __init__(self, d: AbstractDevice):
        self._d = d
        bin_name = "scrcpy" if os.name == "posix" else "scrcpy.exe"
        self._scrcpy_path = shutil.which(bin_name)
        self._p: subprocess.Popen = None

    def is_recording(self) -> bool:
        return bool(self._p and self._p.poll() is None)

    def check_env(self) -> bool:
        return self._scrcpy_path is not None

    def _start(self, filename: str):
        env = os.environ.copy()
        env["ADB"] = adb_path()
        env["ANDROID_SERIAL"] = self._d.serial
        self._p = subprocess.Popen(
            [self._scrcpy_path, "--no-control", "--no-display", "--record", filename],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            env=env,
        )
        self._finalizer = weakref.finalize(self._p, self._p.kill)

    def _stop(self):
        self._finalizer.detach()
        self._p.send_signal(signal.SIGINT)
        try:
            returncode = self._p.wait(timeout=3)
            if returncode == 0:
                pass  # 正常退出
            elif returncode == 1:
                raise AdbError("scrcpy error: start failure")
            elif returncode == 2:
                raise AdbError("scrcpy error: device disconnected while running")
            else:
                raise AdbError("scrcpy error", returncode)
        except subprocess.TimeoutExpired:
            self._p.kill()
            raise AdbError("scrcpy not handled SIGINT, killed")


class _ScrcpyJarScreenrecord:
    """
    # -y  overwrite output files
    ffmpeg -i "output.h264" -c:v copy -f mp4 -y "video.mp4"

    遗留问题：秒表视频，转化后的视频时长不对啊（本来5s的，转化后变成了20s）

    https://stackoverflow.com/questions/21263064/how-to-wrap-h264-into-a-mp4-container

    协议没有完全理解，Frame的pts也没有。还是需要多看看scrcpy的代码才行。
    """

    def __init__(self, d: AbstractDevice, h264_filename: str = None):
        self._d = d
        self._filename = h264_filename
        self._conn: AdbConnection = None
        self._done_event = threading.Event()

    def is_recording(self) -> bool:
        return self._conn and not self._conn.closed

    def _start(self, filename: str):
        self._filename = filename
        curdir = pathlib.Path(__file__).absolute().parent
        device_jar_path = "/data/local/tmp/scrcpy-server.jar"

        # scrcpy deleted
        scrcpy_server_jar_path = curdir.joinpath("binaries/scrcpy-server-1.24.jar")
        assert scrcpy_server_jar_path.exists()

        self._d.sync.push(scrcpy_server_jar_path, device_jar_path)

        opts = [
            "control=false",
            "bit_rate=8000000",
            "tunnel_forward=true",
            "lock_video_orientation=-1",
            "send_dummy_byte=false",
            "send_device_meta=false",
            "send_frame_meta=true",
            "downsize_on_error=true",
        ]
        cmd = [
            "CLASSPATH=" + device_jar_path,
            "app_process",
            "/",
            "--nice-name=scrcpy-server",
            "com.genymobile.scrcpy.Server",
            "1.24",
        ] + opts
        _c = self._d.shell(cmd, stream=True)
        c: AdbConnection = _c
        del _c
        message = c.conn.recv(100).decode("utf-8")
        print("Scrcpy:", message)
        self._conn = c
        threading.Thread(
            name="scrcpy_main", target=self._copy2null, args=(c.conn,), daemon=True
        ).start()
        time.sleep(0.1)
        stream_sock = self._safe_dial_scrcpy()
        fh = pathlib.Path(self._filename).open("wb")
        threading.Thread(
            name="socket_copy",
            target=self._copy2file,
            args=(stream_sock, fh),
            daemon=True,
        ).start()

    @retry(AdbError, tries=10, delay=0.1, jitter=0.01)
    def _safe_dial_scrcpy(self) -> socket.socket:
        return self._d.create_connection(Network.LOCAL_ABSTRACT, "scrcpy")

    def _copy2null(self, s: socket.socket):
        while True:
            try:
                chunk = s.recv(1024)
                if chunk == b"":
                    print("O:", chunk.decode("utf-8"))
                    break
            except:
                break
        print("Scrcpy mainThread stopped")

    def _copy2file(self, s: socket.socket, fh: typing.BinaryIO):
        while True:
            chunk = s.recv(1 << 16)
            if not chunk:
                break
            fh.write(chunk)
        fh.close()
        print("Copy h264 stream finished", flush=True)
        self._done_event.set()

    def _stop(self) -> bool:
        self._conn.close()
        self._done_event.wait(timeout=3.0)
        time.sleep(1)
        self._done_event.clear()


class _AdbScreenRecord(AbstractScreenrecord):

    def __init__(self, d: AbstractDevice, remote_path=None, autostart=False):
        """The maxium record time is 3 minutes"""
        self._d = d
        if not remote_path:
            remote_path = "/sdcard/adbutils-tmp-video-%d.mp4" % int(time.time() * 1000)
        self._remote_path = remote_path
        self._stream = None

    def check_env(self) -> bool:
        ret = self._d.shell2(["which", "screenrecord"])
        return ret.returncode == 0

    def is_recording(self) -> bool:
        return bool(self._stream and not self._stream.closed)

    def _start(self, filename: str):
        self._filename = filename
        script_content = textwrap.dedent(
            """\
        #!/system/bin/sh
        # generate by adbutils
        screenrecord "$1" &
        PID=$!
        read ANY
        kill -INT $PID
        wait
        """
        ).encode("utf-8")
        self._d.sync.push(script_content, "/sdcard/adbutils-screenrecord.sh")
        self._stream: AdbConnection = self._d.shell(
            ["sh", "/sdcard/adbutils-screenrecord.sh", self._remote_path], stream=True
        )

    def _stop(self):
        self._stream.send(b"\n")
        self._stream.read_until_close()
        self._stream.close()

        self._d.sync.pull(self._remote_path, self._filename)
        self._d.remove(self._remote_path)
