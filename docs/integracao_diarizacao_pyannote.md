# Integração de Diarização com Resemblyzer

## Contexto

O VAD (Silero) usado em `speech_to_text.py` só detecta a **presença** de fala,
não **quem** fala. Por isso vozes de fundo inflam o `LIMIAR_FALA`
(`speech_to_text.py:26`) tanto quanto a voz do usuário, e nenhum limiar separa
as duas candidatas — em `LIMIAR_FALA = 1.0` tudo é descartado, inclusive a voz
principal.

## Decisão de arquitetura

Não usar o diarizador clássico `pyannote/speaker-diarization-3.1` no fluxo ao
vivo: ele é um pipeline **em lote (offline)**, lento (segundos por trecho), e
as frases duram ~1,2s+. Em tempo real o correto é a **verificação de locatário
por frase** com o modelo de *embedding*.

A primeira proposta usava o `pyannote/embedding`, mas ele é um modelo **gated**
(assinado): exige aceitar a licença no Hugging Face e configurar `HF_TOKEN`.
Para eliminar essa credencial, trocamos para o **Resemblyzer**, que usa um
modelo aberto (`pretrained.pt`, d-vector/GE2E) empacotado na própria lib, sem
qualquer licença nem token.

> **Atenção:** apesar de não precisar de licença HF, o resemblyzer continua
> dependendo de **torch** (o `VoiceEncoder` é um `nn.Module`) e de **librosa**.
> A troca resolve a burocracia da licença, mas **não** reduz o peso de ML —
> que segue isolado no subprocesso do worker.

1. Enrolar a voz do usuário uma vez (gravação limpa de ~5s) → `_ref_voz`
   (ou deixar a **Fase 5** adaptá-la sozinha a partir das frases ao vivo).
2. A cada frase que o VAD encerrar, calcular o *embedding* e comparar com
   `_ref_voz` (score 0–1 por cosseno).
3. Se `score >= limiar`, transcreve; caso contrário, descarta a frase.

Isso responde a pergunta "a fala é do **usuário**?" em vez de "existe fala?",
resolvendo exatamente o gargalo atual.

### Arquitetura (isolamento do subprocesso)

Todo o peso de ML continua isolado no subprocesso do worker (como o Whisper,
carregado de forma preguiçosa em `stt.py:_modelo_whisper`), seguindo a regra do
`speech_to_text.py:146`, que evita o crash nativo (`0xC0000005`) de onnxruntime
combinado com o streaming de áudio.

---

## Fase 1 — Dependências

Adicionar ao `pyproject.toml:7`:

```toml
"resemblyzer>=0.1.4",
"webrtcvad-wheels>=2.0.14",
```

> **Por que `webrtcvad-wheels` e não `webrtcvad`?** O resemblyzer importa
> `webrtcvad` no topo do `audio.py`. O pacote `webrtcvad` 2.0.10 (original)
> usa `pkg_resources`, módulo removido no setuptools ≥81 — e o projeto usa
> `setuptools>=83.0.0`. O `webrtcvad-wheels==2.0.14` mantém a mesma API sem
> esse problema.

Instala:

```bash
uv add resemblyzer "webrtcvad-wheels>=2.0.14"
```

> O resemblyzer atrai `torch` (pesado) e `librosa`→`numba`. No Python 3.14 a
> resolução original do `numba` falha; a instalação nova resolve com `numba
> 0.66`, que já suporta 3.14. **Não** há necessidade de `HF_TOKEN` no `.env`.

---

## Fase 2 — Novo módulo `src/PyStreamingTool/llm/workers/diarization.py`

Module que orça enrolar e verificar. Importa o resemblyzer apenas por demanda
para não atrasar o load do módulo principal.

### Enrolagem da voz (offline, uma vez)

