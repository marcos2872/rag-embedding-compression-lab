"""
src/quantization/lloyd_max.py
-------------------------------
Variante B — Codebook Lloyd-Max ótimo para a distribuição de coordenada na esfera unitária.

Fundamento matemático
---------------------
Para x uniformemente distribuído em S^(d-1), cada coordenada x_i segue a distribuição:

    f(t) = C_d * (1 - t²)^((d-3)/2)   para t ∈ [-1, 1]

Isso é equivalente à distribuição Beta(a, a) escalada de [0,1] para [-1,1]:
    a = (d-1)/2
    Se U ~ Beta(a, a)  então  Y = 2U - 1 ~ f(t)

O codebook é calculado uma única vez para cada (dim, bits) e é
independente dos dados — pode ser reutilizado para qualquer corpus.

Variante B vs C (TurboQuantMSE):
  B: aplica codebook diretamente nos vetores (sem rotação)
  C: aplica rotação ortogonal PRIMEIRO, depois o mesmo codebook
  A rotação uniformiza a distribuição de energia entre coordenadas,
  o que é o insight central do paper TurboQuant.
"""

from __future__ import annotations

import numpy as np
from rich.console import Console
from scipy.stats import beta as beta_dist

console = Console()

# Cache global: (dim, bits) → codebook [2^bits] float32
_codebook_cache: dict[tuple[int, int], np.ndarray] = {}


# ── Distribuição ────────────────────────────────────────────────────────────────

def _beta_alpha(dim: int) -> float:
    """Parâmetro a=b da Beta(a,a) equivalente à distribuição de coordenada em S^(d-1)."""
    return (dim - 1) / 2.0


def coord_pdf(xs: np.ndarray, dim: int) -> np.ndarray:
    """
    PDF de uma coordenada de vetor uniforme em S^(d-1).

    Usa scipy.stats.beta(a, a) — estável numericamente mesmo para dim=384
    onde o expoente direto (1-t²)^190.5 causaria underflow em float64.

    xs  : array com valores em [-1, 1]
    dim : dimensão do embedding
    """
    a = _beta_alpha(dim)
    u = np.clip((xs + 1.0) / 2.0, 0.0, 1.0)   # [-1,1] → [0,1]
    return beta_dist.pdf(u, a, a) / 2.0          # Jacobian: dx/du = 2


# ── Lloyd-Max ────────────────────────────────────────────────────────────────────

def _init_centroids_from_quantiles(
    xs: np.ndarray,
    pdf: np.ndarray,
    K: int,
) -> np.ndarray:
    """
    Inicializa K centróides pelos quantis uniformes da distribuição discreta.
    Substitui a chamada indefinida `initialize_centroids_from_quantiles` do plano original.
    """
    cdf = np.cumsum(pdf)
    cdf /= cdf[-1]                                        # normaliza para [0, 1]
    quantile_targets = (np.arange(K) + 0.5) / K          # quantis 1/(2K), 3/(2K), ...
    return np.interp(quantile_targets, cdf, xs)


def lloyd_max_codebook(
    dim: int,
    bits: int,
    num_grid: int = 500_000,
    num_iters: int = 300,
) -> np.ndarray:
    """
    Computa o codebook Lloyd-Max para a distribuição de coordenada em S^(d-1).

    O algoritmo itera entre dois passos até convergência:
      1. Partition: boundaries = midpoints entre centróides vizinhos
      2. Reconstruction: centroide_k = E[X | boundary_k ≤ X < boundary_{k+1}]

    Usa np.bincount + np.searchsorted para complexidade O(num_grid) por iteração
    em vez de O(K * num_grid) — essencial para bits=8 (K=256).

    Parâmetros
    ----------
    dim      : dimensão do embedding (ex: 384)
    bits     : 2, 4 ou 8  →  K = 2^bits centróides
    num_grid : pontos na grade de integração numérica
    num_iters: máximo de iterações

    Retorna
    -------
    centroids : [2^bits] float32, ordenados em ordem crescente
    """
    K = 1 << bits   # 2^bits

    # Grade uniforme em (-1, 1) — evita singularidades nos extremos
    xs = np.linspace(-1.0 + 1e-9, 1.0 - 1e-9, num_grid)
    pdf = coord_pdf(xs, dim)          # densidade em cada ponto da grade

    # Inicializa centróides pelos quantis
    centroids = _init_centroids_from_quantiles(xs, pdf, K).astype(np.float64)

    prev  = np.empty_like(centroids)
    delta = float("inf")   # inicializa antes do loop (evita NameError no bloco else)

    for iteration in range(num_iters):
        prev[:] = centroids

        # Passo 1 — Partition: midpoints entre centróides vizinhos
        midpoints = (centroids[:-1] + centroids[1:]) / 2.0   # [K-1]

        # Atribui cada ponto da grade ao seu bucket usando searchsorted O(N log K)
        bucket_idx = np.searchsorted(midpoints, xs)           # [num_grid], valores 0..K-1

        # Passo 2 — Reconstruction: E[X | bucket k] via bincount O(N)
        denom = np.bincount(bucket_idx, weights=pdf,       minlength=K)
        numer = np.bincount(bucket_idx, weights=pdf * xs,  minlength=K)

        # Evita divisão por zero em buckets vazios (fallback: manter centróide anterior)
        mask = denom > 1e-15
        centroids[mask] = numer[mask] / denom[mask]

        # Critério de convergência
        delta = float(np.max(np.abs(centroids - prev)))
        if delta < 1e-10:
            console.print(
                f"    [dim]Lloyd-Max convergiu em {iteration + 1} iterações "
                f"(Δ={delta:.2e})[/dim]"
            )
            break
    else:
        console.print(
            f"    [dim yellow]Lloyd-Max: {num_iters} iterações sem convergência "
            f"(Δ={delta:.2e})[/dim yellow]"
        )

    return np.sort(centroids).astype(np.float32)


def get_codebook(dim: int, bits: int) -> np.ndarray:
    """
    Retorna o codebook para (dim, bits), computando e cacheando se necessário.
    Thread-safe para uso sequencial (sem multiprocessing).
    """
    key = (dim, bits)
    if key not in _codebook_cache:
        console.print(
            f"  [cyan]Codebook Lloyd-Max:[/cyan] dim={dim}, bits={bits} "
            f"({1 << bits} centróides)…"
        )
        _codebook_cache[key] = lloyd_max_codebook(dim, bits)
        lo, hi = float(_codebook_cache[key][0]), float(_codebook_cache[key][-1])
        console.print(f"    range=[{lo:.4f}, {hi:.4f}]")
    return _codebook_cache[key]


# ── Quantização / Dequantização ──────────────────────────────────────────────────

def quantize_lloyd(X: np.ndarray, codebook: np.ndarray) -> np.ndarray:
    """
    Quantiza cada coordenada para o índice do centróide mais próximo.
    Usa np.searchsorted nos midpoints → O(N·D·log K) sem alocar [N,D,K].

    X       : [N, D] float32
    codebook: [K] float32 (deve estar ordenado)
    Retorna : [N, D] int32 com valores 0..K-1
    """
    midpoints = (codebook[:-1] + codebook[1:]) / 2.0      # [K-1]
    indices = np.searchsorted(midpoints, X)                 # [N, D]
    return indices.astype(np.int32)


def dequantize_lloyd(indices: np.ndarray, codebook: np.ndarray) -> np.ndarray:
    """
    indices : [N, D] int32
    codebook: [K] float32
    Retorna : [N, D] float32
    """
    return codebook[indices].astype(np.float32)
