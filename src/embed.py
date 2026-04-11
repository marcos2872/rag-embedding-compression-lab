"""
src/embed.py
------------
Fase 2 — Geração de embeddings baseline.

Gera e salva dois arquivos:
  embeddings/baseline_f32.npy  — float32 [N, D], vetores na esfera unitária
  embeddings/baseline_f16.npy  — float16 [N, D], idem com metade da memória

O modelo roda 100% local (sem API). Na primeira execução, o modelo é
baixado do HuggingFace Hub e cacheado em ~/.cache/huggingface/hub/.

Sobre AMD RX 580 (gfx803 / Polaris):
  A RX 580 NÃO é suportada pelo PyTorch ROCm moderno (suporte gfx803
  foi removido no ROCm 5.0+). O fallback automático para CPU é ativado.
  Com BGE-small-en-v1.5 e 556 chunks o tempo na CPU é ~15-30 segundos.
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Optional

import numpy as np
import yaml
from dotenv import load_dotenv
from rich.console import Console
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)

load_dotenv()
console = Console()

# ── Configuração ───────────────────────────────────────────────────────────────

def _embedding_cfg() -> dict:
    p = Path("configs/embedding.yaml")
    if p.exists():
        with p.open() as f:
            return yaml.safe_load(f) or {}
    return {}


# ── Detecção de device ─────────────────────────────────────────────────────────

def detect_device(preferred: Optional[str] = None) -> str:
    """
    Detecta o melhor device disponível.

    Ordem de preferência: cuda → mps → cpu
    Se `preferred` for passado, tenta usá-lo; avisa e faz fallback se indisponível.

    Notas sobre AMD RX 580 (gfx803):
      - /dev/kfd existe (kernel module AMDGPU+KFD carregado)
      - gfx803 não é suportado pelo PyTorch ROCm >= 5.0
      - torch.cuda.is_available() retorna False mesmo com ROCm para gfx803
      - Solução: rodar na CPU (15-30s para ~500 chunks com BGE-small)
    """
    import torch

    def _check_cuda() -> bool:
        return torch.cuda.is_available()

    def _check_rocm() -> bool:
        """Verifica se é build ROCm E há GPU acessível."""
        if torch.version.hip is None:
            return False
        return torch.cuda.is_available()  # ROCm usa a mesma API cuda no PyTorch

    def _check_mps() -> bool:
        return (
            hasattr(torch.backends, "mps")
            and torch.backends.mps.is_available()
        )

    available = {
        "cuda": _check_cuda() or _check_rocm(),
        "mps":  _check_mps(),
        "cpu":  True,
    }

    if preferred:
        preferred = preferred.lower()
        if preferred in available and available[preferred]:
            return preferred
        console.print(
            f"[yellow]⚠ Device '{preferred}' não disponível. Fallback automático.[/yellow]"
        )

    # Auto-detect
    if available["cuda"]:
        import torch
        name = torch.cuda.get_device_name(0)
        console.print(f"[green]GPU detectada:[/green] {name}")
        return "cuda"
    if available["mps"]:
        console.print("[green]GPU detectada:[/green] Apple Silicon (MPS)")
        return "mps"

    # CPU — mostra motivo se houver GPU AMD sem suporte
    kfd = Path("/dev/kfd")
    if kfd.exists():
        import torch
        if torch.version.hip is None:
            console.print(
                "[yellow]⚠ GPU AMD detectada (/dev/kfd existe) mas o PyTorch instalado "
                "é build CUDA, não ROCm.[/yellow]"
            )
        else:
            console.print(
                "[yellow]⚠ GPU AMD detectada mas gfx803 (RX 580/Polaris) não é suportada "
                "pelo PyTorch ROCm >= 5.0. Usando CPU.[/yellow]"
            )

    return "cpu"


# ── Modelo ─────────────────────────────────────────────────────────────────────

def load_model(
    model_name: str,
    device: str,
    cache_dir: Optional[str] = None,
):
    """
    Carrega um SentenceTransformer.

    Na primeira execução faz download do HuggingFace Hub (~130 MB para BGE-small).
    Execuções seguintes usam o cache em ~/.cache/huggingface/hub/.
    """
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError:
        raise ImportError("Execute: uv sync  (sentence-transformers não instalado)")

    console.print(f"[cyan]Modelo:[/cyan]  {model_name}")
    console.print(f"[cyan]Device:[/cyan]  {device}")
    if cache_dir:
        console.print(f"[cyan]Cache:[/cyan]   {cache_dir}")
    else:
        console.print("[cyan]Cache:[/cyan]   ~/.cache/huggingface/hub/")

    t0 = time.time()
    model = SentenceTransformer(
        model_name,
        device=device,
        cache_folder=cache_dir or None,
    )
    elapsed = time.time() - t0
    console.print(f"[green]✓ Modelo carregado[/green] em {elapsed:.1f}s\n")
    return model


# ── Embedding ──────────────────────────────────────────────────────────────────

def embed_corpus(
    corpus_path: str | Path,
    model,
    batch_size: int = 64,
) -> np.ndarray:
    """
    Lê corpus.jsonl, extrai o campo 'text' de cada linha e gera embeddings.

    Retorna array float32 de shape [N, D].
    """
    import json

    corpus_path = Path(corpus_path)
    if not corpus_path.exists():
        raise FileNotFoundError(
            f"corpus.jsonl não encontrado em {corpus_path}. "
            "Execute: make ingest"
        )

    with corpus_path.open(encoding="utf-8") as f:
        docs = [json.loads(line) for line in f if line.strip()]

    texts = [d["text"] for d in docs]
    n = len(texts)

    console.print(f"[cyan]Corpus:[/cyan]  {n} chunks  →  {(n + batch_size - 1) // batch_size} batches (batch_size={batch_size})\n")

    progress = Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        TaskProgressColumn(),
        TimeElapsedColumn(),
        TextColumn("eta"),
        TimeRemainingColumn(),
        console=console,
    )

    embeddings_list: list[np.ndarray] = []
    t0 = time.time()

    with progress:
        task = progress.add_task("Gerando embeddings…", total=n)
        for start in range(0, n, batch_size):
            batch = texts[start : start + batch_size]
            vecs = model.encode(
                batch,
                batch_size=len(batch),
                normalize_embeddings=False,  # normalizamos depois manualmente
                show_progress_bar=False,
                convert_to_numpy=True,
            )
            embeddings_list.append(vecs.astype(np.float32))
            progress.advance(task, len(batch))

    elapsed = time.time() - t0
    X = np.vstack(embeddings_list)  # [N, D]
    console.print(
        f"\n[green]✓ Embeddings gerados[/green]  shape={X.shape}  dtype={X.dtype}  "
        f"tempo={elapsed:.1f}s  ({elapsed/n*1000:.1f} ms/chunk)"
    )
    return X


# ── Normalização ───────────────────────────────────────────────────────────────

def normalize_rows(X: np.ndarray) -> np.ndarray:
    """
    Normaliza cada vetor para norma L2 = 1 (projeção na esfera unitária).

    Necessário: TurboQuant e os benchmarks assumem vetores em S^(d-1).
    Vetores nulos (norma=0) são mantidos como estão para evitar divisão por zero.
    """
    norms = np.linalg.norm(X, axis=1, keepdims=True)  # [N, 1]
    # Evita divisão por zero
    norms_safe = np.where(norms == 0, 1.0, norms)
    X_norm = X / norms_safe

    # Diagnóstico
    normas_resultado = np.linalg.norm(X_norm, axis=1)
    ok = np.sum(np.abs(normas_resultado - 1.0) < 1e-5)
    zeros = np.sum(norms.squeeze() == 0)

    console.print(
        f"[green]✓ Normalizado:[/green] {ok}/{len(X)} vetores com norma≈1.0"
        + (f"  [yellow]({zeros} vetores nulos ignorados)[/yellow]" if zeros else "")
    )
    return X_norm.astype(np.float32)


# ── I/O ────────────────────────────────────────────────────────────────────────

def save_embeddings(X: np.ndarray, path: str | Path, dtype=None) -> None:
    """Salva array de embeddings como .npy."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    arr = X.astype(dtype) if dtype is not None else X
    np.save(str(path), arr)
    size_mb = path.stat().st_size / 1_048_576
    console.print(
        f"[green]✓ Salvo:[/green] {path}  "
        f"shape={arr.shape}  dtype={arr.dtype}  {size_mb:.2f} MB"
    )


