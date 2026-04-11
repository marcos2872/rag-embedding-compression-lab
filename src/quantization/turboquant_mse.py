"""
src/quantization/turboquant_mse.py
------------------------------------
Variante C — TurboQuantMSE completo.

Combina:
  1. Rotação ortogonal aleatória (equaliza energia entre dimensões)
  2. Codebook Lloyd-Max da distribuição de coordenada em S^(d-1)
  3. Bit-packing para taxas de compressão corretas

Diferença vs Variante B (lloyd_max sem rotação):
  A rotação garante que cada coordenada rotacionada siga (aproximadamente)
  a distribuição teórica da esfera, validando o codebook Lloyd-Max.
  Sem rotação, as coordenadas têm energia não-uniforme e o codebook
  pode ser subótimo para dimensões com variância elevada.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from src.quantization.lloyd_max import dequantize_lloyd, get_codebook, quantize_lloyd
from src.quantization.rotation import apply_inverse_rotation, apply_rotation, fit_rotation


@dataclass
class TurboMSEState:
    R: np.ndarray         # [D, D] float32 — matriz de rotação ortogonal
    codebook: np.ndarray  # [2^bits] float32 — centróides Lloyd-Max
    dim: int
    bits: int
    seed: int


def fit_turbo_mse(dim: int, bits: int, seed: int) -> TurboMSEState:
    """
    Prepara o estado de TurboQuantMSE.
    Totalmente independente dos dados — depende apenas de (dim, bits, seed).
    """
    R        = fit_rotation(dim, seed)
    codebook = get_codebook(dim, bits)
    return TurboMSEState(R=R, codebook=codebook, dim=dim, bits=bits, seed=seed)


def quantize_mse_batch(X: np.ndarray, state: TurboMSEState) -> np.ndarray:
    """
    Quantiza um batch de vetores normalizados.

    X      : [N, D] float32, vetores na esfera unitária
    Retorna: [N, D] int32 — índices no codebook (0 .. 2^bits-1)
    """
    Y       = apply_rotation(X, state.R)            # [N, D] — coordenadas rotacionadas
    indices = quantize_lloyd(Y, state.codebook)     # [N, D] int32
    return indices


def dequantize_mse_batch(
    indices: np.ndarray,
    norms: np.ndarray,
    state: TurboMSEState,
) -> np.ndarray:
    """
    Reconstrói vetores a partir de índices quantizados.

    indices: [N, D] int32
    norms  : [N] float32 — normas originais (tipicamente ≈1.0)
    Retorna: [N, D] float32
    """
    Y_hat = dequantize_lloyd(indices, state.codebook)   # [N, D] — lookup no codebook
    X_hat = apply_inverse_rotation(Y_hat, state.R)      # [N, D] — rotação inversa
    return (X_hat * norms[:, np.newaxis]).astype(np.float32)
