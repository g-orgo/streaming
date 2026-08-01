import json
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Protocol

import numpy as np
import sounddevice as sd  # type: ignore[import-untyped]
from vosk import KaldiRecognizer, Model, SetLogLevel  # type: ignore[import-untyped]

from PyStreamingTool.llm.core import LlamaChat


class _Recognizer(Protocol):
    """Métodos do vosk.KaldiRecognizer, isto aqui impede erros de tipagem"""

    def AcceptWaveform(self, data: bytes) -> bool: ...

    def Result(self) -> str: ...

    def PartialResult(self) -> str: ...


SAMPLE_RATE = 16000
BLOCK_SIZE = 8000
MODEL_PATH = (
    Path(__file__).parent.parent.parent.parent / "models" / "vosk-model-small-pt-0.3"
)

SetLogLevel(-1)
model = Model(str(MODEL_PATH))
recognizer: _Recognizer = KaldiRecognizer(model, SAMPLE_RATE)


def iniciar_stt(callback: Callable[[str], None]) -> None:
    """
    Captura áudio do microfone em tempo real com sounddevice,
    reconhece a fala com Vosk e, ao final de cada frase,
    envia o texto reconhecido pra LLM e devolve o resultado
    através do callback
    """

    def _callback(
        indata: np.ndarray, _frames: int, _time_info: object, _status: object
    ) -> None:
        if recognizer.AcceptWaveform(indata.tobytes()):
            resultado = json.loads(recognizer.Result())
            texto = resultado.get("text", "").strip()
            if texto:
                threading.Thread(
                    target=_processar_texto, args=(texto, callback), daemon=True
                ).start()
        else:
            parcial = json.loads(recognizer.PartialResult())
            if parcial.get("partial", "").strip():
                callback(parcial["partial"])

    _stream = sd.InputStream(
        samplerate=SAMPLE_RATE,
        channels=1,
        dtype="int16",
        blocksize=BLOCK_SIZE,
        callback=_callback,
    )
    _stream.start()


def _processar_texto(texto: str, callback: Callable[[str], None]) -> None:
    try:
        llama_client = LlamaChat()
        resultado = llama_client.chat({"content": texto})
        if resultado is not None:
            callback(resultado)
    except (OSError, RuntimeError, ValueError) as err:
        print(err)