```python
from typing import Any

import numpy as np

# Taxa de amostragem esperada pelo modelo (16kHz), igual à do Whisper e do VAD.
SR = 16000

# Score mínimo de cosseno para aceitar que uma frase é do usuário.
LIMIAR = 0.6


def gravar_referencia(audio: np.ndarray, sr: int = SR) -> np.ndarray:
    """Embedding de referência (L2-normado) da voz do usuário.

    Recebe um áudio limpo (~5s) já normalizado em float32 16kHz e devolve o
    *embedding*, pronto para comparar por cosseno. Sem licença HF.
    """
    from resemblyzer import VoiceEncoder, preprocess_wav  # type: ignore[import-untyped]
    from resemblyzer.hparams import sampling_rate  # type: ignore[import-untyped]

    encoder = VoiceEncoder(verbose=False)
    wav = preprocess_wav(audio, source_sr=sr)
    if sampling_rate != sr:
        wav = preprocess_wav(audio, source_sr=sr)
    return np.asarray(encoder.embed_utterance(wav), dtype=np.float32)
```

### Verificação por frase

```python
def fala_do_usuario(
    frase: np.ndarray,
    referencia: np.ndarray,
    encoder: Any,
    sr: int = SR,
    limiar: float = LIMIAR,
) -> bool:
    """True se o embedding da frase é parecido com a referência (score >= limiar)."""
    from resemblyzer import preprocess_wav  # type: ignore[import-untyped]

    wav = preprocess_wav(frase, source_sr=sr)
    emb = np.asarray(encoder.embed_utterance(wav), dtype=np.float32)
    return float(np.dot(emb, referencia)) >= limiar
```

### Carregamento do encoder

```python
def carregar_encoder() -> Any:
    """Carrega o VoiceEncoder (torch) no subprocesso do worker, uma única vez.

    O resemblyzer decide a device: cuda se disponível, senão cpu.
    """
    from resemblyzer import VoiceEncoder

    return VoiceEncoder(verbose=False)
```

> O `embedd` é L2-normado (0–1), então o score por cosseno é simplesmente o
> **produto escalar** `np.dot(emb, referencia)` — sem precisar de módulo extra.
> Nas validações, a mesma voz deu `1.0` e o ruído puro `0.48`.

---

## Fase 3 — Carregar/liberar a referência no worker

Em `worker_stt.py` (`stt.py:22`), junto das variáveis globais do modelo,
criar o verificador e a referência, carregados uma única vez:

```python
_ref_voz: np.ndarray | None = None
_verificador: Any = None


def _voz_do_usuario(frase: np.ndarray) -> bool:
    """True se a frase é da voz de referência; sem ref, aceita tudo."""
    global _verificador
    if _ref_voz is None:
        return True
    if _verificador is None:
        from PyStreamingTool.llm.workers.diarization import (
            carregar_encoder,
            fala_do_usuario,
        )

        _verificador = (carregar_encoder(), fala_do_usuario)
    encoder, checar = _verificador
    return bool(checar(frase, _ref_voz, encoder))
```

### Integração no `worker_main`

```python
audio = file_entrada.get()
if audio is None:
    break
try:
    if not _voz_do_usuario(audio):
        fila_saida.put(None)
        continue
    transcrito = _transcrever(audio)
    ...
```

---

## Fase 4 — Exercitar o limiar

O `limiar` (score do modelo) é o novo "seletor de vozes". Comece em `0.6` e
suba em passos de `0.05` até as vozes de fundo pararem de ser transcritas sem
cortar a sua. Nas validações, `0.6` separou bem o tronco da referencia
(1.0) do ruído (0.48).

Recomendado: por alguns minutos, registrar no log (`_logger` do worker) os
scores tanto da sua voz quanto do fundo para fixar o limiar com dados reais.

---

## Fase 5 — Referência adaptativa (bootstrap por "bom senso")

### Contexto

A referência não precisa (nem deve) vir só de uma gravação manual. Em vez de
descartar tudo até existir `_ref_voz`, o worker **adapta** a referência a
partir das próprias frases, distinguindo o usuário do fundo por **volume em
relação à média falada** e **semelhança cosseno** com a referência mantida.

