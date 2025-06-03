#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Created on Sun Apr 07 2024 19:38:48 by codeskyblue
"""


import logging
import struct
import datetime
import typing
import os
import io
import stat
import pathlib
from contextlib import contextmanager

from adbutils._adb import AdbError
from adbutils._proto import FileInfo
from adbutils._utils import append_path
from adbutils.errors import AdbSyncError
from adbutils._device_base import BaseDevice

logger = logging.getLogger(__name__)

_OKAY = "OKAY"
_FAIL = "FAIL"
_DENT = "DENT"  # Directory Entity
_DONE = "DONE"
_DATA = "DATA"


class Sync():

    def __init__(self, device: BaseDevice):
        self._device = device

    @contextmanager
    def _prepare_sync(self, path: str, cmd: str):
        with self._device.open_transport(timeout=None) as c:
            c.send_command("sync:")
            c.check_okay()
            # {COMMAND}{LittleEndianPathLength}{Path}
            path_len = len(path.encode('utf-8'))
            c.conn.send(
                cmd.encode("utf-8") + struct.pack("<I", path_len) +
                path.encode("utf-8"))
            yield c

    def exists(self, path: str) -> bool:
        finfo = self.stat(path)
        return finfo.mtime is not None

    def stat(self, path: str) -> FileInfo:
        with self._prepare_sync(path, "STAT") as c:
            assert "STAT" == c.read_string(4)
            mode, size, mtime = struct.unpack("<III", c.conn.recv(12))
            # when mtime is 0, windows will error
            mdtime = datetime.datetime.fromtimestamp(mtime) if mtime else None
            return FileInfo(mode, size, mdtime, path)

    def iter_directory(self, path: str):
        with self._prepare_sync(path, "LIST") as c:
            while 1:
                response = c.read_string(4)
                if response == _DONE:
                    break
                mode, size, mtime, namelen = struct.unpack(
                    "<IIII", c.conn.recv(16))
                name = c.read_string(namelen)
                try:
                    mtime = datetime.datetime.fromtimestamp(mtime)
                except OSError:  # bug in Python 3.6
                    mtime = datetime.datetime.now()
                yield FileInfo(mode, size, mtime, name)

    def list(self, path: str) -> typing.List[str]:
        return list(self.iter_directory(path))

    def push(self, src: typing.Union[pathlib.Path, str, bytes, bytearray, typing.BinaryIO],
             dst: typing.Union[pathlib.Path, str],
             mode: int = 0o755,
             check: bool = False) -> int:
        """
        Push file from local:src to device:dst

        Args:
            src: source file path
            dst: destination file path or directory path
            mode: file mode
            check: check if push size is correct
        
        Returns:
            total file size pushed
        """
        if isinstance(dst, pathlib.Path):
            dst = dst.as_posix()
        finfo = self.stat(dst)
        if finfo.mode & stat.S_IFDIR != 0:
            if not isinstance(src, (pathlib.Path, str)):
                raise AdbSyncError("src should be a file path when dst is a directory")
            dst = append_path(dst, pathlib.Path(src).name)
            logger.debug("dst is a directory, update dst to %s", dst)
        return self._push_file(src, dst, mode, check)
    
    def _push_file(
            self,
            src: typing.Union[pathlib.Path, str, bytes, bytearray, typing.BinaryIO],
            dst: str,
            mode: int = 0o755,
            check: bool = False) -> int:  # yapf: disable
        # IFREG: File Regular
        # IFDIR: File Directory
        if isinstance(src, pathlib.Path):
            src = src.open("rb")
        elif isinstance(src, str):
            src = pathlib.Path(src).open("rb")
        elif isinstance(src, (bytes, bytearray)):
            src = io.BytesIO(src)
        else:
            if not hasattr(src, "read"):
                raise TypeError("Invalid src type: %s" % type(src))

        path = dst + "," + str(stat.S_IFREG | mode)
        total_size = 0
        with self._prepare_sync(path, "SEND") as c:
            r = src if hasattr(src, "read") else open(src, "rb")
            try:
                while True:
                    chunk = r.read(4096) # should not >64k
                    if not chunk:
                        mtime = int(datetime.datetime.now().timestamp())
                        c.conn.send(b"DONE" + struct.pack("<I", mtime))
                        break
                    c.conn.send(b"DATA" + struct.pack("<I", len(chunk)))
                    c.conn.send(chunk)
                    total_size += len(chunk)
                status_msg = c.read_string(4)
                if status_msg != _OKAY:
                    raise AdbError(status_msg)
            finally:
                if hasattr(r, "close"):
                    r.close()
        if check:
            file_size = self.stat(dst).size
            if total_size != file_size:
                raise AdbError(
                    "Push not complete, expect pushed %d, actually pushed %d" %
                    (total_size, file_size))
        return total_size

    def iter_content(self, path: str) -> typing.Iterator[bytes]:
        with self._prepare_sync(path, "RECV") as c:
            while True:
                cmd = c.read_string(4)
                if cmd == _FAIL:
                    str_size = struct.unpack("<I", c.read(4))[0]
                    error_message = c.read_string(str_size)
                    raise AdbError(error_message, path)
                elif cmd == _DONE:
                    break
                elif cmd == _DATA:
                    chunk_size = struct.unpack("<I", c.read(4))[0]
                    chunk = c.read(chunk_size)
                    if len(chunk) != chunk_size:
                        raise AdbError("read chunk missing")
                    yield chunk
                else:
                    raise AdbError("Invalid sync cmd", cmd)

    def read_bytes(self, path: str) -> bytes:
        return b''.join(self.iter_content(path))

    def read_text(self, path: str, encoding: str = 'utf-8') -> str:
        """ read content of a file """
        return self.read_bytes(path).decode(encoding=encoding)

    def pull(self, src: str, dst: typing.Union[str, pathlib.Path], exist_ok: bool = False) -> int:
        """
        Pull file or directory from device:src to local:dst

        Returns:
            total file size pulled
        """
        src_file_info = self.stat(src)
        is_src_file = src_file_info.mode & stat.S_IFREG != 0
        
        if is_src_file:
            return self.pull_file(src, dst)
        else:
            return self.pull_dir(src, dst, exist_ok)


    def pull_file(self, src: str, dst: typing.Union[str, pathlib.Path]) -> int:
        """
        Pull file from device:src to local:dst

        Returns:
            file size
        """
        if isinstance(dst, str):
            dst = pathlib.Path(dst)
        with dst.open("wb") as f:
            size = 0
            for chunk in self.iter_content(src):
                f.write(chunk)
                size += len(chunk)
            return size
        
    def pull_dir(self, src: str, dst: typing.Union[str, pathlib.Path], exist_ok: bool = True) -> int:
        """Pull directory from device:src into local:dst

        Returns:
            total files size pulled
        """

        def rec_pull_contents(src: str, dst: typing.Union[str, pathlib.Path], exist_ok: bool = True) -> int:
            s = 0
            items = list(self.iter_directory(src))

            items = list(filter(
                lambda i: i.path != '.' and i.path != '..',
                items
            ))

            dirs = list(
                filter(
                    lambda f: stat.S_IFDIR & f.mode != 0,
                    items
                ))
            files = list(
                filter(
                    lambda f: stat.S_IFREG & f.mode != 0,
                    items
                ))
            
            for dir in dirs:
                new_src:str = append_path(src, dir.path) 
                new_dst:pathlib.Path = pathlib.Path(append_path(dst, dir.path)) 
                os.makedirs(new_dst, exist_ok=exist_ok)
                s += rec_pull_contents(new_src, new_dst ,exist_ok=exist_ok)

            for file in files:
                new_src:str = append_path(src, file.path) 
                new_dst:str = append_path(dst, file.path) 
                s += self.pull_file(new_src, new_dst)

            return s


        if isinstance(dst, str):
            dst = pathlib.Path(dst)
        os.makedirs(dst, exist_ok=exist_ok)

        return rec_pull_contents(src, dst, exist_ok=exist_ok)

