from dataclasses import dataclass
from enum import StrEnum

class AudioSource(StrEnum):
    """Enum representing different audio sources."""

    MICROPHONE = "microphone"
    SYSTEM = "system"

@dataclass(frozen=True, slots=True)
class AudioChunk:
    """Represents a chunk of audio data."""
    source: AudioSource
    samples: bytes
    sample_rate: int
    channels: int
    started_ns: int
    ended_ns: int

@dataclass(frozen=True, slots=True)
    class Transcript:
        """Represents a transcript of audio data."""
        source: AudioSource
        text: str
        language: str
        started_ns: int
        ended_ns: int
        confidence: float | None = None