# ADB Protocol
Tested with adb 1.0.41, Capture data with Charles

Charles settings

Proxy->Port Forwarding

```
TCP Local(5555) -> Remote(localhost:5037)
```

execute adb command, e.g. `adb -P 5555 devices`, now data should be seen in charles.

ADB Protocols from Android Source Code

- [OVERVIEW.TXT](https://cs.android.com/android/platform/superproject/+/main:packages/modules/adb/OVERVIEW.TXT)
- [SERVICES.TXT](https://cs.android.com/android/platform/superproject/+/main:packages/modules/adb/SERVICES.TXT)
- [SYNC.TXT](https://cs.android.com/android/platform/superproject/+/main:packages/modules/adb/SYNC.TXT)

## host version
```bash
>send
000chost:version

<recv
00000000  4f 4b 41 59 30 30 30 34 30 30 32 39               OKAY00040029    
```

## host tport device not found
```bash
>send
0026host:tport:serial:GBG5T197110027690014

<recv
00000000  46 41 49 4c 30 30 32 37 64 65 76 69 63 65 20 27   FAIL0027device '
00000010  47 42 47 35 54 31 39 37 31 31 30 30 32 37 36 39   GBG5T19711002769
00000020  30 30 31 34 27 20 6e 6f 74 20 66 6f 75 6e 64      0014' not found 
```

## forward
```bash
$ adb forward --list
>send
0011host:list-forward

<recv
OKAY0020emulator-5554 tcp:5678 tcp:8765

$ adb forward --remove-all
>send
000ehost:tport:any
0014host:killforward-all

<recv
00000000  4f 4b 41 59 08 00 00 00 00 00 00 00 4f 4b 41 59   OKAY        OKAY
00000010  4f 4b 41 59                                       OKAY            

$ adb -s emulator-5554 forward tcp:1234 tcp:4321
>send
001fhost:tport:serial:emulator-5554
001ehost:forward:tcp:1234;tcp:4321

<recv
00000000  4f 4b 41 59 08 00 00 00 00 00 00 00 4f 4b 41 59   OKAY        OKAY
00000010  4f 4b 41 59 30 30 30 34 31 32 33 34               OKAY00041234    
```

## reverse
adb help
```
reverse --list           list all reverse socket connections from device
 reverse [--no-rebind] REMOTE LOCAL
     reverse socket connection using:
       tcp:<port> (<remote> may be "tcp:0" to pick any open port)
       localabstract:<unix domain socket name>
       localreserved:<unix domain socket name>
       localfilesystem:<unix domain socket name>
 reverse --remove REMOTE  remove specific reverse socket connection
 reverse --remove-all     remove all reverse socket connections from device
```

```bash
$ adb reverse --list
>send
0022host:tport:serial:GBG5T197110027690014

<recv
00000000  4f 4b 41 59 06 00 00 00 00 00 00 00               OKAY        

>send
reverse:list-forward

<recv
00000000  4f 4b 41 59                                       OKAY
00000010  30 30 33 63 75 73 62 20 6c 6f 63 61 6c 61 62 73   003cusb localabs
00000020  74 72 61 63 74 3a 67 6e 69 72 65 68 74 65 74 20   tract:gnirehtet 
00000030  74 63 70 3a 33 31 34 31 36 0a 75 73 62 20 74 63   tcp:31416 usb tc
00000040  70 3a 35 31 32 33 20 74 63 70 3a 37 38 39 30 0a   p:5123 tcp:7890 
```

```
$ adb -s GBG5T197110027690014 reverse localabstract:test tcp:12345
>send
001fhost:tport:serial:emulator-5554002creverse:forward:localabstract:test;tcp:12345

<recv
00000000  4f 4b 41 59 03 00 00 00 00 00 00 00 4f 4b 41 59   OKAY        OKAY
00000010  4f 4b 41 59                                       OKAY            
```