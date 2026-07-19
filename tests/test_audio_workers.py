from live_caption_bridge.domain.models import AudioChunk, AudioSource
from live_caption_bridge.services.audio_workers import AudioWorker


def _make_chunk(source: AudioSource) -> AudioChunk:
    return AudioChunk(
        source=source,
        samples=b"\x00\x00" * 1600,
        sample_rate=16000,
        channels=1,
        started_ns=0,
        ended_ns=100_000_000,
    )


def test_worker_delivers_chunk_with_correct_source() -> None:
    worker = AudioWorker(
        source=AudioSource.SYSTEM,
        read_chunk=lambda: _make_chunk(AudioSource.SYSTEM),
    )
    worker.start()
    import time
    time.sleep(0.05)
    worker.stop()
    chunk = worker.read()
    assert chunk is not None
    assert chunk.source == AudioSource.SYSTEM


def test_two_workers_produce_separate_sources() -> None:
    mic = AudioWorker(
        source=AudioSource.MICROPHONE,
        read_chunk=lambda: _make_chunk(AudioSource.MICROPHONE),
    )
    sys = AudioWorker(
        source=AudioSource.SYSTEM,
        read_chunk=lambda: _make_chunk(AudioSource.SYSTEM),
    )
    mic.start()
    sys.start()
    import time
    time.sleep(0.05)
    mic.stop()
    sys.stop()
    mc = mic.read()
    sc = sys.read()
    assert mc is not None and mc.source == AudioSource.MICROPHONE
    assert sc is not None and sc.source == AudioSource.SYSTEM
