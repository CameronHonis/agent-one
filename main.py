import logging
import multiprocessing as mp

from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic
from langchain_core.language_models.chat_models import BaseChatModel

from models.ears import Ears
from models.mouth import Mouth
from vosk_streamed_ears import VoskStreamedEars

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
        procs: list[mp.Process] = []
        if self.ears:
            procs.append(self.ears.listen())
        
        for proc in procs:
            proc.join()

    def prompt(self, prompt: str):
        logger.info("human: %s", prompt)
        resp = self.llm.invoke(prompt)
        logger.info("agent: %s", resp.content)


def setup():
    logger.info("creating agent...")

    model = ChatAnthropic(model_name="claude-3-7-sonnet-latest")
    listener = VoskStreamedEars("models/vosk-model-en-us-0.22")

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
