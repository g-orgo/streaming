import json
import logging
from pathlib import Path

from live_caption_bridge.domain.models import AudioChunk
from live_caption_bridge.ports.speech import SpeechSegment

logger = logging.getLogger(__name__)

_MODEL_MAP: dict[str, str] = {
    "tiny": "vosk-model-small-en-us-0.15",
    "small": "vosk-model-small-en-us-0.15",
    "medium": "vosk-model-en-us-0.22",
    "large": "vosk-model-en-us-0.22",
}

def _default_model_path(model_size: str) -> str:
    name = _MODEL_MAP.get(model_size, "vosk-model-small-en-us-0.15")
    return str(Path.home() / "Vosk" / name)

class WhisperSTT:
    def __init__(self, model_size: str = "tiny", device: str = "cpu") -> None:
        self._model_path = _default_model_path(model_size)
        self._model = None
        self._rec = None
        self._sample_rate = 16000

    def _load(self) -> None:
        if self._model is not None:
            return
        from vosk import KaldiRecognizer, Model # type: ignore

        logger.info("Carregando modelo Vosk de %s", self._model_path)
        self._model = Model(self._model_path)
        self._rec = KaldiRecognizer(self._model, self._sample_rate)

    def transcribe(self, chunk: AudioChunk) -> SpeechSegment:
        self._load()

        data = chunk.samples
        if chunk.channels > 1:
            import array
            raw = array.array("h", data)
            data = raw[:: chunk.channels].tobytes()

        self._rec.AcceptWaveform(data) # type: ignore
        result = json.loads(self._rec.FinalResult()) # type: ignore
        text = result.get("text", "").strip()

        return SpeechSegment(
            text=text,
            language="en",
            start_ns=chunk.started_ns,
            end_ns=chunk.ended_ns,
            confidence=None,
        )
