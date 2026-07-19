from typing import Protocol
from live_caption_bridge.domain.models import AudioChunk
from enum import StrEnum

class DeviceKind(StrEnum):
    MICROPHONE = "microphone"
    SPEAKER = "speaker"

class AudioDeviceInfo:
    def __init__(self, name: str, id: int, kind: DeviceKind = DeviceKind.MICROPHONE) -> None:
        self.name = name
        self.id = id
        self.kind = kind

class AudioSourcePort(Protocol):
    def list_devices(self) -> list[AudioDeviceInfo]: ...
    
    def open(self, device_id: str, sample_rate: int = 16000, channels: int = 1) -> None: ...
    
    def read_chunk(self) -> AudioChunk: ...
    
    def close(self) -> None: ...
