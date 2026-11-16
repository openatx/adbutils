# -*- coding: utf-8 -*-

"""Created on Sun Apr 07 2024 19:52:19 by codeskyblue
"""

import abc
import io
import logging
import pathlib
import re
import tempfile
import threading
from typing import List, Optional, Union
from adbutils.errors import AdbError
from adbutils.sync import Sync
from adbutils._proto import WindowSize
from PIL import Image

try:
    from PIL import UnidentifiedImageError
except ImportError:
    # fix for py37
    UnidentifiedImageError = OSError

logger = logging.getLogger(__name__)

# When a device has more than one display, screencap prepends a warning to
# stdout unless -d is given, so the png has to be located by its signature
# instead of assuming the buffer starts with it.
_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"

class AbstractDevice(abc.ABC):
    @property
    @abc.abstractmethod
    def sync(self) -> Sync:
        pass

    @abc.abstractmethod
    def shell(self, cmd: str, encoding: Optional[str]) -> Union[str, bytes]:
        pass

    @abc.abstractmethod
    def exec_out(self, cmdargs: Union[str, List[str]]) -> bytes:
        pass

    @abc.abstractmethod
    def window_size(self) -> WindowSize:
        pass

    @abc.abstractmethod
    def framebuffer(self) -> Image.Image:
        pass

class ScreenshotExtesion(AbstractDevice):
    def screenshot(self, display_id: Optional[int] = None, error_ok: bool = True) -> Image.Image:
        """ Take a screenshot and return PIL.Image.Image object
        Args:
            display_id: int, default None, see "dumpsys SurfaceFlinger --display-id" for valid display IDs
            error_ok: bool, default True, if True, return a black image when capture failed
        
        Returns:
            PIL.Image.Image object
        
        Raises:
            AdbError: when capture failed and error_ok is False
        """
        try:
            pil_image = self.__screencap(display_id)
            if pil_image.mode == "RGBA":
                pil_image = pil_image.convert("RGB")
            return pil_image
        except UnidentifiedImageError as e:
            logger.warning("screencap error: %s", e)
            if error_ok:
                wsize = self.window_size()
                return Image.new("RGB", wsize, (0, 0, 0))
            else:
                raise AdbError("screencap error") from e
    
    def __screencap(self, display_id: int = None) -> Image.Image:
        """ Take a screenshot and return PIL.Image.Image object
        """
        cmdargs = ['screencap', '-p']
        if display_id is not None:
            _id = self.__get_real_display_id(display_id)
            cmdargs.extend(['-d', _id])
        png_bytes = self.__screencap_bytes(cmdargs)
        return Image.open(io.BytesIO(png_bytes))

    def __screencap_bytes(self, cmdargs: List[str]) -> bytes:
        """Capture a png, preferring the raw exec: service

        The pty behind shell: rewrites LF bytes inside a png on API 23, so the
        image must never be streamed through it. exec: is used first, and the
        file + pull path is kept as a fallback for adb builds without
        exec-out (platform-tools before 2016).

        Returns b"" when nothing usable was captured, so screenshot() can
        apply its error_ok fallback.
        """
        exec_error: Optional[AdbError] = None
        try:
            png_bytes = self.__trim_png(self.exec_out(cmdargs))
            if png_bytes:
                return png_bytes
        except AdbError as e:
            exec_error = e

        try:
            return self.__screencap_to_file(cmdargs)
        except Exception as e:
            logger.debug("screencap file fallback failed: %s", e)
            if exec_error is not None:
                # e.g. device offline: report the transport error instead of a
                # meaningless "cannot identify image file" further down
                raise exec_error from e
            return b""

    @staticmethod
    def __trim_png(data: bytes) -> bytes:
        """Drop anything before the png signature, b"" when there is none"""
        index = data.find(_PNG_SIGNATURE)
        if index < 0:
            return b""
        return data[index:]

    def __screencap_to_file(self, cmdargs: List[str]) -> bytes:
        """screencap to a device file, then pull it (pre 2.4 behaviour)

        Used for adb builds without exec-out. The image is written to a file
        because the shell transport cannot carry binary data unchanged.
        """
        remote_path = "/data/local/tmp/adbutils-screencap-{}.png".format(
            threading.get_native_id())
        self.shell(list(cmdargs) + [remote_path])
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                local_path = pathlib.Path(tmpdir) / "screencap.png"
                self.sync.pull(remote_path, local_path)
                return local_path.read_bytes()
        finally:
            try:
                self.shell(["rm", "-f", remote_path])
            except AdbError:
                logger.debug("failed to remove %s", remote_path, exc_info=True)

    def __get_real_display_id(self, display_id: int) -> str:
        # adb shell dumpsys SurfaceFlinger --display-id
        # Display 4619827259835644672 (HWC display 0): port=0 pnpId=GGL displayName="EMU_display_0"
        output = self.shell("dumpsys SurfaceFlinger --display-id")
        _RE = re.compile(r"Display (\d+) ")
        ids = _RE.findall(output)
        if not ids:
            raise AdbError("No display found, debug with 'dumpsys SurfaceFlinger --display-id'")
        if display_id >= len(ids):
            raise AdbError("Invalid display_id", display_id)
        return ids[display_id]