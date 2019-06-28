import re


class AdbError(Exception):
    """ adb error """

class AdbInstallError(AdbError):
    def __init__(self, output: str):
        """
        Errors examples:
        Failure [INSTALL_FAILED_ALREADY_EXISTS: Attempt to re-install io.appium.android.apis without first uninstalling.]
        Error: Failed to parse APK file: android.content.pm.PackageParser$PackageParserException: Failed to parse /data/local/tmp/tmp-29649242.apk

        Reference: https://github.com/mzlogin/awesome-adb
        """
        m = re.search(r"Failure \[([\w_]+)", output)
        self.reason = m.group(1) if m else "Unknown"
        self.output = output

    def __str__(self):
        return self.output