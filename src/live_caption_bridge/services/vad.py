import math
import struct
from collections.abc import Sequence
from live_caption_bridge.domain.models import AudioChunk

def _rms_dbfs(samples: bytes, channels: int) -> float:
    if not samples:
        return -float("inf")
    fmt = "<" + "h" * (len(samples) // 2)
    try:
        values = struct.unpack(fmt, samples)
    except struct.error:
        return -float("inf")
    if not values:
        return -float("inf")
    sq_sum = sum(v * v for v in values)
    rms = math.sqrt(sq_sum / len(values)) / 32767.0
    if rms <= 0:
        return -float("inf")
    return 20.0 * math.log10(rms)

def rms_dbfs(samples: bytes, channels: int = 1) -> float:
    return _rms_dbfs(samples, channels)

Segment = tuple[int, int]

def segment_chunks(
    chunks: Sequence[AudioChunk],
    threshold_dbfs: float = -30.0,
    pre_roll_ns: int = 500_000_000,
    max_duration_ns: int = 30_000_000_000,
    min_silence_ns: int = 800_000_000,
) -> list[Segment]:
    if not chunks:
        return []
    segments: list[Segment] = []
    in_speech = False
    seg_start: int | None = None
    last_speech_end: int | None = None
    speech_timestamps: list[int] = []

    for chunk in chunks:
        energy = _rms_dbfs(chunk.samples, chunk.channels)
        is_speech = energy >= threshold_dbfs
        now = chunk.started_ns

        if is_speech:
            if not in_speech:
                speech_timestamps = [now]
                in_speech = True
                seg_start = now
            else:
                speech_timestamps.append(now)
            last_speech_end = chunk.ended_ns
        else:
            if in_speech:
                silence_duration = chunk.ended_ns - last_speech_end # type: ignore
                if silence_duration >= min_silence_ns:
                    dur = last_speech_end - seg_start # type: ignore
                    if dur > max_duration_ns:
                        last_speech_end = seg_start + max_duration_ns # type: ignore
                    segments.append(
                        (max(0, seg_start - pre_roll_ns), last_speech_end) # type: ignore
                    )
                    in_speech = False
                    seg_start = None

    if in_speech and seg_start is not None:
        end = last_speech_end if last_speech_end else seg_start
        if end - seg_start > max_duration_ns:
            end = seg_start + max_duration_ns
        segments.append((max(0, seg_start - pre_roll_ns), end))

    return segments
