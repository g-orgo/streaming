import wave

import pyaudio

SAMPLE_RATE = 16000
DURATION = 5
CHUNK = 1024
FORMAT = pyaudio.paInt16
CHANNELS = 1


def _capture(device_index: int | None) -> bytes:
    p = pyaudio.PyAudio()
    stream = p.open(
        format=FORMAT, channels=CHANNELS, rate=SAMPLE_RATE,
        input=True, input_device_index=device_index,
        frames_per_buffer=CHUNK,
    )
    frames = []
    for _ in range(0, int(SAMPLE_RATE / CHUNK * DURATION)):
        data = stream.read(CHUNK)
        frames.append(data)
    stream.stop_stream()
    stream.close()
    p.terminate()
    return b"".join(frames)


p = pyaudio.PyAudio()
for i in range(p.get_device_count()):
    info = p.get_device_info_by_index(i)
    if info["maxInputChannels"] > 0:
        kind = "mic" if not info.get("isloopback", False) else "speaker"
        path = f"docs/lab/capture_{kind}_{i}.wav"
        audio = _capture(i)
        with wave.open(path, "wb") as w:
            w.setnchannels(CHANNELS)
            w.setsampwidth(p.get_sample_size(FORMAT))
            w.setframerate(SAMPLE_RATE)
            w.writeframes(audio)
        print(f"Salvo {path}")
p.terminate()
