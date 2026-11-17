# adbutils
[![PyPI](https://img.shields.io/pypi/v/adbutils.svg?color=blue)](https://pypi.org/project/adbutils/#history)

[English](README.md) | [简体中文](README.zh-CN.md)

用于 adb 服务的 Python adb 库

# 环境要求
Python 3.8+

**目录**

<!--ts-->
   * [adbutils](#adbutils)
   * [安装](#安装)
   * [用法](#用法)
      * [连接 ADB Server](#连接-adb-server)
      * [列出所有设备并获取设备对象](#列出所有设备并获取设备对象)
      * [连接或断开远程设备](#连接或断开远程设备)
      * [无线调试 (mDNS)](#无线调试-mdns)
      * [adb forward 与 adb reverse](#adb-forward-与-adb-reverse)
      * [与设备建立 socket 连接](#与设备建立-socket-连接)
      * [执行 shell 命令](#执行-shell-命令)
      * [传输文件](#传输文件)
      * [扩展功能](#扩展功能)
      * [命令行使用](#命令行使用)
         * [环境变量](#环境变量)
         * [彩色 Logcat](#彩色-logcat)
      * [实验功能](#实验功能)
      * [示例](#示例)
   * [开发](#开发)
      * [监听 adb socket 数据](#监听-adb-socket-数据)
   * [致谢](#致谢)
   * [参考](#参考)
   * [LICENSE](#license)

<!-- Added by: shengxiang, at: 2021年 3月26日 星期五 15时05分04秒 CST -->

<!--te-->

# 安装
```
pip3 install adbutils

# or
pip3 install adbutils[all]
```

# 用法
示例

## 连接 ADB Server
```python
import adbutils

adb = adbutils.AdbClient(host="127.0.0.1", port=5037)
for info in adb.list(extended=True):
    print(info.serial, info.state)
    # <serial> <device|offline>
    print(info.transport_id)

# only list state=device
print(adb.device_list())

# Set socket timeout to 10 (default None)
adb = adbutils.AdbClient(host="127.0.0.1", port=5037, socket_timeout=10)
print(adb.device_list())

# device_list/list also accept a per-call timeout. Without one they fall back
# to socket_timeout, or 10 seconds, so an unresponsive server raises AdbTimeout
# instead of blocking forever.
print(adb.device_list(timeout=10))
```

上面的代码可以简写为 `from adbutils import adb`

## 列出所有设备并获取设备对象
```python
from adbutils import adb

for d in adb.device_list():
    print(d.serial) # print device serial

d = adb.device(serial="33ff22xx")

# or
d = adb.device(transport_id=24) # transport_id can be found in: adb devices -l

# You do not need to offer serial if only one device connected
# RuntimeError will be raised if multi device connected
d = adb.device()
```

为简洁起见，后续代码不再重复写 `from adbutils import adb`

## 连接或断开远程设备
等同于命令 `adb connect`

```python
output = adb.connect("127.0.0.1:5555")
print(output)
# output: already connected to 127.0.0.1:5555

# connect with timeout
try:
    adb.connect("127.0.0.1:5555", timeout=3.0)
except AdbTimeout as e:
    print(e)

adb.disconnect("127.0.0.1:5555")
adb.disconnect("127.0.0.1:5555", raise_error=True) # if device is not present, AdbError will raise

# wait-for-device
adb.wait_for("127.0.0.1:5555", state="device") # wait for device online, state default value is "device"
adb.wait_for("127.0.0.1:5555", state="disconnect") # wait device disconnect
```

## 无线调试 (mDNS)
等同于 `adb mdns services` 与 `adb connect <instance>`。mDNS 发现由 adb server
完成，adbutils 不再自带一套 DNS-SD 实现。

需要支持 mDNS 的 platform-tools，且 adb server 未禁用 mDNS（不要设置
`ADB_MDNS=0`）。系统没有 Bonjour 时，可用 `ADB_MDNS_OPENSCREEN=1` 启动 server。

```python
# 列出 mDNS 发现的设备，包含配对服务
for service in adb.mdns_services():
    print(service.instance_name, service.service_name, service.addr)
    # adb-1234abcd-xyz _adb-tls-connect._tcp 192.168.1.2:6666

# 连接所有已配对好的无线调试设备
for service in adb.connect_mdns():
    print("connected:", service.serial)
    # connected: adb-1234abcd-xyz._adb-tls-connect._tcp
```

`connect_mdns()` 用 mDNS instance 名连接，serial 与 adb mDNS 自动连接一致。
仍需 `adb pair` 的设备会连接失败并被跳过（暂不实现配对）。

命令行：

```bash
python -m adbutils --mdns
python -m adbutils --connect-mdns
```

## adb forward 与 adb reverse
等同于：
* `adb forward <local> <remote>`
* `adb forward --remove <local>`
* `adb forward --remove-all`
* `adb reverse <remote> <local>`
* `adb reverse --remove <remote>`
* `adb reverse --remove-all`
* `adb forward --list` 
* `adb reverse --list`

```python
# forward local address to remote address
d.forward("tcp:9999", "localabstract:scrcpy")

# forward remote address to local random port
port = d.forward_port("localabstract:scrcpy")
print(port)  # 54622 (random)

# remove forwarded connection
d.forward_remove("tcp:9999")  # use local address

# remove all forwarded connections tied to specific device
d.forward_remove_all()

# reverse (forward) a remote address to a local address
d.reverse("localabstract:scrcpy", "tcp:9999")

# remove reversed connection
d.reverse_remove("localabstract:scrcpy")

# remove all reversed connection tied to specific device
d.reverse_remove_all()

# list all forwards
for item in adb.forward_list():
    print(item.serial, item.local, item.remote)
    # 8d1f93be tcp:10603 tcp:7912
    # 12345678 tcp:10664 tcp:7912

# list only one device forwards
for item in adb.forward_list("8d1f93be"):
    print(item.serial, item.local, item.remote)
    # 8d1f93be tcp:10603 tcp:7912
    # 12345678 tcp:10664 tcp:7912

# list all reversed forwards
for item in adb.reverse_list():
    print(item.serial, item.local, item.remote)
    # 8d1f93be tcp:9999 localabstract:scrcpy
    # 12345678 tcp:9999 localabstract:scrcpy

# 监控设备连接 track-devices
for event in adb.track_devices():
    print(event.present, event.serial, event.status)

## When plugin two device, output
# True WWUDU16C22003963 device
# True bf755cab device
# False bf755cab absent

# When adb-server killed, AdbError will be raised
```

## 与设备建立 socket 连接

例如

```python
# minitouch: https://github.com/openstf/minitouch
c = d.create_connection("unix", "minitouch")
print(c.recv(500))
c.close()
```

```python
c = d.create_connection("tcp", 7912) # the second argument must be int
c.send(b"GET / HTTP/1.1\r\nHost: localhost\r\n\r\n")
print(c.recv(500))
c.close()
```

```python
# read device file
with d.create_connection(adbutils.Network.DEV, "/data/local/tmp/hello.txt") as c:
    print(c.recv(500))
```

还有很多其他用法，详见 [SERVICES.TXT](https://cs.android.com/android/platform/superproject/+/master:packages/modules/adb/SERVICES.TXT;l=175)

感谢 [@hfutxqd](https://github.com/openatx/adbutils/pull/27) 提交的 Pull Request

## 执行 shell 命令
假设只连接了一台设备。

```python
import io
from adbutils import adb

d = adb.device()

print(d.serial) # 获取序列号

# Argument support list, str
serial = d.shell(["getprop", "ro.serial"]) # 获取Prop信息

# Same as
serial = d.shell("getprop ro.serial")

# Set timeout for shell command
d.shell("sleep 1", timeout=0.5) # Should raise adbutils.AdbTimeout

# 二进制安全输出，不经过设备 pty（等价于 adb exec-out）
png_data = d.exec_out("screencap -p")

# Open shell as connection
c = d.open_shell('cat') # AdbConnection, use c.conn to get socket.socket object
c.send(b'hello\n')
print(c.recv(100))
c.close()
# Expect output: b'hello\n'

# The advanced shell (returncode archieved by add command suffix: ;echo EXIT:$?)
ret = d.shell2("echo 1")
print(ret)
# expect: ShellReturn(args='echo 1', returncode=0, output='1\n')

# Advanced shell using the shell v2 protocol
ret = d.shell2("echo 1; echo 2 1>&2", v2=True)
print(ret)
# expect: ShellReturn(command='echo 1; echo 2 1>&2', returncode=0, output='1\n2\n', stderr='2\n', stdout='1\n')

# show property, also based on d.shell
print(d.prop.name) # output example: surabaya
d.prop.model
d.prop.device
d.prop.get("ro.product.model")
d.prop.get("ro.product.model", cache=True) # a little faster, use cache data first

d.get_serialno() # same as adb get-serialno
d.get_devpath() # same as adb get-devpath
d.get_state() # same as adb get-state
```

截屏

```python
# Method 1 (Recommend)
pil_image = d.screenshot()
# default display_id=0, error_ok=True
try:
    pil_image = d.screenshot(display_id=1, error_ok=False)
except AdbError:
    print("failed to takeScreenshot")

# Method 2
# same as: adb exec-out screencap -p > p.png
png_data = d.exec_out("screencap -p")
pathlib.Path("p.png").write_bytes(png_data)
```

## 传输文件
```python
d.sync.push(b"Hello Android", "/data/local/tmp/hi.txt") # 推送二进制文本
d.sync.push(io.BytesIO(b"Hello Android"), "/data/local/tmp/hi.txt") # 推送可读对象Readable object
d.sync.push("/tmp/hi.txt", "/data/local/tmp/hi.txt") # 推送本地文件
d.sync.push(pathlib.Path("/tmp/hi.txt"), "/data/local/tmp/hi.txt") # 推送本地文件

# 读取文件
for chunk in d.sync.iter_content("/data/local/tmp/hi.txt"):
    print("Chunk", chunk)

d.sync.push(b"Hello world", "/data/local/tmp/hi.txt")
output = d.sync.read_text("/data/local/tmp/hi.txt", encoding="utf-8")
# Expect output: "Hello world"
output = d.sync.read_bytes("/data/local/tmp/hi.txt")
# Expect output: b"Hello world"

# 拷贝到本地
d.sync.pull("/data/local/tmp/hi.txt", "hi.txt")

# 获取包的信息
info = d.app_info("com.example.demo")
if info:
    print(info) 
	# output example:
    # {
	# "version_name": "1.2.3", "version_code": "12", "signature": "0xff132", 
    # "first_install_time": datetime-object, "last_update_time": datetime-object,
    # }
```

## 扩展功能

AdbUtils 为一些复杂操作提供了自定义函数。

可以这样使用：

```python
# save screenshot
pilimg = d.screenshot()
pilimg.save("screenshot.jpg")

# get current app info
app_info = d.app_current()
print(app_info.package)
print(app_info.activity)
print(app_info.pid) # might be 0

# install apk
d.install("apidemo.apk") # use local path
d.install("http://example.com/apidemo.apk") # install from url
# 额外参数会直接追加到 "pm install"（默认 ["-r", "-t"]）
d.install("apidemo.apk", flags=["-r", "-t", "-d"])
# raise AdbInstallError if something went wrong

# install split apks (adb install-multiple)
d.install_multiple(["base.apk", "split_config.arm64_v8a.apk", "split_config.xxhdpi.apk"])

# simulate click
d.click(100, 100)
d.click(0.5, 0.5) # center, should be float and <= 1.0

# swipe from(10, 10) to(200, 200) 500ms
d.swipe(10, 10, 200, 200, 0.5)

# drag and drop from(10, 10) to(200, 200) 3000ms
d.drag(10, 10, 200, 200, 3)

d.list_packages()
# example output: ["com.example.hello"]

d.window_size()
# example output: (1080, 1920) when phone is portrait
# example output: (1920, 1080) when phone is landscape
d.window_size(landscape=True) # force landscape mode
# example output: (1920, 1080)

d.rotation() -> int
# example output: 0
# 0: natural, 1: left, 2: right, 3: upsidedown

d.app_info("com.github.uiautomator")
# example output: {"version_name": "1.1.7", "version_code": "1007"}

d.keyevent("HOME")

d.volume_up()
d.volume_down()
# default times=1, If you want to adjust the volume multiple times, you can use：d.volume_up(times=xxx)

d.volume_mute()  # device mute

d.send_keys("hello world$%^&*") # simulate: adb shell input text "hello%sworld\%\^\&\*"

d.open_browser("https://www.baidu.com") # 打开百度
# There still too many functions, please see source codes

# check if screen is on
d.is_screen_on() # 返回屏幕是否亮屏 True or False

# adb root
d.root()

# adb tcpip <port>
d.tcpip(5555)

print(d.battery())  # get battery info
BatteryInfo(ac_powered=False, usb_powered=False, wireless_powered=False, dock_powered=False, max_charging_current=0, max_charging_voltage=0, charge_counter=10000, status=4, health=2, present=True, level=100, scale=100, voltage=5000, temperature=25.0, technology='Li-ion')

print(d.brightness_value)  # get brightness value, return int value in 0-255
d.brightness_value = 100  # set brightness value

# you can also set brightness mode
from adbutils import BrightnessMode
print(d.brightness_mode)  # output BrightnessMode.AUTO or BrightnessMode.MANUAL
d.brightness_mode = BrightnessMode.MANUAL  # set brightness mode is manual
d.brightness_mode = BrightnessMode.AUTO  # set brightness mode is auto

```

录屏（mp4）

```python
d.start_recording("video.mp4")
time.sleep(5)
d.stop_recording()
```

Logcat

```python
# filter logcat to file
logcat = d.logcat("logcat.txt", clear=True, re_filter=".*FA.*") # clear default False
# do something else
logcat.stop(timeout=3) # tell thread to stop write, wait for 3s, if not stopped, raise TimeoutError
logcat.stop_nowait() # tell thread to stop write and close file
```


> 如果在 `$PATH` 中找到 scrcpy，录屏会优先使用 scrcpy，否则回退到 `adb shell screenrecord`

_注意：旧方法 d.screenrecord() 已在 0.16.2 之后移除_

<!-- # run screenrecord to record screen
r = d.screenrecord()
# sleep for a while, can not large then 3 minutes
r.stop() # stop recording
r.stop_and_pull("video.mp4") # stop recording and pull video to local, then remove video from device

# control start time manually
r = d.screenrecord(no_autostart=True)
r.start() # start record
r.stop_and_pull("video.mp4") # stop recording and pull video to local, then remove video from device
``` -->

更多用法请阅读 [_device.py](adbutils/_device.py)。

## 命令行使用

```bash
# List devices
$ python -m adbutils -l
8d1f93be              MI 5s
192.168.190.101:5555  Google Nexus 5X - 7.0.0 - API 24 - 1080x1920

# Show adb server version
$ python -m adbutils -V
39

# Install apk from local filesystem 安装本地apk(带有进度)
$ python -m adbutils -i some.apk
# Install apk from URL 通过URL安装apk(带有进度)
$ python -m adbutils -i http://example.com/some.apk
# Install and launch (-L or --launch)
$ python -m adbutils -i http://example.com/some.apk -L

# Parse apk info (support URL and local)
$ python -m adbutils --parse http://example.com/some.apk
$ python -m adbutils --parse some.apk
package: com.example.some
main-activity: com.example.some.MainActivity
version-name: 1.0.0
version-code: 100

# Uninstall 卸载应用
$ python -m adbutils -u com.github.example

# Push
$ python -m adbutils --push local.txt:/sdcard/remote.txt

# Pull
$ python -m adbutils --pull /sdcard/remote.txt # save to ./remote.txt

# List installed packages 列出所有应用
$ python -m adbutils --list-packages
com.android.adbkeyboard
com.buscode.whatsinput
com.finalwire.aida64
com.github.uiautomator

# Show URL of file QRCode 
$ python -m adbutils --qrcode some.apk
.--------.
|        |
| qrcode |
|        |
\--------/

# screenshot with screencap
$ python -m adbutils --screenshot screen.jpg 

# download minicap, minicap.so to device
$ python -m adbutils --minicap

# take screenshot with minicap
$ python -m adbutils --minicap --screenshot screen.jpg # screenshot with minicap

# Show more info for developers
$ python -m adbutils --dump-info
==== ADB Info ====
Path: /usr/local/bin/adb
Server version: 41

>> List of devices attached
- 9de75303 picasso Redmi K30 5G

# Track device status, function like: watch adb devices
$ python -m adbutils --track
15:09:59.534 08a3d291 -> device
15:10:02.683 08a3d291 -> absent
15:10:05.196 08a3d291 -> offline
15:10:06.545 08a3d291 -> absent
15:10:06.545 08a3d291 -> device
```

### 环境变量

```bash
ANDROID_SERIAL  serial number to connect to
ANDROID_ADB_SERVER_HOST adb server host to connect to
ANDROID_ADB_SERVER_PORT adb server port to connect to
```

### 彩色 Logcat

为了方便使用 logcat，我把 pidcat 内置了。

```bash
python3 -m adbutils.pidcat [package]
```

![](assets/images/pidcat.png)


## 实验功能
支持安装时自动确认（Beta），需要先熟悉 [uiautomator2](https://github.com/openatx/uiautomator2)

```bash
# Install with auto confirm (Experiment, based on github.com/openatx/uiautomator2)
$ python -m adbutils --install-confirm -i some.apk
```

更多用法请查看源码。

## 示例
使用 screenrecord 录制视频

```python
stream = d.shell("screenrecord /sdcard/s.mp4", stream=True)
time.sleep(3) # record for 3 seconds
with stream:
	stream.send(b"\003") # send Ctrl+C
	stream.read_until_close()

start = time.time()
print("Video total time is about", time.time() - start)
d.sync.pull("/sdcard/s.mp4", "s.mp4") # pulling video
```

读取 Logcat

```python
d.shell("logcat --clear")
stream = d.shell("logcat", stream=True)
with stream:
    f = stream.conn.makefile()
    for _ in range(100): # read 100 lines
        line = f.readline()
        print("Logcat:", line.rstrip())
    f.close()
```

# 开发
```sh
git clone https://github.com/openatx/adbutils adbutils
pip3 install -e adbutils # install as development mode
```

现在你可以修改 `adbutils` 中的代码并测试

```python
import adbutils
# .... test code here ...
```

运行测试需要连接一台设备到电脑

```sh
# change to repo directory
cd adbutils

pip3 install pytest
pytest tests/
```

# 环境
以下环境变量会影响 adbutils 的行为

- ADBUTILS_ADB_PATH: specify adb path, default search from PATH
- ANDROID_SERIAL: default adb serial
- ANDROID_ADB_SERVER_HOST: default 127.0.0.1
- ANDROID_ADB_SERVER_PORT: default 5037

在 docker 环境中需要设置

```sh
export ANDROID_ADB_SERVER_HOST=host.docker.internal
```

## 监听 adb socket 数据
使用 `socat` 监听 adb socket 数据

```
$ socat -t100 -x -v TCP-LISTEN:5577,reuseaddr,fork TCP4:localhost:5037
```

打开另一个终端，输入以下命令即可看到 socket 数据

```bash
$ export ANDROID_ADB_SERVER_PORT=5577
$ adb devices
```

## 从 1.x 到 2.x 的变化

### 移除
- 移除了 current_app，请改用 app_current
- package_info 即将移除，请改用 app_info

### 新增
- 新增 volume_up、volume_down、volume_mute

## 生成目录
```bash
gh-md-toc --insert README.md
```

<https://github.com/ekalinin/github-markdown-toc>

# 致谢
- [swind pure-python-adb](https://github.com/Swind/pure-python-adb)
- [openstf/adbkit](https://github.com/openstf/adbkit)
- [ADB Source Code](https://android.googlesource.com/platform/system/core/+/android-4.4_r1/adb/adb.c)
- [Awesome ADB](https://github.com/mzlogin/awesome-adb)
- [JakeWharton/pidcat](https://github.com/JakeWharton/pidcat)

# 开发
[PROTOCOL.md](docs/PROTOCOL.md)

# 其他实现
- https://github.com/Swind/pure-python-adb
- https://github.com/touxiaoling/adbutils_async

# 参考
- <https://github.com/imageio/imageio-ffmpeg/blob/80e37882d0/imageio_ffmpeg/_utils.py>

# LICENSE
[MIT](LICENSE)
