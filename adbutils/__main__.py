# coding: utf-8
#
"""
python -m apkutils COMMAND

Commands:
    install     Install apk to device
"""

from __future__ import absolute_import

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
import socket
import time
import zipfile

import requests

import adbutils
from adbutils import adb as adbclient
from adbutils.errors import AdbError, AdbInstallError

MB = 1024 * 1024


def humanize(n: int) -> str:
    return '%.1f MB' % (float(n) / MB)


def current_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        return ip
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


class ReadProgress():
    def __init__(self, r, total_size: int):
        self.r = r
        self.total = total_size
        self.copied = 0
        self.start_time = time.time()
        self.update_time = time.time()
        self.m = hashlib.md5()
        self._chunk_size = 0
        self._hash = ''

    def update(self, chunk: bytes):
        chunk_size = len(chunk)
        self.m.update(chunk)
        if chunk_size == 0:
            self._hash = self.m.hexdigest()
        self.copied += chunk_size
        self._chunk_size += chunk_size

        if self.total:
            percent = float(self.copied) / self.total * 100
        else:
            percent = 0.0 if chunk_size else 100.0

        p = int(percent)
        duration = time.time() - self.update_time
        if p == 100.0 or duration > 1.0:
            if duration:
                speed = humanize(self._chunk_size / duration) + "/s"
            else:
                copytime = time.time() - self.start_time
                speed = humanize(self.copied / copytime) + "/s"

            self.update_time = time.time()
            self._chunk_size = 0

            copysize = humanize(self.copied)
            totalsize = humanize(self.total)
            print("{:.1f}%\t{} [{}/{}]".format(percent, speed, copysize,
                                               totalsize))

    def read(self, n: int) -> bytes:
        chunk = self.r.read(n)
        self.update(chunk)
        return chunk


def _setup_minicap(d: adbutils.AdbDevice):
    def cache_download(url, dst):
        if os.path.exists(dst):
            print("Use cached", dst)
            return
        print("Download {} from {}".format(dst, url))
        resp = requests.get(url, stream=True)
        resp.raise_for_status()
        length = int(resp.headers.get("Content-Length", 0))
        r = ReadProgress(resp.raw, length)
        with open(dst + ".cached", "wb") as f:
            shutil.copyfileobj(r, f)
        shutil.move(dst + ".cached", dst)

    def push_zipfile(path: str,
                     dest: str,
                     mode=0o755,
                     zipfile_path: str = "vendor/stf-binaries-master.zip"):
        """ push minicap and minitouch from zip """
        with zipfile.ZipFile(zipfile_path) as z:
            if path not in z.namelist():
                print("WARNING: stf stuff %s not found", path)
                return
            with z.open(path) as f:
                d.sync.push(f, dest, mode)

    zipfile_path = "stf-binaries.zip"
    cache_download("https://github.com/openatx/stf-binaries/archive/0.2.zip",
                   zipfile_path)
    zip_folder = "stf-binaries-0.2"

    sdk = d.getprop("ro.build.version.sdk")  # eg 26
    abi = d.getprop('ro.product.cpu.abi')  # eg arm64-v8a
    abis = (d.getprop('ro.product.cpu.abilist').strip() or abi).split(",")
    # return
    print("sdk: %s, abi: %s, support-abis: %s" % (sdk, abi, ','.join(abis)))
    print("Push minicap+minicap.so to device")
    prefix = zip_folder + "/node_modules/minicap-prebuilt/prebuilt/"
    push_zipfile(prefix + abi + "/lib/android-" + sdk + "/minicap.so",
                 "/data/local/tmp/minicap.so", 0o644, zipfile_path)
    push_zipfile(prefix + abi + "/bin/minicap", "/data/local/tmp/minicap",
                 0o0755, zipfile_path)

    print("Push minitouch to device")
    prefix = zip_folder + "/node_modules/minitouch-prebuilt/prebuilt/"
    push_zipfile(prefix + abi + "/bin/minitouch", "/data/local/tmp/minitouch",
                 0o0755, zipfile_path)

    # check if minicap installed
    output = d.shell(
        ["LD_LIBRARY_PATH=/data/local/tmp", "/data/local/tmp/minicap", "-i"])
    print(output)
    print("If you see JSON output, it means minicap installed successfully")


