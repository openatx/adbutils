import os
import sys
import subprocess
import struct
from pkg_resources import resource_filename

import whichcraft


def get_adb_exe():
    # 1. find in $PATH
    exe = whichcraft.which("adb")
    if exe and _is_valid_exe(exe):
        return exe
    
    # 2. use buildin adb
    bin_dir = resource_filename("adbutils", "binaries")
    exe = os.path.join(bin_dir, "adb.exe" if os.name == 'nt' else 'adb')
    if os.path.isfile(exe) and _is_valid_exe(exe):
        return exe

    raise RuntimeError("No adb exe could be found. Install adb on your system")


def _popen_kwargs(prevent_sigint=False):
    startupinfo = None
    preexec_fn = None
    creationflags = 0
    if sys.platform.startswith("win"):
        # Stops executable from flashing on Windows (see imageio/imageio-ffmpeg#22)
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    if prevent_sigint:
        # Prevent propagation of sigint (see imageio/imageio-ffmpeg#4)
        # https://stackoverflow.com/questions/5045771
        if sys.platform.startswith("win"):
            creationflags = 0x00000200
        else:
            preexec_fn = os.setpgrp  # the _pre_exec does not seem to work
    return {
        "startupinfo": startupinfo,
        "creationflags": creationflags,
        "preexec_fn": preexec_fn,
    }


def _is_valid_exe(exe: str):
    cmd = [exe, "version"]
    try:
        with open(os.devnull, "w") as null:
            subprocess.check_call(
                cmd, stdout=null, stderr=subprocess.STDOUT, **_popen_kwargs()
            )
        return True
    except (OSError, ValueError, subprocess.CalledProcessError):
        return False
