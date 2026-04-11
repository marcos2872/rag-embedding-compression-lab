"""
src/quantization/turboquant_prod.py
-------------------------------------
Variante D — TurboQuantProd = TurboQuantMSE(b-1 bits) + QJL(1 bit) no resíduo.

O QJL (Johnson-Lindenstrauss Quantized estimator) corrige o viés de produto interno
que o TurboQuantMSE introduz ao ignorar o resíduo de quantização.

Algoritmo (total = b bits por dimensão):
  1. Normaliza x, guarda ||x||
  2. Rotaciona: y = R @ x
  3. TurboQuantMSE com (b-1) bits:
       y_hat = dequantize(quantize(y, b-1 bits))
       r = y - y_hat          ← resíduo no espaço rotacionado
  4. QJL no resíduo:
       γ     = ||r||
       signs = sign(S @ r)    ← S gaussiana [D, D], N(0,1) por entrada
       Armazena: signs (1 bit/dimensão via packbits), γ (float16)
  5. Reconstrução:
       r_hat = √(π/2) / D · γ · Sᵀ @ signs
       y_hat_final = y_hat + r_hat
       x_hat = Rᵀ @ y_hat_final · ||x||

Prova de não-viés (inner product):
  E[⟨q, r_hat⟩] = ⟨q, r⟩  para qualquer query q
  (prova via decomposição de variáveis Gaussianas conjuntas — ver PLAN.md)

Memória por vetor (dim=384):
  b=2: 48B (MSE 1-bit) + 48B (signs) + 2B (γ) = 98B   (~15.7×)
  b=4: 144B (MSE 3-bit) + 48B (signs) + 2B (γ) = 194B  (~7.9×)
  b=8: 336B (MSE 7-bit) + 48B (signs) + 2B (γ) = 386B  (~4.0×)

Nota: 3-bit e 7-bit não são múltiplos de 8, então há 1-2 bits de padding.
  3-bit: ceil(384*3/8) = 144B ✓ (nenhum padding pois 384*3=1152 é múltiplo de 8)
  7-bit: ceil(384*7/8) = 336B ✓ (idem, 384*7=2688 é múltiplo de 8)
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from src.quantization.lloyd_max import dequantize_lloyd, get_codebook, quantize_lloyd
from src.quantization.rotation import apply_inverse_rotation, apply_rotation, fit_rotation


@dataclass
class TurboProdState:
    R: np.ndarray         # [D, D] float32 — rotação ortogonal
    S: np.ndarray         # [D, D] float32 — matriz Gaussiana para QJL
    codebook: np.ndarray  # [2^mse_bits] float32 (array vazio se mse_bits=0)
    dim: int
    bits: int             # bits totais por dimensão
    mse_bits: int         # bits para parte MSE = bits - 1
    seed: int
    qjl_seed: int


def fit_turbo_prod(
    dim: int,
    bits: int,
    seed: int,
    qjl_seed: int,
) -> TurboProdState:
    """
    Prepara estado para TurboQuantProd.
    Independente dos dados — depende apenas de (dim, bits, seed, qjl_seed).
    """
    mse_bits = bits - 1

    R = fit_rotation(dim, seed)

    # S com entradas N(0,1) — escala padrão para fórmula r_hat = √(π/2)/D · γ · Sᵀ·signs
    rng = np.random.default_rng(qjl_seed)
    S   = rng.standard_normal((dim, dim)).astype(np.float32)

    codebook = get_codebook(dim, mse_bits) if mse_bits > 0 else np.array([], dtype=np.float32)

    return TurboProdState(
        R=R, S=S, codebook=codebook,
        dim=dim, bits=bits, mse_bits=mse_bits,
        seed=seed, qjl_seed=qjl_seed,
    )


def quantize_prod_batch(X: np.ndarray, state: TurboProdState):
    """
    Quantiza vetores com TurboQuantProd.

    X: [N, D] float32 (vetores normalizados)
    Retorna: (mse_indices ou None, signs [N,D] float32, gammas [N] float32)
    """
    Y = apply_rotation(X, state.R)   # [N, D]

    # — Parte MSE (b-1 bits) —
    if state.mse_bits > 0:
        mse_indices = quantize_lloyd(Y, state.codebook)          # [N, D]
        Y_hat_mse   = dequantize_lloyd(mse_indices, state.codebook)  # [N, D]
    else:
        mse_indices = None
        Y_hat_mse   = np.zeros_like(Y)

    # — Resíduo no espaço rotacionado —
    residual = (Y - Y_hat_mse).astype(np.float32)               # [N, D]

    # — Parte QJL (1 bit) —
    # S @ r para cada vetor: S [D,D] @ residual.T [D,N] → [D,N] → transposta [N,D]
    SR     = (state.S @ residual.T).T                            # [N, D]
    signs  = np.sign(SR).astype(np.float32)
    signs[signs == 0.0] = 1.0                                    # sign(0) → +1

    gammas = np.linalg.norm(residual, axis=1).astype(np.float32) # [N]

    return mse_indices, signs, gammas


def dequantize_prod_batch(
    mse_indices: np.ndarray | None,
    norms: np.ndarray,
    signs: np.ndarray,
    gammas: np.ndarray,
    state: TurboProdState,
) -> np.ndarray:
    """
    Reconstrói vetores a partir de representação TurboQuantProd.

    mse_indices: [N, D] int32 ou None (quando mse_bits=0)
    norms      : [N] float32 — normas originais
    signs      : [N, D] float32 — signs QJL desempacotados (+1/-1)
    gammas     : [N] float32 — ||resíduo||
    Retorna    : [N, D] float32
    """
    # — Parte MSE —
    if state.mse_bits > 0 and mse_indices is not None:
        Y_hat_mse = dequantize_lloyd(mse_indices, state.codebook)   # [N, D]
    else:
        N = len(norms)
        Y_hat_mse = np.zeros((N, state.dim), dtype=np.float32)

    # — Parte QJL: r_hat = √(π/2) / D · γ_i · Sᵀ @ signs_i —
    factor = math.sqrt(math.pi / 2.0) / state.dim
    # (Sᵀ @ (signs * γ).T).T = (signs * γ) @ S — mais eficiente
    weighted = (signs * gammas[:, np.newaxis]).astype(np.float32)   # [N, D]
    r_hat    = factor * (weighted @ state.S)                         # [N, D]

    # — Combina e rotaciona de volta —
    Y_hat = (Y_hat_mse + r_hat).astype(np.float32)
    X_hat = apply_inverse_rotation(Y_hat, state.R)
    return (X_hat * norms[:, np.newaxis]).astype(np.float32)
