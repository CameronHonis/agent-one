from enum import Enum
import json
import logging
import math
import multiprocessing as mp
import time
from typing import override

from models.ears import Ears

from vosk import Model, KaldiRecognizer

PAUSE_THRESHOLD_SECS = 2  # amount of time to allow pass with no additional incoming words before sending prompt
AUDIO_SAMPLE_RATE = 16_000  # 16kHz works best with vosk
TRIGGER = "hey agent"

logger = logging.getLogger(__name__)


class Recognizer(KaldiRecognizer):
    def get_partial(self) -> str:
        """
        wrapper for the `PartialResult` method on `KaldiRecognizer`
        extracts important information and filters out unwanted results
        """
        partial = json.loads(self.PartialResult())["partial"]
        return self.filter_results(partial)

    def get_full(self) -> str:
        """
        wrapper for the `Result` method on `KaldiRecognizer`
        extracts important information and filters out unwanted results
        """
        full = json.loads(self.Result())["text"]
        return self.filter_results(full)

    @staticmethod
    def filter_results(result: str) -> str:
        result = result.strip().lower()
        if result == "the":
            return ""
        return result


class ListeningMode(Enum):
    PASSIVE = "passive"
    ACTIVE = "active"


class VoskStreamedEars(Ears):
    def __init__(self, model_path: str):
        super().__init__()
        self.model_path = model_path

        self._manager = mp.Manager()
        self._shared_audio_q = self._manager.Queue()
        self._shared_last_audio_time = self._manager.Value("d", None)
        self._shared_words = self._manager.list()
        self._shared_timer_active = self._manager.Value("b", False)
        self._shared_listening_mode = self._manager.Value("s", ListeningMode.PASSIVE)
        self._lock = self._manager.Lock()

    def listen(self) -> mp.Process:
        model = Model(self.model_path)
        recognizer = Recognizer(model, AUDIO_SAMPLE_RATE)

        proc = mp.Process(target=self._listen_for_speech, args=(recognizer,))
        proc.start()
        return proc

    def _listen_for_speech(self, recognizer: Recognizer):
        """
        Note: this blocks forever!
        """
        blocksize = AUDIO_SAMPLE_RATE // 2
        logger.debug(
            "listening for words: rate=%s, blocksize=%s", AUDIO_SAMPLE_RATE, blocksize
        )
        logger.info("say '%s' to get the agent's attention", TRIGGER)
        import sounddevice as sd

        with sd.RawInputStream(
            samplerate=AUDIO_SAMPLE_RATE,
            blocksize=blocksize,
            device=None,
            dtype="int16",
            channels=1,
            callback=self._ingest_audio,
        ):
            while True:
                audio_bytes = self._shared_audio_q.get()
                self._process_audio(audio_bytes, recognizer)

    def _ingest_audio(self, audio_data, _, __, status):
        if status:
            raise ValueError(
                f"audio data with non-zero status error ({status}) inbound"
            )
        self._shared_audio_q.put(bytes(audio_data))

    def _process_audio(self, audio_bytes: bytes, recognizer: Recognizer):
        is_final = recognizer.AcceptWaveform(audio_bytes)
        if is_final:
            full = recognizer.get_full()
            self._handle_words(full)
        else:
            partial = recognizer.get_partial()
            if partial:
                self._handle_partial(partial)

    def _try_start_prompter_clock(self):
        with self._lock:
            if self._shared_timer_active.value:
                return
            self._shared_timer_active.value = True
        logger.debug("starting clock")
        mp.Process(target=self._prompter_clock).start()

    def _prompter_clock(self):
        while True:
            logger.debug("running prompt clock")
            to_send_prompt = False
            with self._lock:
                now = time.time()
                dt_secs = now - self._shared_last_audio_time.value
                logger.debug("seconds since last word spoken: %s", dt_secs)
                if dt_secs >= PAUSE_THRESHOLD_SECS and len(self._shared_words):
                    to_send_prompt = True

            if to_send_prompt:
                prompt_sent = self._init_prompt()

                if prompt_sent:
                    logger.debug("prompt sent, killing clock")
                    with self._lock:
                        self._shared_timer_active.value = False
                        return
                else:
                    logger.debug("prompt couldn't be sent, keeping clock alive")

            wait_secs = max(PAUSE_THRESHOLD_SECS - dt_secs, 1)
            time.sleep(wait_secs)

    def _handle_partial(self, words: str):
        """
        handles words that have not yet been finalized by the transcriber
        """
        logger.info("partial: %s", words)
        with self._lock:
            self._shared_last_audio_time.value = time.time()
            is_passive = self._shared_listening_mode.value == ListeningMode.PASSIVE
            if is_passive and TRIGGER in words:
                self._shared_listening_mode.value = ListeningMode.ACTIVE
                logger.info("actively listening...")

    def _handle_words(self, words: str):
        """
        handles words that have been finalized by the transcriber
        """
        logger.info("heard: %s", words)

        with self._lock:
            self._shared_words.append(words)
            self._shared_last_audio_time.value = time.time()
            is_active = self._shared_listening_mode.value == ListeningMode.ACTIVE
            if (not is_active) and TRIGGER in words:
                self._shared_listening_mode.value = ListeningMode.ACTIVE
                logger.info("actively listening...")
                is_active = True
        if is_active:
            self._try_start_prompter_clock()

    def _build_prompt(self) -> str:
        """
        iterates through recorded words in reverse order until full prompt is built, excludes trigger words
        """
        with self._lock:
            words = " ".join(self._shared_words)
        trigger_match_idx = words.rfind(TRIGGER)
        if trigger_match_idx == -1:
            raise ValueError("Trigger was never spoken, cannot built prompt")
        return words[trigger_match_idx + len(TRIGGER) :]

    def _init_prompt(self) -> bool:
        """
        assumes that audio_q has been fully processed.
        it should, unless transcription of a single block took longer than the required
        pause before sending prompt.
        if not, though, this function will raise a ValueError.

        returns True if prompt could be built, otherwise returns False
        """
        try:
            prompt = self._build_prompt()
        except Exception:
            pass
        if not prompt:
            return False

        logger.debug("built prompt: %s", prompt)
        with self._lock:
            if not self._shared_audio_q.empty():
                raise ValueError(
                    "tried sending prompt when audio queue is still populated"
                )

            if self.agent:
                self.agent.prompt(prompt)
            else:
                logger.warning("no agent connected, failed to send prompt")

            self._shared_words[:] = []
            self._shared_listening_mode.value = ListeningMode.PASSIVE
            logger.info("passively listening...")
            return True


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.DEBUG,
    )
    ears = VoskStreamedEars("/home/camer/Downloads/vosk-model-en-us-0.22")
    ears.listen().join()
