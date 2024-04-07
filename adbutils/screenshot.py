#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Created on Sun Apr 07 2024 19:52:19 by codeskyblue
"""

import abc
import os
from adbutils.sync import Sync
from adbutils._proto import WindowSize
from PIL import Image
import threading
import tempfile

try:
    from PIL import UnidentifiedImageError
except ImportError:
    # fix for py37
    UnidentifiedImageError = OSError


class AbstractDevice(abc.ABC):
    @property
    @abc.abstractmethod
    def sync(self) -> Sync:
        pass

    @abc.abstractmethod
    def shell(self, cmd: str) -> str:
        pass

    @abc.abstractmethod
    def window_size(self) -> WindowSize:
        pass


class ScreenshotExtesion(AbstractDevice):
    def screenshot(self) -> Image.Image:
        """ not thread safe
        
        Note:
            screencap to file and pull is more stable then shell(stream=True)
            Ref: https://github.com/openatx/adbutils/pull/78
        """
        try:
            return self.__screencap()
        except UnidentifiedImageError as e:
            wsize = self.window_size()
            return Image.new("RGB", wsize) # return a blank image when screenshot is not allowed


    def __screencap(self) -> Image.Image:
        thread_id = threading.get_native_id()
        inner_tmp_path = f"/data/local/tmp/adbutils-tmp{thread_id}.png"
        self.shell(["screencap", "-p", inner_tmp_path])
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                target_path = os.path.join(tmpdir, "adbutils-tmp.png")
                self.sync.pull(inner_tmp_path, target_path)
                im = Image.open(target_path)
                im.load()
                return im.convert("RGB")
        finally:
            self.shell(['rm', inner_tmp_path])