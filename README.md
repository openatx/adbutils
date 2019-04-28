# adbutils
[![Build Status](https://travis-ci.org/openatx/adbutils.svg?branch=master)](https://travis-ci.org/openatx/adbutils)
![PyPI](https://img.shields.io/pypi/v/adbutils.svg?color=blue)

Python adb library for adb service

# Install
```
pip install adbutils
```

# Usgae
Example

## Connect ADB Server
```python
import adbutils

adb = adbutils.AdbClient(host="127.0.0.1", port=5037)
print(adb.devices())
```

The above code can be short to `from adbutils import adb`

## List all the device and get device object
```python
from adbutils import adb

for d in adb.devices():
    print(d.serial) # print device serial

d = adb.device(serial="33ff22xx")

# You do not need to offer serial if only one device connected
# RuntimeError will be raised if multi device connected
d = adb.device()
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
# Install apk from local filesystem 安装本地apk(带有进度)
$ python -m adbutils -i some.apk
# Install apk from URL 通过URL安装apk(带有进度)
$ python -m adbutils -i http://example.com/some.apk

# Uninstall 卸载应用
$ python -m adbutils -u com.github.example

# List installed packages 列出所有应用
$ python -m adbutils -l
```

For more usage, please see the code for details. (Sorry I'm too lazy.)

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

# LICENSE
[MIT](LICENSE)