O "bom senso" é: **tudo que estiver abaixo da média de energia que vêm sendo
falada é candidato a "possível ruído"** — mas **não é descartado de cara**.
Volume só gera *suspeita*; a *verdade* quem decide é a semelhança. Isso cobre
os dois casos que parecem iguais:

- **Usuário longe do mic:** volume baixo, mas semelhança alta com a
  referência **intacta** → ainda é o usuário → **mantida**.
- **Ruído de fundo:** volume baixo e semelhança baixa → *possível ruído*,
  fica em quarentena → sem confirmação por semelhança, é **descartado**.

### Estados da frase (sem decisão imediata)

Para cada frase `F` (energia `vol`, semelhança `score = cos(emb(F), ref)`):

**1. Confirmação forte (`score >= limiar_alto`)** → é o usuário, sempre.
- Atualiza `_vol_medio` (média móvel da energia falada).
- Atualiza `_ref_voz` com peso leve (`_ref = 0.9 * _ref + 0.1 * emb`) para
  acompanhar mudanças sutis de voz.
- *Mesmo com volume baixo*, é a "mesma pessoa mais baixa" → mantida.

**2. Suspeita** (`vol` abaixo de `_vol_medio` e `score` abaixo de `limiar_alto`):
- Entra numa **quarentena** (buffer rotativo com `embedding`, energia e
  `timestamp`). Deixa de ser candidata a atualizar a referência, **mas não é
  descartada ainda**.

**3. Desfecho (a partir do retorno do usuário)** — decide o fim da quarentena:
- Se, quando o usuário fala alto e forte de novo, houver semelhança entre o
  embedding confirmado e um em quarentena → era a **mesma voz** (usuário fora
  do alcance) → **resgate** e realimenta a referência.
- Se uma amostra em quarentena **não** conseguir par com ninguém confirmado
  dentro de `idade_max` (janela) → agora sim: **ruído confirmado →
  descartada de vez** e fora da referência para sempre.

### Referência dominada

Com a referência adaptativa e o `_vol_medio`, o domínio do fundo não vira
referência: ruído só entra se confirmado por semelhança, e o cluster dominante
de ruído (baixa autoconsistência) esgota na quarentena sem atualizar `_ref`.

### Boot e seeds

