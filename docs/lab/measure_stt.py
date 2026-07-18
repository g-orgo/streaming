import time

import pyaudio

from live_caption_bridge.domain.models import AudioChunk, AudioSource
from live_caption_bridge.adapters.whisper_stt import WhisperSTT

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
frames = []
for _ in range(0, int(SAMPLE_RATE / CHUNK * DURATION)):
    data = stream.read(CHUNK)
    frames.append(data) # type: ignore
stream.stop_stream()
stream.close()
p.terminate()
audio = b"".join(frames) # type: ignore

chunk = AudioChunk(
    source=AudioSource.MICROPHONE,
    samples=audio,
    sample_rate=SAMPLE_RATE,
    channels=1,
    started_ns=0,
    ended_ns=DURATION * 1_000_000_000,
)

stt = WhisperSTT(model_size="tiny", device="cpu")
t0 = time.perf_counter()
result = stt.transcribe(chunk)
elapsed = time.perf_counter() - t0

rtf = elapsed / DURATION
print(f"Audio: {DURATION}s, Inferência: {elapsed:.2f}s, RTF: {rtf:.2f}")
print(f"Texto: {result.text}")
print(f"Idioma: {result.language}, Confiança: {result.confidence}")
print("RTF < 1.0 significa tempo real; acima disso o modelo não acompanha.")
