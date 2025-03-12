import json
import logging
from multiprocessing import Manager, Process, Queue
from multiprocessing.shared_memory import SharedMemory
import time

from models.ears import Ears

from vosk import Model, KaldiRecognizer
import sounddevice as sd

PAUSE_THRESHOLD_SECS = 2  # amount of time to allow pass with no additional incoming words before sending prompt
AUDIO_SAMPLE_RATE = 16_000  # 16kHz works best with vosk

logger = logging.getLogger(__name__)


class VoskStreamedEars(Ears):
    def __init__(self, model_path: str):
        super().__init__()

        model = Model(model_path)
        self._recognizer = KaldiRecognizer(model, AUDIO_SAMPLE_RATE)

        self._shared = Manager().dict(
            dict(
                audio_q=Queue(),
                last_audio_time=None,
                prompt=[],
                prompter_process=None,
            )
        )

    def listen(self):
        Process(target=self._listen_for_speech).start()

    def _listen_for_speech(self):
        """
        Note: this blocks forever!
        """
        logger.debug("listening for words")

        with sd.RawInputStream(
            samplerate=AUDIO_SAMPLE_RATE,
            blocksize=AUDIO_SAMPLE_RATE // 2,
            device=None,
            dtype="int16",
            channels=1,
            callback=self._ingest_audio,
        ):
            while True:
                audio_data = self._shared["audio_q"].get()
                self._process_audio(audio_data)

    def _ingest_audio(self, audio_data, _, __, status):
        if status:
            raise ValueError(
                f"audio data with non-zero status error ({status}) inbound"
            )
        self._shared["_audio_q"].put(audio_data)

    def _process_audio(self, audio_data):
        self._last_audio_time = time.time()

        if self._recognizer.AcceptWaveform(audio_data):
            full = json.loads(self._recognizer.Result())["text"]
            logger.debug("heard: %s", full)

        else:
            partial = json.loads(self._recognizer.PartialResult())["partial"]
            logger.debug("heard partial: %s", partial)

    def _prompter_clock(self):
        while True:
            now = time.time()
            if now - self._last_audio_time >= 2 and len(self._shared["prompt"]):
                self._send_prompt()
                break
            last_audio_df_secs = now - self._shared["last_audio_time"]
            wait_secs = 2 - last_audio_df_secs
            time.sleep(wait_secs)

    def _send_prompt(self):
        pass


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.DEBUG,
    )
