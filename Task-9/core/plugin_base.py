from abc import ABC, abstractmethod

class PluginBase(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        pass
        
    @property
    @abstractmethod
    def version(self) -> str:
        pass
        
    @property
    def dependencies(self) -> list[str]:
        return []
        
    @property
    def plugin_type(self) -> str:
        return "third-party"
        
    @abstractmethod
    def activate(self) -> str:
        pass
        
    @abstractmethod
    def deactivate(self) -> None:
        pass
