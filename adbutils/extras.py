import typing

if typing.TYPE_CHECKING:
    from adbutils import AdbDevice


class ExtraUtils(object):
    def __init__(self, device: 'AdbDevice'):
        self.__device = device

    def _execute(self, command) -> str:
        return self.__device.shell(command)

    def say_hello(self) -> str:
        return self._execute('echo hello')
