"""
src/quantization/__init__.py
------------------------------
Pipeline de quantização para todas as variantes da Fase 3.

Variantes implementadas:
  A) uniform    — sem rotação, bins uniformes com min/max global
  B) lloyd_max  — sem rotação, codebook Lloyd-Max (distribuição esférica)
  C) turbo_mse  — rotação + codebook Lloyd-Max  (TurboQuantMSE)
  D) turbo_prod — rotação + Lloyd-Max + QJL     (TurboQuantProd)

Progressão das variantes:
  uniform → lloyd_max : melhor codebook (bins ótimos para distribuição esférica)
  lloyd_max → turbo_mse: adiciona rotação (equaliza energia entre dimensões)
  turbo_mse → turbo_prod: adiciona QJL (corrige viés de produto interno)
"""

from __future__ import annotations

import os
import time
from pathlib import Path

import numpy as np
from rich.console import Console
from rich.table import Table

console = Console()

VARIANTS = ["uniform", "lloyd_max", "turbo_mse", "turbo_prod"]
BITS     = [2, 4, 8]


# ── Utilitários ────────────────────────────────────────────────────────────────

def _load_baseline() -> tuple[np.ndarray, np.ndarray]:
    """Carrega baseline_f32.npy. Retorna (X [N,D], norms [N])."""
    path = Path("embeddings/baseline_f32.npy")
    if not path.exists():
        raise FileNotFoundError(
            "embeddings/baseline_f32.npy não encontrado. Execute: make embed"
        )
    X     = np.load(str(path)).astype(np.float32)
    norms = np.linalg.norm(X, axis=1).astype(np.float32)
    return X, norms


def _output_path(variant: str, bits: int) -> Path:
    return Path(f"embeddings/{variant}_{bits}bit.npz")


def _theoretical_bytes_per_vector(variant: str, bits: int, D: int) -> int:
    """
    Bytes de dados por vetor (exclui overhead compartilhado como R e S).
    Essa é a métrica relevante para corpora grandes.
    """
    import math
    if variant == "uniform":
        return math.ceil(D * bits / 8) + 2          # índices + norma float16
    elif variant == "lloyd_max":
        return math.ceil(D * bits / 8) + 2
    elif variant == "turbo_mse":
        return math.ceil(D * bits / 8) + 2
    elif variant == "turbo_prod":
        mse_bits = bits - 1
        mse_bytes  = math.ceil(D * mse_bits / 8) if mse_bits > 0 else 0
        sign_bytes = math.ceil(D / 8)              # 1 bit/dim
        return mse_bytes + 2 + sign_bytes + 2      # mse_idx + mse_norm + signs + gamma
    return D * 4


def _quick_metrics(X_orig: np.ndarray, X_hat: np.ndarray) -> tuple[float, float]:
    """Retorna (MSE, cosine_sim_médio)."""
    mse    = float(np.mean((X_orig - X_hat) ** 2))
    # Para vetores normalizados: cosine ≈ dot product
    cosine = float(np.mean(np.einsum("ij,ij->i", X_orig, X_hat)))
    return mse, cosine


# ── Variante A — Uniform ───────────────────────────────────────────────────────

def _run_uniform(X: np.ndarray, norms: np.ndarray, bits: int) -> Path:
    from src.quantization.scalar_uniform import fit_uniform, quantize_uniform, dequantize_uniform
    from src.quantization.storage import save_uniform

    state   = fit_uniform(X, bits)
    indices = quantize_uniform(X, state)
    path    = _output_path("uniform", bits)
    save_uniform(indices, norms, state, path)

    X_hat       = dequantize_uniform(indices, state)
    return path, X_hat


# ── Variante B — Lloyd-Max ─────────────────────────────────────────────────────

def _run_lloyd_max(X: np.ndarray, norms: np.ndarray, bits: int) -> Path:
    from src.quantization.lloyd_max import get_codebook, quantize_lloyd, dequantize_lloyd
    from src.quantization.storage import save_lloyd

    dim      = X.shape[1]
    codebook = get_codebook(dim, bits)
    indices  = quantize_lloyd(X, codebook)
    path     = _output_path("lloyd_max", bits)
    save_lloyd(indices, norms, codebook, bits, dim, path)

    X_hat = dequantize_lloyd(indices, codebook)
    return path, X_hat


# ── Variante C — TurboQuantMSE ────────────────────────────────────────────────

