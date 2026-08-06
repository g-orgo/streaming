"""Aqui é onde a voz do usuário é reconhecida, para filtrar o que não é dele."""

from collections import deque
from dataclasses import dataclass
from typing import Any, Deque  # noqa: UP035

import numpy as np

# Taxa de amostragem esperada pelo modelo (16kHz), igual à do Whisper e do VAD.
SR = 16000

# Score mínimo de cosseno para aceitar que uma frase é do usuário.
LIMIAR = 0.6  # Sensibilidade do detector de voz do usuário.

# Volume mínimo (RMS) para uma frase contar como "fala real".
# Abaixo disso é silêncio/ruído baixo: não deve ancorar a referência nem o
# baseline de energia, para o app funcionar mesmo quando o usuário fica calado.
VOL_MIN = 0.001

LIMIAR_ALTO = 0.6  # Semelhança que confirma/atualiza a referência
ALPHA_VOL = 0.5  # fração da média de energia que vira "suspeita"
PESO_ATUAL = 0.2  # peso da nova frase na referência adaptiva
IDADE_MAX = 100  # n° de frases que uma quarentena vive antes do descarte
MIN_BOOTSTRAP = 10  # mínimo p/ tentar travar a 1ª referência
MAX_BOOTSTRAP = 40  # buffer do bootstrap
MAX_QUARENTENA = 40  # buffer da quarentena


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
        vol_min: float = VOL_MIN,
    ) -> None:
        self._encoder = encoder
        self._ref = ref_inicial
        self._vol_medio: float | None = None
        self._vol_min = vol_min
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

    def processar(
        self, frase: np.ndarray
    ) -> tuple[np.ndarray | None, float, float | None, bool]:
        """Classifica a frase e devolve (emb, vol, score, aceita).

        - ``emb``: embedding da frase, ou ``None`` se nem chegou a ser calculado
          (silêncio/ruído baixo).
        - ``vol``: energia (RMS) da frase.
        - ``score``: semelhança cosseno com a referência, ou ``None`` se ainda
          não há referência (bootstrap) ou a frase foi descartada por volume.
        - ``aceita``: True se a frase é do usuário e deve ser transcrita.
        """
        vol = self._energia(frase)

        # Silêncio/ruído baixo: não é a voz do usuário e não deve afetar a
        # referência nem o baseline de energia (usuário pode ficar calado).
        if vol < self._vol_min:
            return (None, vol, None, False)

        emb = self._embed(frase)

        # Sem referência ainda: bootstrap. Durante o aprendizado aceita tudo.
        if self._ref is None:
            self._alimentar_bootstrap(emb, vol)
            return (emb, vol, None, True)

        # Estado 3: envelhecer a quarentena (antes de comparar).
        self._envelhecer_quarentena()

        score = float(np.dot(emb, self._ref))  # cosseno (embeddings L2-normados)

        # Estado 1: confirmação rápida -> é o usuário, sempre.
        if score >= self._limiar_alto:
            self._confirmar(emb, vol)
            return (emb, vol, score, True)

        # Estado 2: suspeita (volume baixo relativo à média) -> quarentena.
        if self._vol_medio is None or vol < self._vol_medio * self._alpha_vol:
            self._quarentena.append(Suspeita(emb=emb, vol=vol))
        return (emb, vol, score, False)

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
        assert self._ref is not None  # _confirmar só roda com referência travada
        self._ref = self._peso * emb + (1 - self._peso) * self._ref
        norm = float(np.linalg.norm(self._ref))
        if norm:
            self._ref = self._ref / norm
        self._resgatar(emb)

    def _resgatar(self, emb: np.ndarray) -> None:
        """Sai da quarentena o que vir a ser a mesma voz (usuário longe)."""
        manter = [
            sus
            for sus in self._quarentena
            if float(np.dot(sus.emb, emb)) < self._limiar_alto
        ]
        self._quarentena.clear()
        self._quarentena.extend(manter)

    def _envelhecer_quarentena(self) -> None:
        """Incrementa a idade e descarta as suspeitas que venceram `idade_max`."""
        vivos = []
        for sus in self._quarentena:
            sus.idade += 1
            if sus.idade <= self._idade_max:
                vivos.append(sus)  # type: ignore
        self._quarentena.clear()
        self._quarentena.extend(vivos)  # type: ignore


def gravar_referencia(audio: np.ndarray, sr: int = SR) -> np.ndarray:
    """Embedding de referência (L2-normado) da voz do usuário.

    Recebe um áudio limpo (~5s) já normalizado em float32 16kHz e devolve o
    *embedding*, pronto para comparar por cosseno. Sem licença HF.

    Importa o resemblyzer apenas por demanda para não atrasar o load do
    módulo principal.
    """
    from resemblyzer import VoiceEncoder, preprocess_wav  # type: ignore
    from resemblyzer.hparams import sampling_rate  # type: ignore[import-untyped]

    encoder = VoiceEncoder(verbose=False)
    wav = preprocess_wav(audio, source_sr=sr)
    if sampling_rate != sr:
        wav = preprocess_wav(audio, source_sr=sr)
    return np.asarray(encoder.embed_utterance(wav), dtype=np.float32)


def fala_do_usuario(
    frase: np.ndarray,
    referencia: np.ndarray,
    encoder: Any,
    sr: int = SR,
    limiar: float = LIMIAR,
) -> bool:
    """True se o embedding da frase é parecido com a referência (score >= limiar)."""
    from resemblyzer import preprocess_wav  # type: ignore

    wav = preprocess_wav(frase, source_sr=sr)
    emb = np.asarray(encoder.embed_utterance(wav), dtype=np.float32)
    return float(np.dot(emb, referencia)) >= limiar


def carregar_encoder() -> Any:
    """Carrega o VoiceEncoder (torch) no subprocesso do worker, uma única vez.

    O resemblyzer decide a device: cuda se disponível, senão cpu.
    """

    from resemblyzer import VoiceEncoder  # type: ignore

    return VoiceEncoder(verbose=False)
