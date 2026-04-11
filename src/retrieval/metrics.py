"""
src/retrieval/metrics.py
--------------------------
Métricas de qualidade de retrieval.

  recall_at_k   — fração de queries com ≥1 relevante no top-k
  mrr           — mean reciprocal rank do primeiro relevante
  mean_latency  — latência média em ms por query (n_runs repetições)
"""

from __future__ import annotations

import time
from typing import Callable

import numpy as np


def recall_at_k(
    retrieved: list[list[str]],
    relevant:  list[list[str]],
    k: int,
) -> float:
    """
    Recall@k: fração das queries em que pelo menos 1 relevante aparece no top-k.

    retrieved : lista de listas de IDs recuperados (ordenados por score desc)
    relevant  : lista de conjuntos de IDs relevantes
    k         : profundidade de corte
    """
    if not retrieved:
        return 0.0
    hits = sum(
        1 for ret, rel in zip(retrieved, relevant)
        if set(ret[:k]) & set(rel)
    )
    return hits / len(retrieved)


def mrr(
    retrieved: list[list[str]],
    relevant:  list[list[str]],
) -> float:
    """
    Mean Reciprocal Rank.

    Para cada query, encontra o rank do primeiro relevante e soma 1/rank.
    Queries sem relevante no resultado contribuem 0.
    """
    if not retrieved:
        return 0.0
    rr_sum = 0.0
    for ret, rel in zip(retrieved, relevant):
        rel_set = set(rel)
        for rank, doc_id in enumerate(ret, start=1):
            if doc_id in rel_set:
                rr_sum += 1.0 / rank
                break
    return rr_sum / len(retrieved)


def mean_latency_ms(
    search_fn: Callable[[np.ndarray, int], tuple],
    query_vecs: np.ndarray,
    k: int = 10,
    n_runs: int = 3,
) -> float:
    """
    Latência média por query em ms.

    Executa n_runs repetições para estabilidade e retorna a mediana dos tempos.

    search_fn  : função que recebe (query_matrix, k) e retorna (distances, indices)
    query_vecs : [num_q, D] float32
    """
    times: list[float] = []
    for _ in range(n_runs):
        t0 = time.perf_counter()
        search_fn(query_vecs, k)
        times.append((time.perf_counter() - t0) * 1000)   # ms

    # Usa a mediana para robustez contra outliers de JIT/cache
    return float(np.median(times) / len(query_vecs))       # ms por query
