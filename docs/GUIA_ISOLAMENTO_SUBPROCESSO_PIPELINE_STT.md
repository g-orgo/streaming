# Guia: isolamento do pipeline de transcrição/tradução em subprocesso

## 1. Contexto do problema

O aplicativo captura o microfone com `sounddevice` e, a cada frase, executa o
pipeline **Whisper → LLM → validação de idioma (langdetect)**. Nessa
arquitetura original, o Whisper (`ctranslate2`) era carregado no próprio
processo da captura e o `langdetect.detect()` era carregado de forma preguiçosa
na primeira tradução.

**Causa-raiz do crash (diagnosticada e medida):** a primeira chamada a
`langdetect.detect()` (que carrega os perfis de idioma) rodando logo após a
inferência do Whisper, com o streaming do microfone ativo, corrompia a memória
e derrubava o processo com um **crash nativo**:

- ocorre na thread `Dummy-3` (callback do PortAudio via cffi);
- códigos observados: `0xC0000005`, `0xC0000094`, `0xC000001D`;
- `rbp = 0x1f40` (= 8000 = `BLOCK_SIZE`) em todas as capturas;
- às vezes o RIP caía dentro de `_cffi_backend.cp314-win_amd64.pyd`.

Não é um problema de thread: **threads compartilham memória**. Um
`threading.Thread` executando o pipeline continuaria corrompendo o heap do
processo e derrubaria a captura/UI junto. Por isso a solução definitiva é
isolar o pipeline num **subprocesso** (`multiprocessing.Process`), que tem
memória própria.

## 2. Solução adotada

- O Whisper + LLM + langdetect rodam num **processo filho persistente**
  (`worker_stt.worker_main`).
- O processo principal (captura com `sounddevice` + VAD) **nunca** executa a
  inferência do Whisper.
- A comunicação é feita com duas `multiprocessing.Queue`:
  - `fila_do_worker`: recebe o áudio da frase (`np.ndarray` float32) ou `None`
    (sentinela de encerramento);
  - `fila_de_resultados`: devolve a legenda traduzida (`str`) ou `None`.
- Uma thread de ponte (`_le_resultados`) lê `fila_de_resultados` e chama o
  callback da UI. O signal Qt (`legenda_recebida.emit`) é thread-safe, então
  pode ser emitido dessa thread sem tocar na thread da UI.
- O worker faz `daemon=True`: morre junto com o aplicativo (sem processo
  órfão ao fechar a janela).

## 3. Pré-requisito: `main.py` com guard de `__main__`

O Windows usa `spawn` no `multiprocessing`. O processo filho reimporta o script
principal; sem o guard, a UI seria recriada no filho. O `main.py` do projeto já
tem o guard necessário:

```python
if __name__ == "__main__":
    # inicia a aplicação
```

## 4. Arquivo novo: `src/PyStreamingTool/llm/worker_stt.py`

