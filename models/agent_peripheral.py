from abc import ABC
import typing


if typing.TYPE_CHECKING:
    from main import Agent


class AgentPeripheral(ABC):
    def __init__(self):
        self.agent: Agent = None
