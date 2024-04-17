#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Created on Sun Apr 07 2024 19:52:19 by codeskyblue
"""

import abc
import io
import logging
from typing import Optional, Union
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
    def __init__(self):
        self.__framebuffer_ok = True

    def screenshot(self) -> Image.Image:
        """ Take a screenshot and return PIL.Image.Image object
        If capture failed, return a black image
        """
        try:
            pil_image = self.__screencap()
            if pil_image.mode == "RGBA":
                pil_image = pil_image.convert("RGB")
            return pil_image
        except UnidentifiedImageError as e:
            wsize = self.window_size()
            return Image.new("RGB", wsize, (0, 0, 0))
    
    def __screencap(self) -> Image.Image:
        if self.__framebuffer_ok:
            try:
                return self.framebuffer()
            except NotImplementedError:
                self.__framebuffer_ok = False
            except UnidentifiedImageError as e:
                logger.warning("framebuffer error: %s", e)
        png_bytes = self.shell('screencap -p', encoding=None)
        return Image.open(io.BytesIO(png_bytes))