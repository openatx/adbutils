"""Check per-user package removal and restoration."""

from unittest.mock import patch

import pytest

from adbutils import AdbClient, AdbError
from adbutils._proto import ShellReturn


@pytest.mark.parametrize("user_id, flags", [(None, []), (0, ["--user", "0"]), (10, ["--user", "10"])])
def test_uninstall_user(user_id, flags):
    """Select the requested user and return implicitly on success."""
    device = AdbClient().device(serial="test")
    result = ShellReturn(command="", returncode=0, output="Success\n")
    with patch.object(target=device, attribute="shell2", return_value=result) as shell:
        assert device.uninstall(package_name="com.example.app", user_id=user_id) is None
    shell.assert_called_once_with(["pm", "uninstall"] + flags + ["com.example.app"])


@pytest.mark.parametrize("user_id, flags", [(None, []), (0, ["--user", "0"]), (10, ["--user", "10"])])
def test_install_existing_user(user_id, flags):
    """Wait for restoration and return implicitly on success."""
    device = AdbClient().device(serial="test")
    result = ShellReturn(command="", returncode=0, output="Received intent for package install\n")
    with patch.object(target=device, attribute="shell2", return_value=result) as shell:
        assert device.install_existing(package_name="com.example.app", user_id=user_id) is None
    shell.assert_called_once_with(cmdargs=["pm", "install-existing", "--wait"] + flags + ["com.example.app"])


@pytest.mark.parametrize("output, expected", [("Package does not exist\n", "Package does not exist"), ("", "exit code 1")])
def test_install_existing_failure(output, expected):
    """Raise with command output or the exit code when restoration fails."""
    device = AdbClient().device(serial="test")
    result = ShellReturn(command="", returncode=1, output=output)
    with patch.object(target=device, attribute="shell2", return_value=result):
        with pytest.raises(expected_exception=AdbError, match=expected):
            device.install_existing(package_name="com.example.app")


def test_uninstall_without_user():
    """Omit the user flag when no user is supplied."""
    device = AdbClient().device(serial="test")
    result = ShellReturn(command="", returncode=0, output="Success\n")
    with patch.object(target=device, attribute="shell2", return_value=result) as shell:
        assert device.uninstall(package_name="com.example.app") is None
    shell.assert_called_once_with(["pm", "uninstall", "com.example.app"])


@pytest.mark.parametrize("output, expected", [("Failure [DELETE_FAILED_INTERNAL_ERROR]", "DELETE_FAILED_INTERNAL_ERROR"), ("", "exit code 1")])
def test_uninstall_failure(output, expected):
    """Raise on failed removal, including failures with no output."""
    device = AdbClient().device(serial="test")
    result = ShellReturn(command="", returncode=1, output=output)
    with patch.object(target=device, attribute="shell2", return_value=result):
        with pytest.raises(expected_exception=AdbError, match=expected):
            device.uninstall(package_name="com.example.app", user_id=0)
