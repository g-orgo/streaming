from live_caption_bridge.ports.audio import AudioDeviceInfo

class FakeEnumerator:
    def list_devices(self) -> list[AudioDeviceInfo]:
        return [
            AudioDeviceInfo(name="FAKE: Microphone (Realtek)", id=1),
            AudioDeviceInfo(name="FAKE: Speakers (Realtek)", id=2),
        ]
        
def test_enumerator_returns_name_and_id() -> None:
    enumerator = FakeEnumerator()
    devices = enumerator.list_devices()
    
    assert len(devices) == 2
    assert all(d.name and d.id for d in devices)