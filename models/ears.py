from abc import ABC, abstractmethod
import multiprocessing as mp

from models.agent_peripheral import AgentPeripheral


class Ears(AgentPeripheral, ABC):
    @abstractmethod
    def listen(self) -> mp.Process:
        pass
