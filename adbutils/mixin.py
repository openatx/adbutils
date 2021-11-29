# coding: utf-8
import json
import os
import re
import time
import typing
import warnings
from collections import namedtuple
from datetime import datetime

import apkutils2
import requests
from retry import retry

from adbutils._utils import ReadProgress, humanize
from adbutils.errors import AdbError, AdbInstallError

_DISPLAY_RE = re.compile(
    r'.*DisplayViewport{.*?valid=true, .*?orientation=(?P<orientation>\d+), .*?deviceWidth=(?P<width>\d+), deviceHeight=(?P<height>\d+).*'
)

WindowSize = namedtuple("WindowSize", ['width', 'height'])


class ShellMixin(object):
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

    def keyevent(self, key_code: typing.Union[int, str]) -> str:
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

    def send_keys(self, text: str):
        """ 
        Type a given text 

        Args:
            text: text to be type
        """
        escaped_text = self._escape_special_characters(text)
        return self._run(['input', 'text', escaped_text])

    @staticmethod
    def _escape_special_characters(text):
        """
        A helper that escape special characters

        Args:
            text: str
        """
        escaped = text.translate(
            str.maketrans({
                "-": r"\-",
                "+": r"\+",
                "[": r"\[",
                "]": r"\]",
                "(": r"\(",
                ")": r"\)",
                "{": r"\{",
                "}": r"\}",
                "\\": r"\\\\",
                "^": r"\^",
                "$": r"\$",
                "*": r"\*",
                ".": r"\.",
                ",": r"\,",
                ":": r"\:",
                "~": r"\~",
                ";": r"\;",
                ">": r"\>",
                "<": r"\<",
                "%": r"\%",
                "#": r"\#",
                "\'": r"\\'",
                "\"": r'\\"',
                "`": r"\`",
                "!": r"\!",
                "?": r"\?",
                "|": r"\|",
                "=": r"\=",
                "@": r"\@",
                "/": r"\/",
                "_": r"\_",
                " ": r"%s",  # special
                "&": r"\&"
            }))
        return escaped

    def wlan_ip(self) -> str:
        """
        get device wlan ip

        Raises:
            IndexError
        """
        # TODO better design?
        result = self._run(['ifconfig', 'wlan0'])
        return re.findall(r'inet\s*addr:(.*?)\s', result, re.DOTALL)[0]

    @retry(BrokenPipeError, delay=5.0, jitter=[3, 5], tries=3)
    def install(self,
                path_or_url: str,
                nolaunch: bool = False,
                uninstall: bool = False,
                silent: bool = False,
                callback: typing.Callable[[str], None] = None):
        """
        Install APK to device

        Args:
            path_or_url: local path or http url
            nolaunch: do not launch app after install
            uninstall: uninstall app before install
            silent: disable log message print
            callback: only two event now: <"BEFORE_INSTALL" | "FINALLY">
        
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

        version_name = apk.manifest.version_name
        _dprint("packageName:", package_name)
        _dprint("mainActivity:", main_activity)
        _dprint("apkVersion: {}".format(version_name))
        _dprint("Success pushed, time used %d seconds" % (time.time() - start))

        new_dst = "/data/local/tmp/{}-{}.apk".format(package_name,
                                                     version_name)
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

            self.install_remote(dst, clean=True)
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
                self.install_remote(dst, clean=True)
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
                self.install_remote(dst, clean=True)
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
        output = self._run(["pm", "list", "packages"])
        for m in re.finditer(r'^package:([^\s]+)\r?$', output, re.M):
            result.append(m.group(1))
        return list(sorted(result))

    def package_info(self, package_name: str) -> typing.Union[dict, None]:
        """
        version_code might be empty

        Returns:
            None or dict(version_name, version_code, signature)
        """
        output = self._run(['dumpsys', 'package', package_name])
        m = re.compile(r'versionName=(?P<name>[\d.]+)').search(output)
        version_name = m.group('name') if m else ""
        m = re.compile(r'versionCode=(?P<code>\d+)').search(output)
        version_code = m.group('code') if m else ""
        if version_code == "0":
            version_code = ""
        m = re.search(r'PackageSignatures\{.*?\[(.*)\]\}', output)
        signature = m.group(1) if m else None
        if not version_name and signature is None:
            return None
        m = re.compile(r"pkgFlags=\[\s*(.*)\s*\]").search(output)
        pkgflags = m.group(1) if m else ""
        pkgflags = pkgflags.split()

        time_regex = r"[-\d]+\s+[:\d]+"
        m = re.compile(f"firstInstallTime=({time_regex})").search(output)
        first_install_time = datetime.strptime(
            m.group(1), "%Y-%m-%d %H:%M:%S") if m else None

        m = re.compile(f"lastUpdateTime=({time_regex})").search(output)
        last_update_time = datetime.strptime(
            m.group(1).strip(), "%Y-%m-%d %H:%M:%S") if m else None

        return dict(package_name=package_name,
                    version_name=version_name,
                    version_code=version_code,
                    flags=pkgflags,
                    first_install_time=first_install_time,
                    last_update_time=last_update_time,
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
            if output.startswith('INFO:'):
                output = output[output.index('{'):]
            data = json.loads(output)
            return data['rotation'] / 90
        except ValueError:
            pass

        raise AdbError("rotation get failed")

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

    def app_stop(self, package_name: str):
        """ stop app with "am force-stop"
        """
        self._run(['am', 'force-stop', package_name])

    def app_clear(self, package_name: str):
        self._run(["pm", "clear", package_name])

    def is_screen_on(self):
        output = self._run(["dumpsys", "power"])
        return 'mHoldingDisplaySuspendBlocker=true' in output

    def open_browser(self, url: str):
        if not re.match("^https?://", url):
            url = "https://" + url
        self._run(
            ['am', 'start', '-a', 'android.intent.action.VIEW', '-d', url])

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
            return dict(package=m.group('package'),
                        activity=m.group('activity'))

        # try: adb shell dumpsys activity top
        _activityRE = re.compile(
            r'ACTIVITY (?P<package>[^\s]+)/(?P<activity>[^/\s]+) \w+ pid=(?P<pid>\d+)'
        )
        output = self._run(['dumpsys', 'activity', 'top'])
        ms = _activityRE.finditer(output)
        ret = None
        for m in ms:
            ret = dict(package=m.group('package'),
                       activity=m.group('activity'),
                       pid=int(m.group('pid')))
        if ret:  # get last result
            return ret
        raise AdbError("Couldn't get focused app")

    def remove(self, path: str):
        """ rm device file """
        self.shell(["rm", path])

    def screenrecord(self, remote_path=None, no_autostart=False):
        """
        Args:
            remote_path: device video path
            no_autostart: do not start screenrecord, when call this method
        """
        return _ScreenRecord(self, remote_path, autostart=not no_autostart)


class _ScreenRecord():
    def __init__(self, d, remote_path=None, autostart=False):
        """ The maxium record time is 3 minutes """
        self._d = d
        if not remote_path:
            remote_path = "/sdcard/video-%d.mp4" % int(time.time() * 1000)
        self._remote_path = remote_path
        self._stream = None
        self._stopped = False
        self._started = False

        if autostart:
            self.start()

    def start(self):
        """ start recording """
        if self._started:
            warnings.warn("screenrecord already started", UserWarning)
            return
        self._stream = self._d.shell(["screenrecord", self._remote_path],
                                     stream=True)
        self._started = True

    def stop(self):
        """ stop recording """
        if not self._started:
            raise RuntimeError("screenrecord is not started")

        if self._stopped:
            return
        self._stream.send("\003")
        self._stream.read_until_close()
        self._stream.close()
        self._stopped = True

    def stop_and_pull(self, path: str):
        """ pull remote to local and remove remote file """
        self.stop()
        self._d.sync.pull(self._remote_path, path)
        self._d.remove(self._remote_path)

    def close(self):  # alias of stop
        return self.stop()

    def close_and_pull(self, path: str):  # alias of stop_and_pull
        return self.stop_and_pull(path=path)