```python
"""Pipeline de transcrição e tradução isolado num subprocesso.

O Whisper (ctranslate2) e o langdetect rodam aqui, num processo separado da
captura de áudio (sounddevice). Rodar a inferência do Whisper no mesmo processo
da captura causava um crash nativo (corrupção de memória no callback do
PortAudio) logo após a primeira tradução. Isolado neste processo filho, um
crash nativo no pipeline não derruba mais o aplicativo de captura.
"""
import time
from multiprocessing import Queue
from typing import Any

import numpy as np
from faster_whisper import WhisperModel  # type: ignore[import-untyped]
from langdetect import detect  # type: ignore[import-untyped]

from PyStreamingTool.llm.core import LlamaChat

# Tamanho do modelo Whisper. "base" é multilíngue (detecta o idioma sozinho),
# leve o bastante para rodar em tempo real em CPU nesta máquina.
MODELO_STT = "base"

# O modelo é carregado só na primeira transcrição do worker. Assim o processo
# principal (captura) nunca executa a inferência do Whisper, que é a fonte do
# crash nativo quando combinada com o streaming de áudio.
_modelo: Any = None


def _modelo_whisper() -> Any:
    """Carrega (uma única vez) e devolve o modelo Whisper do worker."""
    global _modelo
    if _modelo is None:
        _modelo = WhisperModel(MODELO_STT, device="cpu", compute_type="int8")
    return _modelo


def _transcrever(audio: np.ndarray) -> tuple[str, str] | None:
    """
    Transcreve o áudio de uma frase e devolve (texto, idioma) ou None.

    O vad_filter=True usa o Silero para descartar ruídos de fundo que tenham
    passado do nosso detector. O language=None deixa o Whisper detectar o
    idioma automaticamente, o que resolve o problema do modelo monolíngue.
    """
    segmentos, info = _modelo_whisper().transcribe(
        audio,
        beam_size=1,  # Busca gulosa: mais rápido e suficiente para legendas
        language=None,  # Detecção automática de idioma (multilíngue)
        vad_filter=True,  # Filtra trechos sem fala antes de transcrever
    )
    texto = " ".join(seg.text.strip() for seg in segmentos).strip()
    if not texto:
        return None
    return texto, info.language


def _processar_e_traduzir_texto(texto: str) -> str | None:
    """Traduz com a LLM e devolve o texto traduzido (ou None).

    O detect(text_gerado) aqui valida o idioma DA STRING GERADA PELA LLM, ou
    seja, sem interferência do áudio do usuário (esse já foi detectado pelo
    Whisper e define o idioma-alvo). Queremos garantir que a legenda sai no
    idioma-alvo mesmo que a LLM responda no idioma errado.
    """
    try:
        text_gerado = LlamaChat().chat({"content": texto})
        print(f"text_gerado: {text_gerado}")
        if text_gerado is None:
            return None
        print(f"Detected language: {detect(text_gerado)}")
        return text_gerado
    except (OSError, RuntimeError, ValueError) as err:
        print(err)
        return None


def worker_main(fila_entrada: Queue[Any], fila_saida: Queue[Any]) -> None:
    """Loop do worker: recebe áudio, transcreve, traduz, valida e devolve.

    Roda num processo filho (multiprocessing.Process). Uma chamada detect()
    aqui pré-aquece o langdetect longe do microfone, para o primeiro uso não
    colidir com o streaming de áudio do processo principal.

    Contrato de comunicação:
    - fila_entrada recebe np.ndarray float32 (áudio da frase) ou None
      (sentinela de encerramento do worker);
    - fila_saida devolve a legenda traduzida (str) quando a tradução passa na
      validação de idioma, ou None quando não há legenda para aquela frase.
    """
    # Pré-aquece o langdetect (carrega os perfis de idioma) antes de qualquer
    # frase chegar, para o primeiro uso ser leve.
    detect("hello")  # noqa: B018  carrega os perfis do langdetect uma única vez
    print("[worker] pipeline carregado e aquecido", flush=True)
    while True:
        audio = fila_entrada.get()  # bloqueia até chegar uma frase (ou None)
        if audio is None:
            break
        try:
            transcrito = _transcrever(audio)
            if transcrito is None:
                fila_saida.put(None)
                continue

            texto, idioma_original = transcrito
            # Português por padrão, mas se for em português traduzimos para inglês.
            idioma_desejado = "pt" if idioma_original != "pt" else "en"
            print(f"Texto reconhecido: {texto}")

            gerado = _processar_e_traduzir_texto(texto)
            if gerado is not None:
                print(f"Expected language: {idioma_desejado}")
                print(f"Language match: {detect(gerado) == idioma_desejado}")
                if detect(gerado) == idioma_desejado:
                    fila_saida.put(gerado)
                    continue
            fila_saida.put(None)
        except Exception as err:  # noqa: BLE001  falha do pipeline não derruba o app
            print(err)
            fila_saida.put(None)
```

## 5. Alterações em `src/PyStreamingTool/llm/speech_to_text.py`

### 5.1 Imports

Trocar o bloco de imports por:

```python
import multiprocessing as mp
import queue
import threading
import time
from collections.abc import Callable
from typing import Any

import numpy as np
import sounddevice as sd  # type: ignore[import-untyped]
from faster_whisper.vad import get_vad_model  # type: ignore[import-untyped]

from PyStreamingTool.llm.worker_stt import worker_main
```