def main():
    parser = argparse.ArgumentParser()
    # formatter_class=argparse.ArgumentDefaultsHelpFormatter)

    parser.add_argument("-s", "--serial", help="device serial number")
    parser.add_argument("-V",
                        "--server-version",
                        action="store_true",
                        help="show adb server version")
    parser.add_argument("-l",
                        "--list",
                        action="store_true",
                        help="list devices")
    parser.add_argument("-i",
                        "--install",
                        help="install from local apk or url")
    parser.add_argument(
        "--install-confirm",
        action="store_true",
        help="auto confirm when install (based on uiautomator2)")
    parser.add_argument("-u", "--uninstall", help="uninstall apk")
    parser.add_argument("--qrcode", help="show qrcode of the specified file")
    parser.add_argument("--clear",
                        action="store_true",
                        help="clear all data when uninstall")
    parser.add_argument("--list-packages",
                        action="store_true",
                        help="list packages installed")
    parser.add_argument("-p",
                        "--package",
                        help="show package info in json format")
    parser.add_argument("--grep", help="filter matched package names")
    parser.add_argument("--connect", type=str, help="connect remote device")
    parser.add_argument("--shell",
                        action="store_true",
                        help="run shell command")
    parser.add_argument("--minicap",
                        action="store_true",
                        help="install minicap and minitouch to device")
    parser.add_argument("--screenshot", type=str, help="take screenshot")
    parser.add_argument("-b", "--browser", help="open browser in device")
    parser.add_argument(
        "--push",
        help=
        "push local to remote, arg is colon seperated, eg some.txt:/sdcard/s.txt"
    )
    parser.add_argument(
        "--pull",
        help="push local to remote, arg is colon seperated, eg /sdcard/some.txt"
    )
    parser.add_argument("args", nargs="*", help="arguments")

    args = parser.parse_args()

    if args.connect:
        adbclient.connect(args.connect)
        return

    if args.server_version:
        print("ADB Server version: {}".format(adbclient.server_version()))
        return

    if args.list:
        rows = []
        for d in adbclient.devices():
            rows.append([d.serial, d.shell("getprop ro.product.model")])
        lens = []
        for col in zip(*rows):
            lens.append(max([len(v) for v in col]))
        format = "  ".join(["{:<" + str(l) + "}" for l in lens])
        for row in rows:
            print(format.format(*row))
        return

    if args.qrcode:
        from http.server import ThreadingHTTPServer
        from http.server import SimpleHTTPRequestHandler

        filename = args.qrcode
        port = 8000
        url = "http://%s:%d/%s" % (current_ip(), port, filename)
        print("File URL:", url)
        try:
            import qrcode
            qr = qrcode.QRCode(border=2)
            qr.add_data(url)
            qr.print_ascii(tty=True)
        except ImportError:
            print(
                "In order to show QRCode, you need install with: pip3 install qrcode"
            )

        httpd = ThreadingHTTPServer(('', port), SimpleHTTPRequestHandler)
        httpd.serve_forever()
        return

    d = adbclient.device(args.serial)

    if args.shell:
        output = d.shell(args.args)
        print(output)
        return

    if args.install:
        dst = "/data/local/tmp/tmp-%d.apk" % (int(time.time() * 1000))
        print("push to %s" % dst)
        if re.match(r"^https?://", args.install):
            resp = requests.get(args.install, stream=True)
            resp.raise_for_status()
            length = int(resp.headers.get("Content-Length", 0))
            r = ReadProgress(resp.raw, length)
        else:
            length = os.stat(args.install).st_size
            fd = open(args.install, "rb")
            r = ReadProgress(fd, length)

        start = time.time()
        d.sync.push(r, dst)
        print("Success pushed, time used %d seconds" % (time.time() - start))

        new_dst = "/data/local/tmp/tmp-%s.apk" % r._hash[:8]
        d.shell(["mv", dst, new_dst])
        dst = new_dst
        info = d.sync.stat(dst)
        print("verify pushed apk, md5: %s, size: %s" %
              (r._hash, humanize(info.size)))
        assert info.size == r.copied

        print("install to android system ...")
        if args.install_confirm:
            # Beta
            import uiautomator2 as u2
            ud = u2.connect(args.serial)
            ud.press("home")
            ud.xpath.when("继续安装").click()
            ud.xpath.when("允许").click()
            ud.xpath.when("安装").click()
            ud.xpath.watch_background(2.0)

        for i in range(3):
            try:
                start = time.time()
                d.install_remote(dst, clean=True)
                print("Success installed, time used %d seconds" %
                      (time.time() - start))
                break
            except AdbInstallError as e:
                if i < 2 and e.reason == "INSTALL_FAILED_CANCELLED_BY_USER":
                    print("Catch error %s, reinstall" % e.reason)
                    continue
                sys.exit(
                    "Failure " + e.reason + "\n" +
                    "Remote apk is not removed. Manually install command:\n\t"
                    + "adb shell pm install -r -t " + dst)

    elif args.uninstall:
        d.shell(["pm", "uninstall", args.uninstall])

    elif args.list_packages:
        patten = re.compile(args.grep or ".*")
        for p in d.list_packages():
            if patten.search(p):
                print(p)

    elif args.screenshot:
        if args.minicap:
            json_output = d.shell([
                "LD_LIBRARY_PATH=/data/local/tmp", "/data/local/tmp/minicap",
                "-i", "2&>/dev/null"
            ]).strip()
            data = json.loads(json_output)
            w, h, r = data["width"], data["height"], data["rotation"]
            d.shell([
                "LD_LIBRARY_PATH=/data/local/tmp", "/data/local/tmp/minicap",
                "-P", "{0}x{1}@{0}x{1}/{2}".format(w, h, r), "-s",
                ">/sdcard/minicap.jpg"
            ])
            d.sync.pull("/sdcard/minicap.jpg", args.screenshot)
        else:
            remote_tmp_path = "/data/local/tmp/screenshot.png"
            d.shell(["rm", remote_tmp_path])
            d.shell(["screencap", "-p", remote_tmp_path])
            d.sync.pull(remote_tmp_path, args.screenshot)

    elif args.minicap:  # without args.screenshot
        _setup_minicap(d)

    elif args.push:
        local, remote = args.push.split(":", 1)
        length = os.stat(local).st_size
        with open(local, "rb") as fd:
            r = ReadProgress(fd, length)
            d.sync.push(r, remote, filesize=length)

    elif args.pull:
        remote_path = args.pull
        target_path = os.path.basename(remote_path)
        finfo = d.sync.stat(args.pull)

        if finfo.mode == 0 and finfo.size == 0:
            sys.exit(f"remote file '{remote_path}' does not exist")

        bytes_so_far = 0
        for chunk in d.sync.iter_content(remote_path):
            bytes_so_far += len(chunk)
            percent = bytes_so_far / finfo.size * 100 if finfo.size != 0 else 100.0
            print(
                f"\rDownload to {target_path} ... [{bytes_so_far} / {finfo.size}] %.1f %%"
                % percent,
                end="",
                flush=True)
        print(f"{remote_path} pulled to {target_path}")

    elif args.browser:
        d.open_browser(args.browser)

    elif args.package:
        info = d.package_info(args.package)
        print(json.dumps(info, indent=4))


if __name__ == "__main__":
    main()
