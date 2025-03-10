from enum import Enum
import logging
from collections import deque
import typing

from models.blip import Blip
from models.blip_kind import BlipKind

if typing.TYPE_CHECKING:
    from main import Agent

logger = logging.getLogger(__name__)


class BlipHandlerState(Enum):
    PASSIVE = "passive"
    ACTIVE = "active"


class BlipHandler:
    def __init__(self):
        self._mem = deque()
        self._state = BlipHandlerState.PASSIVE

    def handle(self, blip: Blip, agent: "Agent"):
        if not blip:
            return
        blip = BlipHandler._filter_blip(blip)
        logger.debug("heard %s", str(blip))

        if blip.kind != BlipKind.WORD:
            logger.debug("not handling non verbals at the moment")

        self._mem.append(blip)
        logger.info("mem cache: %s", self._concat_mem())

        if self._state == BlipHandlerState.PASSIVE:
            self._passive_handle()
        else:
            self._active_handle(agent)

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
        if self._match_last_words("hey", "agent"):
            self._state = BlipHandlerState.ACTIVE
            logger.info("actively listening")
            self._mem.clear()

    def _active_handle(self, agent: "Agent"):
        if self._match_last_words("go"):
            prompt = self._concat_mem()
            agent.prompt(prompt)
            self._mem.clear()
            # TODO: handle case when model responds with follow-up question
            self._state = BlipHandlerState.PASSIVE
            logger.info("passively listening")

    @staticmethod
    def _filter_blip(blip: Blip) -> Blip:
        if blip.kind == BlipKind.WORD:
            builder = []
            for char in blip.val:
                if char.isalnum():
                    builder.append(char.lower())
            return Blip.word("".join(builder))
        return blip


def _test_blip_handler_filter_blips():
    # pylint: disable=W0212
    assert BlipHandler._filter_blip(Blip.word("Hello")).val == "hello"
    assert BlipHandler._filter_blip(Blip.word("Hello!")).val == "hello"
    assert BlipHandler._filter_blip(Blip.word("asdf 123")).val == "asdf123"
    # pylint: enable=all


def _test_blip_handler_match_last_words():
    # pylint: disable=W0212
    bh = BlipHandler()
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
    _test_blip_handler_filter_blips()
    _test_blip_handler_match_last_words()
    print("tests passed")
