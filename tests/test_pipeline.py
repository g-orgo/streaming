from live_caption_bridge.domain.models import AudioChunk, AudioSource
from live_caption_bridge.ports.speech import SpeechSegment
from live_caption_bridge.services.pipeline import Pipeline
from tests.fakes import FakeCaptionSink


class FakeSTT:
    def transcribe(self, chunk: AudioChunk) -> SpeechSegment:
        return SpeechSegment(
            text="hello world",
            language="en",
            start_ns=chunk.started_ns,
            end_ns=chunk.ended_ns,
            confidence=0.9,
        )


def test_pipeline_delivers_caption_to_sink() -> None:
    sink = FakeCaptionSink()
    stt = FakeSTT()
    p = Pipeline(stt=stt, sink=sink)
    chunk = AudioChunk(
        source=AudioSource.MICROPHONE,
        samples=b"\x00\x00" * 16000,
        sample_rate=16000,
        channels=1,
        started_ns=0,
        ended_ns=1_000_000_000,
    )
    p.process(chunk)
    assert sink.last is not None
    assert sink.last.original == "hello world"


def test_pipeline_skips_empty_text() -> None:
    sink = FakeCaptionSink()
    stt = FakeSTT()
    stt.transcribe = lambda chunk: SpeechSegment(
        text="", language="en", start_ns=chunk.started_ns, end_ns=chunk.ended_ns
    )
    p = Pipeline(stt=stt, sink=sink) # type: ignore
    chunk = AudioChunk(
        source=AudioSource.MICROPHONE,
        samples=b"\x00\x00" * 16000,
        sample_rate=16000,
        channels=1,
        started_ns=0,
        ended_ns=1_000_000_000,
    )
    p.process(chunk)
    assert sink.last is None
