from dataclasses import dataclass
from enum import StrEnum

class AudioSource(StrEnum):
    MICROPHONE = "microphone"
    SYSTEM = "system"

@dataclass(frozen=True, slots=True)
class AudioChunk:
    source: AudioSource
    samples: bytes
    sample_rate: int
    channels: int
    started_ns: int
    ended_ns: int

@dataclass(frozen=True, slots=True)
class Transcript:
    source: AudioSource
    text: str
    language: str
    started_ns: int
    ended_ns: int
    confidence: float | None = None

@dataclass(frozen=True, slots=True)
class Caption:
    original: str
    translated: str
    source_lang: str
    target_lang: str
    started_ns: int
    ended_ns: int
