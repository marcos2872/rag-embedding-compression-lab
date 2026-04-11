"""
src/quantization/scalar_uniform.py
-----------------------------------
Variante A — Quantização escalar uniforme com min/max global.

Não usa rotação nem codebook ótimo. Serve como baseline mais simples
para comparação com as variantes Lloyd-Max e TurboQuant.

Algoritmo:
  1. Armazena normas originais
  2. Calcula q_min / q_max sobre todos os valores de todos os vetores
  3. Divide o intervalo em 2^bits - 1 bins iguais
  4. Arredonda cada valor ao bin mais próximo → índice inteiro
  5. Armazena índices (bit-packed) + q_min + q_scale + norms

Reconstrução:
  x_hat[i,j] = q_min + indices[i,j] * q_scale
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class UniformState:
    q_min: float
    q_scale: float   # (q_max - q_min) / (2^bits - 1)
    bits: int
    dim: int


def fit_uniform(X: np.ndarray, bits: int) -> UniformState:
    """
    Calcula q_min e q_scale sobre todos os valores de X.

    X    : [N, D] float32
    bits : número de bits (2, 4 ou 8)
    """
    q_min = float(X.min())
    q_max = float(X.max())
    levels = (1 << bits) - 1          # 2^bits - 1
    q_scale = (q_max - q_min) / levels if q_max > q_min else 1.0
    return UniformState(q_min=q_min, q_scale=q_scale, bits=bits, dim=X.shape[1])


def quantize_uniform(X: np.ndarray, state: UniformState) -> np.ndarray:
    """
    X      : [N, D] float32
    Retorna: [N, D] int32 com índices 0 .. 2^bits-1
    """
    levels = (1 << state.bits) - 1
    X_clipped = np.clip(X, state.q_min, state.q_min + state.q_scale * levels)
    indices = np.round((X_clipped - state.q_min) / state.q_scale).astype(np.int32)
    return np.clip(indices, 0, levels)


def dequantize_uniform(indices: np.ndarray, state: UniformState) -> np.ndarray:
    """
    indices: [N, D] int32
    Retorna: [N, D] float32
    """
    return (indices.astype(np.float32) * state.q_scale + state.q_min)
