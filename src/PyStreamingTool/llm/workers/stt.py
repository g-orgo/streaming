"""
Pipeline de transcrição e tradução isolado em um subprocesso.
"""

from multiprocessing import Queue
from pathlib import Path
from typing import Any

import numpy as np
from faster_whisper import WhisperModel  # type: ignore[import-untyped]
from langdetect import detect  # type: ignore[import-untyped]

from PyStreamingTool.llm.core import LlamaChat
from PyStreamingTool.llm.workers.diarization import VozAdaptativa

MODELO_STT = "base"

# O modelo é carregado só na primeira transcrição do worker.
# Assim o processo principal (captura) nunca executa a inferência
# do Whisper, que é a fonte do crash nativo quando combinada com
# o streaming de áudio.
_modelo: Any = None
_voz: VozAdaptativa | None = None


def _logger(msg: str) -> None:
    """Logger do worker"""
    print(f"[Worker STT] {msg}")


def _referencia_seed() -> np.ndarray | None:
    """Seed opcional (referencia.npy). Sem o arquivo, cai no bootstrap."""
    caminho = Path("referencia.npy")
    return np.load(caminho) if caminho.is_file() else None


def _voz_do_usuario(
    frase: np.ndarray,
) -> tuple[np.ndarray | None, float, float | None, bool]:
    """Classifica a frase da voz do usuário.

    Devolve (embedding, volume, score, aceita) propagando o resultado de
    `VozAdaptativa.processar` para o log e a decisão de transcrição.
    """
    global _voz
    if _voz is None:
        from PyStreamingTool.llm.workers.diarization import (
            VozAdaptativa,
            carregar_encoder,
        )

        _voz = VozAdaptativa(carregar_encoder(), ref_inicial=_referencia_seed())
    return _voz.processar(frase)


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
    Traduz com a LLM e devolve texto traduzido ou None.

    O SYSTEM_PROMPT (config.py) instrui traduzir tudo para português, exceto o
    português que vira inglês, e a responder exclusivamente com a tradução — ou
    com a palavra "ignorar" quando a entrada for ruído/trecho incompleto. O
    `detect()` aparece no log só para inspeção e não decide a política de idioma.

    Returns:
        A tradução, a sentinela "ignorar" (quando não há o que traduzir) ou
        None se a LLM falhou.
    """
    try:
        text_gerado = LlamaChat().chat({"content": texto})
        _logger(f"Texto gerado pela LLM: {text_gerado}")
        if text_gerado is None:
            return None
        _logger(f"Idioma detectado do texto gerado: {detect(text_gerado)}")
        return text_gerado
    except (OSError, RuntimeError, ValueError) as error:
        _logger(f"Erro ao traduzir texto: {error}")
        return None


def _pre_aquecer() -> None:
    """
    Pré-aquece o langdetect, o encoder da voz, o Whisper e a LLM
    para evitar crash ou demora na primeira frase.
    """
    # 1) Whisper + VAD interno (vad_filter=true): 1s de silêncio
    _transcrever(np.zeros(16000, dtype=np.float32))
    # 2) Enconder de voz + VozAdaptativa (resembly/torch)
    _voz_do_usuario(np.zeros(16000, dtype=np.float32))
    # 3) Pré-aquece o langdetect antes de qualquer frase chegar
    detect("Hello")
    # 4) LLM na memória
    _processar_e_traduzir_texto("Hello")


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

    _pre_aquecer()
    _logger("Worker STT iniciado.")

    while True:
        audio = file_entrada.get()

        if audio is None:
            break
        try:
            _, vol, score, aceita = _voz_do_usuario(audio)
            vol_medio = _voz._vol_medio if _voz is not None else None  # type: ignore
            score_txt = f"{score:.3f}" if score is not None else "n/a"
            vol_medio_txt = f"{vol_medio:.3f}" if vol_medio is not None else "n/a"
            ref_txt = "set" if _voz is not None and _voz._ref is not None else "none"  # type: ignore
            _logger(
                f"score={score_txt} vol={vol:.3f} "
                f"vol_medio={vol_medio_txt} ref={ref_txt}"
            )
            if not aceita:
                _logger("Frase descartada: não é do usuário.")
                fila_saida.put(None)
                continue
            transcrito = _transcrever(audio)
            if transcrito is None:
                fila_saida.put(None)
                continue

            text, idioma_original = transcrito
            # Política de tradução (igual ao SYSTEM_PROMPT em config.py):
            # falou em português -> legenda em inglês; o resto -> português.
            idioma_desejado = "en" if idioma_original == "pt" else "pt"
            _logger(f"Texto reconhecido: {text} (idioma={idioma_original})")

            gerado = _processar_e_traduzir_texto(text)

            # Guarda de saída: a LLM sinalizou "ignorar" (ruído/trecho sem
            # sentido) ou falhou. Nesses casos não emitimos legenda alguma.
            if gerado is None or gerado.strip().lower() == "ignorar":
                fila_saida.put(None)
                continue

            # Valida o idioma do resultado. Fugiu do alvo, tenta uma única
            # segunda rodada e usa ESSE resultado final — a versão anterior
            # descartava o retry e ainda enviava o texto original errado.
            if detect(gerado) != idioma_desejado:
                _logger("Houve a necessidade de uma segunda rodada de tradução")
                gerado = _processar_e_traduzir_texto(text)
                if gerado is None or gerado.strip().lower() == "ignorar":
                    fila_saida.put(None)
                    continue

            _logger(f"Expected language: {idioma_desejado}")
            _logger(f"Detected language: {detect(gerado)}")
            fila_saida.put(gerado)
            continue
        except Exception as error:  # noqa: BLE001
            _logger(f"Erro inesperado no worker: {error}")
            fila_saida.put(None)
