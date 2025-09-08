import abc
from typing import List, Optional, Union, overload

try:
    from typing import Literal
except ImportError:
    from typing_extensions import Literal

from adbutils._adb import AdbConnection, Network
from adbutils.sync import Sync
from adbutils._proto import ShellReturn, ShellReturnRaw

class AbstractShellDevice(abc.ABC):
    @abc.abstractmethod
    def shell(self, cmd: Union[str, List[str]]) -> str:
        pass

    @property
    @abc.abstractmethod
    def sync(self) -> Sync:
        pass


class AbstractDevice(abc.ABC):
    @overload
    @abc.abstractmethod
    def shell(self, cmd: str, stream: Literal[True]) -> AdbConnection: ...
    
    @overload
    @abc.abstractmethod
    def shell(self, cmd: str, stream: Literal[False] = False) -> str: ...
    
    @abc.abstractmethod
    def shell(self, cmd: str, stream: bool = False) -> Union[str, AdbConnection]:
        pass
    
    @overload
    @abc.abstractmethod
    def shell2(self, cmd: str, encoding: Literal[None]) -> ShellReturnRaw: ...
    
    @overload
    @abc.abstractmethod
    def shell2(self, cmd: str, encoding: str = "utf-8") -> ShellReturn: ...
    
    @abc.abstractmethod
    def shell2(self, cmd: str) -> ShellReturn:
        pass

    @property
    @abc.abstractmethod
    def sync(self) -> Sync:
        pass

    @abc.abstractmethod
    def app_start(self, package_name: str, activity: Optional[str] = None):
        pass

    @abc.abstractmethod
    def uninstall(self, package_name: str):
        pass

    @abc.abstractmethod
    def install_remote(self, path: str, clean: bool = False, flags: list = ["-r", "-t"]):
        pass
    
    @abc.abstractmethod
    def remove(self, path: str):
        pass