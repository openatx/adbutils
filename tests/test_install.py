#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from adbutils.errors import AdbInstallError
from adbutils.install import InstallExtension
from adbutils.shell import ShellExtension


class FakeInstallDevice(InstallExtension):
    """Record what install_multiple pushes and which shell commands it runs."""

    def __init__(self):
        self.pushed = []
        self.shell_commands = []
        self.install_output = "Success\n"

    def shell(self, cmd, stream=False):
        self.shell_commands.append(cmd)
        if cmd[:2] == ["pm", "install-multiple"]:
            return self.install_output
        return ""

    def _push_apk(self, apk_path: Path, device_dst: str, show_progress: bool = True):
        self.pushed.append((str(apk_path), device_dst, show_progress))

    @property
    def sync(self):
        raise NotImplementedError

    def shell2(self, cmd, encoding="utf-8"):
        raise NotImplementedError

    def app_start(self, package_name, activity=None):
        raise NotImplementedError

    def uninstall(self, package_name):
        raise NotImplementedError

    def install_remote(self, path, clean=False, flags=["-r", "-t"]):
        raise NotImplementedError

    def remove(self, path):
        raise NotImplementedError


class FakeShellDevice(ShellExtension):
    """Exercise ShellExtension.install_remote without a real adb connection."""

    def __init__(self, output="Success\n"):
        self.shell_commands = []
        self.output = output

    def shell(self, cmd, stream=False):
        self.shell_commands.append(cmd)
        return self.output

    @property
    def sync(self):
        raise NotImplementedError


class FakeSync:
    """Just enough of Sync for install(): push the apk and report its size."""

    def __init__(self, size: int):
        self.size = size
        self.pushed = []

    def push(self, fd, remote_path):
        self.pushed.append(remote_path)

    def stat(self, remote_path):
        return SimpleNamespace(size=self.size)


class RecordingInstallDevice(InstallExtension):
    """Record the install_remote calls made by install()."""

    def __init__(self, apk_size: int):
        self.remote_calls = []
        self._sync = FakeSync(apk_size)

    @property
    def sync(self):
        return self._sync

    def shell(self, cmd, stream=False):
        raise NotImplementedError

    def shell2(self, cmd, encoding="utf-8"):
        raise NotImplementedError

    def app_start(self, package_name, activity=None):
        raise NotImplementedError

    def uninstall(self, package_name):
        raise NotImplementedError

    def install_remote(self, path, clean=False, flags=["-r", "-t"]):
        self.remote_calls.append((path, clean, list(flags)))

    def remove(self, path):
        raise NotImplementedError

    def _push_apk(self, apk_path: Path, device_dst: str, show_progress: bool = True):
        self.sync.push(None, device_dst)


def make_split_apks(tmp_path: Path):
    names = [
        "base.apk",
        "split_config.arm64_v8a.apk",
        "split_config.xxhdpi.apk",
    ]
    paths = []
    for name in names:
        path = tmp_path / name
        path.write_bytes(b"fake apk")
        paths.append(path)
    return paths


def test_install_multiple_pushes_and_installs_split_apks(tmp_path: Path):
    paths = make_split_apks(tmp_path)
    device = FakeInstallDevice()

    device.install_multiple(paths, silent=True)

    remote_paths = [f"/data/local/tmp/{path.name}" for path in paths]
    assert device.pushed == [
        (str(path), remote, False) for path, remote in zip(paths, remote_paths)
    ]
    assert device.shell_commands[0] == [
        "pm",
        "install-multiple",
        "-r",
        "-t",
    ] + remote_paths
    assert device.shell_commands[1:] == [["rm", remote] for remote in remote_paths]


def test_install_multiple_accepts_str_paths_and_custom_flags(tmp_path: Path):
    paths = make_split_apks(tmp_path)
    device = FakeInstallDevice()

    device.install_multiple([str(path) for path in paths], silent=True, flags=["-d"])

    remote_paths = [f"/data/local/tmp/{path.name}" for path in paths]
    assert device.shell_commands[0] == [
        "pm",
        "install-multiple",
        "-d",
    ] + remote_paths


def test_install_multiple_rejects_empty_list():
    device = FakeInstallDevice()

    with pytest.raises(ValueError):
        device.install_multiple([], silent=True)

    assert device.pushed == []
    assert device.shell_commands == []


def test_install_multiple_cleans_up_when_install_fails(tmp_path: Path):
    paths = make_split_apks(tmp_path)
    device = FakeInstallDevice()
    device.install_output = "Failure [INSTALL_FAILED_INVALID_APK]"

    with pytest.raises(AdbInstallError) as exc_info:
        device.install_multiple(paths, silent=True)

    assert exc_info.value.reason == "INSTALL_FAILED_INVALID_APK"
    remote_paths = [f"/data/local/tmp/{path.name}" for path in paths]
    assert device.shell_commands[1:] == [["rm", remote] for remote in remote_paths]


def test_install_multiple_cleans_up_already_pushed_files_on_missing_file(tmp_path: Path):
    paths = make_split_apks(tmp_path)
    device = FakeInstallDevice()
    paused = [paths[0], tmp_path / "missing.apk"]

    with pytest.raises(FileNotFoundError):
        device.install_multiple(paused, silent=True)

    assert device.pushed == [(str(paths[0]), f"/data/local/tmp/{paths[0].name}", False)]
    assert device.shell_commands == [
        ["rm", f"/data/local/tmp/{paths[0].name}"],
    ]


def test_install_remote_appends_custom_flags_to_pm_install():
    device = FakeShellDevice()

    device.install_remote(
        "/data/local/tmp/apidemo.apk", clean=True, flags=["-r", "-t", "-d"]
    )

    assert device.shell_commands == [
        ["pm", "install", "-r", "-t", "-d", "/data/local/tmp/apidemo.apk"],
        ["rm", "/data/local/tmp/apidemo.apk"],
    ]


def test_install_remote_defaults_to_r_t_flags():
    device = FakeShellDevice()

    device.install_remote("/data/local/tmp/apidemo.apk")

    assert device.shell_commands == [
        ["pm", "install", "-r", "-t", "/data/local/tmp/apidemo.apk"],
    ]


def test_install_forwards_default_flags_to_install_remote(tmp_path: Path, monkeypatch):
    # Force the no-apkutils branch so the empty test apk is never parsed.
    monkeypatch.setitem(sys.modules, "apkutils", None)
    src_path = tmp_path / "apidemo.apk"
    src_path.write_bytes(b"fake apk")
    device = RecordingInstallDevice(apk_size=src_path.stat().st_size)

    device.install(src_path, silent=True)

    assert device.remote_calls == [
        ("/data/local/tmp/unknown.apk", True, ["-r", "-t"]),
    ]


def test_install_forwards_custom_flags_to_install_remote(tmp_path: Path, monkeypatch):
    monkeypatch.setitem(sys.modules, "apkutils", None)
    src_path = tmp_path / "apidemo.apk"
    src_path.write_bytes(b"fake apk")
    device = RecordingInstallDevice(apk_size=src_path.stat().st_size)

    device.install(str(src_path), silent=True, flags=["-r", "-t", "-d"])

    assert device.remote_calls == [
        ("/data/local/tmp/unknown.apk", True, ["-r", "-t", "-d"]),
    ]
