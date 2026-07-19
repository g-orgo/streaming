from live_caption_bridge.ports.audio import AudioDeviceInfo, DeviceKind


class FakeLoopbackEnumerator:
    def list_devices(self) -> list[AudioDeviceInfo]:
        return [
            AudioDeviceInfo("Microphone (Realtek)", "mic1", DeviceKind.MICROPHONE), # type: ignore
            AudioDeviceInfo("Speakers (Realtek)", "spk1", DeviceKind.SPEAKER), # type: ignore
        ]


def test_enumerator_distinguishes_mic_and_speaker() -> None:
    enum = FakeLoopbackEnumerator()
    devices = enum.list_devices()
    mics = [d for d in devices if d.kind == DeviceKind.MICROPHONE]
    spk = [d for d in devices if d.kind == DeviceKind.SPEAKER]
    assert len(mics) == 1
    assert len(spk) == 1
    assert mics[0].id == "mic1"
    assert spk[0].id == "spk1"
