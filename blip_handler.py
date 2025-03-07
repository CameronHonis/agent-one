# pylint: disable=missing-docstring
# pylint: disable=fixme
from enum import Enum
import logging
from collections import deque
from langchain_core.language_models.chat_models import BaseChatModel

from models.blip import Blip
from models.blip_kind import BlipKind

logger = logging.getLogger(__name__)


class BlipHandlerState(Enum):
    PASSIVE = "passive"
    ACTIVE = "active"


class BlipHandler:
    def __init__(self, model: BaseChatModel):
        self._model = model
        self._mem = deque()
        self._state = BlipHandlerState.PASSIVE

    def handle(self, blip: Blip):
        logger.debug("heard %s", str(blip))
        if blip.kind != BlipKind.WORD:
            logger.debug("not handling non verbals at the moment")

        self._mem.append(blip)
        if self._state == BlipHandlerState.PASSIVE:
            self._passive_handle()
        else:
            self._active_handle()

    def _match_last_words(self, *words) -> bool:
        words = list(words)
        words.reverse()
        if len(words) > len(self._mem):
            return False
        for i, word in enumerate(words):
            mem_i = -i - 1
            mem_blip: Blip = self._mem[mem_i]
            if mem_blip.kind != BlipKind.WORD or mem_blip.val != word:
                return False
        return True

    def _concat_mem(self) -> str:
        return " ".join([blip.val for blip in self._mem])

    def _passive_handle(self):
        if (
            len(self._mem) >= 2
            and self._mem[-2].val == "hey"
            and self._mem[-1] == "agent"
        ):
            logger.debug("actively listening")
            self._state = BlipHandlerState.ACTIVE
            self._mem.clear()

    def _active_handle(self):
        if len(self._mem) and self._mem[-1] == "go":
            prompt = self._concat_mem()
            self._model.invoke(prompt)
            self._mem.clear()
            # TODO: handle case when model responds with follow-up question
            self._state = BlipHandlerState.PASSIVE


def test_blip_handler_match_last_words():
    # pylint: disable=W0212
    bh = BlipHandler(None)
    bh._mem.append(Blip.word("first"))
    bh._mem.append(Blip.word("second"))
    bh._mem.append(Blip.word("third"))

    assert bh._match_last_words("first", "second", "third")

    assert bh._match_last_words("second", "third")

    assert bh._match_last_words("third")

    assert not bh._match_last_words("first")

    assert not bh._match_last_words("second")

    assert not bh._match_last_words("first", "third")

    assert not bh._match_last_words("zero", "first", "second", "third")
    # pylint: enable=all


if __name__ == "__main__":
    test_blip_handler_match_last_words()
    print("tests passed")