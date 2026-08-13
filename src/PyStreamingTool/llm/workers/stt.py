"""
Pipeline de transcrição e tradução isolado em um subprocesso.
"""

from multiprocessing import Queue
from pathlib import Path
from threading import Thread
from typing import Any

import numpy as np
from faster_whisper import WhisperModel  # type: ignore[import-untyped]

from PyStreamingTool.llm.config import (
    IDIOMA_TRADUCAO,
    IDIOMA_USUARIO,
    NOME_TRADUCAO,
    SIMILARIDADE_MIN,
)
from PyStreamingTool.llm.core import LlamaChat, get_embeddings
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


def _normalizar(texto: str) -> str:
    """Normaliza um texto para comparação (espaços, pontuação e caixa)."""
    return " ".join(texto.split()).strip(" .!?;:-_").lower()


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

    O idioma é fixado no idioma do usuário (`IDIOMA_USUARIO`): o microfone
    captura a voz dele. A detecção automática do Whisper errava em frases
    curtas (detectava "en" para fala em pt), o que invertia a política de
    tradução e resultava em legenda não traduzida.
    """
    segmentos, info = _modelo_whisper().transcribe(
        audio,
        beam_size=1,  # Busca gulosa: mais rápido e suficiente para legendas
        language=IDIOMA_USUARIO,  # Sem detecção automática (idioma do usuário)
        vad_filter=True,  # Filtra ruídos de fundo
    )
    texto = " ".join(segment.text for segment in segmentos).strip()
    if not texto:
        return None
    return texto, info.language


def _processar_e_traduzir_texto(texto: str, reforcar: bool = False) -> str | None:
    """Traduz com a LLM e devolve texto traduzido ou None.

    Quando `reforcar` é True, a mensagem ao usuário ganha o idioma-alvo
    explícito, para a segunda tentativa (o modelo pequeno às vezes ignora o
    system prompt e precisa da instrução repetida).

    Returns:
        A tradução ou None se a LLM falhou.
    """
    try:
        mensagem = texto
        if reforcar:
            mensagem = f"Traduza para o {NOME_TRADUCAO}: {texto}"
        text_gerado = LlamaChat().chat({"content": mensagem})
        _logger(f"Texto gerado pela LLM: {text_gerado}")
        if text_gerado is None:
            return None
        return text_gerado.strip()
    except (OSError, RuntimeError, ValueError) as error:
        _logger(f"Erro ao traduzir texto: {error}")
        return None


def _fidelidade_semantica(original: str, traducao: str) -> bool:
    """True se a tradução preserva o sentido do original (e não é o próprio original).

    Duas travas:
    - Igualdade textual: a LLM devolveu a própria entrada sem traduzir
      (não tradução tem cosseno ~1.0, então só o cosseno não pega).
    - Cosseno dos embeddings multilíngues (bge-m3 via Ollama): abaixo de
      `SIMILARIDADE_MIN` a tradução fugiu do sentido.

    Se o modelo de embedding não estiver configurado ou a chamada falhar,
    devolve True (permissivo): o guard nunca derruba uma legenda por falta
    de infraestrutura ou erro de rede.
    """
    if _normalizar(original) == _normalizar(traducao):
        _logger("Tradução idêntica ao original: LLM repetiu a entrada.")
        return False
    matriz = get_embeddings([original, traducao])
    if matriz is None:
        return True
    a, b = (np.asarray(v, dtype=np.float32) for v in matriz)
    if a.size == 0 or b.size == 0:
        return True
    (norm_a, norm_b) = (float(np.linalg.norm(a)), float(np.linalg.norm(b)))
    if norm_a == 0.0 or norm_b == 0.0:
        return True
    cosseno = float(np.dot(a, b) / (norm_a * norm_b))
    _logger(f"Similaridade semântica: {cosseno:.3f}")
    return cosseno >= SIMILARIDADE_MIN

def _pre_aquecer_voz() -> None:
    """Pré-aquece o encoder de voz + VozAdaptativa (resemblyzer/torch)."""
    # Enconder de voz + VozAdaptativa (resembly/torch)
    _voz_do_usuario(np.zeros(16000, dtype=np.float32))
    # Aquece o forward do encoder de voz (torch) com um sinal sintético.
    # A chamada com silêncio acima não roda o embed por volume baixo, então a
    # primeira frase real pagava a compilação do forward do torch aqui.
    if _voz is not None:
        _voz._embed( # type: ignore
            np.random.default_rng(0).standard_normal(16000, dtype=np.float32)
        )


def _pre_aquecer() -> None:
    """
    Pré-aquece o Whisper e o encoder da voz em paralelo; a LLM em background.

    Whisper e resemblyzer demoram segundos para carregar (download/load do
    modelo, compilação do torch) e precisam estar prontos antes da primeira
    frase — rodam em threads paralelas para o tempo ser o máximo, não a soma.

    A LLM (Ollama) também precisa carregar os ~2GB do modelo, mas isso não
    bloqueia o loop: o warmup roda numa thread daemon enquanto o worker já
    aceita áudio. Com `keep_alive` configurado no core, a primeira tradução
    real reaproveita o modelo já residente.
    """
    erros: list[str] = []

    def _etapa(nome: str, funcao: Any) -> None:
        try:
            funcao()
        except Exception as error:  # noqa: BLE001
            erros.append(f"{nome}: {error}")

    # 1) Whisper + VAD interno (vad_filter=true). Usa um sinal sintético curto
    # em vez de silêncio puro: o VAD filtrava o silêncio antes do encoder, e a
    # primeira frase real pagaria o custo de inicialização do ctranslate2.
    # 2) Encoder de voz + VozAdaptativa (resemblyzer/torch).
    passos: list[tuple[str, Any]] = [
        (
            "whisper",
            lambda: _transcrever(
                np.random.default_rng(0).standard_normal(16000, dtype=np.float32)
            ),
        ),
        ("voz", _pre_aquecer_voz),
    ]
    threads = [
        Thread(target=_etapa, args=(nome, funcao), daemon=True)
        for nome, funcao in passos
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # 3) LLM na memória (Ollama) em segundo plano: não atrasa o start.
    # A chamada direta (sem `_etapa`) evita corrida na lista `erros`;
    # `_processar_e_traduzir_texto` já loga as próprias falhas.
    Thread(
        target=lambda: _processar_e_traduzir_texto("Hello"),
        daemon=True,
    ).start()

    if erros:
        _logger(f"Avisos no pré-aquecimento: {erros}")


def worker_main(file_entrada: Queue[Any], fila_saida: Queue[Any]) -> None:
    """
    Loop do worker: Recebe áudio, transcreve, traduz, valida e devolve.
    roda num processo filho (multipprocessing.Process).

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
            vol_medio = _voz._vol_medio if _voz is not None else None # type: ignore
            score_txt = f"{score:.3f}" if score is not None else "n/a"
            vol_medio_txt = f"{vol_medio:.3f}" if vol_medio is not None else "n/a"
            ref_txt = "set" if _voz is not None and _voz._ref is not None else "none" # type: ignore
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
            _logger(f"Texto reconhecido: {text} (idioma={idioma_original})")

            # Política de tradução: o microfone captura o idioma do usuário
            # (`IDIOMA_USUARIO`), então a legenda sai sempre em
            # `IDIOMA_TRADUCAO` — sem depender de detecção automática.
            _logger(f"Idioma desejado: {IDIOMA_TRADUCAO}")

            gerado = _processar_e_traduzir_texto(text)

            # Caso 1: LLM fora do ar (None). Emite o texto reconhecido para
            # não apagar o que foi captado — a tradução é um extra.
            if gerado is None:
                _logger("LLM indisponível: emitindo texto reconhecido.")
                fila_saida.put(text)
                continue

            # Caso 2: LLM sinalizou 'ignorar' (ruído/trecho sem sentido).
            # Sentinela real: não emite legenda alguma, como era antes.
            if _normalizar(gerado) == "ignorar":
                fila_saida.put(None)
                continue

            # Caso 3: tradução válida (não é a entrada repetida nem fugiu
            # do sentido) — emite direto.
            if _fidelidade_semantica(text, gerado):
                fila_saida.put(gerado)
                _logger(f"Ciclo 1 emitido: {gerado}")
                continue

            # Ciclo 2: reforça o idioma-alvo na instrução e tenta de novo.
            _logger("Ciclo 1 reprovado: gerando correção com instrução explícita.")
            corrigido = _processar_e_traduzir_texto(text, reforcar=True)
            if (
                corrigido is not None
                and _normalizar(corrigido) != "ignorar"
                and _fidelidade_semantica(text, corrigido)
            ):
                fila_saida.put(corrigido)
                _logger(f"Ciclo 2 corrigido: {corrigido}")
                continue

            # Fallback: nenhuma tradução confiável. Emite o texto reconhecido
            # para não apagar o que foi captado (a tradução é um extra).
            _logger("Tradução falhou: emitindo texto reconhecido como fallback.")
            fila_saida.put(text)
            continue
        except Exception as error:  # noqa: BLE001
            _logger(f"Erro inesperado no worker: {error}")
            fila_saida.put(None)
