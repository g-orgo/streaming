import json
import threading
from collections.abc import Callable
from pathlib import Path

import numpy as np
import sounddevice as sd  # type: ignore[import-untyped]
from vosk import KaldiRecognizer, Model, SetLogLevel  # type: ignore[import-untyped]

from PyStreamingTool.llm.core import LlamaChat

SAMPLE_RATE = 16000
BLOCK_SIZE = 8000
MODEL_PATH = (
    Path(__file__).parent.parent.parent.parent / "models" / "vosk-model-small-pt-0.3"
)

SetLogLevel(-1)
model = Model(str(MODEL_PATH))
recognizer = KaldiRecognizer(model, SAMPLE_RATE)


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
        if recognizer.AcceptWaveform(indata.tobytes()):  # type: ignore
            resultado = json.loads(recognizer.Result())  # type: ignore
            texto = resultado.get("text", "").strip()
            if texto:
                threading.Thread(
                    target=_processar_texto, args=(texto, callback), daemon=True
                ).start()

    stream = sd.InputStream(
        samplerate=SAMPLE_RATE,
        channels=1,
        dtype="int16",
        blocksize=BLOCK_SIZE,
        callback=_callback,
    )
    stream.start()


def _processar_texto(texto: str, callback: Callable[[str], None]) -> None:
    try:
        llama_client = LlamaChat()
        resultado = llama_client.chat({"content": texto})
        if resultado is not None:
            callback(resultado)
    except (OSError, RuntimeError, ValueError) as err:
        print(err)
