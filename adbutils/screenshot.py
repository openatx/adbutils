#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Created on Sun Apr 07 2024 19:52:19 by codeskyblue
"""

import abc
import io
import logging
from typing import Optional, Union
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

class AbstractDevice(abc.ABC):
    @property
    @abc.abstractmethod
    def sync(self) -> Sync:
        pass

    @abc.abstractmethod
    def shell(self, cmd: str, encoding: Optional[str]) -> Union[str, bytes]:
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
        # framebuffer() is not stable, so here still use screencap
        cmdargs = ['screencap', '-p']
        if display_id is not None:
            cmdargs.extend(['-d', str(display_id)])
        png_bytes = self.shell(cmdargs, encoding=None)
        return Image.open(io.BytesIO(png_bytes))