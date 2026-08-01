import json
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Protocol

import numpy as np
import sounddevice as sd  # type: ignore[import-untyped]
from langdetect import detect  # type: ignore[import-untyped]
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
            original_lang = resultado.get("lang", "")
            language_it_should_be = (
                "pt"
                if original_lang != "pt"
                else "en"  # Português por padrão mas se for em português traduzimos para inglês
            )

            print(f"Texto reconhecido: {texto}")

            if texto:
                threading.Thread(
                    target=_processar_texto,
                    args=(texto, callback, language_it_should_be),
                    daemon=True,
                ).start()
        # else:
        #     """ Este else é opcional e serve para capturar resultados parciais do reconhecimento de fala """
        #     # todo: isso está sendo enviado sem filtro para a LLM, não está sendo traduzido.
        #     parcial = json.loads(recognizer.PartialResult())
        #     if parcial.get("partial", "").strip():
        #         callback(parcial["partial"])

    _stream = sd.InputStream(
        samplerate=SAMPLE_RATE,
        channels=1,
        dtype="int16",
        blocksize=BLOCK_SIZE,
        callback=_callback,
    )
    _stream.start()


def _processar_texto(
    texto: str,
    callback: Callable[[str], None],
    language_it_should_be: str = "pt",
) -> None:
    """Processa o texto reconhecido pela LLM e envia o resultado para a UI através do callback"""
    try:
        text_gerado = LlamaChat().chat({"content": texto})

        # Aqui vamos validar se o texto que será enviado à UI
        # e que foi processado pela LLM foi traduzido. Isso é
        # importante porque a LLM pode gerar respostas no
        # idioma original do usuário, e queremos que a legenda seja sempre em português.

        print(f"text_gerado: {text_gerado}")
        print(f"Detected language: {detect(text_gerado)}")
        print(f"Expected language: {language_it_should_be}")
        print(f"Language match: {detect(text_gerado) == language_it_should_be}")

        if text_gerado is not None and detect(text_gerado) == language_it_should_be:
            callback(text_gerado)
    except (OSError, RuntimeError, ValueError) as err:
        print(err)