def _run_turbo_mse(X: np.ndarray, norms: np.ndarray, bits: int) -> Path:
    from src.quantization.turboquant_mse import fit_turbo_mse, quantize_mse_batch, dequantize_mse_batch
    from src.quantization.storage import save_turbo_mse

    seed  = int(os.getenv("RANDOM_SEED", 42))
    state = fit_turbo_mse(X.shape[1], bits, seed)

    indices = quantize_mse_batch(X, state)
    path    = _output_path("turbo_mse", bits)
    save_turbo_mse(indices, norms, state, path)

    X_hat = dequantize_mse_batch(indices, norms, state)
    return path, X_hat


# ── Variante D — TurboQuantProd ───────────────────────────────────────────────

def _run_turbo_prod(X: np.ndarray, norms: np.ndarray, bits: int) -> Path:
    from src.quantization.turboquant_prod import fit_turbo_prod, quantize_prod_batch, dequantize_prod_batch
    from src.quantization.storage import save_turbo_prod

    seed     = int(os.getenv("RANDOM_SEED",  42))
    qjl_seed = int(os.getenv("QJL_SEED",    123))
    state    = fit_turbo_prod(X.shape[1], bits, seed, qjl_seed)

    mse_indices, signs, gammas = quantize_prod_batch(X, state)
    path = _output_path("turbo_prod", bits)
    save_turbo_prod(mse_indices, norms, signs, gammas, state, path)

    X_hat = dequantize_prod_batch(mse_indices, norms, signs, gammas, state)
    return path, X_hat


_RUNNERS = {
    "uniform":    _run_uniform,
    "lloyd_max":  _run_lloyd_max,
    "turbo_mse":  _run_turbo_mse,
    "turbo_prod": _run_turbo_prod,
}


# ── Entry point ────────────────────────────────────────────────────────────────

def quantize_pipeline(variant: str, bits: int) -> None:
    """
    Quantiza os embeddings baseline e salva em embeddings/<variant>_<bits>bit.npz.

    variant : "uniform" | "lloyd_max" | "turbo_mse" | "turbo_prod"
    bits    : 2 | 4 | 8
    """
    if variant not in _RUNNERS:
        raise ValueError(f"Variante desconhecida: {variant!r}. Opções: {VARIANTS}")
    if bits not in (2, 4, 8):
        raise ValueError(f"bits deve ser 2, 4 ou 8. Recebido: {bits}")

    console.print(f"\n[bold cyan]Quantizando:[/bold cyan] {variant}  bits={bits}\n")

    X, norms = _load_baseline()
    N, D = X.shape
    console.print(f"  Embeddings: {N} vetores × {D} dims  dtype={X.dtype}\n")

    t0       = time.time()
    runner   = _RUNNERS[variant]
    path, X_hat = runner(X, norms, bits)
    elapsed  = time.time() - t0

    # Métricas rápidas de qualidade
    mse, cosine = _quick_metrics(X, X_hat)
    file_kb     = path.stat().st_size / 1024
    f32_bytes   = N * D * 4
    f32_kb      = f32_bytes / 1024
    # Compressão teórica por vetor (exclui R/S compartilhados)
    vec_bytes   = _theoretical_bytes_per_vector(variant, bits, D)
    ratio_vec   = (D * 4) / vec_bytes           # por vetor
    ratio_file  = f32_bytes / path.stat().st_size

    table = Table(show_header=True, header_style="bold")
    table.add_column("Métrica",     style="cyan")
    table.add_column("Valor",       justify="right")
    table.add_column("",            style="dim")

    table.add_row("Variante",            f"{variant}_{bits}bit", "")
    table.add_row("Shape",               f"[{N}, {D}]",          "")
    table.add_row("Arquivo",             str(path),               "")
    table.add_row("Tamanho arquivo",     f"{file_kb:.1f} KB",     f"(f32={f32_kb:.1f} KB, inclui R/S)")
    table.add_row("Bytes/vetor (dados)", f"{vec_bytes} B",        f"(f32={D*4} B)")
    table.add_row("Compressão (vetor)",  f"{ratio_vec:.2f}×",     "dados por vetor, sem overhead")
    table.add_row("Compressão (arquivo)",f"{ratio_file:.2f}×",    "arquivo total (N=556 é pequeno)")
    table.add_row("MSE",                 f"{mse:.6f}",            "↓ melhor")
    table.add_row("Cosine sim médio",    f"{cosine:.6f}",         "↑ melhor (máx=1.0)")
    table.add_row("Tempo",              f"{elapsed:.1f}s",        "")

    console.print(table)
    console.print(f"\n[bold green]✓[/bold green] {path}\n")
