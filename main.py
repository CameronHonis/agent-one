import logging
from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic
from langchain_core.language_models.chat_models import BaseChatModel
from blip_handler import BlipHandler
from listener import Listener

logger = logging.getLogger(__name__)


class Agent:
    def __init__(self, model: BaseChatModel, listener: Listener):
        self.model = model
        self.listener = listener

    def start(self):
        self.listener.listen()


def setup():
    logger.info("creating agent...")

    model = ChatAnthropic(model_name="claude-3-7-sonnet-latest")
    blip_handler = BlipHandler(model)
    listener = Listener(handle_blip=blip_handler.handle)
    agent = Agent(model, listener=listener)

    logger.info("Agent created!")
    return agent


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.DEBUG,
    )

    load_dotenv()

    _agent = setup()
    _agent.start()
