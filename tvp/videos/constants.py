from enum import Enum, StrEnum


class VideoProcessingState(StrEnum):
    NOT_STARTED = "NOT_STARTED"

    # Phase 2
    TRANSCODING = "TRANSCODING"
    TRANSCODING_FAILED = "TRANSCODING_FAILED"

    # Phase 3
    MUXING = "MUXING"
    MUXING_FAILED = "MUXING_FAILED"

    # Final stage
    READY = "READY"


class VideoVariantCode(Enum):
    V_2160 = 2160
    V_1440 = 1440
    V_1080 = 1080
    V_720 = 720
    V_480 = 480
    V_360 = 360
    V_240 = 240
    V_144 = 144


## Magic Numbers

# We don't support 2k and 4k for now.
# TODO: make this configurable
HIGHEST_RESOLUTION_SUPPORTED = VideoVariantCode.V_1080
LOWEST_RESOLUTION_SUPPORTED = VideoVariantCode.V_480

# 2 second long segment is the industry standard.
# Youtube uses 4 for better buffering, but we use 2 as
# the base line.
SEGMENT_LENGTH_SECONDS = 2

# For now we don't transcode to higher FPS.
MAX_ALLOWED_FPS = 30

# This dictionary is used to determine suitable video bitrate for given resolution.
VIDEO_BITRATES: dict[VideoVariantCode, int] = {
    VideoVariantCode.V_2160: 45000000,  # 45 Mbps (4K)
    VideoVariantCode.V_1440: 16000000,  # 16 Mbps (2K)
    VideoVariantCode.V_1080: 8000000,  # 8 Mbps
    VideoVariantCode.V_720: 5000000,  # 5 Mbps
    VideoVariantCode.V_480: 2500000,  # 2.5 Mbps
    VideoVariantCode.V_360: 1000000,  # 1 Mbps
    VideoVariantCode.V_240: 500000,  # 0.5 Mbps
    VideoVariantCode.V_144: 200000,  # 0.2 Mbps
}

# This dictionary is used to determine suitable audio bitrate for given resolution.
AUDIO_BITRATES: dict[VideoVariantCode, int] = {
    VideoVariantCode.V_2160: 192000,  # 192 kbps (AAC)
    VideoVariantCode.V_1440: 192000,
    VideoVariantCode.V_1080: 128000,  # 128 kbps
    VideoVariantCode.V_720: 128000,
    VideoVariantCode.V_480: 96000,  # 96 kbps
    VideoVariantCode.V_360: 96000,
    VideoVariantCode.V_240: 64000,  # 64 kbps
    VideoVariantCode.V_144: 64000,
}
