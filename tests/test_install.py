#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from adbutils._proto import FileInfo
from adbutils.errors import AdbInstallError
from adbutils.install import InstallExtension
from adbutils.shell import ShellExtension


class FakeInstallDevice(InstallExtension):
    """Record pushes, shell commands, and single-APK install calls."""

    def __init__(self):
        self.pushed = []
        self.shell_commands = []
        self.install_output = "Success\n"
        self.calls = []
        self.install_remote_error = None

    def shell(self, cmd, stream=False):
        self.shell_commands.append(cmd)
        if cmd[:2] == ["pm", "install-multiple"]:
            return self.install_output
        return ""

    def _push_apk(self, apk_path: Path, device_dst: str, show_progress: bool = True):
        self.pushed.append((str(apk_path), device_dst, show_progress))

    @property
    def sync(self):
        device = self

        class _Sync:
            def stat(_self, path):
                for local, dst, _show in device.pushed:
                    if dst == path:
                        return FileInfo(0, Path(local).stat().st_size, None, path)
                return FileInfo(0, 0, None, path)

        return _Sync()

    def shell2(self, cmd, encoding="utf-8"):
        raise NotImplementedError

    def app_start(self, package_name, activity=None):
        self.calls.append(("app_start", package_name, activity))

    def uninstall(self, package_name):
        self.calls.append(("uninstall", package_name))

    def install_remote(self, path, clean=False, flags=["-r", "-t"]):
        self.calls.append(("install_remote", path, clean, list(flags)))
        if self.install_remote_error is not None:
            raise self.install_remote_error

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


def fake_apkutils(
    monkeypatch,
    package_name="com.example.app",
    activities=("MainActivity",),
    error=None,
):
    class _APK:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def get_manifest(self):
            if error is not None:
                raise error

        def get_manifest_main_activities(self):
            return list(activities)

    _APK.package_name = package_name
    module = SimpleNamespace(APK=SimpleNamespace(from_file=lambda _path: _APK()))
    monkeypatch.setitem(sys.modules, "apkutils", module)


def test_install_continues_when_manifest_parse_fails(tmp_path, monkeypatch, caplog):
    apk_path = tmp_path / "app.apk"
    apk_path.write_bytes(b"fake apk")
    fake_apkutils(monkeypatch, error=Exception("invalid decoded string length"))
    device = FakeInstallDevice()

    with caplog.at_level(logging.WARNING, logger="adbutils.install"):
        device._install(apk_path, uninstall=True, silent=True, has_apkutils=True)

    assert device.pushed == [(str(apk_path), "/data/local/tmp/unknown.apk", False)]
    assert device.calls == [
        ("install_remote", "/data/local/tmp/unknown.apk", True, ["-r", "-t"]),
    ]
    assert "invalid decoded string length" in caplog.text


def test_install_launches_parsed_main_activity(tmp_path, monkeypatch):
    apk_path = tmp_path / "app.apk"
    apk_path.write_bytes(b"fake apk")
    fake_apkutils(monkeypatch)
    device = FakeInstallDevice()

    device._install(apk_path, silent=True, has_apkutils=True)

    remote = "/data/local/tmp/com.example.app.apk"
    assert device.pushed == [(str(apk_path), remote, False)]
    assert device.calls == [
        ("install_remote", remote, True, ["-r", "-t"]),
        ("app_start", "com.example.app", ".MainActivity"),
    ]


def test_install_nolaunch_skips_app_start(tmp_path, monkeypatch):
    apk_path = tmp_path / "app.apk"
    apk_path.write_bytes(b"fake apk")
    fake_apkutils(monkeypatch)
    device = FakeInstallDevice()

    device._install(apk_path, nolaunch=True, silent=True, has_apkutils=True)

    assert device.calls == [
        ("install_remote", "/data/local/tmp/com.example.app.apk", True, ["-r", "-t"]),
    ]


def test_install_uninstalls_before_remote_install(tmp_path, monkeypatch):
    apk_path = tmp_path / "app.apk"
    apk_path.write_bytes(b"fake apk")
    fake_apkutils(monkeypatch)
    device = FakeInstallDevice()

    device._install(apk_path, uninstall=True, silent=True, has_apkutils=True)

    remote = "/data/local/tmp/com.example.app.apk"
    assert device.calls == [
        ("uninstall", "com.example.app"),
        ("install_remote", remote, True, ["-r", "-t"]),
        ("app_start", "com.example.app", ".MainActivity"),
    ]


def test_install_missing_file_pushes_nothing(tmp_path):
    device = FakeInstallDevice()

    with pytest.raises(FileNotFoundError):
        device._install(tmp_path / "missing.apk", silent=True, has_apkutils=True)

    assert device.pushed == []
    assert device.calls == []


def test_install_remote_invalid_apk_still_raises(tmp_path, monkeypatch):
    apk_path = tmp_path / "app.apk"
    apk_path.write_bytes(b"fake apk")
    fake_apkutils(monkeypatch)
    device = FakeInstallDevice()
    device.install_remote_error = AdbInstallError("Failure [INSTALL_FAILED_INVALID_APK]")

    with pytest.raises(AdbInstallError) as exc_info:
        device._install(apk_path, silent=True, has_apkutils=True)

    assert exc_info.value.reason == "INSTALL_FAILED_INVALID_APK"
    assert device.calls == [
        ("install_remote", "/data/local/tmp/com.example.app.apk", True, ["-r", "-t"]),
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
