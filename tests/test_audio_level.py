import math
import struct


def dbfs(samples: bytes, sample_width: int = 2) -> float:
    """
    Calcula o nível de áudio em decibéis em relação ao full scale (dBFS).

    :param samples: Amostras de áudio como bytes.
    :param sample_width: Largura da amostra em bytes (1 para 8 bits, 2 para 16 bits, etc.).
    :return: Nível de áudio em dBFS.
    """
    if not samples:
        return -float("inf")
    max_possible = 2 ** (sample_width * 8-1)
    max_val = 0
    for i in range(0, len(samples), sample_width):
        val = abs(int.from_bytes(
            samples[i:i + sample_width], "little", signed=True
        ))
        max_val = max(max_val, val)
    if max_val == 0:
        return -float("inf")
    return 20.0 * math.log10(max_val / max_possible)

def test_silence_returns_neg_inf() -> None:
    silence = struct.pack("<h", 0) * 100
    assert dbfs(silence) == -float("inf")

def test_half_amplitude_is_minus_6db() -> None:
    signal = struct.pack("<h", 16384) * 100
    assert abs(dbfs(signal) - (-6.02)) < 0.1


def test_clipping_is_0db() -> None:
    clip = struct.pack("<h", 32767) * 100
    assert abs(dbfs(clip) - 0) < 0.1
