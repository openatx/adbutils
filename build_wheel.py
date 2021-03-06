#!/usr/bin/env python3
# coding: utf-8
import os
import shutil
import subprocess
import sys
from urllib.request import urlopen

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
LIBNAME = "adbutils"
BINARIES_DIR = os.path.join(ROOT_DIR, "adbutils", "binaries")


ADB_VERSION = "1.0.41"
FNAMES_PER_PLATFORM = {
    "win32": ["adb.exe", "AdbWinApi.dll", "AdbWinUsbApi.dll"],
    "osx64": ["adb"],
}

osxplats = "macosx_10_9_intel.macosx_10_9_x86_64.macosx_10_10_intel.macosx_10_10_x86_64"

WHEEL_BUILDS = {
    "py3-none-win32": "win32",
    "py3-none-win_amd64": "win32",
    "py3-none-" + osxplats: "osx64",
}

def copy_binaries(target_dir, platform: str):
    assert os.path.isdir(target_dir)
    
    base_url = f"https://github.com/openatx/adb-binaries/raw/master/{ADB_VERSION}"
    for fname in FNAMES_PER_PLATFORM[platform]:
        filename = os.path.join(target_dir, fname)
        fileurl = "/".join([base_url, platform, fname])
        
        print("Downloading", fileurl, "...", end=" ", flush=True)
        with urlopen(fileurl, timeout=5) as f1:
            with open(filename, "wb") as f2:
                shutil.copyfileobj(f1, f2)
            if fname == "adb":
                os.chmod(filename, 0o755)
        print("done")

# copy_binaries(os.path.join(ROOT_DIR, "adbutils", "binaries"), "win32")

def clear_binaries_dir(target_dir):
    assert os.path.isdir(target_dir)
    assert os.path.basename(target_dir) == "binaries"
    
    for fname in os.listdir(target_dir):
        if fname != "README.md":
            print("Removing", fname, "...", end=" ")
            os.remove(os.path.join(target_dir, fname))
            print("done")

def clean():
    for root, dirs, files in os.walk(ROOT_DIR):
        for dname in dirs:
            if dname in (
                "__pycache__",
                ".cache",
                "dist",
                "build",
                LIBNAME + ".egg-info",
            ):
                shutil.rmtree(os.path.join(root, dname))
                print("Removing", dname)
        for fname in files:
            if fname.endswith((".pyc", ".pyo")):
                os.remove(os.path.join(root, fname))
                print("Removing", fname)
    
def build():
    clean()
    # Clear binaries, we don't want them in the reference release
    clear_binaries_dir(os.path.join(ROOT_DIR, "adbutils", "binaries"))
    
    print("Using setup.py to generate wheel ...", end="")
    subprocess.check_output(
        [sys.executable, "setup.py", "sdist", "bdist_wheel"], cwd=ROOT_DIR
    )
    print("done")
    
    # Version is generated by pbr
    version = None
    distdir = os.path.join(ROOT_DIR, "dist")
    for fname in os.listdir(distdir):
        if fname.endswith(".whl"):
            version = fname.split("-")[1]
            break
    assert version

    # Prepare
    fname = "-".join([LIBNAME, version, "py3-none-any.whl"])
    packdir = LIBNAME+"-"+version
    infodir = f"{LIBNAME}-{version}.dist-info"
    wheelfile = os.path.join(distdir, packdir, infodir, "WHEEL")
    print("Path:", os.path.join(distdir, fname))
    assert os.path.isfile(os.path.join(distdir, fname))
    
    print("Unpacking ...", end="")
    subprocess.check_output(
        [sys.executable, "-m", "wheel", "unpack", fname], cwd=distdir)
    os.remove(os.path.join(distdir, packdir, infodir, "RECORD"))
    print("done")
    
    # Build for different platforms
    for wheeltag, platform in WHEEL_BUILDS.items():
        print(f"Edit for {platform} {wheeltag}")

        # copy binaries
        binary_dir = os.path.join(distdir, packdir, LIBNAME, "binaries")
        clear_binaries_dir(binary_dir)
        copy_binaries(binary_dir, platform)
        
        lines = []
        for line in open(wheelfile, "r", encoding="UTF-8"):
            if line.startswith("Tag:"):
                line = "Tag: " + wheeltag
            lines.append(line.rstrip())
        with open(wheelfile, "w", encoding="UTF-8") as f:
            f.write("\n".join(lines))
        
        print("Pack ...", end="")
        subprocess.check_output(
            [sys.executable, "-m", "wheel", "pack", packdir], cwd=distdir)
        print("done")
    
    # Clean up
    os.remove(os.path.join(distdir, fname))
    shutil.rmtree(os.path.join(distdir, packdir))
    
    # Show overview
    print("Dist folder:")
    for fname in sorted(os.listdir(distdir)):
        s = os.stat(os.path.join(distdir, fname)).st_size
        print("  {:0.0f} KB {}".format(s / 2**10, fname))


def release():
    """ Release the packages to pypi """
    username = os.environ["PYPI_USERNAME"]
    password = os.environ['PYPI_PASSWORD']
    subprocess.check_call(
        [sys.executable, "-m", "twine", "upload", "-u", username, '-p', password, "dist/*"])


if __name__ == "__main__":
    build()
