import struct

from live_caption_bridge.domain.models import AudioChunk, AudioSource
from live_caption_bridge.services.vad import rms_dbfs, segment_chunks


def _silence_chunk(start_ns: int = 0, dur_ns: int = 1_000_000_000) -> AudioChunk:
    return AudioChunk(
        source=AudioSource.MICROPHONE,
        samples=b"\x00\x00" * 16000,
        sample_rate=16000,
        channels=1,
        started_ns=start_ns,
        ended_ns=start_ns + dur_ns,
    )


def _speech_chunk(start_ns: int = 0, dur_ns: int = 1_000_000_000) -> AudioChunk:
    samples = b"".join(
        struct.pack("<h", 10000) for _ in range(16000)
    )
    return AudioChunk(
        source=AudioSource.MICROPHONE,
        samples=samples,
        sample_rate=16000,
        channels=1,
        started_ns=start_ns,
        ended_ns=start_ns + dur_ns,
    )


def test_rms_dbfs_silence_is_neg_inf() -> None:
    assert rms_dbfs(b"") == -float("inf")
    assert rms_dbfs(b"\x00\x00" * 100) == -float("inf")


def test_rms_dbfs_full_scale_is_zero() -> None:
    samples = struct.pack("<" + "h" * 100, *([32767] * 100))
    val = rms_dbfs(samples)
    assert abs(val) < 0.1


def test_segment_silence_yields_empty() -> None:
    chunks = [_silence_chunk(0), _silence_chunk(1_000_000_000)]
    assert segment_chunks(chunks) == []


def test_segment_speech_continuous() -> None:
    chunks = [_speech_chunk(0), _speech_chunk(1_000_000_000)]
    segs = segment_chunks(chunks, pre_roll_ns=0)
    assert len(segs) == 1
    assert segs[0][0] == 0
    assert segs[0][1] == 2_000_000_000


def test_segment_speech_with_pause_is_two_segments() -> None:
    c1 = _speech_chunk(0)
    c2 = _silence_chunk(1_000_000_000, dur_ns=2_000_000_000)
    c3 = _speech_chunk(3_000_000_000)
    segs = segment_chunks([c1, c2, c3], pre_roll_ns=0, min_silence_ns=1_500_000_000)
    assert len(segs) == 2


def test_segment_noise_stays_below_threshold() -> None:
    low = struct.pack("<h", 1)
    chunk = AudioChunk(
        source=AudioSource.MICROPHONE,
        samples=low * 16000,
        sample_rate=16000,
        channels=1,
        started_ns=0,
        ended_ns=1_000_000_000,
    )
    assert segment_chunks([chunk], threshold_dbfs=-20.0) == []


def test_segment_max_duration_truncates() -> None:
    long = _speech_chunk(0, dur_ns=60_000_000_000)
    segs = segment_chunks([long], pre_roll_ns=0, max_duration_ns=30_000_000_000)
    assert len(segs) == 1
    assert segs[0][1] - segs[0][0] <= 30_000_000_000


def test_segment_pre_roll_shifts_start() -> None:
    c = _speech_chunk(5_000_000_000)
    segs = segment_chunks([c], pre_roll_ns=2_000_000_000)
    assert len(segs) == 1
    assert segs[0][0] == 3_000_000_000