- **Seed manual (opcional):** as opções originais A (UI, botão "Gravar sua
  voz" → `.npy`) e B (arquivo `referencia.npy` no iniciar) continuam válidas
  e **dão o start-point** para a adaptação.
- **Seed automática:** mesmo sem `.npy`, o sistema acumula no modo bootstrap
  até travar a primeira `_ref`.

### Parâmetros de ajuste (somados ao `limiar`)

| Parâmetro | Papel |
|-----------|-------|
| `limiar_alto` | semelhança forte (usuário), separado do `LIMIAR` de aceite |
| `_vol_medio`  | média móvel da energia falada (só atualiza com vozes confirmadas) |
| `alpha_vol`   | quanto a energia precisa cair p/ virar suspeita (ex.: `vol < 0.5 * média`) |
| `peso_atual`  | peso da atualização da referência (ex.: `0.1`) |
| `idade_max`/janela | tempo máximo que uma amostra em quarentena espera antes do descarte |

### Implementação concreta

O monitor adaptativo fica em `diarization.py` como uma **classe com estado**
(`VozAdaptativa`), substituindo o par `_ref_voz`/`_verificador` do Fase 3. Ele
encapsula: bootcompleto (seed ou bootstrap), energia das frases, quarentena e
atualização branda da referência.

Adicionar ao topo de `src/PyStreamingTool/llm/workers/diarization.py`:

```python
from collections import deque
from dataclasses import dataclass
from typing import Any, Deque

# Parâmetros ajustáveis da Fase 5
LIMIAR_ALTO = 0.6    # semelhança que confirma/atualiza a referência
ALPHA_VOL = 0.5       # fração da média de energia que vira "suspeita"
PESO_ATUAL = 0.2      # peso da nova frase na referência adaptiva
IDADE_MAX = 100       # n° de frases que uma quarentena vive antes do descarte
MIN_BOOTSTRAP = 10    # mínimo p/ tentar travar a 1ª referência
MAX_BOOTSTRAP = 40    # buffer do bootstrap
MAX_QUARENTENA = 40   # buffer da quarentena


@dataclass
class Suspeita:
    """Uma frase em quarentena aguardando resgate (semelhança) ou descarte (idade)."""
    emb: np.ndarray
    vol: float
    idade: int = 0


class VozAdaptativa:
    """Aprende/adapta a referência da voz do usuário e separa o ruído de fundo."""

    def __init__(
        self,
        encoder: Any,
        ref_inicial: np.ndarray | None = None,
        sr: int = SR,
        limiar_alto: float = LIMIAR_ALTO,
        alpha_vol: float = ALPHA_VOL,
        peso: float = PESO_ATUAL,
        idade_max: int = IDADE_MAX,
        max_boot: int = MAX_BOOTSTRAP,
        min_boot: int = MIN_BOOTSTRAP,
        max_quarentena: int = MAX_QUARENTENA,
    ) -> None:
        self._encoder = encoder
        self._ref = ref_inicial
        self._vol_medio: float | None = None
        self._sr = sr
        self._limiar_alto = limiar_alto
        self._alpha_vol = alpha_vol
        self._peso = peso
        self._idade_max = idade_max
        self._boot: list[tuple[np.ndarray, float]] = []  # (emb, vol) no bootstrap
        self._max_boot = max_boot
        self._min_boot = min_boot
        self._quarentena: Deque[Suspeita] = deque(maxlen=max_quarentena)

    def _embed(self, frase: np.ndarray) -> np.ndarray:
        """Embedding L2-normado da frase, pronto para cosseno via produto escalar."""
        from resemblyzer import preprocess_wav  # type: ignore[import-untyped]

        wav = preprocess_wav(frase, source_sr=self._sr)
        return np.asarray(self._encoder.embed_utterance(wav), dtype=np.float32)

    @staticmethod
    def _energia(audio: np.ndarray) -> float:
        return float(np.sqrt(np.mean(audio * audio, dtype=np.float64)))

    def processar(self, frase: np.ndarray) -> bool:
        """Decide se transcreve a frase e mantém a referência em forma."""
        emb = self._embed(frase)
        vol = self._energia(frase)

        # Sem referência ainda: bootstrap. Durante o aprendizado aceita tudo.
        if self._ref is None:
            self._alimentar_bootstrap(emb, vol)
            return True

        # Estado 3: envelhecer a quarentena (antes de comparar).
        self._envelhecer_quarentena()

        score = float(np.dot(emb, self._ref))  # cosseno (embeddings L2-normados)

        # Estado 1: confirmação forte -> é o usuário, sempre.
        if score >= self._limiar_alto:
            self._confirmar(emb, vol)
            return True

        # Estado 2: suspeita (energia baixa relativa à média) -> quarentena.
        if self._vol_medio is None or vol < self._vol_medio * self._alpha_vol:
            self._quarentena.append(Suspeita(emb=emb, vol=vol))
        return False

    def _alimentar_bootstrap(self, emb: np.ndarray, vol: float) -> None:
        """Guarda amostras e tenta travar a referência assim que houver grupo."""
        self._boot.append((emb, vol))
        if len(self._boot) > self._max_boot:
            self._boot.pop(0)
        if len(self._boot) >= self._min_boot:
            self._travar_bootstrap()

    def _travar_bootstrap(self) -> None:
        """Trava `_ref` no cluster autoconsistente de maior frequência."""
        n = len(self._boot)
        if n < self._min_boot:
            return
        embs = np.asarray([e for e, _ in self._boot])
        matriz = embs @ embs.T  # cosseno, pois embeddings são L2-normados
        # Quantos irmãos (score >= limiar) cada amostra tem.
        freq = np.count_nonzero(matriz >= self._limiar_alto, axis=1) - 1
        melhor = int(np.argmax(freq))
        if freq[melhor] < self._min_boot:
            return  # ainda não há cluster dominante confiável (ruído fechou)
        mask = matriz[melhor] >= self._limiar_alto
        grupo = np.mean(embs[mask], axis=0)
        self._ref = grupo / float(np.linalg.norm(grupo))
        vols = np.array([v for (_, v), sim in zip(self._boot, mask) if sim])
        self._vol_medio = float(np.mean(vols))
        self._boot.clear()

    def _confirmar(self, emb: np.ndarray, vol: float) -> None:
        """Atualiza a referência com peso leve e a média de energia."""
        self._vol_medio = (
            vol if self._vol_medio is None else 0.9 * self._vol_medio + 0.1 * vol
        )
        self._ref = self._peso * emb + (1 - self._peso) * self._ref
        norm = float(np.linalg.norm(self._ref))
        if norm:
            self._ref = self._ref / norm
        self._resgatar(emb)

    def _resgatar(self, emb: np.ndarray) -> None:
        """Sai da quarentena o que vir a ser a mesma voz (usuário longe)."""
        manter = [
            sus for sus in self._quarentena
            if float(np.dot(sus.emb, emb)) < self._limiar_alto
        ]
        self._quarentena.clear()
        self._quarentena.extend(manter)

    def _envelhecer_quarentena(self) -> None:
        """Incrementa a idade e descarta as suspeitas que venceram `idade_max`."""
        vivos = [
            sus for sus in self._quarentena
            if (sus.idade := sus.idade + 1) <= self._idade_max
        ]
        self._quarentena.clear()
        self._quarentena.extend(vivos)
```

Depois, **substituir** o bloco da Fase 3 em `stt.py` (linhas 22-23 e
`_voz_do_usuario`, linhas 31-44) por:

```python
from pathlib import Path

_voz: VozAdaptativa | None = None


def _referencia_seed() -> np.ndarray | None:
    """Seed opcional (referencia.npy). Sem o arquivo, cai no bootstrap."""
    caminho = Path("referencia.npy")
    return np.load(caminho) if caminho.is_file() else None


def _voz_do_usuario(frase: np.ndarray) -> bool:
    """True se a frase é do usuário; adapta a referência automaticamente."""
    global _voz
    if _voz is None:
        from PyStreamingTool.llm.workers.diarization import (
            VozAdaptativa,
            carregar_encoder,
        )

        _voz = VozAdaptativa(carregar_encoder(), ref_inicial=_referencia_seed())
    return _voz.processar(frase)
```

O `worker_main` **não muda** — segue chamando `_voz_do_usuario(audio)`.

> **Atenção (decisão offline, no worker):** o bootstrap e a quarentena rodam
> no subprocesso (`stt.py`), nunca no streaming do processo principal — mesmo
> isolamento dos arquivos de segurança do worker.

---

## Resumo das mudanças

1. `pyproject.toml` — dependências `resemblyzer>=0.1.4` e
   `webrtcvad-wheels>=2.0.14` (e o `numba` resolvido para o Python 3.14).
2. Novo `src/PyStreamingTool/llm/workers/diarization.py` — enrolar + verificar.
3. `src/PyStreamingTool/llm/workers/stt.py` — globais `_ref_voz`/`_verificador`
   e chamada `_voz_do_usuario` no `worker_main`.
4. `.env` — **sem mudanças** (nenhum `HF_TOKEN` necessário).
5. `docs/` — este plano.
6. Ajuste fino do `limiar` com dados reais.

## Validação executada

- `mypy --strict src/PyStreamingTool/llm/workers/diarization.py
  src/PyStreamingTool/llm/workers/stt.py` → `Success`.
- Fluxo `gravar_referencia` + `fala_do_usuario`: mesma voz `True`, ruído
  `False`, sem referência aceita tudo → **3 execuções limpas**.
- `pytest src/tests -q` → `4 passed`.