from abc import ABC, abstractmethod

from models.agent_peripheral import AgentPeripheral


class Ears(AgentPeripheral, ABC):
    @abstractmethod
    def listen(self):
        pass
