import collections
import math
import os
import audioop
from typing import override
from speech_recognition import Recognizer, AudioSource, WaitTimeoutError, AudioData


class ModdedRecognizer(Recognizer):
    def listen_with_dispatch(
        self,
        source,
        timeout=None,
        on_phrase_start=None,
        phrase_time_limit=None,
        snowboy_configuration=None,
        stream=False,
    ):
        """
        Records a single phrase from ``source`` (an ``AudioSource`` instance) into an ``AudioData`` instance, which it returns.

        If the ``stream`` keyword argument is ``True``, the ``listen()`` method will yield ``AudioData`` instances representing chunks of audio data as they are detected. The first yielded ``AudioData`` instance represents the first buffer of the phrase, and the last yielded ``AudioData`` instance represents the last buffer of the phrase. If ``stream`` is ``False``, the method will return a single ``AudioData`` instance representing the entire phrase.

        This is done by waiting until the audio has an energy above ``recognizer_instance.energy_threshold`` (the user has started speaking), and then recording until it encounters ``recognizer_instance.pause_threshold`` seconds of non-speaking or there is no more audio input. The ending silence is not included.

        The ``timeout`` parameter is the maximum number of seconds that this will wait for a phrase to start before giving up and throwing an ``speech_recognition.WaitTimeoutError`` exception. If ``timeout`` is ``None``, there will be no wait timeout.

        The ``on_phrase_start`` parameter is the callback that gets dispatched once the phrase is started.

        The ``phrase_time_limit`` parameter is the maximum number of seconds that this will allow a phrase to continue before stopping and returning the part of the phrase processed before the time limit was reached. The resulting audio will be the phrase cut off at the time limit. If ``phrase_timeout`` is ``None``, there will be no phrase time limit.

        The ``snowboy_configuration`` parameter allows integration with `Snowboy <https://snowboy.kitt.ai/>`__, an offline, high-accuracy, power-efficient hotword recognition engine. When used, this function will pause until Snowboy detects a hotword, after which it will unpause. This parameter should either be ``None`` to turn off Snowboy support, or a tuple of the form ``(SNOWBOY_LOCATION, LIST_OF_HOT_WORD_FILES)``, where ``SNOWBOY_LOCATION`` is the path to the Snowboy root directory, and ``LIST_OF_HOT_WORD_FILES`` is a list of paths to Snowboy hotword configuration files (`*.pmdl` or `*.umdl` format).

        This operation will always complete within ``timeout + phrase_timeout`` seconds if both are numbers, either by returning the audio data, or by raising a ``speech_recognition.WaitTimeoutError`` exception.
        """
        result = self._listen_with_dispatch(
            source,
            timeout,
            on_phrase_start,
            phrase_time_limit,
            snowboy_configuration,
            stream,
        )
        if not stream:
            for a in result:
                return a
        return result

    def _listen_with_dispatch(
        self,
        source,
        timeout=None,
        on_phrase_start=None,
        phrase_time_limit=None,
        snowboy_configuration=None,
        stream=False,
    ):
        assert isinstance(source, AudioSource), "Source must be an audio source"
        assert (
            source.stream is not None
        ), "Audio source must be entered before listening, see documentation for ``AudioSource``; are you using ``source`` outside of a ``with`` statement?"
        assert self.pause_threshold >= self.non_speaking_duration >= 0
        if snowboy_configuration is not None:
            assert os.path.isfile(
                os.path.join(snowboy_configuration[0], "snowboydetect.py")
            ), "``snowboy_configuration[0]`` must be a Snowboy root directory containing ``snowboydetect.py``"
            for hot_word_file in snowboy_configuration[1]:
                assert os.path.isfile(
                    hot_word_file
                ), "``snowboy_configuration[1]`` must be a list of Snowboy hot word configuration files"

        seconds_per_buffer = float(source.CHUNK) / source.SAMPLE_RATE
        pause_buffer_count = int(
            math.ceil(self.pause_threshold / seconds_per_buffer)
        )  # number of buffers of non-speaking audio during a phrase, before the phrase should be considered complete
        phrase_buffer_count = int(
            math.ceil(self.phrase_threshold / seconds_per_buffer)
        )  # minimum number of buffers of speaking audio before we consider the speaking audio a phrase
        non_speaking_buffer_count = int(
            math.ceil(self.non_speaking_duration / seconds_per_buffer)
        )  # maximum number of buffers of non-speaking audio to retain before and after a phrase

        # read audio input for phrases until there is a phrase that is long enough
        elapsed_time = 0  # number of seconds of audio read
        buffer = b""  # an empty buffer means that the stream has ended and there is no data left to read
        while True:
            frames = collections.deque()

            if snowboy_configuration is None:
                # store audio input until the phrase starts
                while True:
                    # handle waiting too long for phrase by raising an exception
                    elapsed_time += seconds_per_buffer
                    if timeout and elapsed_time > timeout:
                        raise WaitTimeoutError(
                            "listening timed out while waiting for phrase to start"
                        )

                    buffer = source.stream.read(source.CHUNK)
                    if len(buffer) == 0:
                        break  # reached end of the stream
                    frames.append(buffer)
                    if (
                        len(frames) > non_speaking_buffer_count
                    ):  # ensure we only keep the needed amount of non-speaking buffers
                        frames.popleft()

                    # detect whether speaking has started on audio input
                    energy = audioop.rms(
                        buffer, source.SAMPLE_WIDTH
                    )  # energy of the audio signal
                    if energy > self.energy_threshold:
                        break

                    # dynamically adjust the energy threshold using asymmetric weighted average
                    if self.dynamic_energy_threshold:
                        damping = (
                            self.dynamic_energy_adjustment_damping**seconds_per_buffer
                        )  # account for different chunk sizes and rates
                        target_energy = energy * self.dynamic_energy_ratio
                        self.energy_threshold = (
                            self.energy_threshold * damping
                            + target_energy * (1 - damping)
                        )
            else:
                # read audio input until the hotword is said
                snowboy_location, snowboy_hot_word_files = snowboy_configuration
                buffer, delta_time = self.snowboy_wait_for_hot_word(
                    snowboy_location, snowboy_hot_word_files, source, timeout
                )
                elapsed_time += delta_time
                if len(buffer) == 0:
                    break  # reached end of the stream
                frames.append(buffer)

            if on_phrase_start:
                on_phrase_start()

            # read audio input until the phrase ends
            pause_count, phrase_count = 0, 0
            phrase_start_time = elapsed_time

            if stream:
                # yield the first buffer of the phrase
                yield AudioData(
                    b"".join(frames), source.SAMPLE_RATE, source.SAMPLE_WIDTH
                )
                frames.clear()

            while True:
                # handle phrase being too long by cutting off the audio
                elapsed_time += seconds_per_buffer
                if (
                    phrase_time_limit
                    and elapsed_time - phrase_start_time > phrase_time_limit
                ):
                    break

                buffer = source.stream.read(source.CHUNK)
                if len(buffer) == 0:
                    break  # reached end of the stream
                frames.append(buffer)
                phrase_count += 1

                # check if speaking has stopped for longer than the pause threshold on the audio input
                energy = audioop.rms(
                    buffer, source.SAMPLE_WIDTH
                )  # unit energy of the audio signal within the buffer
                if energy > self.energy_threshold:
                    pause_count = 0
                else:
                    pause_count += 1
                if pause_count > pause_buffer_count:  # end of the phrase
                    break

                # dynamically adjust the energy threshold using asymmetric weighted average
                if self.dynamic_energy_threshold:
                    damping = (
                        self.dynamic_energy_adjustment_damping**seconds_per_buffer
                    )  # account for different chunk sizes and rates
                    target_energy = energy * self.dynamic_energy_ratio
                    self.energy_threshold = (
                        self.energy_threshold * damping + target_energy * (1 - damping)
                    )

                if stream:
                    # yield the current chunk of audio data wrapped in AudioData
                    yield AudioData(buffer, source.SAMPLE_RATE, source.SAMPLE_WIDTH)

            # check how long the detected phrase is, and retry listening if the phrase is too short
            phrase_count -= (
                pause_count  # exclude the buffers for the pause before the phrase
            )
            if phrase_count >= phrase_buffer_count or len(buffer) == 0:
                break  # phrase is long enough or we've reached the end of the stream, so stop listening

        if stream:
            # yield the last buffer of the phrase.
            yield AudioData(buffer, source.SAMPLE_RATE, source.SAMPLE_WIDTH)
        else:
            # obtain frame data
            for i in range(pause_count - non_speaking_buffer_count):
                frames.pop()  # remove extra non-speaking frames at the end

            frame_data = b"".join(frames)
            # yield the entire phrase as a single AudioData instance
            yield AudioData(frame_data, source.SAMPLE_RATE, source.SAMPLE_WIDTH)
