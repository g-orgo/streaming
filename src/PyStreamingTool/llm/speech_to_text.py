import multiprocessing as mp
import queue
import threading
import time
from collections.abc import Callable
from typing import Any

import numpy as np
import sounddevice as sd  # type: ignore[import-untyped]
from faster_whisper.vad import get_vad_model  # type: ignore[import-untyped]

from PyStreamingTool.llm.workers.worker_stt import worker_main

# Taxa de amostragem padrão do Whisper. O microfone é capturado já neste formato
# para que o áudio possa ser enviado direto para o modelo sem resampling.
SAMPLE_RATE = 16000

# Cada bloco do microfone tem 0.5s de áudio (8000 amostras em 16kHz).
BLOCK_SIZE = 8000

# O Silero VAD trabalha em janelas de 512 amostras (32ms em 16kHz).
JANELA_VAD = 512

# Probabilidade mínima para uma janela do VAD ser considerada "fala".
# Acima disso a janela conta como voz; abaixo, como silêncio.
LIMIAR_FALA = 0.5

# Duração mínima de fala (em segundos) para aceitarmos uma frase.
# Evita que um tosse/ruído curto dispare a transcrição.
FALA_MIN_SEG = 0.3

# Silêncio (em segundos) após a última fala para considerarmos a frase encerrada.
# É o equivalente ao "fim de frase" que o Vosk sinalizava no AcceptWaveform.
SILENCIO_FIM_SEG = 1.2

# Cauda de áudio (em segundos) adicionada após a última janela de fala,
# para a transcrição não cortar a última palavra no meio.
CAUDA_SEG = 0.35

# Se a pessoa falar sem pausa por mais que isso (segundos), forçamos o fim
# da frase para não acumular áudio indefinidamente na memória.
FALA_MAX_SEG = 15.0

# Tamanho do modelo Whisper. "base" é multilíngue (detecta o idioma sozinho),
# leve o bastante para rodar em tempo real em CPU (RTF ~0.12 nesta máquina).
MODELO_STT = "base"


def _normalizar(indata: np.ndarray) -> np.ndarray:
    """
    Converte o áudio do microfone (int16) para float32 em escala [-1, 1].

    O sounddevice entrega blocos como inteiros de 16 bits com shape
    (frames, canais) — mesmo com 1 canal. O Whisper e o Silero VAD esperam
    um vetor 1D float32, então achatamos o array aqui.
    """
    return indata.astype(np.float32).reshape(-1) / 32768.0


class _DetectorFala:
    """
    Detecta o fim de uma frase no áudio capturado em tempo real.

    Reutilizamos o modelo Silero VAD (já embarcado no faster-whisper, sem
    dependências extras) para saber quando alguém está falando. A nossa
    lógica própria é a máquina de estados: acumulamos o áudio do microfone
    e, quando a pessoa fala e depois fica em silêncio por um tempo mínimo,
    devolvemos a fatia de áudio daquela frase para ser transcrita.
    """

    def __init__(self) -> None:
        # O modelo VAD é lru_cache, então é carregado só uma vez na memória.
        self._modelo_vad = get_vad_model()
        self._amostras: list[np.ndarray] = []

    def adicionar(self, bloco: np.ndarray) -> None:
        """Acumula um bloco de áudio vindo do callback do microfone."""
        self._amostras.append(bloco)

    def _probabilidades(self, audio: np.ndarray) -> np.ndarray:
        """
        Roda o Silero VAD no áudio acumulado.

        Devolve a probabilidade de fala (0.0 a 1.0) para cada janela de 32ms.
        O modelo exige que o tamanho seja múltiplo de 512, então fazemos o
        padding com zeros (que o VAD trata como silêncio).
        """
        resto = len(audio) % JANELA_VAD
        if resto:
            audio = np.pad(audio, (0, JANELA_VAD - resto))
        # O SileroVADModel devolve um vetor 1D (uma probabilidade por janela).
        # O ravel garante isso mesmo que alguma versão devolva (N, 1).
        return np.asarray(self._modelo_vad(audio)).ravel()  # type: ignore

    def frase_terminada(self) -> np.ndarray | None:
        """
        Verifica se uma frase terminou no áudio acumulado.

        Retorna a fatia de áudio correspondente à frase (pronta para
        transcrever) quando a pessoa parou de falar, ou None se ainda
        estamos no meio de uma frase (ou só temos silêncio).
        """
        if not self._amostras:
            return None

        audio = np.concatenate(self._amostras)
        if len(audio) < JANELA_VAD:
            return None

        probs = self._probabilidades(audio)
        janelas_de_fala = np.nonzero(probs >= LIMIAR_FALA)[0]

        # Ninguém falou ainda. Limitamos o buffer de silêncio para não crescer
        # para sempre caso o ambiente fique barulhento demais.
        if janelas_de_fala.size == 0:
            if len(audio) >= FALA_MAX_SEG * SAMPLE_RATE:
                self._amostras.clear()
            return None

        ultima_fala = int(janelas_de_fala[-1])
        duracao_fala_seg = janelas_de_fala.size * JANELA_VAD / SAMPLE_RATE
        silencio_seg = (len(probs) - 1 - ultima_fala) * JANELA_VAD / SAMPLE_RATE

        # Ainda não há fala suficiente para considerar uma frase válida.
        if duracao_fala_seg < FALA_MIN_SEG:
            return None

        # A frase terminou quando o silêncio depois da fala passou do limite
        # (ou quando a fala ficou longa demais e forçamos o corte).
        if silencio_seg >= SILENCIO_FIM_SEG or len(audio) >= FALA_MAX_SEG * SAMPLE_RATE:
            fim = int((ultima_fala + 1) * JANELA_VAD + CAUDA_SEG * SAMPLE_RATE)
            frase = audio[:fim]
            # Limpa o buffer para começar a capturar a próxima frase.
            self._amostras.clear()
            return frase

        return None


