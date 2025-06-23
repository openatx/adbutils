#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Created on Sun Apr 07 2024 18:44:52 by codeskyblue
"""

import datetime
import logging
import re
import time
from typing import List, Optional, Union
from adbutils._proto import WindowSize, AppInfo, RunningAppInfo, BatteryInfo, BrightnessMode
from adbutils.errors import AdbError, AdbInstallError
from adbutils._utils import escape_special_characters
from retry import retry
from adbutils._interfaces import AbstractShellDevice

from adbutils.sync import Sync

logger = logging.getLogger(__name__)

_DISPLAY_RE = re.compile(
    r".*DisplayViewport{.*?valid=true, .*?orientation=(?P<orientation>\d+), .*?deviceWidth=(?P<width>\d+), deviceHeight=(?P<height>\d+).*"
)


def is_percent(v):
    return isinstance(v, float) and v <= 1.0



class ShellExtension(AbstractShellDevice):
    def getprop(self, prop: str) -> str:
        return self.shell(["getprop", prop]).strip()

    def keyevent(self, key_code: Union[int, str]):
        """adb shell input keyevent KEY_CODE"""
        self.shell(["input", "keyevent", str(key_code)])

    def volume_up(self, times: int = 1):
        """
        Increase the volume by times step
        :param times: times to increase volume，default is 1(Wake up volume bar).
        :return:
        """
        for _ in range(times):
            self.shell("input keyevent VOLUME_UP")
            time.sleep(0.5)

    def volume_down(self, times: int = 1):
        """
        Decrease the volume by times step
        :param times: times to decrease volume，default is 1(Wake up volume bar).
        :return:
        """
        for _ in range(times):
            self.shell("input keyevent VOLUME_DOWN")
            time.sleep(0.5)

    def volume_mute(self):
        self.shell("input keyevent VOLUME_MUTE")

    def reboot(self):
        self.shell("reboot")

    def switch_screen(self, enable: bool):
        """turn screen on/off"""
        return self.keyevent(224 if enable else 223)

    @property
    def brightness_value(self) -> int:
        """
        Return screen brightness value, [0, 255]
        
        Examples:
            print(d.brightness_value) output：128
        """
        value = self.shell('settings get system screen_brightness')
        return int(value.strip())

    @brightness_value.setter
    def brightness_value(self, value: int):
        """
        Set screen brightness values
        :param value: brightness value
        eg: d.brightness_value = 128
        """
        if not isinstance(value, int):
            raise ValueError("Brightness value must be an integer")
        if not 0 <= value <= 255:
            raise ValueError("Brightness value must be between 0 and 255")
        self.shell(f"settings put system screen_brightness {value}")

    @property
    def brightness_mode(self) -> BrightnessMode:
        """
        Return screen brightness mode
        :return: BrightnessMode.AUTO or BrightnessMode.MANUAL
        """
        value = int(self.shell('settings get system screen_brightness_mode'))
        return BrightnessMode(value)

    @brightness_mode.setter
    def brightness_mode(self, mode: BrightnessMode):
        """
        Set screen brightness mode
        
        Args:
            mode: BrightnessMode.AUTO or BrightnessMode.MANUAL

        Example:
            d.brightness_mode = BrightnessMode.AUTO
        """
        if isinstance(mode, BrightnessMode):
            self.shell(f"settings put system screen_brightness_mode {mode.value}")
        else:
            raise ValueError("Brightness mode must be an instance of BrightnessMode")

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

    def window_size(self, landscape: Optional[bool] = None) -> WindowSize:
        """
        Return screen (width, height) in pixel, width and height will be swapped if rotation is 90 or 270

        Args:
            landscape: bool, default None, if True, return (width, height), else return (height, width)
            
        Returns:
            WindowSize
        
        Raises:
            AdbError
        """
        wsize = self._wm_size()
        if landscape is None:
            landscape = self.rotation() % 2 == 1
        logger.debug("get window size from 'wm size': %s %s", wsize, landscape)
        return WindowSize(wsize.height, wsize.width) if landscape else wsize
    
    def _wm_size(self) -> WindowSize:
        output = self.shell("wm size")
        o = re.search(r"Override size: (\d+)x(\d+)", output)
        if o:
            w, h = o.group(1), o.group(2)
            return WindowSize(int(w), int(h))
        m = re.search(r"Physical size: (\d+)x(\d+)", output)
        if m:
            w, h = m.group(1), m.group(2)
            return WindowSize(int(w), int(h))
        raise AdbError("wm size output unexpected", output)

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

    def click(self, x, y, display_id: Optional[int] = None) -> None:
        """
        simulate android tap

        Args:
            x, y: int
            display_id: int, default None, see "dumpsys SurfaceFlinger --display-id" for valid display IDs
        """
        if any(map(is_percent, [x, y])):
            w, h = self.window_size()
            x = int(x * w) if is_percent(x) else x
            y = int(y * h) if is_percent(y) else y
        x, y = map(str, [x, y])
        cmdargs = ["input"]
        if display_id is not None:
            cmdargs.extend(['-d', str(display_id)])
        self.shell(cmdargs + ["tap", x, y])

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
            m = re.search(r".*?orientation=(?P<orientation>\d+)", line)
            if not m:
                continue
            o = int(m.group("orientation"))
            return int(o)
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

    def list_packages(self, filter_list: Optional[List[str]] = None) -> List[str]:
        """
        Args:
            filter_list (List[str]): package filter
                -f: See associated file.
                -d: Filter to only show disabled packages.
                -e: Filter to only show enabled packages.
                -s: Filter to only show system packages.
                -3: Filter to only show third-party packages.
                -i: See the installer for the packages.
                -u: Include uninstalled packages.
                --user user_id: The user space to query.
        Returns:
            list of package names
        """
        result = []
        cmd = ["pm", "list", "packages"]
        if filter_list:
            cmd.extend(filter_list)
        output = self.shell(cmd)
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

    def battery(self) -> BatteryInfo:
        """
        Get battery info

        Returns:
            BatteryInfo

        Details:
            AC powered - Indicates that the device is currently not powered by AC power. If true, it indicates that the device is connected to an AC power adapter.
            USB powered - Indicates that the device is currently being powered or charged through the USB interface.
            Wireless powered - Indicates that the device is not powered through wireless charging. If wireless charging is supported and currently in use, this will be true.
            Max charging current - The maximum charging current supported by the device, usually in microamperes（ μ A).
            Max charging voltage - The maximum charging voltage supported by the device may be in millivolts (mV).
            Charge counter - The cumulative charge count of a battery, usually measured in milliampere hours (mAh)
            Status - Battery status code.
            Health - Battery health status code.
            Present  - indicates that the battery is currently detected and installed in the device.
            Level - The percentage of current battery level.
            Scale - The full scale of the percentage of battery charge, indicating that the battery level is measured using 100 as the standard for full charge.
            Voltage - The current voltage of the battery, usually measured in millivolts (mV).
            Temperature - Battery temperature, usually measured in degrees Celsius (° C)
            Technology - Battery type, like (Li-ion) battery
        """

        def to_bool(v: str) -> bool:
            return v == "true"

        output = self.shell(["dumpsys", "battery"])
        shell_kvs = {}
        for line in output.splitlines():
            if ":" not in line:
                continue
            key, val = line.strip().split(':', 1)
            shell_kvs[key.strip()] = val.strip()

        def get_key(k: str, map_function):
            v = shell_kvs.get(k)
            if v is not None:
                return map_function(v)
            return None

        ac_powered = get_key("AC powered", to_bool)
        usb_powered = get_key("USB powered", to_bool)
        wireless_powered = get_key("Wireless powered", to_bool)
        dock_powered = get_key("Dock powered", to_bool)
        max_charging_current = get_key("Max charging current", int)
        max_charging_voltage = get_key("Max charging voltage", int)
        charge_counter = get_key("Charge counter", int)
        status = get_key("status", int)
        health = get_key("health", int)
        present = get_key("present", to_bool)
        level = get_key("level", int)
        scale = get_key("scale", int)
        voltage = get_key("voltage", int)
        temperature = get_key("temperature", lambda x: int(x) / 10)
        technology = shell_kvs.get("technology", str)
        return BatteryInfo(
            ac_powered=ac_powered,
            usb_powered=usb_powered,
            wireless_powered=wireless_powered,
            dock_powered=dock_powered,
            max_charging_current=max_charging_current,
            max_charging_voltage=max_charging_voltage,
            charge_counter=charge_counter,
            status=status,
            health=health,
            present=present,
            level=level,
            scale=scale,
            voltage=voltage,
            temperature=temperature,
            technology=technology,
        )