def load_embeddings(path: str | Path) -> np.ndarray:
    """Carrega embeddings de um arquivo .npy."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(
            f"Embeddings não encontrados em {path}. Execute: make embed"
        )
    return np.load(str(path))


# ── Pipeline principal ─────────────────────────────────────────────────────────

def embed_pipeline(device: Optional[str] = None) -> None:
    """
    Pipeline completo da Fase 2:
      1. Detecta device
      2. Carrega modelo
      3. Gera embeddings float32
      4. Normaliza
      5. Salva baseline_f32.npy e baseline_f16.npy
      6. Imprime relatório
    """
    cfg = _embedding_cfg()

    model_name  = os.getenv("EMBEDDING_MODEL") or cfg.get("model", "BAAI/bge-small-en-v1.5")
    batch_size  = int(os.getenv("EMBEDDING_BATCH_SIZE") or cfg.get("batch_size", 64))
    cache_dir   = cfg.get("cache_dir") or None
    corpus_path = os.getenv("CORPUS_PATH", "data/corpus.jsonl")

    # ── Device ────────────────────────────────────────────────────────────────
    preferred = device or os.getenv("EMBEDDING_DEVICE") or cfg.get("device") or None
    final_device = detect_device(preferred)
    console.print()

    # ── Modelo ────────────────────────────────────────────────────────────────
    model = load_model(model_name, final_device, cache_dir)

    # ── Embeddings ────────────────────────────────────────────────────────────
    X_raw = embed_corpus(corpus_path, model, batch_size)

    # ── Normalização ──────────────────────────────────────────────────────────
    X_f32 = normalize_rows(X_raw)
    console.print()

    # ── Salvar ────────────────────────────────────────────────────────────────
    save_embeddings(X_f32, "embeddings/baseline_f32.npy", dtype=np.float32)
    save_embeddings(X_f32, "embeddings/baseline_f16.npy", dtype=np.float16)
    console.print()

    # ── Relatório ─────────────────────────────────────────────────────────────
    _print_report(X_f32, model_name, final_device)


def _print_report(X: np.ndarray, model_name: str, device: str) -> None:
    """Imprime tabela de resumo da Fase 2."""
    from rich.table import Table

    n, d = X.shape
    f32_mb = n * d * 4 / 1_048_576
    f16_mb = n * d * 2 / 1_048_576

    table = Table(title="Fase 2 — Resumo dos embeddings", show_lines=True)
    table.add_column("Arquivo", style="cyan")
    table.add_column("Shape", justify="right")
    table.add_column("dtype", justify="center")
    table.add_column("Tamanho", justify="right")
    table.add_column("Compressão vs f32", justify="right")

    table.add_row("embeddings/baseline_f32.npy", f"[{n}, {d}]", "float32", f"{f32_mb:.2f} MB", "1×")
    table.add_row("embeddings/baseline_f16.npy", f"[{n}, {d}]", "float16", f"{f16_mb:.2f} MB", "2×")

    console.print(table)
    console.print(f"\n[bold green]✓ Fase 2 concluída.[/bold green]")
    console.print(f"  Modelo : {model_name}")
    console.print(f"  Device : {device}")
    console.print(f"  Vetores: {n}  |  Dimensão: {d}")
    console.print(f"\n  Próximo passo: [bold]make queries-pseudo[/bold]  (ground truth com top-1 f32)")
    console.print(f"  Ou:            [bold]make quantize-all[/bold]   (Fase 3)\n")