### 5.2 `iniciar_stt`: worker + ponte de resultados

Adicionar o worker e trocar o despacho por frase (que criava uma
`threading.Thread` por frase) pelo envio à fila do worker:

```python
    # O detector pré-carrega o VAD aqui (fora da thread do microfone) para o
    # modelo já estar aquecido quando os primeiros blocos chegarem,
    # o que evita crash
    detector = _DetectorFala()
    fila_de_audio: queue.Queue[np.ndarray] = queue.Queue()

    # ==== Worker (subprocesso de transcrição/tradução) ====
    # fila_do_worker: áudio das frases (np.ndarray) vai para o worker.
    # fila_de_resultados: o worker devolve a legenda traduzida (str) ou None.
    fila_do_worker: mp.Queue[Any] = mp.Queue()
    fila_de_resultados: mp.Queue[Any] = mp.Queue()
    worker = mp.Process(
        target=worker_main,
        args=(fila_do_worker, fila_de_resultados),
        daemon=True,
    )
    worker.start()

    def _callback(
        indata: np.ndarray, _frames: int, _time_info: object, _status: object
    ) -> None:
        # Operação barata e segura: normaliza e enfileira o áudio.
        fila_de_audio.put(_normalizar(indata))

    def _le_resultados() -> None:
        """Consome a fila de resultados do worker e entrega a legenda à UI.

        O callback do Qt (legenda_recebida.emit) é thread-safe, então pode ser
        chamado daqui (thread de leitura) sem tocar na thread da UI.
        """
        while True:
            try:
                legenda: str | None = fila_de_resultados.get()
            except (EOFError, OSError):
                # O worker foi encerrado; encerra a leitura.
                return
            if legenda is not None:
                callback(legenda)

    threading.Thread(target=_le_resultados, daemon=True).start()

    def _loop_de_deteccao() -> None:
        """Consome o áudio capturado e despacha cada frase detectada ao worker.

        Roda numa thread Python normal (segura para onnxruntime), drenando a
        fila e alimentando o detector bloco a bloco.
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
```

### 5.3 Remover do arquivo

- `MODELO_STT` + `modelo_stt = WhisperModel(...)` no nível do módulo (o Whisper
  não pode mais carregar no processo da captura);
- as funções `_transcrever`, `_processar_audio`;
- `_processar_e_traduzir_texto` (a validação `detect(text_gerado) ==
  language_it_should_be` passa a rodar dentro do worker).

## 6. Por que cada escolha

| Escolha | Motivo |
| --- | --- |
| `mp.Process` + filas | Isola o pipeline com memória própria; um crash nativo não derruba captura/UI |
| `if __name__ == "__main__"` em `main.py` | Necessário para o `spawn` do Windows (sem isso a UI recria no filho) |
| `daemon=True` | Worker morre com o app; sem processo órfão |
| Sentinela `None` na fila | Encerramento limpo do loop do worker |
| Thread `_le_resultados` | O `callback` (signal Qt) não é picklável; a ponte lê a fila e emite o signal (thread-safe) |
| `detect("hello")` no worker | Pré-aquece o langdetect dentro do processo isolado, longe do streaming |

## 7. Validação executada

- **Worker isolado:** 3/3 execuções limpas com saída correta (áudio `pt_frase.wav`
  → transcreve → LLM traduz → `detect(gerado) == "en"` → devolve a legenda).
- **Flow completo** (`iniciar_stt` = sounddevice + VAD + worker, 10 s):
  3/3 execuções limpas, `EXIT=0`, sem crash.
- `mypy --strict src/PyStreamingTool/llm/speech_to_text.py
  src/PyStreamingTool/llm/worker_stt.py`: **Success**.

## 8. Observação

O estado anterior (antes desta mudança) reporta 2 avisos `Unused "type: ignore"`
no `mypy --strict` atual (`_transcrever` e `_probabilidades`). São pré-existentes
ao commit; podem ser removidos num commit separado se desejado.
