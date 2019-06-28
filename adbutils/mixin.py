# coding: utf-8
import json
import re
import time
import typing
from collections import namedtuple

from retry import retry
from adbutils.errors import AdbError, AdbInstallError

_DISPLAY_RE = re.compile(
    r'.*DisplayViewport{valid=true, .*orientation=(?P<orientation>\d+), .*deviceWidth=(?P<width>\d+), deviceHeight=(?P<height>\d+).*'
)

WindowSize = namedtuple("WindowSize", ['width', 'height'])


class ExtraUtilsMixin(object):
    """ provide custom functions for some complex operations """

    def _run(self, cmd) -> str:
        return self.shell(cmd)

    def say_hello(self) -> str:
        content = 'hello from {}'.format(self.serial)
        return self._run(['echo', content])

    def switch_screen(self, status: bool):
        """
        turn screen on/off

        Args:
            status (bool)
        """
        _key_dict = {
            True: '224',
            False: '223',
        }
        return self.keyevent(_key_dict[status])

    def switch_airplane(self, status: bool):
        """
        turn airplane-mode on/off

        Args:
            status (bool)
        """
        base_setting_cmd = ["settings", "put", "global", "airplane_mode_on"]
        base_am_cmd = [
            "am", "broadcast", "-a", "android.intent.action.AIRPLANE_MODE",
            "--ez", "state"
        ]
        if status:
            base_setting_cmd += ['1']
            base_am_cmd += ['true']
        else:
            base_setting_cmd += ['0']
            base_am_cmd += ['false']

        # TODO better idea about return value?
        self._run(base_setting_cmd)
        return self._run(base_am_cmd)

    def switch_wifi(self, status: bool) -> str:
        """
        turn WiFi on/off

        Args:
            status (bool)
        """
        base_cmd = ['svc', 'wifi']
        cmd_dict = {
            True: base_cmd + ['enable'],
            False: base_cmd + ['disable'],
        }
        return self._run(cmd_dict[status])

    def keyevent(self, key_code: (int, str)) -> str:
        """ adb _run input keyevent KEY_CODE """
        return self._run(['input', 'keyevent', str(key_code)])

    def click(self, x, y):
        """
        simulate android tap

        Args:
            x, y: int
        """
        x, y = map(str, [x, y])
        return self._run(['input', 'tap', x, y])

    def swipe(self, sx, sy, ex, ey, duration: float = 1.0):
        """
        swipe from start point to end point

        Args:
            sx, sy: start point(x, y)
            ex, ey: end point(x, y)
        """
        x1, y1, x2, y2 = map(str, [sx, sy, ex, ey])
        return self._run(
            ['input', 'swipe', x1, y1, x2, y2,
             str(int(duration * 1000))])

    def wlan_ip(self) -> str:
        """
        get device wlan ip

        Raises:
            IndexError
        """
        # TODO better design?
        result = self._run(['ifconfig', 'wlan0'])
        return re.findall(r'inet\s*addr:(.*?)\s', result, re.DOTALL)[0]

    def install(self, apk_path: str):
        """
        sdk = self.getprop('ro.build.version.sdk')
        sdk > 23 support -g

        Raises:
            AdbInstallError
        """
        dst = "/data/local/tmp/tmp-{}.apk".format(int(time.time() * 1000))
        self.sync.push(apk_path, dst)
        self.install_remote(dst, clean=True)

    def install_remote(self,
                       remote_path: str,
                       clean: bool = False,
                       flags: list = ["-r", "-t"]):
        """
        Args:
            remote_path: remote package path
            clean(bool): remove when installed, default(False)
            flags (list): default ["-r", "-t"]

        Raises:
            AdbInstallError
        """
        args = ["pm", "install"] + flags + [remote_path]
        output = self._run(args)
        if "Success" not in output:
            raise AdbInstallError(output)
        if clean:
            self._run(["rm", remote_path])

    def uninstall(self, pkg_name: str):
        """
        Uninstall app by package name

        Args:
            pkg_name (str): package name
        """
        return self._run(["pm", "uninstall", pkg_name])

    def getprop(self, prop: str) -> str:
        return self._run(['getprop', prop]).strip()

    def list_packages(self) -> list:
        """
        Returns:
            list of package names
        """
        result = []
        output = self._run(["pm", "list", "packages", "-3"])
        for m in re.finditer(r'^package:([^\s]+)$', output, re.M):
            result.append(m.group(1))
        return list(sorted(result))

    def package_info(self, pkg_name: str) -> typing.Union[dict, None]:
        """
        version_code might be empty

        Returns:
            None or dict(version_name, version_code, signature)
        """
        output = self._run(['dumpsys', 'package', pkg_name])
        m = re.compile(r'versionName=(?P<name>[\d.]+)').search(output)
        version_name = m.group('name') if m else ""
        m = re.compile(r'versionCode=(?P<code>\d+)').search(output)
        version_code = m.group('code') if m else ""
        if version_code == "0":
            version_code = ""
        m = re.search(r'PackageSignatures\{(.*?)\}', output)
        signature = m.group(1) if m else None
        if not version_name and signature is None:
            return None
        return dict(version_name=version_name,
                    version_code=version_code,
                    signature=signature)

    def rotation(self) -> int:
        """
        Returns:
            int [0, 1, 2, 3]
        """
        for line in self.shell('dumpsys display').splitlines():
            m = _DISPLAY_RE.search(line, 0)
            if not m:
                continue
            o = int(m.group('orientation'))
            return int(o)

        output = self.shell(
            'LD_LIBRARY_PATH=/data/local/tmp /data/local/tmp/minicap -i')
        try:
            data = json.loads(output)
            return data['rotation'] / 90
        except ValueError:
            pass

        raise AdbError("rotation get failed")

    def _raw_window_size(self) -> WindowSize:
        output = self.shell("wm size")
        m = re.search(r"Physical size: (\d+)x(\d+)", output)
        if m:
            w, h = m.group(1), m.group(2)
            return WindowSize(int(w), int(h))

        for line in self.shell('dumpsys display').splitlines():
            m = _DISPLAY_RE.search(line, 0)
            if not m:
                continue
            w = int(m.group('width'))
            h = int(m.group('height'))
            return WindowSize(w, h)
        raise AdbError("get window size failed")

    def window_size(self) -> WindowSize:
        """
        Return screen (width, height)

        Virtual keyborad may get small d.info['displayHeight']
        """
        w, h = self._raw_window_size()
        s, l = min(w, h), max(w, h)
        horizontal = self.rotation() % 2 == 1
        return WindowSize(l, s) if horizontal else WindowSize(s, l)

    def app_start(self, package_name: str, activity: str = None):
        """ start app with "am start" or "monkey"
        """
        if activity:
            self._run(['am', 'start', '-n', package_name + "/" + activity])
        else:
            self._run([
                "monkey", "-p", package_name, "-c",
                "android.intent.category.LAUNCHER", "1"
            ])

    def app_clear(self, package_name: str):
        self._run(["pm", "clear", package_name])

    def dump_hierarchy(self):
        """
        uiautomator dump
        
        Returns:
            content of xml
        """
        output = self._run(
            'uiautomator dump /data/local/tmp/uidump.xml && echo success')
        if "success" not in output:
            raise RuntimeError("uiautomator dump failed")

        buf = b''
        for chunk in self.sync.iter_content("/data/local/tmp/uidump.xml"):
            buf += chunk
        return buf.decode("utf-8")
    
    @retry(AdbError, delay=.5, tries=3, jitter=.1)
    def current_app(self):
        """
        Returns:
            dict(package, activity, pid?)

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
            r'mCurrentFocus=Window{.*\s+(?P<package>[^\s]+)/(?P<activity>[^\s]+)\}'
        )
        m = _focusedRE.search(self._run(['dumpsys', 'window', 'windows']))
        if m:
            return dict(
                package=m.group('package'), activity=m.group('activity'))

        # try: adb shell dumpsys activity top
        _activityRE = re.compile(
            r'ACTIVITY (?P<package>[^\s]+)/(?P<activity>[^/\s]+) \w+ pid=(?P<pid>\d+)'
        )
        output = self._run(['dumpsys', 'activity', 'top'])
        ms = _activityRE.finditer(output)
        ret = None
        for m in ms:
            ret = dict(
                package=m.group('package'),
                activity=m.group('activity'),
                pid=int(m.group('pid')))
        if ret:  # get last result
            return ret
        raise AdbError("Couldn't get focused app")
