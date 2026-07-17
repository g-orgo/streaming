from dataclasses import FrozenInstanceError

from live_caption_bridge.domain.models import AudioChunk, AudioSource, Transcript

def test_audio_sources_are_distinct() -> None:
    assert AudioSource.MICROPHONE != AudioSource.SYSTEM

def test_audio_chunk_preserves_source_and_is_immutable() -> None:
    chunk = AudioChunk(
        source=AudioSource.MICROPHONE,
        samples=b"audio",
        sample_rate=16_000,
        channels=1,
        started_ns=10,
        ended_ns=20,
    )
    assert chunk.source is AudioSource.MICROPHONE
    assert chunk.ended_ns > chunk.started_ns
    try:
        chunk.channels = 2 # type: ignore
    except FrozenInstanceError:
        pass
    else:
        raise AssertionError("AudioChunk deve ser imutável")
    
def test_transcript_holds_text_and_language() -> None:
    t = Transcript(
        source=AudioSource.SYSTEM,
        text="Hello world",
        language="en",
        started_ns=10,
        ended_ns=110,
    )
    assert t.text == "Hello world"
    assert t.language == "en"
    assert t.source is AudioSource.SYSTEM