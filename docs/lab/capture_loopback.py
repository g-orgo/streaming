import wave

import pyaudio

SAMPLE_RATE = 16000
DURATION = 5
CHUNK = 1024
FORMAT = pyaudio.paInt16
CHANNELS = 1


def _capture(device_index: int, sample_rate: int) -> bytes | None:
    p = pyaudio.PyAudio()
    try:
        stream = p.open(
            format=FORMAT, channels=CHANNELS, rate=sample_rate,
            input=True, input_device_index=device_index,
            frames_per_buffer=CHUNK,
        )
    except OSError:
        p.terminate()
        return None
    frames = []
    for _ in range(0, int(sample_rate / CHUNK * DURATION)):
        data = stream.read(CHUNK)
        frames.append(data) # type: ignore
    stream.stop_stream()
    stream.close()
    p.terminate()
    return b"".join(frames) # type: ignore


p = pyaudio.PyAudio()
for i in range(p.get_device_count()):
    info = p.get_device_info_by_index(i)
    if info["maxInputChannels"] > 0: # type: ignore
        sample_rate = int(info.get("defaultSampleRate", SAMPLE_RATE))
        kind = "speaker" if info.get("name", "").startswith("Microphone") else f"mic_{i}" # type: ignore
        path = f"docs/lab/capture_{kind}.wav"
        audio = _capture(i, sample_rate)
        if audio is None:
            print(f"Pulado device {i} (falha ao abrir)")
            continue
        with wave.open(path, "wb") as w:
            w.setnchannels(CHANNELS)
            w.setsampwidth(p.get_sample_size(FORMAT))
            w.setframerate(sample_rate)
            w.writeframes(audio)
        print(f"Salvo {path}")
p.terminate()
