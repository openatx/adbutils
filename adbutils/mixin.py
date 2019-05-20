# coding: utf-8
import re
import time
import typing

import adbutils


class ExtraUtilsMixin(object):
    """ provide custom functions for some complex operations """

    def _execute(self, *args) -> str:
        return self.shell(args)

    def say_hello(self) -> str:
        content = 'hello from {}'.format(self.serial)
        return self._execute('echo {}'.format(content))

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
        self._execute(base_setting_cmd)
        return self._execute(base_am_cmd)

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
        return self._execute(cmd_dict[status])

    def keyevent(self, key_code: (int, str)) -> str:
        """ adb _execute input keyevent KEY_CODE """
        return self._execute('input keyevent {}'.format(str(key_code)))

    def swipe(self, sx, sy, ex, ey):
        """
        swipe from start point to end point

        Args:
            sx, sy: start point(x, y)
            ex, ey: end point(x, y)
        """
        x1, y1, x2, y2 = map(str, [sx, sy, ex, ey])
        return self._execute(['input', 'swipe', x1, y1, x2, y2])

    def click(self, x, y):
        """
        simulate android tap

        Args:
            x, y: int
        """
        x, y = map(str, [x, y])
        return self._execute(['input', 'tap', x, y])

    def wlan_ip(self) -> str:
        """
        get device wlan ip

        Raises:
            IndexError
        """
        # TODO better design?
        result = self._execute(['ifconfig', 'wlan0'])
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
        output = self._execute(*args)
        if "Success" not in output:
            raise adbutils.AdbInstallError(output)
        if clean:
            self._execute("rm", remote_path)

    def uninstall(self, pkg_name: str):
        """
        Uninstall app by package name

        Args:
            pkg_name (str): package name
        """
        return self._execute("pm", "uninstall", pkg_name)

    def getprop(self, prop: str) -> str:
        return self._execute('getprop', prop).strip()

    def list_packages(self) -> list:
        """
        Returns:
            list of package names
        """
        result = []
        output = self._execute("pm", "list", "packages", "-3")
        for m in re.finditer(r'^package:([^\s]+)$', output, re.M):
            result.append(m.group(1))
        return list(sorted(result))

    def package_info(self, pkg_name: str) -> typing.Union[dict, None]:
        """
        version_code might be empty

        Returns:
            None or dict(version_name, version_code, signature)
        """
        output = self._execute('dumpsys', 'package', pkg_name)
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

    def window_size(self):
        """
        Get window size

        Returns:
            (width, height)
        """
        output = self._execute("wm", "size")
        m = re.match(r"Physical size: (\d+)x(\d+)", output)
        if m:
            return list(map(int, m.groups()))
        raise RuntimeError("Can't parse wm size: " + output)

    def app_start(self, package_name: str):
        self._execute("monkey", "-p", package_name, "-c",
                          "android.intent.category.LAUNCHER", "1")

    def app_clear(self, package_name: str):
        self._execute("pm", "clear", package_name)
