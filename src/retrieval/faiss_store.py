"""
src/retrieval/faiss_store.py
------------------------------
Constrói, salva e carrega índices FAISS IndexFlatIP para cada variante.

Todos os índices armazenam vetores float32 (FAISS não aceita float16 nem
vetores quantizados nativamente no IndexFlat). A economia de memória vem
do armazenamento em disco (.npz bit-packed); o índice FAISS em RAM é
sempre float32.
"""

from __future__ import annotations

from pathlib import Path

import faiss
import numpy as np
from rich.console import Console
from rich.progress import track

console = Console()


# ── Primitivos ─────────────────────────────────────────────────────────────────

def build_index(embeddings: np.ndarray) -> faiss.Index:
    """
    Constrói IndexFlatIP a partir de embeddings float32.
    IndexFlatIP com vetores normalizados ≡ busca por cosseno exata.
    """
    vecs = embeddings.astype(np.float32)
    index = faiss.IndexFlatIP(vecs.shape[1])
    index.add(vecs)
    return index


def save_index(index: faiss.Index, path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    faiss.write_index(index, str(path))


def load_index(path: str | Path) -> faiss.Index:
    return faiss.read_index(str(path))


# ── Carregadores de embeddings por variante ────────────────────────────────────

def _load_variant_embeddings(variant: str, bits: int) -> np.ndarray | None:
    """Carrega e dequantiza uma variante. Retorna None se arquivo não existir."""
    from src.quantization.loader import load_and_dequantize
    return load_and_dequantize(variant, bits)


# ── Build all ──────────────────────────────────────────────────────────────────

VARIANTS = ["uniform", "lloyd_max", "turbo_mse", "turbo_prod"]
BITS     = [2, 4, 8]


def build_all_indexes() -> None:
    """
    Constrói e salva índices FAISS para todas as variantes + baselines.

    Índices gerados:
      indexes/faiss_f32.index
      indexes/faiss_f16.index
      indexes/faiss_uniform_8bit.index  ... (e demais)
    """
    console.print("\n[bold cyan]Build Indexes — Fase 5[/bold cyan]\n")

    tasks = [("baseline_f32", 32), ("baseline_f16", 16)] + [
        (v, b) for v in VARIANTS for b in BITS
    ]

    for name, bits in track(tasks, description="Construindo índices…"):
        if name == "baseline_f32":
            emb = np.load("embeddings/baseline_f32.npy").astype(np.float32)
            out = Path("indexes/faiss_f32.index")
        elif name == "baseline_f16":
            emb = np.load("embeddings/baseline_f16.npy").astype(np.float32)
            out = Path("indexes/faiss_f16.index")
        else:
            emb = _load_variant_embeddings(name, bits)
            if emb is None:
                console.print(f"  [yellow]⚠ {name}_{bits}bit não encontrado — pulando[/yellow]")
                continue
            out = Path(f"indexes/faiss_{name}_{bits}bit.index")

        index = build_index(emb)
        save_index(index, out)
        size_kb = out.stat().st_size / 1024
        console.print(
            f"  [green]✓[/green] {out.name:45s}  "
            f"{index.ntotal} vetores  {size_kb:.0f} KB"
        )

    console.print("\n[bold green]✓ Índices prontos em indexes/[/bold green]")
