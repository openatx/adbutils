import hashlib
import importlib.resources
import os
import random
import shlex
import socket
import subprocess
import sys
import tempfile
import threading
import time
import typing
import zipfile
import typing
import pathlib

from shutil import which

from adbutils.errors import AdbError


MB = 1024 * 1024


def append_path(base: typing.Union[str, pathlib.Path], addition: str) -> str:
    if isinstance(base, pathlib.Path):
        return (base / addition).as_posix()
    else:
        return base + '/' + addition if base[-1] != '/' else base + addition

def humanize(n: int) -> str:
    return '%.1f MB' % (float(n) / MB)


def is_port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('127.0.0.1', port)) == 0


def get_free_port():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind(('127.0.0.1', 0))
        try:
            return s.getsockname()[1]
        finally:
            s.close()
    except OSError:
        # bind 0 will fail on Manjaro, fallback to random port
        # https://github.com/openatx/adbutils/issues/85
        for _ in range(20):
            port = random.randint(10000, 20000)
            if not is_port_in_use(port):
                return port
        raise AdbError("No free port found")


def list2cmdline(args: typing.Union[list, tuple]):
    """ do not use subprocess.list2cmdline, use this instead

    Reason:
        subprocess.list2cmdline(['echo', '&']) --> "a &", but what I expect should be "a '&'"
    """
    return ' '.join(map(shlex.quote, args))


def current_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        return ip
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()

def _get_bin_dir():
    if sys.version_info < (3, 9):
        context = importlib.resources.path("adbutils.binaries", "__init__.py")
    else:
        ref = importlib.resources.files("adbutils.binaries") / "__init__.py"
        context = importlib.resources.as_file(ref)
    with context as path:
        pass
    # Return the dir. We assume that the data files are on a normal dir on the fs.
    return str(path.parent)


def adb_path() -> str:
    # 0. check env: ADBUTILS_ADB_PATH
    if os.getenv("ADBUTILS_ADB_PATH"):
        return os.getenv("ADBUTILS_ADB_PATH")
        
    # 1. find in $PATH
    exe = which("adb")
    if exe and _is_valid_exe(exe):
        return exe
    
    # 2. use buildin adb
    bin_dir = _get_bin_dir()
    exe = os.path.join(bin_dir, "adb.exe" if os.name == 'nt' else 'adb')
    if os.path.isfile(exe) and _is_valid_exe(exe):
        return exe

    raise AdbError("No adb exe could be found. Install adb on your system")


def _popen_kwargs(prevent_sigint=False):
    startupinfo = None
    preexec_fn = None
    creationflags = 0
    if sys.platform.startswith("win"):
        # Stops executable from flashing on Windows (see imageio/imageio-ffmpeg#22)
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    if prevent_sigint:
        # Prevent propagation of sigint (see imageio/imageio-ffmpeg#4)
        # https://stackoverflow.com/questions/5045771
        if sys.platform.startswith("win"):
            creationflags = 0x00000200
        else:
            preexec_fn = os.setpgrp  # the _pre_exec does not seem to work
    return {
        "startupinfo": startupinfo,
        "creationflags": creationflags,
        "preexec_fn": preexec_fn,
    }


def _is_valid_exe(exe: str):
    cmd = [exe, "version"]
    try:
        subprocess.check_call(
            cmd, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
            stderr=subprocess.STDOUT, **_popen_kwargs()
        )
        return True
    except (OSError, ValueError, subprocess.CalledProcessError):
        return False


class ReadProgress():
    def __init__(self, r, total_size: int, source_path=None):
        """
        Args:
            source_path (str): store read content to filepath
        """
        self.r = r
        self.total = total_size
        self.copied = 0
        self.start_time = time.time()
        self.update_time = time.time()
        self.m = hashlib.md5()
        self._chunk_size = 0
        self._hash = ''
        self._tmpfd = None if source_path else tempfile.NamedTemporaryFile(suffix=".apk")
        self._filepath = source_path

    def update(self, chunk: bytes):
        chunk_size = len(chunk)
        self.m.update(chunk)
        if chunk_size == 0:
            self._hash = self.m.hexdigest()
        self.copied += chunk_size
        self._chunk_size += chunk_size

        if self.total:
            percent = float(self.copied) / self.total * 100
        else:
            percent = 0.0 if chunk_size else 100.0

        p = int(percent)
        duration = time.time() - self.update_time
        if p == 100.0 or duration > 1.0:
            if duration:
                speed = humanize(self._chunk_size / duration) + "/s"
            else:
                copytime = max(0.1, time.time() - self.start_time)
                speed = humanize(self.copied / copytime) + "/s"

            self.update_time = time.time()
            self._chunk_size = 0

            copysize = humanize(self.copied)
            totalsize = humanize(self.total)
            if sys.stdout.isatty():
                print("{:.1f}%\t{} [{}/{}]".format(percent, speed, copysize,
                                                   totalsize))

    def read(self, n: int) -> bytes:
        chunk = self.r.read(n)
        self.update(chunk)
        if self._tmpfd:
            self._tmpfd.write(chunk)
        return chunk
    
    def filepath(self):
        if self._filepath:
            return self._filepath
        self._tmpfd.seek(0)
        return self._tmpfd.name


class APKReader:
    def __init__(self, fp: typing.BinaryIO):
        self._fp = fp
    
    def dump_info(self):
        try:
            from apkutils import APK
        except ImportError:
            sys.exit("apkutils is not installed, please install it first")
        apk = APK.from_io(self._fp)
        activities = apk.get_main_activities()
        main_activity = activities[0] if activities else None
        package_name = apk.get_package_name()
        if main_activity and main_activity.find(".") == -1:
            main_activity = "." + main_activity
        
        print("package:", package_name)
        print("main-activity:", main_activity)
        print("version-name:", apk._version_name)
        print('version-code:', apk._version_code)


class StopEvent:
    def __init__(self):
        self.__stop = threading.Event()
        self.__done = threading.Event()
    
    def stop(self, timeout=None):
        """ send stop signal and wait signal accepted 
        
        Raises:
            TimeoutError
        """
        self.__stop.set()
        if not self.__done.wait(timeout):
            raise TimeoutError("wait for stopped timeout", timeout)

    def stop_nowait(self):
        """ send stop signal """
        self.__stop.set()

    def is_stopped(self) -> bool:
        return self.__stop.is_set()

    def done(self):
        """ for worker thread to notify stop signal accepted """
        self.__done.set()
    
    def is_done(self) -> bool:
        """ check if background worker has stopped """
        return self.__done.is_set()
    
    def reset(self):
        self.__stop.clear()
        self.__done.clear()


def escape_special_characters(text: str) -> str:
    """
    A helper that escape special characters

    Args:
        text: str
    """
    escaped = text.translate(
        str.maketrans({
            "-": r"\-",
            "+": r"\+",
            "[": r"\[",
            "]": r"\]",
            "(": r"\(",
            ")": r"\)",
            "{": r"\{",
            "}": r"\}",
            "\\": r"\\\\",
            "^": r"\^",
            "$": r"\$",
            "*": r"\*",
            ".": r"\.",
            ",": r"\,",
            ":": r"\:",
            "~": r"\~",
            ";": r"\;",
            ">": r"\>",
            "<": r"\<",
            "%": r"\%",
            "#": r"\#",
            "\'": r"\\'",
            "\"": r'\\"',
            "`": r"\`",
            "!": r"\!",
            "?": r"\?",
            "|": r"\|",
            "=": r"\=",
            "@": r"\@",
            "/": r"\/",
            "_": r"\_",
            " ": r"%s",  # special
            "&": r"\&"
        }))
    return escaped
