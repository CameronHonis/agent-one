import logging
from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic
from langchain_core.language_models.chat_models import BaseChatModel
from blip_handler import BlipHandler
from basic_ears import BasicEars, RecognizerName
from models.ears import Ears
from models.mouth import Mouth

logger = logging.getLogger(__name__)


class Agent:
    def __init__(self, llm: BaseChatModel):
        self.ears: Ears = None
        self.mouth: Mouth = None
        self.llm: BaseChatModel = llm

    def set_ears(self, ears: Ears):
        self.ears = ears
        ears.agent = self

    def set_mouth(self, mouth: Mouth):
        self.mouth = mouth
        mouth.agent = self

    def start(self):
        if self.ears:
            self.ears.listen()

    def prompt(self, prompt: str):
        logger.info("human: %s", prompt)
        resp = self.llm.invoke(prompt)
        logger.info("agent: %s", resp.content)


def setup():
    logger.info("creating agent...")

    model = ChatAnthropic(model_name="claude-3-7-sonnet-latest")
    blip_handler = BlipHandler()
    listener = BasicEars(model_name=RecognizerName.WHISPER_BASE_OFFLINE, handle_blip=blip_handler.handle)

    agent = Agent(model)
    agent.set_ears(listener)

    logger.info("Agent created!")
    return agent


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
    )

    load_dotenv()

    _agent = setup()
    _agent.start()
