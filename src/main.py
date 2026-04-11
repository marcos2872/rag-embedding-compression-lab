"""
src/main.py
-----------
CLI principal do RAG Embedding Compression Lab.

Uso:
    uv run python -m src.main <comando> [opções]
    # ou, após `uv sync`:
    lab <comando> [opções]

Comandos disponíveis por fase:
    Fase 1:  ingest, queries
    Fase 2:  embed
    Fase 3:  quantize
    Fase 4:  distortion-bench
    Fase 5:  build-indexes, retrieval-bench
    Fase 6:  visualize, report
    Fase 7:  rag-demo
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Annotated

import typer
import yaml
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table

load_dotenv()

app = typer.Typer(
    name="lab",
    help="RAG Embedding Compression Lab — CLI",
    add_completion=False,
)
console = Console()

# ── helpers ────────────────────────────────────────────────────────────────────

def _load_yaml(path: str) -> dict:
    with open(path) as f:
        return yaml.safe_load(f) or {}


def _dataset_cfg() -> dict:
    return _load_yaml("configs/dataset.yaml")


# ══════════════════════════════════════════════════════════════════════════════
# FASE 1 — Corpus & Queries
# ══════════════════════════════════════════════════════════════════════════════

@app.command()
def ingest(
    input: Annotated[
        Path,
        typer.Option("--input", "-i", help="Diretório com arquivos raw (PDF/TXT/MD)"),
    ] = Path("data/raw"),
    output: Annotated[
        Path,
        typer.Option("--output", "-o", help="Caminho de saída do corpus.jsonl"),
    ] = Path("data/corpus.jsonl"),
    chunk_size: Annotated[
        int,
        typer.Option("--chunk-size", help="Palavras por chunk"),
    ] = 0,
    chunk_overlap: Annotated[
        int,
        typer.Option("--chunk-overlap", help="Sobreposição entre chunks"),
    ] = 0,
    min_length: Annotated[
        int,
        typer.Option("--min-length", help="Tamanho mínimo do chunk (palavras)"),
    ] = 0,
) -> None:
    """Processa data/raw/ → corpus.jsonl (PDF + TXT + MD)."""
    cfg = _dataset_cfg()

    cs = chunk_size or cfg.get("chunk_size", 256)
    co = chunk_overlap or cfg.get("chunk_overlap", 32)
    ml = min_length or cfg.get("min_chunk_length", 50)

    from src.ingest import ingest as _ingest

    total = _ingest(
        input_dir=input,
        output_path=output,
        chunk_size=cs,
        chunk_overlap=co,
        min_chunk_length=ml,
    )

    if total == 0:
        console.print(
            "[red]Nenhum chunk gerado. Verifique se há arquivos em data/raw/[/red]"
        )
        raise typer.Exit(1)


@app.command()
def queries(
    strategy: Annotated[
        str,
        typer.Option(
            "--strategy",
            help="Estratégia de geração: 'pseudo' (requer embeddings) | "
                 "'first_sentence' (funciona sem embeddings)",
        ),
    ] = "first_sentence",
    topk: Annotated[
        int,
        typer.Option("--topk", help="Top-k para estratégia pseudo"),
    ] = 1,
    output: Annotated[
        Path,
        typer.Option("--output", "-o", help="Caminho de saída do queries.jsonl"),
    ] = Path("data/queries.jsonl"),
    corpus: Annotated[
        Path,
        typer.Option("--corpus", "-c", help="Caminho do corpus.jsonl"),
    ] = Path("data/corpus.jsonl"),
    max_queries: Annotated[
        int,
        typer.Option("--max-queries", help="Máximo de queries a gerar"),
    ] = 200,
) -> None:
    """
    Gera queries.jsonl com pares query → relevant_ids.

    Estratégias:
      first_sentence  Usa a primeira frase de cada chunk como query (Fase 1).
      pseudo          Usa top-1 f32 como ground truth (requer embeddings, Fase 2+).
    """
    from src.ingest import load_corpus
    corpus_docs = load_corpus(corpus)
    console.print(f"[cyan]Corpus carregado:[/cyan] {len(corpus_docs)} chunks\n")

    from src.ingest import queries_first_sentence, queries_pseudo

    if strategy == "first_sentence":
        pairs = queries_first_sentence(corpus_docs, max_queries)
    elif strategy == "pseudo":
        seed = int(os.getenv("RANDOM_SEED", "42"))
        pairs = queries_pseudo(corpus_docs, topk, max_queries, console, seed)
    else:
        console.print(f"[red]Estratégia desconhecida: {strategy}[/red]")
        raise typer.Exit(1)

    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as f:
        for pair in pairs:
            f.write(json.dumps(pair, ensure_ascii=False) + "\n")

    console.print(
        f"[bold green]✓ queries.jsonl gravado:[/bold green] "
        f"{len(pairs)} pares em {output}"
    )

    # Exibe amostra
    table = Table(title="Amostra de queries geradas", show_lines=True)
    table.add_column("Query", max_width=60)
    table.add_column("Relevant IDs", max_width=40)
    for pair in pairs[:5]:
        table.add_row(pair["query"], ", ".join(pair["relevant_ids"]))
    console.print(table)



# ══════════════════════════════════════════════════════════════════════════════
# FASE 2 — Embeddings (stub — implementado na Fase 2)
# ══════════════════════════════════════════════════════════════════════════════

@app.command()
def embed(
    device: Annotated[
        str | None,
        typer.Option("--device", help="cpu | cuda | mps | rocm"),
    ] = None,
) -> None:
    """Gera embeddings float32 e float16 (Fase 2)."""
    from src.embed import embed_pipeline
    embed_pipeline(device=device)


# ══════════════════════════════════════════════════════════════════════════════
# FASE 3 — Quantização (stub)
# ══════════════════════════════════════════════════════════════════════════════

@app.command()
def quantize(
    variant: Annotated[str, typer.Option("--variant", help="uniform | lloyd_max | turbo_mse | turbo_prod")] = "uniform",
    bits: Annotated[int, typer.Option("--bits", help="2 | 4 | 8")] = 8,
) -> None:
    """Quantiza os embeddings baseline (Fase 3)."""
    from src.quantization import quantize_pipeline
    quantize_pipeline(variant=variant, bits=bits)


# ══════════════════════════════════════════════════════════════════════════════
# FASE 4 — Distortion Benchmark (stub)
# ══════════════════════════════════════════════════════════════════════════════

@app.command(name="distortion-bench")
def distortion_bench() -> None:
    """Calcula MSE, cosine error e IP error por variante (Fase 4)."""
    from src.benchmark.distortion import run_distortion_bench
    run_distortion_bench()


# ══════════════════════════════════════════════════════════════════════════════
# FASE 5 — Retrieval Benchmark (stubs)
# ══════════════════════════════════════════════════════════════════════════════

@app.command(name="build-indexes")
def build_indexes() -> None:
    """Constrói índices FAISS para todas as variantes (Fase 5)."""
    from src.retrieval.faiss_store import build_all_indexes
    build_all_indexes()


@app.command(name="retrieval-bench")
def retrieval_bench(
    topk: Annotated[int, typer.Option("--topk", help="Top-k para busca")] = 10,
) -> None:
    """Recall@k, MRR, latência e memória por variante (Fase 5)."""
    from src.benchmark.retrieval_bench import run_retrieval_bench
    run_retrieval_bench(topk=topk)


# ══════════════════════════════════════════════════════════════════════════════
# FASE 6 — Visualizações (stubs)
# ══════════════════════════════════════════════════════════════════════════════

@app.command()
def visualize() -> None:
    """Gera todos os 8 gráficos estáticos + dashboard.html (Fase 6)."""
    from src.visualization.dashboard import generate_dashboard
    from src.visualization.plots import generate_all_plots
    generate_all_plots()
    console.print()
    generate_dashboard()


@app.command()
def report() -> None:
    """Gera relatório Markdown com análise das queries (Fase 6)."""
    from src.benchmark.reports import generate_report
    generate_report()


# ══════════════════════════════════════════════════════════════════════════════
# FASE 7 — RAG Demo (stub)
# ══════════════════════════════════════════════════════════════════════════════

@app.command(name="rag-demo")
def rag_demo(
    query: Annotated[str, typer.Option("--query", "-q", help="Pergunta para o RAG")] = "",
    variants: Annotated[
        str,
        typer.Option("--variants", help="Variantes separadas por vírgula"),
    ] = "f32,turbo_mse_4bit,uniform_2bit",
    k: Annotated[int, typer.Option("--k", help="Número de documentos a recuperar")] = 5,
    backend: Annotated[
        str | None,
        typer.Option("--backend", help="LLM backend: mock | ollama | openai"),
    ] = None,
    model: Annotated[
        str | None,
        typer.Option("--model", help="Nome do modelo LLM"),
    ] = None,
) -> None:
    """Demo interativo RAG: compara retrieval entre variantes (Fase 7)."""
    if not query:
        console.print("[red]--query é obrigatório. Uso: make rag-demo QUERY='sua pergunta'[/red]")
        raise typer.Exit(1)
    from src.rag.pipeline import run_demo
    run_demo(
        query    = query,
        variants = [v.strip() for v in variants.split(",")],
        k        = k,
        llm_backend = backend,
        llm_model   = model,
    )


# ══════════════════════════════════════════════════════════════════════════════
# Entry point
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    app()
