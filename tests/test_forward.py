# coding: utf-8
#


def test_forward(device):
    """
    Test commands:
    
        adb forward --list
        adb -s xxxxx forward --list
    """
    device.forward("tcp:11221", "tcp:7912")
    exists = False
    for item in device.forward_list():
        if item.local == "tcp:11221" and item.remote == "tcp:7912":
            assert item.serial == device.serial
            exists = True
    assert exists
