import json
import logging
import multiprocessing as mp
import time
from typing import override

from models.ears import Ears

from vosk import Model, KaldiRecognizer

PAUSE_THRESHOLD_SECS = 2  # amount of time to allow pass with no additional incoming words before sending prompt
AUDIO_SAMPLE_RATE = 16_000  # 16kHz works best with vosk

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


class VoskStreamedEars(Ears):
    def __init__(self, model_path: str):
        super().__init__()
        self.model_path = model_path

        self._manager = mp.Manager()
        self._shared_audio_q = self._manager.Queue()
        self._shared_last_audio_time = self._manager.Value("d", None)
        self._shared_prompts = self._manager.list()
        self._shared_timer_active = self._manager.Value("b", False)
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
        with self._lock:
            if recognizer.AcceptWaveform(audio_bytes):
                full = recognizer.get_full()
                logger.debug("heard: %s", full)

                if not self._shared_timer_active.value:
                    self._shared_timer_active.value = True
                    proc = mp.Process(target=self._prompter_clock)
                    proc.start()
                self._shared_last_audio_time.value = time.time()
            else:
                partial = recognizer.get_partial()
                if partial:
                    logger.debug("heard partial: %s", partial)
                    self._shared_last_audio_time.value = time.time()

    def _prompter_clock(self):
        while True:
            logger.debug("running prompt clock")
            with self._lock:
                now = time.time()
                dt_secs = now - self._shared_last_audio_time.value
                logger.debug("seconds since last word spoken: %s", dt_secs)
                if dt_secs >= PAUSE_THRESHOLD_SECS and len(self._shared_prompts):
                    self._send_prompt()
                    self._shared_timer_active.value = False
                    return
            wait_secs = PAUSE_THRESHOLD_SECS - dt_secs
            time.sleep(wait_secs)

    def _send_prompt(self):
        """
        assumes that audio_q has been fully processed.
        it should, unless transcription of a single block took longer than the required
        pause before sending prompt.
        if not, though, this function will raise a ValueError.
        """
        with self._lock:
            if len(self._shared_audio_q):
                raise ValueError(
                    "tried sending prompt when audio queue is still populated"
                )
            prompt = " ".join(self._shared_prompts)
            logger.debug("built prompt: %s", prompt)
            if self.agent:
                self.agent.prompt(prompt)
            else:
                logger.warning("no agent connected, failed to send prompt")

            self._shared_prompts.clear()
            self._shared_audio_q.empty()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.DEBUG,
    )
    ears = VoskStreamedEars("/home/camer/Downloads/vosk-model-en-us-0.22")
    ears.listen().join()
