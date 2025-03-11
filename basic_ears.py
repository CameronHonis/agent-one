from collections.abc import Callable
from enum import Enum
import logging
from multiprocessing import Process, Queue
import speech_recognition as sr

from models.blip import Blip
from models.blip_kind import BlipKind
from models.ears import Ears
from models.recognizer_name import RecognizerName

logger = logging.getLogger(__name__)


class BasicEars(Ears):
    def __init__(
        self,
        model_name: str = RecognizerName.WHISPER_MEDIUM_OFFLINE,
        handle_blip: Callable | None = None,
    ):
        super().__init__()
        self.model_name = model_name
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

        with sr.Microphone() as source:
            while True:
                self._listen_for_sentence(source)

    def _listen_for_sentence(self, source: sr.Microphone) -> str:
        logger.debug("listening for sentence")
        # TODO: allow for mic configuration, handle multi-mic setups
        self._recognizer.adjust_for_ambient_noise(source)
        audio = self._recognizer.listen(source)

        try:
            if self.model_name == RecognizerName.WHISPER_SMALL_OFFLINE:
                text = self._recognizer.recognize_whisper(audio, model="small.en")
            elif self.model_name == RecognizerName.WHISPER_BASE_OFFLINE:
                text = self._recognizer.recognize_whisper(audio, model="base.en")
            elif self.model_name == RecognizerName.WHISPER_MEDIUM_OFFLINE:
                text = self._recognizer.recognize_whisper(audio, model="medium.en")
            elif self.model_name == RecognizerName.WHISPER_LARGE_OFFLINE:
                text = self._recognizer.recognize_whisper(audio, model="large")
            elif self.model_name == RecognizerName.GOOGLE:
                text = self._recognizer.recognize_google(audio)
            else:
                raise TypeError(f"Unhandled model type {self.model_name}")

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
            self.handle_blip(blip, self.agent)
