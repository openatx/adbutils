# adbutils
[![Build Status](https://travis-ci.org/openatx/adbutils.svg?branch=master)](https://travis-ci.org/openatx/adbutils)

Python adb library for adb service

# Install
```
pip install adbutils
```

# Usgae
Example

```python
import io
from adbutils import adb

for d in adb.devices():
    print(d.serial) # 获取序列号
    print(d.shell_output("getprop", "ro.serial")) # 获取Prop信息
    d.sync.push(io.BytesIO(b"Hello Android"), "/data/local/tmp/hi.txt") # 推送文件

    # 读取文件
    for chunk in d.sync.iter_content("/data/local/tmp/hi.txt"):
        print("Chunk", chunk)

    # 拷贝到本地
    d.sync.pull("/data/local/tmp/hi.txt", "hi.txt")
```

命令行使用

```bash
# 安装本地apk(带有进度)
$ python -m adbutils -i some.apk
# 通过URL安装apk(带有进度)
$ python -m adbutils -i http://example.com/some.apk

# 卸载应用
$ python -m adbutils -u com.github.example

# 列出所有应用
$ python -m adbutils -l
```

For more usage, please see the code for details. (Sorry I'm too lazy.)

# Thanks
- [swind pure-python-adb](https://github.com/Swind/pure-python-adb)
- [openstf/adbkit](https://github.com/openstf/adbkit)
- [ADB Source Code](https://github.com/aosp-mirror/platform_system_core/blob/master/adb)
- ADB Protocols [OVERVIEW.TXT](https://github.com/aosp-mirror/platform_system_core/blob/master/adb/OVERVIEW.TXT) [SERVICES.TXT](https://github.com/aosp-mirror/platform_system_core/blob/master/adb/SERVICES.TXT) [SYNC.TXT](https://github.com/aosp-mirror/platform_system_core/blob/master/adb/SYNC.TXT)

# LICENSE
[MIT](LICENSE)