def iniciar_stt(callback: Callable[[str], None]) -> None:
    """
    Captura áudio do microfone em tempo real com sounddevice.

    O callback do sounddevice roda numa thread criada pelo PortAudio (via
    cffi). Não executamos nenhum modelo de ML ali dentro: rodar onnxruntime
    (o VAD) numa thread "estrangeira" causa crash nativo (0xC0000005) quando
    a transcrição usa o mesmo modelo ao mesmo tempo. Então o callback apenas
    empilha o áudio numa fila, e uma thread Python dedicada consome a fila,
    roda o VAD e detecta o fim de cada frase.
    """

    # O detector pré-carrega o VAD aqui (fora da thread do microfone) para o
    # modelo já estar aquecido quando os primeiros blocos chegarem,
    # o que evita crash ao carregar modelos na primeira chamada do callback
    detector = _DetectorFala()
    fila_de_audio: queue.Queue[np.ndarray] = queue.Queue()

    fila_do_worker: mp.Queue[Any] = mp.Queue()
    fila_de_resultados: mp.Queue[Any] = mp.Queue()
    worker = mp.Process(
        target=worker_main, args=(fila_do_worker, fila_de_resultados), daemon=True
    )

    worker.start()

    def _callback(
        indata: np.ndarray, _frames: int, _time_info: object, _status: object
    ) -> None:
        # Operação barata e segura: normaliza e enfileira o áudio.
        fila_de_audio.put(_normalizar(indata))

    def _le_resultados() -> None:
        """Lê resultados do worker e envia para a UI via callback."""
        while True:
            try:
                legenda: str | None = fila_de_resultados.get()
            except OSError, EOFError:
                return
            if legenda is None:
                break
            callback(legenda)

    threading.Thread(target=_le_resultados, daemon=True).start()

    def _loop_de_deteccao() -> None:
        """Consome o áudio capturado e dispara a transcrição ao fim de cada frase.

        Roda numa thread Python normal (segura para onnxruntime/ctranslate2),
        drenando a fila e alimentando o detector bloco a bloco.
        """
        while True:
            try:
                bloco = fila_de_audio.get_nowait()
            except queue.Empty:
                # Sem áudio novo por enquanto; evita queimar CPU no loop.
                time.sleep(0.05)
                continue

            detector.adicionar(bloco)
            frase = detector.frase_terminada()
            if frase is not None:
                fila_do_worker.put(frase)

    threading.Thread(target=_loop_de_deteccao, daemon=True).start()

    _stream = sd.InputStream(
        samplerate=SAMPLE_RATE,
        channels=1,
        dtype="int16",
        blocksize=BLOCK_SIZE,
        callback=_callback,
    )
    _stream.start()
