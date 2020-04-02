# coding: utf-8
#

import os
import pathlib
import shutil
import struct
import sys
import tempfile
import zipfile
from urllib.request import urlopen


def get_platform():
    bits = struct.calcsize("P") * 8
    if sys.platform.startswith("linux"):
        return "linux{}".format(bits)
    elif sys.platform.startswith("win"):
        return "win{}".format(bits)
    elif sys.platform.startswith("cygwin"):
        return "win{}".format(bits)
    elif sys.platform.startswith("darwin"):
        return "osx{}".format(bits)
    else:  # pragma: no cover
        return None


# Platform string -> adb filename
FNAME_PER_PLATFORM = {
    "win32": "1.0.41/adb-win32-1.0.41.zip",
    "win64": "1.0.41/adb-win32-1.0.41.zip",
}


def download_adb() -> str:
    """
    get adb path, if not exist local, download from github
    
    Returns:
        path of adb.exe
    """
    fname = FNAME_PER_PLATFORM[get_platform()]
    url = "https://github.com/openatx/adb-binaries/raw/master/" + fname
    source_dir = os.path.expandvars("$HOME/.adbutils/bin")

    path = pathlib.Path(source_dir).joinpath("adb.exe")
    if path.exists():
        return str(path)

    with tempfile.NamedTemporaryFile(suffix=".zip") as tmpf:
        print("Downloading adb binaries", "...", end="")
        with urlopen(url, timeout=5) as f1:
            shutil.copyfileobj(f1, tmpf)
            tmpf.flush()
        print("done")
        with zipfile.ZipFile(tmpf.name, "r") as zf:
            os.makedirs(source_dir, exist_ok=True)
            zf.extractall(source_dir)
    return str(path)


# def mirror_download(url: str, storepath: str) -> str:
#     """
#     Returns:
#         storepath
#     """
#     if os.path.exists(storepath):
#         return storepath
#     github_host = "https://github.com"
#     if url.startswith(github_host):
#         mirror_url = "http://tool.appetizer.io" + url[len(
#             github_host):]  # mirror of github
#         try:
#             return download(mirror_url, storepath)
#         except (requests.RequestException, ValueError) as e:
#             logger.debug("download from mirror error, use origin source")

#     return download(url, storepath)

# def download(url: str, storepath: str):
#     target_dir = os.path.dirname(storepath) or "."
#     os.makedirs(target_dir, exist_ok=True)

#     r = requests.get(url, stream=True)
#     r.raise_for_status()
#     total_size = int(r.headers.get("Content-Length", "-1"))
#     bytes_so_far = 0
#     prefix = "Downloading %s" % os.path.basename(storepath)
#     chunk_length = 16 * 1024
#     with open(storepath + '.part', 'wb') as f:
#         for buf in r.iter_content(chunk_length):
#             bytes_so_far += len(buf)
#             print(f"\r{prefix} {bytes_so_far} / {total_size}",
#                   end="",
#                   flush=True)
#             f.write(buf)
#         print(" [Done]")
#     if total_size != -1 and os.path.getsize(storepath + ".part") != total_size:
#         raise ValueError("download size mismatch")
#     shutil.move(storepath + '.part', storepath)
