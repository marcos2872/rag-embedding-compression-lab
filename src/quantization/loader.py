"""
src/quantization/loader.py
----------------------------
Carregamento e dequantização centralizados.

Elimina a duplicação entre benchmark/distortion.py e retrieval/faiss_store.py:
ambos precisavam do mesmo bloco if/elif para cada variante.

Uso:
    from src.quantization.loader import load_and_dequantize
    X_hat = load_and_dequantize("turbo_mse", 4)  # [N, D] float32 | None
"""

from __future__ import annotations

from pathlib import Path

import numpy as np


def load_and_dequantize(variant: str, bits: int) -> np.ndarray | None:
    """
    Carrega arquivo .npz da variante, dequantiza e retorna [N, D] float32.

    Retorna None se o arquivo não existir.

    Parâmetros
    ----------
    variant : "uniform" | "lloyd_max" | "turbo_mse" | "turbo_prod"
    bits    : 2 | 4 | 8
    """
    path = Path(f"embeddings/{variant}_{bits}bit.npz")
    if not path.exists():
        return None

    if variant == "uniform":
        from src.quantization.scalar_uniform import dequantize_uniform
        from src.quantization.storage import load_uniform
        idx, _norms, state = load_uniform(path)
        return dequantize_uniform(idx, state)

    if variant == "lloyd_max":
        from src.quantization.lloyd_max import dequantize_lloyd
        from src.quantization.storage import load_lloyd
        idx, _norms, cb = load_lloyd(path)
        return dequantize_lloyd(idx, cb)

    if variant == "turbo_mse":
        from src.quantization.storage import load_turbo_mse
        from src.quantization.turboquant_mse import dequantize_mse_batch
        idx, norms, state = load_turbo_mse(path)
        return dequantize_mse_batch(idx, norms, state)

    if variant == "turbo_prod":
        from src.quantization.storage import load_turbo_prod
        from src.quantization.turboquant_prod import dequantize_prod_batch
        idx, norms, signs, gammas, state = load_turbo_prod(path)
        return dequantize_prod_batch(idx, norms, signs, gammas, state)

    return None
