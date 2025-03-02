import logging
from blip_handler import BlipHandler
from listener import Listener

logger = logging.getLogger(__name__)


class Agent:
    def __init__(self, listener: Listener):
        self.listener = listener

    def start(self): ...


def setup():
    logger.info("creating agent...")

    blip_handler = BlipHandler()
    listener = Listener(handler=blip_handler.handle)
    agent = Agent(listener=listener)

    logger.info("Agent created!")
    return agent


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%s(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    agent = setup()
    agent.start()
