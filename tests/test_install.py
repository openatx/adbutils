#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from pathlib import Path

import pytest

from adbutils.errors import AdbInstallError
from adbutils.install import InstallExtension


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
