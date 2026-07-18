from typing import Protocol
from live_caption_bridge.domain.models import AudioChunk


class AudioDeviceInfo:
    def __init__(self, name: str, id: int) -> None:
        self.name = name
        self.id = id
        
class AudioSourcePort(Protocol):
    def list_devices(self) -> list[AudioDeviceInfo]: ...
    
    def open(self, device_id: str, sample_rate: int = 16000, channels: int = 1) -> None: ...
    
    def read_chunk(self) -> AudioChunk: ...
    
    def close(self) -> None: ...