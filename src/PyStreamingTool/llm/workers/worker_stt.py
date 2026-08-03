"""
Pipeline de transcrição e tradução isolado em um subprocesso.
"""

from multiprocessing import Queue
from typing import Any

import numpy as np
from faster_whisper import WhisperModel  # type: ignore[import-untyped]
from langdetect import detect  # type: ignore[import-untyped]

from PyStreamingTool.llm.core import LlamaChat

MODELO_STT = "base"

# O modelo é carregado só na primeira transcrição do worker.
# Assim o processo principal (captura) nunca executa a inferência
# do Whisper, que é a fonte do crash nativo quando combinada com
# o streaming de áudio.
_modelo: Any = None


def _logger(msg: str) -> None:
    """Logger do worker"""
    print(f"[Worker STT] {msg}")


def _modelo_whisper() -> Any:
    """Carrega e devolve modelo Whisper do worker"""
    global _modelo
    if _modelo is None:
        _modelo = WhisperModel(MODELO_STT, device="cpu", compute_type="int8")
    return _modelo


def _transcrever(audio: np.ndarray) -> tuple[str, str] | None:
    """
    Transcreve o áudio de uma frase e devolve (texto, idioma) ou None.

    o vad_filter=True usa o Silero para descartar ruídos de fundo que
    tenham passado pelo VAD do microfone. O Language=None deixa o whisper
    detectar o idioma automaticamente, o que resolve o problema do modelo monolíngue.

    """
    segmentos, info = _modelo_whisper().transcribe(
        audio,
        beam_size=1,  # Busca gulosa: mais rápido e suficiente para legendas
        language=None,  # Detecta idioma automaticamente
        vad_filter=True,  # Filtra ruídos de fundo
    )

    texto = " ".join(segment.text for segment in segmentos).strip()
    if not texto:
        return None
    return texto, info.language


def _processar_e_traduzir_texto(texto: str) -> str | None:
    """
    Traduz com a LLM e devolve texto traduzido ou None

    o detect(texto_gerado) aqui valida o idioma DA STRING
    GERADA PELA LLM, ou seja, sem interferência do áudio do usuário
    (esse já fio detectado pelo Whisper e define o idioma-alvo).
    Queremos garantir que a legenda sai no idioma-alvo mesmo que
    a LLM responda no idioma errado.
    """
    try:
        text_gerado = LlamaChat().chat({"content": texto})
        _logger(f"Texto gerado pela LLM: {text_gerado}")
        if text_gerado is None:
            return None
        _logger(f"Idioma detectado do texto gerado: {detect(text_gerado)}")
    except (OSError, RuntimeError, ValueError) as error:
        _logger(f"Erro ao traduzir texto: {error}")
        return None


def worker_main(file_entrada: Queue[Any], fila_saida: Queue[Any]) -> None:
    """
    Loop do worker: Recebe áudio, transcreve, traduz, valida e devolve.
    roda num processo filho (multipprocessing.Process). Uma chamada detect()
    aqui pré-aquece o langdetect longe do microfone, para o primeiro uso não
    colidir com o streaming de áudio do processo principal.

    contrato de comunicação:
    - fila_entrada recebe np.ndarray float32 (áudio da frase) ou None
    (sentinela de encerramento do worker);
    - fila_saida devolve a legenda traduzida (str) quando a tradução passa
    na validação de idioma, ou None quando não há legenda para aquela frase.
    """
    # Pré-aquece o langdetect antes de qualquer frase chegar
    # para evitar crash ou demora na primeira tradução.
    detect("Hello")

    _logger("Worker STT iniciado.")
    while True:
        audio = file_entrada.get()

        if audio is None:
            break
        try:
            transcrito = _transcrever(audio)
            if transcrito is None:
                fila_saida.put(None)
                continue

            text, idioma_original = transcrito
            # Português por padrão, mas se for em português traduzimos para inglês.
            idioma_desejado = "pt" if idioma_original != "pt" else "en"
            _logger(f"Texto reconhecido: {text}")

            gerado = _processar_e_traduzir_texto(text)
            if gerado is not None:
                _logger(f"Expected language: {idioma_desejado}")
                _logger(f"Language match: ${detect(gerado) == idioma_desejado}")

                if detect(gerado) == idioma_desejado:
                    fila_saida.put(gerado)
                    continue
            fila_saida.put(None)
        except Exception as error:  # noqa: BLE001
            _logger(f"Erro inesperado no worker: {error}")
            fila_saida.put(None)
