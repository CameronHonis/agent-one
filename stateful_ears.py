from enum import Enum
import logging
from multiprocessing import Process, Queue
import speech_recognition as sr

from modded_deps.modded_recognizer import ModdedRecognizer
from models.ears import Ears
from models.recognizer_name import RecognizerName

logger = logging.getLogger(__name__)


class SpokenKind(Enum):
    NONE = "none"
    COMPLETE = "complete"
    INCOMPLETE = "incomplete"

    @staticmethod
    def kind_from_transcription(tr: str) -> "SpokenKind":
        if len(tr.strip()) == 0:
            return SpokenKind.NONE
        if tr.endswith("..."):
            return SpokenKind.INCOMPLETE
        is_complete = tr.endswith(".") or tr.endswith("!") or tr.endswith("?")
        return SpokenKind.COMPLETE if is_complete else SpokenKind.INCOMPLETE


class StatefulEars(Ears):
    def __init__(
        self,
        model_name: str = RecognizerName.WHISPER_BASE_EN_OFFLINE,
        pause_after_incomplete_threshold_secs=1.5,
        pause_after_complete_threshold_secs=3,
    ):
        super().__init__()
        self.model_name = model_name
        self.pause_after_incomplete_threshold_secs = (
            pause_after_incomplete_threshold_secs
        )
        self.pause_after_complete_threshold_secs = pause_after_complete_threshold_secs

        self._recognizer = ModdedRecognizer()
        self._prompt = ""
        self._is_actively_listening = False
        self._is_talking = False
        self._delay_id = 0
        self._last_speak_time = None
        self._last_audio_processed = None
        self._audio_data_queue = Queue()
        self._last_spoken_kind = SpokenKind.NONE

    def listen(self):
        Process(target=self._listen_for_speech).start()

    def _listen_for_speech(self):
        """
        Note: this blocks forever
        """
        logger.debug("listening for words")

        with sr.Microphone() as source:
            while True:
                phrase = self._listen_for_phrase(source)

    def _listen_for_phrase(self, source: sr.Microphone) -> str:
        logger.debug("listening for sentence")
        # TODO: allow for mic configuration, handle multi-mic setups
        self._recognizer.adjust_for_ambient_noise(source)
        audio = self._recognizer.listen_with_dispatch(
            source, on_phrase_start=self._on_phrase_start
        )

        if self.model_name == RecognizerName.WHISPER_BASE_OFFLINE:
            text = self._recognizer.recognize_whisper(audio, model="base")
        elif self.model_name == RecognizerName.WHISPER_BASE_EN_OFFLINE:
            text = self._recognizer.recognize_whisper(audio, model="base.en")
        elif self.model_name == RecognizerName.WHISPER_SMALL_OFFLINE:
            text = self._recognizer.recognize_whisper(audio, model="small")
        elif self.model_name == RecognizerName.WHISPER_SMALL_EN_OFFLINE:
            text = self._recognizer.recognize_whisper(audio, model="small.en")
        elif self.model_name == RecognizerName.WHISPER_MEDIUM_OFFLINE:
            text = self._recognizer.recognize_whisper(audio, model="medium")
        elif self.model_name == RecognizerName.WHISPER_MEDIUM_EN_OFFLINE:
            text = self._recognizer.recognize_whisper(audio, model="medium.en")
        elif self.model_name == RecognizerName.WHISPER_LARGE_OFFLINE:
            text = self._recognizer.recognize_whisper(audio, model="large")
        elif self.model_name == RecognizerName.WHISPER_TURBO_OFFLINE:
            text = self._recognizer.recognize_whisper(audio, model="turbo")
        elif self.model_name == RecognizerName.GOOGLE:
            text = self._recognizer.recognize_google(audio)
        else:
            raise TypeError(f"Unhandled model type {self.model_name}")

        logger.debug("heard: %s", text)
        return text

    def _on_phrase_start(self):
        logger.debug("voice started")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.DEBUG,
    )

    ears = StatefulEars(model_name=RecognizerName.WHISPER_BASE_EN_OFFLINE)
    ears.listen()
