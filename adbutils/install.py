#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Created on Sun Apr 07 2024 20:07:44 by codeskyblue
"""

import logging
import re
import tempfile
import time
import typing
from pathlib import Path
from typing import Optional, Union

import requests

from adbutils._interfaces import AbstractDevice
from adbutils._utils import ReadProgress, humanize
from adbutils.errors import AdbInstallError

logger = logging.getLogger(__name__)


class InstallExtension(AbstractDevice):
    @staticmethod
    def download_apk(url: str, path: Path):
        """
        Download apk file from url
    
        Args:
            url (str): The URL of the APK file to download.
            path (Path): The local file path where the APK will be saved.
    
        Raises:
            requests.exceptions.RequestException: If the download fails.
        """
        try:
            response = requests.get(url, stream=True)
            response.raise_for_status()  # Raise an error for HTTP errors
    
            # Write the content to the specified path
            with open(path, "wb") as file:
                for chunk in response.iter_content(chunk_size=10240):
                    if chunk:  # Filter out keep-alive chunks
                        file.write(chunk)
        except requests.exceptions.RequestException as e:
            logger.warning(f"Failed to download APK from {url}: {e}")
            raise
    

    def install(self,
                path_or_url: Union[str, Path],
                nolaunch: bool = False,
                uninstall: bool = False,
                silent: bool = False,
                callback: typing.Callable[[str], None] = None,
                flags: list = ["-r", "-t"]):
        try:
            import apkutils
            has_apkutils = True
        except ImportError:
            logger.warning("apkutils is not installed, install it with 'pip install adbutils[apk]'")
            has_apkutils = False
        self._install(path_or_url, nolaunch, uninstall, silent, callback, flags, has_apkutils)

    def _install(self,
                path_or_url: Union[str, Path],
                nolaunch: bool = False,
                uninstall: bool = False,
                silent: bool = False,
                callback: typing.Callable[[str], None] = None,
                flags: list = ["-r", "-t"],
                has_apkutils: bool = True):
        """
        Install APK to device

        Args:
            path_or_url: local path or http url
            nolaunch: do not launch app after install
            uninstall: uninstall app before install
            silent: disable log message print
            callback: only two event now: <"BEFORE_INSTALL" | "FINALLY">
            flags (list): default ["-r", "-t"]
            has_apkutils: whether apkutils is installed

        Raises:
            AdbInstallError, BrokenPipeError
        """
        def dprint(msg):
            if not silent:
                print(msg)
                
        if isinstance(path_or_url, str) and re.match(r"^https?://", path_or_url):
            tmpfile = tempfile.NamedTemporaryFile(suffix=".apk")
            self.download_apk(path_or_url, Path(tmpfile.name))
            tmpfile.flush()
            tmpfile.seek(0)
            src_path = Path(tmpfile.name)
            dprint(f"download apk to {src_path}")
        else:
            src_path = Path(path_or_url)
        if not src_path.is_file():
            raise FileNotFoundError(f"File or URL not found: {path_or_url}")
        
        package_name = None
        main_activity = None
        
        if has_apkutils:
            import apkutils
            with apkutils.APK.from_file(str(src_path)) as apk:
                activities = apk.get_main_activities()
                main_activity = activities[0] if activities else None
                package_name = apk.get_package_name()
                if main_activity and main_activity.find(".") == -1:
                    main_activity = "." + main_activity
            
            dprint(f"APK packageName: {package_name}")
            dprint(f"APK mainActivity: {main_activity}")

        device_dst = f"/data/local/tmp/{package_name or 'unknown'}.apk"
        dprint(f'push apk to device: {device_dst}')
        self._push_apk(src_path, device_dst, show_progress=not silent)

        info = self.sync.stat(device_dst)
        apk_size = src_path.stat().st_size
        if not info.size == apk_size:
            AdbInstallError(f'pushed apk size not matched, expect {apk_size} got {info.size}')
        
        if uninstall and package_name:
            dprint(f"uninstall app: {package_name}")
            self.uninstall(package_name)

        dprint("install to android system ...")
        try:
            start = time.time()
            if callback:
                callback("BEFORE_INSTALL")

            self.install_remote(device_dst, clean=True, flags=flags)
            time_used = time.time() - start
            dprint(f"successfully installed, time used {time_used:.1f} seconds")
            if not nolaunch and package_name and main_activity:
                dprint("launch app: %s/%s" % (package_name, main_activity))
                self.app_start(package_name, main_activity)

        except AdbInstallError as e:
            if package_name and e.reason in [
                "INSTALL_FAILED_PERMISSION_MODEL_DOWNGRADE",
                "INSTALL_FAILED_UPDATE_INCOMPATIBLE",
                "INSTALL_FAILED_VERSION_DOWNGRADE"
            ]:
                dprint("uninstall %s because %s" % (package_name, e.reason))
                self.uninstall(package_name)
                self.install_remote(device_dst, clean=True, flags=flags)
                dprint(f"successfully installed, time used {time.time() - start} seconds")
                if not nolaunch and main_activity:
                    dprint(f"Launch app: {package_name}/{main_activity}")
                    self.app_start(package_name, main_activity)
            else:
                # print to console
                print(
                    "Failure " + e.reason + "\n" +
                    "Remote apk is not removed. Manually install command:\n\t"
                    + "adb shell pm install -r -t " + device_dst)
                raise
        finally:
            if callback:
                callback("FINALLY")

    def _push_apk(self, apk_path: Path, device_dst: str, show_progress: bool = True):
        """
        Push APK file to device with progress indication.
    
        Args:
            apk_path (Path): Path to the APK file.
            device_dst (str): Destination path on the device.
    
        Returns:
            None
        """
        start = time.time()
        length = apk_path.stat().st_size
        with apk_path.open("rb") as fd:
            if show_progress:
                r = ReadProgress(fd, length, source_path=str(apk_path))
                self.sync.push(r, device_dst)
            else:
                self.sync.push(fd, device_dst)
        logger.info("Success pushed, time used %d seconds" % (time.time() - start))
