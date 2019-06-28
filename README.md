# adbutils
[![Build Status](https://travis-ci.org/openatx/adbutils.svg?branch=master)](https://travis-ci.org/openatx/adbutils)
[![PyPI](https://img.shields.io/pypi/v/adbutils.svg?color=blue)](https://pypi.org/project/adbutils/#history)

Python adb library for adb service (Only support Python3.6+)

# Install
```
pip install adbutils
```

# Usage
Example

## Connect ADB Server
```python
import adbutils

adb = adbutils.AdbClient(host="127.0.0.1", port=5037)
print(adb.devices())
```

The above code can be short to `from adbutils import adb`

## List all the devices and get device object
```python
from adbutils import adb

for d in adb.devices():
    print(d.serial) # print device serial

d = adb.device(serial="33ff22xx")

# You do not need to offer serial if only one device connected
# RuntimeError will be raised if multi device connected
d = adb.device()
```

The following code will not write `from adbutils import adb` for short

## Connect remote device
Same as command `adb connect`

```python
output = adb.connect("127.0.0.1:5555")
print(output)
# output: already connected to 127.0.0.1:5555
```

## List forward
Same as `adb forward --list`

```python
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
```

## Run shell command and transfer files
I assume there is only one device connected.

```python
import io
from adbutils import adb

d = adb.device()

print(d.serial) # 获取序列号
print(d.shell(["getprop", "ro.serial"])) # 获取Prop信息
d.sync.push(io.BytesIO(b"Hello Android"), "/data/local/tmp/hi.txt") # 推送文件

# 读取文件
for chunk in d.sync.iter_content("/data/local/tmp/hi.txt"):
    print("Chunk", chunk)

# 拷贝到本地
d.sync.pull("/data/local/tmp/hi.txt", "hi.txt")

# 获取包的信息
info = d.package_info("com.example.demo")
if info:
    print(info) # expect {"version_name": "1.2.3", "version_code": "12", "signature": "0xff132"}
```

## Run in command line 命令行使用

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

# Uninstall 卸载应用
$ python -m adbutils -u com.github.example

# List installed packages 列出所有应用
$ python -m adbutils --list-packages
com.android.adbkeyboard
com.buscode.whatsinput
com.finalwire.aida64
com.github.uiautomator
```

For more usage, please see the code for details. (Sorry I'm too lazy.)

## Extra Functions

AdbUtils provided some custom functions for some complex operations.

You can use it like this:

```python
# simulate click
d.click(100, 100)

# swipe from(10, 10) to(200, 200) 500ms
d.swipe(10, 10, 200, 200, 0.5)

d.list_packages()
# example output: ["com.example.hello"]

d.window_size() 
# example output: (1080, 1920)

d.rotation()
# example output: 1
# other possible valus: 0, 1, 2, 3

d.package_info("com.github.uiautomator")
# example output: {"version_name": "1.1.7", "version_code": "1007"}

d.keyevent("HOME")

# There still too many functions, please see source codes
```

For further usage, please read [mixin.py](adbutils/mixin.py) for details.

## Develop
```sh
git clone https://github.com/openatx/adbutils adbutils
pip install -e adbutils # install as development mode
```

Now you can edit code in `adbutils` and test with

```python
import adbutils
# .... test code here ...
```

Run tests requires one device connected to your computer

```sh
# change to repo directory
cd adbutils

pip install pytest
pytest tests/
```

# Thanks
- [swind pure-python-adb](https://github.com/Swind/pure-python-adb)
- [openstf/adbkit](https://github.com/openstf/adbkit)
- [ADB Source Code](https://github.com/aosp-mirror/platform_system_core/blob/master/adb)
- ADB Protocols [OVERVIEW.TXT](https://github.com/aosp-mirror/platform_system_core/blob/master/adb/OVERVIEW.TXT) [SERVICES.TXT](https://github.com/aosp-mirror/platform_system_core/blob/master/adb/SERVICES.TXT) [SYNC.TXT](https://github.com/aosp-mirror/platform_system_core/blob/master/adb/SYNC.TXT)
- [Awesome ADB](https://github.com/mzlogin/awesome-adb)

# LICENSE
[MIT](LICENSE)