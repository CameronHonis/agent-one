from enum import Enum


class RecognizerName(Enum):
    WHISPER_BASE_OFFLINE = "whisper_base_offline"
    WHISPER_BASE_EN_OFFLINE = "whisper_base_en_offline"

    WHISPER_SMALL_OFFLINE = "whisper_small_offline"
    WHISPER_SMALL_EN_OFFLINE = "whisper_small_en_offline"

    WHISPER_MEDIUM_OFFLINE = "whisper_medium_offline"
    WHISPER_MEDIUM_EN_OFFLINE = "whisper_medium_en_offline"

    WHISPER_LARGE_OFFLINE = "whisper_large_offline"

    WHISPER_TURBO_OFFLINE = "whisper_turbo_offline"

    GOOGLE = "google"
