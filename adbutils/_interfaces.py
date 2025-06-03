import abc
from typing import Union, List
from adbutils.sync import Sync


class AbstractShellDevice(abc.ABC):
    @abc.abstractmethod
    def shell(self, cmd: Union[str, List[str]]) -> str:
        pass

    @property
    @abc.abstractmethod
    def sync(self) -> Sync:
        pass