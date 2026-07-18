import wave

import pyaudio

DURATION = 5
SAMPLE_RATE = 16000
CHUNK = 1024
FORMAT = pyaudio.paInt16
CHANNELS = 1

p = pyaudio.PyAudio()
stream = p.open(
    format=FORMAT, channels=CHANNELS, rate=SAMPLE_RATE,
    input=True, frames_per_buffer=CHUNK,
)
frames: list[bytes] = []
for _ in range(0, int(SAMPLE_RATE / CHUNK * DURATION)):
    data = stream.read(CHUNK)
    frames.append(data)
stream.stop_stream()
stream.close()
p.terminate()

with wave.open("docs/lab/capture.wav", "wb") as w:
    w.setnchannels(CHANNELS)
    w.setsampwidth(pyaudio.PyAudio().get_sample_size(FORMAT))
    w.setframerate(SAMPLE_RATE)
    w.writeframes(b"".join(frames))
