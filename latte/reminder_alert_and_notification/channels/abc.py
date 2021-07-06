from abc import ABC,abstractmethod

class ChannelABC(ABC):
    @abstractmethod
    def send(self,*args, **kwargs):
        pass