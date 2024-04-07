#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Created on Sun Apr 07 2024 18:44:52 by codeskyblue
"""


import abc
import datetime
import json
import re
from typing import List, Optional, Union
from adbutils._proto import WindowSize, AppInfo, RunningAppInfo
from adbutils.errors import AdbError, AdbInstallError
from adbutils._utils import escape_special_characters
from retry import retry

from adbutils.sync import Sync


_DISPLAY_RE = re.compile(
    r".*DisplayViewport{.*?valid=true, .*?orientation=(?P<orientation>\d+), .*?deviceWidth=(?P<width>\d+), deviceHeight=(?P<height>\d+).*"
)


def is_percent(v):
    return isinstance(v, float) and v <= 1.0


class AbstractShellDevice(abc.ABC):
    @abc.abstractmethod
    def shell(self, cmd: Union[str, List[str]]) -> str:
        pass

    @property
    @abc.abstractmethod
    def sync(self) -> Sync:
        pass


class ShellExtension(AbstractShellDevice):
    def getprop(self, prop: str) -> str:
        return self.shell(["getprop", prop]).strip()

    def keyevent(self, key_code: Union[int, str]):
        """adb shell input keyevent KEY_CODE"""
        self.shell(["input", "keyevent", str(key_code)])

    def volume_up(self):
        self.shell("input keyevent VOLUME_UP")

    def volume_down(self):
        self.shell("input keyevent VOLUME_DOWN")

    def volume_mute(self):
        self.shell("input keyevent VOLUME_MUTE")

    def reboot(self):
        self.shell("reboot")

    def switch_screen(self, enable: bool):
        """turn screen on/off"""
        return self.keyevent(224 if enable else 223)

    def switch_airplane(self, enable: bool):
        """turn airplane-mode on/off"""
        base_setting_cmd = ["settings", "put", "global", "airplane_mode_on"]
        base_am_cmd = [
            "am",
            "broadcast",
            "-a",
            "android.intent.action.AIRPLANE_MODE",
            "--ez",
            "state",
        ]
        if enable:
            base_setting_cmd += ["1"]
            base_am_cmd += ["true"]
        else:
            base_setting_cmd += ["0"]
            base_am_cmd += ["false"]

        self.shell(base_setting_cmd)
        self.shell(base_am_cmd)

    def switch_wifi(self, enable: bool):
        """turn WiFi on/off"""
        arglast = "enable" if enable else "disable"
        cmdargs = ["svc", "wifi", arglast]
        self.shell(cmdargs)

    def window_size(self) -> WindowSize:
        """
        Return screen (width, height)

        Virtual keyborad may get small d.info['displayHeight']
        """
        w, h = self._raw_window_size()
        s, l = min(w, h), max(w, h)
        horizontal = self.rotation() % 2 == 1
        return WindowSize(l, s) if horizontal else WindowSize(s, l)

    def _raw_window_size(self) -> WindowSize:
        output = self.shell("wm size")
        o = re.search(r"Override size: (\d+)x(\d+)", output)
        m = re.search(r"Physical size: (\d+)x(\d+)", output)
        if o:
            w, h = o.group(1), o.group(2)
            return WindowSize(int(w), int(h))
        elif m:
            w, h = m.group(1), m.group(2)
            return WindowSize(int(w), int(h))

        for line in self.shell("dumpsys display").splitlines():
            m = _DISPLAY_RE.search(line, 0)
            if not m:
                continue
            w = int(m.group("width"))
            h = int(m.group("height"))
            return WindowSize(w, h)
        raise AdbError("get window size failed")

    def swipe(self, sx, sy, ex, ey, duration: float = 1.0) -> None:
        """
        swipe from start point to end point

        Args:
            sx, sy: start point(x, y)
            ex, ey: end point(x, y)
        """
        if any(map(is_percent, [sx, sy, ex, ey])):
            w, h = self.window_size()
            sx = int(sx * w) if is_percent(sx) else sx
            sy = int(sy * h) if is_percent(sy) else sy
            ex = int(ex * w) if is_percent(ex) else ex
            ey = int(ey * h) if is_percent(ey) else ey
        x1, y1, x2, y2 = map(str, [sx, sy, ex, ey])
        self.shell(["input", "swipe", x1, y1, x2, y2, str(int(duration * 1000))])

    def click(self, x, y) -> None:
        """
        simulate android tap

        Args:
            x, y: int
        """
        if any(map(is_percent, [x, y])):
            w, h = self.window_size()
            x = int(x * w) if is_percent(x) else x
            y = int(y * h) if is_percent(y) else y
        x, y = map(str, [x, y])
        self.shell(["input", "tap", x, y])

    def send_keys(self, text: str):
        """
        Type a given text

        Args:
            text: text to be type
        """
        escaped_text = escape_special_characters(text)
        return self.shell(["input", "text", escaped_text])

    def wlan_ip(self) -> str:
        """get device wlan ip address"""
        result = self.shell(["ifconfig", "wlan0"])
        m = re.search(r"inet\s*addr:(.*?)\s", result, re.DOTALL)
        if m:
            return m.group(1)

        # Huawei P30, has no ifconfig
        result = self.shell(["ip", "addr", "show", "dev", "wlan0"])
        m = re.search(r"inet (\d+.*?)/\d+", result)
        if m:
            return m.group(1)

        # On VirtualDevice, might use eth0
        result = self.shell(["ifconfig", "eth0"])
        m = re.search(r"inet\s*addr:(.*?)\s", result, re.DOTALL)
        if m:
            return m.group(1)

        raise AdbError("fail to parse wlan ip")

    def rotation(self) -> int:
        """
        Returns:
            int [0, 1, 2, 3]
        """
        for line in self.shell("dumpsys display").splitlines():
            m = _DISPLAY_RE.search(line, 0)
            if not m:
                continue
            o = int(m.group("orientation"))
            return int(o)

        output = self.shell(
            "LD_LIBRARY_PATH=/data/local/tmp /data/local/tmp/minicap -i"
        )
        try:
            if output.startswith("INFO:"):
                output = output[output.index("{") :]
            data = json.loads(output)
            return data["rotation"] / 90
        except ValueError:
            pass

        raise AdbError("rotation get failed")

    def remove(self, path: str):
        """rm device file"""
        self.shell(["rm", path])

    def rmtree(self, path: str):
        """rm -r directory"""
        self.shell(["rm", "-r", path])

    def is_screen_on(self):
        output = self.shell(["dumpsys", "power"])
        return "mHoldingDisplaySuspendBlocker=true" in output

    def open_browser(self, url: str):
        if not re.match("^https?://", url):
            url = "https://" + url
        self.shell(["am", "start", "-a", "android.intent.action.VIEW", "-d", url])

    def list_packages(self) -> List[str]:
        """
        Returns:
            list of package names
        """
        result = []
        output = self.shell(["pm", "list", "packages"])
        for m in re.finditer(r"^package:([^\s]+)\r?$", output, re.M):
            result.append(m.group(1))
        return list(sorted(result))

    def uninstall(self, pkg_name: str):
        """
        Uninstall app by package name

        Args:
            pkg_name (str): package name
        """
        return self.shell(["pm", "uninstall", pkg_name])

    def install_remote(
        self, remote_path: str, clean: bool = False, flags: list = ["-r", "-t"]
    ):
        """
        Args:
            remote_path: remote package path
            clean(bool): remove when installed, default(False)
            flags (list): default ["-r", "-t"]

        Raises:
            AdbInstallError
        """
        args = ["pm", "install"] + flags + [remote_path]
        output = self.shell(args)
        if "Success" not in output:
            raise AdbInstallError(output)
        if clean:
            self.shell(["rm", remote_path])

    def app_start(self, package_name: str, activity: str = None):
        """start app with "am start" or "monkey" """
        if activity:
            self.shell(["am", "start", "-n", package_name + "/" + activity])
        else:
            self.shell(
                [
                    "monkey",
                    "-p",
                    package_name,
                    "-c",
                    "android.intent.category.LAUNCHER",
                    "1",
                ]
            )

    def app_stop(self, package_name: str):
        """stop app with "am force-stop" """
        self.shell(["am", "force-stop", package_name])

    def app_clear(self, package_name: str):
        self.shell(["pm", "clear", package_name])

    def app_info(self, package_name: str) -> Optional[AppInfo]:
        """
        Get app info

        Returns:
            None or AppInfo
        """
        output = self.shell(["pm", "path", package_name])
        if "package:" not in output:
            return None

        apk_paths = output.splitlines()
        apk_path = apk_paths[0].split(":", 1)[-1].strip()
        sub_apk_paths = list(map(lambda p: p.replace("package:", "", 1), apk_paths[1:]))

        output = self.shell(["dumpsys", "package", package_name])
        m = re.compile(r"versionName=(?P<name>[^\s]+)").search(output)
        version_name = m.group("name") if m else ""
        if version_name == "null":  # Java dumps "null" for null values
            version_name = None
        m = re.compile(r"versionCode=(?P<code>\d+)").search(output)
        version_code = m.group("code") if m else ""
        version_code = int(version_code) if version_code.isdigit() else None
        m = re.search(r"PackageSignatures\{.*?\[(.*)\]\}", output)
        signature = m.group(1) if m else None
        if not version_name and signature is None:
            return None
        m = re.compile(r"pkgFlags=\[\s*(.*)\s*\]").search(output)
        pkgflags = m.group(1) if m else ""
        pkgflags = pkgflags.split()

        time_regex = r"[-\d]+\s+[:\d]+"
        m = re.compile(f"firstInstallTime=({time_regex})").search(output)
        first_install_time = (
            datetime.datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S") if m else None
        )

        m = re.compile(f"lastUpdateTime=({time_regex})").search(output)
        last_update_time = (
            datetime.datetime.strptime(m.group(1).strip(), "%Y-%m-%d %H:%M:%S")
            if m
            else None
        )

        app_info = AppInfo(
            package_name=package_name,
            version_name=version_name,
            version_code=version_code,
            flags=pkgflags,
            first_install_time=first_install_time,
            last_update_time=last_update_time,
            signature=signature,
            path=apk_path,
            sub_apk_paths=sub_apk_paths,
        )
        return app_info

    @retry(AdbError, delay=0.5, tries=3, jitter=0.1)
    def app_current(self) -> RunningAppInfo:
        """
        Returns:
            RunningAppInfo(package, activity, pid?)  pid can be 0

        Raises:
            AdbError
        """
        # Related issue: https://github.com/openatx/uiautomator2/issues/200
        # $ adb shell dumpsys window windows
        # Example output:
        #   mCurrentFocus=Window{41b37570 u0 com.incall.apps.launcher/com.incall.apps.launcher.Launcher}
        #   mFocusedApp=AppWindowToken{422df168 token=Token{422def98 ActivityRecord{422dee38 u0 com.example/.UI.play.PlayActivity t14}}}
        # Regexp
        #   r'mFocusedApp=.*ActivityRecord{\w+ \w+ (?P<package>.*)/(?P<activity>.*) .*'
        #   r'mCurrentFocus=Window{\w+ \w+ (?P<package>.*)/(?P<activity>.*)\}')
        _focusedRE = re.compile(
            r"mCurrentFocus=Window{.*\s+(?P<package>[^\s]+)/(?P<activity>[^\s]+)\}"
        )
        m = _focusedRE.search(self.shell(["dumpsys", "window", "windows"]))
        if m:
            return RunningAppInfo(
                package=m.group("package"), activity=m.group("activity")
            )

        # search mResumedActivity
        # https://stackoverflow.com/questions/13193592/adb-android-getting-the-name-of-the-current-activity
        package = None
        output = self.shell(["dumpsys", "activity", "activities"])
        _recordRE = re.compile(
            r"mResumedActivity: ActivityRecord\{.*?\s+(?P<package>[^\s]+)/(?P<activity>[^\s]+)\s.*?\}"
        )  # yapf: disable
        m = _recordRE.search(output)
        if m:
            package = m.group("package")

        # try: adb shell dumpsys activity top
        _activityRE = re.compile(
            r"ACTIVITY (?P<package>[^\s]+)/(?P<activity>[^/\s]+) \w+ pid=(?P<pid>\d+)"
        )
        output = self.shell(["dumpsys", "activity", "top"])
        ms = _activityRE.finditer(output)
        ret = None
        for m in ms:
            ret = RunningAppInfo(
                package=m.group("package"),
                activity=m.group("activity"),
                pid=int(m.group("pid")),
            )
            if ret.package == package:
                return ret

        if ret:  # get last result
            return ret
        raise AdbError("Couldn't get focused app")

    def dump_hierarchy(self) -> str:
        """
        uiautomator dump

        Returns:
            content of xml
        
        Raises:
            AdbError
        """
        target = '/data/local/tmp/uidump.xml'
        output = self.shell(
            f'rm -f {target}; uiautomator dump {target} && echo success')
        if 'ERROR' in output or 'success' not in output:
            raise AdbError("uiautomator dump failed", output)

        buf = b''
        for chunk in self.sync.iter_content(target):
            buf += chunk
        xml_data = buf.decode("utf-8")
        if not xml_data.startswith('<?xml'):
            raise AdbError("dump output is not xml", xml_data)
        return xml_data
    