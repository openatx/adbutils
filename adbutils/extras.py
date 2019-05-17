import typing
import re
import time

import adbutils


class ExtraUtilsMixin(object):
    """ provide custom functions for some complex operations """

    def _execute(self, command) -> str:
        return self.shell(command)

    def _show_all_functions(self) -> list:
        return [_ for _ in self.__dir__() if not _.startswith('_')]

    def say_hello(self) -> str:
        content = 'hello from {}'.format(self.serial)
        return self._execute('echo {}'.format(content))

    def input_key_event(self, key_code: (int, str)) -> str:
        """ adb shell input keyevent KEY_CODE """
        return self._execute('input keyevent {}'.format(str(key_code)))

    def clean_cache(self, package_name: str) -> str:
        """
        清理对应包的缓存（需要root）

        :param package_name: 对应包名
        :return:
        """
        return self._execute('pm clear {}'.format(package_name))

    def switch_screen(self, status: bool) -> str:
        """
        点亮/熄灭 屏幕

        :param status: true or false
        :return:
        """
        _key_dict = {
            True: '224',
            False: '223',
        }
        return self.input_key_event(_key_dict[status])

    def switch_airplane(self, status: bool) -> str:
        """
        切换飞行模式的开关

        :param status: true or false
        :return:
        """
        base_setting_cmd = ["settings", "put", "global", "airplane_mode_on"]
        base_am_cmd = ["am", "broadcast", "-a", "android.intent.action.AIRPLANE_MODE", "--ez", "state"]
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
        切换wifi开关

        :param status: true or false
        :return:
        """
        base_cmd = ['svc', 'wifi']
        cmd_dict = {
            True: base_cmd + ['enable'],
            False: base_cmd + ['disable'],
        }
        return self._execute(cmd_dict[status])

    def start_activity(self, command: str) -> str:
        """
        实际上是运行 adb shell am start <command>

        :param command: adb shell am start <command>
        :return:
        """
        return self._execute('am start {}'.format(command))

    def start_broadcast(self, command: str) -> str:
        """
        实际上是运行 adb shell am broadcast <command>

        :param command: adb shell am start <command>
        :return:
        """
        return self._execute('am broadcast {}'.format(command))

    def swipe(self, start: typing.Sequence, end: typing.Sequence) -> str:
        """
        swipe from start point to end point

        :param start: (100, 100)
        :param end: (400, 400)
        :return:
        """
        x1, y1, x2, y2 = map(str, [*start, *end])
        return self._execute(['input', 'swipe', x1, y1, x2, y2])

    def click(self, point: typing.Sequence) -> str:
        """
        adb shell input tap

        :param point: (100, 100)
        :return:
        """
        x, y = map(str, point)
        return self._execute(['input', 'tap', x, y])

    def set_ime(self, ime_name: str) -> str:
        """
        设置输入法（可以使用adb shell ime list -a 获取输入法包名）

        :param ime_name: 输入法包名 eg：com.android.inputmethod.pinyin/.PinyinIME
        :return:
        """
        return self._execute(['ime', 'set', ime_name])

    def make_dir(self, target: str) -> str:
        """
        make empty dir: adb shell mkdir <target_dir>

        :param target: 目标路径，/sdcard/somewhere
        :return:
        """
        return self._execute(['mkdir', target])

    def remove_dir(self, target: str) -> str:
        """
        clean dir: adb shell rm -rf <target>

        :param target: 目标路径，/sdcard/somewhere
        :return:
        """
        return self._execute(['rm', '-rf', target])

    def get_ip_address(self) -> str:
        """ 获取android设备ip """
        # TODO better design?
        result = self._execute(['ifconfig', 'wlan0'])
        print(result)
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
        # try:
        #     output = self.shell_output("pm", "install", "-r", "-t", dst)
        #     if "Success" not in output:
        #         raise AdbError(output)
        # finally:
        #     self.shell_output("rm", dst)
        # self.adb_output("install", "-r", apk_path)

    def install_remote(self,
                       remote_path: str,
                       clean: bool = False,
                       flags: list = ["-r", "-t"]):
        """
        Args:
            clean(bool): remove when installed

        Raises:
            AdbInstallError
        """
        args = ["pm", "install"] + flags + [remote_path]
        output = self.shell_output(*args)
        if "Success" not in output:
            raise adbutils.AdbInstallError(output)
        if clean:
            self.shell_output("rm", remote_path)

    def uninstall(self, pkg_name: str):
        return self.shell_output("pm", "uninstall", pkg_name)
        # self.adb_output("uninstall", pkg_name)

    def getprop(self, prop: str) -> str:
        return self.shell_output('getprop', prop).strip()

    def list_packages(self) -> list:
        """
        Returns:
            list of package names
        """
        result = []
        output = self.shell_output("pm", "list", "packages", "-3")
        for m in re.finditer(r'^package:([^\s]+)$', output, re.M):
            result.append(m.group(1))
        return list(sorted(result))

    def package_info(self, pkg_name: str) -> typing.Union[dict, None]:
        """
        version_code might be empty

        Returns:
            None or dict
        """
        output = self.shell_output('dumpsys', 'package', pkg_name)
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
        return dict(
            version_name=version_name,
            version_code=version_code,
            signature=signature)

    def window_size(self):
        """get window size
        Returns:
            (width, height)
        """
        output = self.shell_output("wm", "size")
        m = re.match(r"Physical size: (\d+)x(\d+)", output)
        if m:
            return list(map(int, m.groups()))
        raise RuntimeError("Can't parse wm size: " + output)

    def app_start(self, package_name: str):
        self.shell_output("monkey", "-p", package_name, "-c",
                          "android.intent.category.LAUNCHER", "1")
