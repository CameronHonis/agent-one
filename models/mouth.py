from abc import ABC, abstractmethod
from models.agent_peripheral import AgentPeripheral


class Mouth(AgentPeripheral, ABC):
    @abstractmethod
    def speak(self, words: str):
        pass
