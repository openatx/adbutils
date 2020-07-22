# coding: utf-8
#


def test_reverse(device):
    """
    Test commands:
    
        adb reverse --list
        adb -s xxxxx reverse --list
    """
    device.reverse("tcp:12345", "tcp:4000")
    exists = False
    for item in device.reverse_list():
        if item.local == "tcp:12345" and item.remote == "tcp:4000":
            exists = True
    assert exists
