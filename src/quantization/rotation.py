"""
src/quantization/rotation.py
----------------------------
Gera e aplica a rotação ortogonal aleatória usada em TurboQuantMSE/Prod.

A matriz ortogonal Q é obtida via decomposição QR de uma matriz Gaussiana aleatória,
o que garante distribuição uniforme sobre o grupo ortogonal (medida de Haar).
"""

from __future__ import annotations

import numpy as np


def fit_rotation(dim: int, seed: int) -> np.ndarray:
    """
    Retorna uma matriz ortogonal D×D deterministicamente dada (dim, seed).

    Parâmetros
    ----------
    dim  : dimensão do embedding (ex: 384)
    seed : semente aleatória para reprodutibilidade

    Retorna
    -------
    Q : [D, D] float32 — matriz ortogonal (Q @ Q.T = I)
    """
    rng = np.random.default_rng(seed)
    G = rng.standard_normal((dim, dim)).astype(np.float64)
    Q, _ = np.linalg.qr(G)
    return Q.astype(np.float32)


def apply_rotation(X: np.ndarray, R: np.ndarray) -> np.ndarray:
    """
    Aplica rotação a cada vetor linha de X.

    y_i = R @ x_i  →  Y = X @ R.T

    X : [N, D] float32
    R : [D, D] float32
    Retorna: [N, D] float32
    """
    return (X @ R.T).astype(np.float32)


def apply_inverse_rotation(Y: np.ndarray, R: np.ndarray) -> np.ndarray:
    """
    Aplica rotação inversa (R é ortogonal → inversa = transposta).

    x_i = R.T @ y_i  →  X = Y @ R

    Y : [N, D] float32
    R : [D, D] float32
    Retorna: [N, D] float32
    """
    return (Y @ R).astype(np.float32)
