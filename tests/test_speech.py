from live_caption_bridge.domain.models import AudioChunk, AudioSource
from live_caption_bridge.ports.speech import SpeechPort, SpeechSegment


class FakeSTT:
    def __init__(self, text: str = "hello world", lang: str = "en") -> None:
        self._text = text
        self._lang = lang
        self.called_with: list[AudioChunk] = []

    def transcribe(self, chunk: AudioChunk) -> SpeechSegment:
        self.called_with.append(chunk)
        return SpeechSegment(
            text=self._text,
            language=self._lang,
            start_ns=chunk.started_ns,
            end_ns=chunk.ended_ns,
            confidence=0.9,
        )


def test_fake_stt_returns_fixed_text() -> None:
    stt: SpeechPort = FakeSTT(text="hello", lang="en") # type: ignore
    chunk = AudioChunk(
        source=AudioSource.MICROPHONE,
        samples=b"\x00\x00" * 16000,
        sample_rate=16000,
        channels=1,
        started_ns=0,
        ended_ns=1_000_000_000,
    )
    result = stt.transcribe(chunk) # type: ignore
    assert result.text == "hello" # type: ignore
    assert result.language == "en" # type: ignore
    assert result.confidence == 0.9 # type: ignore
    assert len(stt.called_with) == 1 # type: ignore


def test_fake_stt_preserves_timestamps() -> None:
    stt: SpeechPort = FakeSTT() # type: ignore
    chunk = AudioChunk(
        source=AudioSource.SYSTEM,
        samples=b"\x00\x00" * 16000,
        sample_rate=16000,
        channels=1,
        started_ns=500,
        ended_ns=1_500_000_000,
    )
    result = stt.transcribe(chunk) # type: ignore
    assert result.start_ns == 500 # type: ignore
    assert result.end_ns == 1_500_000_000 # type: ignore


def test_speech_segment_named_tuple() -> None:
    s = SpeechSegment(text="hi", language="en", start_ns=0, end_ns=1_000_000_000)
    assert s.text == "hi"
    assert s.confidence is None


def test_speech_segment_with_confidence() -> None:
    s = SpeechSegment(text="hi", language="en", start_ns=0, end_ns=1_000_000_000, confidence=0.95)
    assert s.confidence == 0.95
    assert s.start_ns == 0
    assert s.end_ns == 1_000_000_000