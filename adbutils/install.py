#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Created on Sun Apr 07 2024 20:07:44 by codeskyblue
"""

import abc
import os
import re
import time
import typing

import requests
import apkutils2
from retry import retry
from adbutils.errors import AdbInstallError
from adbutils.sync import Sync
from adbutils._utils import humanize, ReadProgress


class AbstractDevice(abc.ABC):
    @abc.abstractmethod
    def shell(self, cmd: str) -> str:
        pass

    @property
    @abc.abstractmethod
    def sync(self) -> Sync:
        pass

    @abc.abstractmethod
    def app_start(self, package_name: str, activity: str):
        pass

    @abc.abstractmethod
    def uninstall(self, package_name: str):
        pass

    @abc.abstractmethod
    def install_remote(self, path: str, clean: bool = False, flags: list = ["-r", "-t"]):
        pass


class InstallExtension(AbstractDevice):
    @retry(BrokenPipeError, delay=5.0, jitter=[3, 5], tries=3)
    def install(self,
                path_or_url: str,
                nolaunch: bool = False,
                uninstall: bool = False,
                silent: bool = False,
                callback: typing.Callable[[str], None] = None,
                flags: list = ["-r", "-t"]):
        """
        Install APK to device

        Args:
            path_or_url: local path or http url
            nolaunch: do not launch app after install
            uninstall: uninstall app before install
            silent: disable log message print
            callback: only two event now: <"BEFORE_INSTALL" | "FINALLY">
            flags (list): default ["-r", "-t"]

        Raises:
            AdbInstallError, BrokenPipeError
        """
        if re.match(r"^https?://", path_or_url):
            resp = requests.get(path_or_url, stream=True)
            resp.raise_for_status()
            length = int(resp.headers.get("Content-Length", 0))
            r = ReadProgress(resp.raw, length)
            print("tmpfile path:", r.filepath())
        else:
            length = os.stat(path_or_url).st_size
            fd = open(path_or_url, "rb")
            r = ReadProgress(fd, length, source_path=path_or_url)

        def _dprint(*args):
            if not silent:
                print(*args)

        dst = "/data/local/tmp/tmp-%d.apk" % (int(time.time() * 1000))
        _dprint("push to %s" % dst)

        start = time.time()
        self.sync.push(r, dst)

        # parse apk package-name
        apk = apkutils2.APK(r.filepath())
        package_name = apk.manifest.package_name
        main_activity = apk.manifest.main_activity
        if main_activity and main_activity.find(".") == -1:
            main_activity = "." + main_activity

        version_code = apk.manifest.version_code
        _dprint("packageName:", package_name)
        _dprint("mainActivity:", main_activity)
        _dprint("apkVersion: {}".format(apk.manifest.version_name))
        _dprint("Success pushed, time used %d seconds" % (time.time() - start))

        new_dst = "/data/local/tmp/{}-{}.apk".format(package_name,
                                                     version_code)
        _dprint("Rename to {}".format(new_dst))
        self.shell(["mv", dst, new_dst])

        dst = new_dst
        info = self.sync.stat(dst)
        print("verify pushed apk, md5: %s, size: %s" %
              (r._hash, humanize(info.size)))
        assert info.size == r.copied

        if uninstall:
            _dprint("Uninstall app first")
            self.uninstall(package_name)

        _dprint("install to android system ...")
        try:
            start = time.time()
            if callback:
                callback("BEFORE_INSTALL")

            self.install_remote(dst, clean=True, flags=flags)
            _dprint("Success installed, time used %d seconds" %
                    (time.time() - start))
            if not nolaunch:
                _dprint("Launch app: %s/%s" % (package_name, main_activity))
                self.app_start(package_name, main_activity)

        except AdbInstallError as e:
            if e.reason in [
                "INSTALL_FAILED_PERMISSION_MODEL_DOWNGRADE",
                "INSTALL_FAILED_UPDATE_INCOMPATIBLE",
                "INSTALL_FAILED_VERSION_DOWNGRADE"
            ]:
                _dprint("uninstall %s because %s" % (package_name, e.reason))
                self.uninstall(package_name)
                self.install_remote(dst, clean=True, flags=flags)
                _dprint("Success installed, time used %d seconds" %
                        (time.time() - start))
                if not nolaunch:
                    _dprint("Launch app: %s/%s" %
                            (package_name, main_activity))
                    self.app_start(package_name, main_activity)
                    # self.shell([
                    #     'am', 'start', '-n', package_name + "/" + main_activity
                    # ])
            elif e.reason == "INSTALL_FAILED_CANCELLED_BY_USER":
                _dprint("Catch error %s, reinstall" % e.reason)
                self.install_remote(dst, clean=True, flags=flags)
                _dprint("Success installed, time used %d seconds" %
                        (time.time() - start))
            else:
                # print to console
                print(
                    "Failure " + e.reason + "\n" +
                    "Remote apk is not removed. Manually install command:\n\t"
                    + "adb shell pm install -r -t " + dst)
                raise
        finally:
            if callback:
                callback("FINALLY")

