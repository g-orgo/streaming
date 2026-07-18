from typing import NamedTuple, Protocol

from live_caption_bridge.domain.models import AudioChunk

class SpeechSegment(NamedTuple):
    text: str
    language: str
    start_ns: int
    end_ns: int
    confidence: float | None = None

class SpeechPort(Protocol):
    def transcribe(self, chunks: list[AudioChunk]) -> list[SpeechSegment]:
        ...