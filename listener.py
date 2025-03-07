from collections.abc import Callable
import logging
from multiprocessing import Process, Queue
import speech_recognition as sr

from models.blip import Blip
from models.blip_kind import BlipKind

logger = logging.getLogger(__name__)


class Listener:
    def __init__(self, handle_blip: Callable | None = None):
        self._recognizer = sr.Recognizer()
        self._queue = Queue()

        self.handle_blip = handle_blip

    def listen(self):
        Process(target=self._listen_for_speech).start()
        Process(target=self._process_blips).start()

    def _listen_for_speech(self):
        """
        Note: this blocks forever
        """
        logger.debug("listening for words")
        while True:
            self._listen_for_sentence()

    def _listen_for_sentence(self) -> str:
        logger.debug("listening for sentence")
        #  TODO: allow for mic configuration, handle multi-mic setups
        with sr.Microphone() as source:
            self._recognizer.adjust_for_ambient_noise(source)
            audio = self._recognizer.listen(source)

            try:
                text = self._recognizer.recognize_whisper(
                    audio, model="base"
                )  # Works offline!
                for word in text.split(" "):
                    self._queue.put(Blip(kind=BlipKind.WORD, val=word))
                    logger.debug("put word '%s' in queue to be processed", word)
            except sr.UnknownValueError:
                logger.error("Sorry, I couldn't understand that.")
            except sr.RequestError:
                logger.error("Speech service unavailable")

    # TODO: add brakes?
    def _process_blips(self) -> str:
        """
        Note: This blocks forever
        """
        while True:
            blip = self._queue.get()
            if not isinstance(blip, Blip):
                raise TypeError(f"unexpected type {type(blip)}")
            logger.debug("processing blip [%s]", str(blip))
            self.handle_blip(blip)
