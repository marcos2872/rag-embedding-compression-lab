"""
src/benchmark/retrieval_bench.py
----------------------------------
Fase 5 — Benchmark de Retrieval.

Fluxo:
  1. Carrega queries.jsonl  →  textos + relevant_ids
  2. Embeda os textos das queries (mesmo modelo, normalize=True)
  3. Para cada variante:
       a. Carrega (ou constrói) o índice FAISS
       b. Busca top-k para todas as queries de uma vez
       c. Mapeia índices → corpus IDs
       d. Calcula Recall@1, @5, @10 e MRR
       e. Mede latência mediana (ms/query)
  4. Agrega em DataFrame e salva reports/benchmark_results.csv
  5. Imprime tabela rica e gera 2 gráficos

Sobre embed_size_mb:
  Mede o tamanho teórico dos DADOS de embedding (sem overhead de R/S),
  ou seja, o que importa para armazenar N embeddings em produção.
"""

from __future__ import annotations

import json
import math
import os
import time
from pathlib import Path

import numpy as np
import pandas as pd
from rich.console import Console
from rich.progress import track
from rich.table import Table

from src.retrieval.faiss_store import build_index, load_index, save_index, _load_variant_embeddings
from src.retrieval.metrics import recall_at_k, mrr, mean_latency_ms

console = Console()


# ── Constantes ─────────────────────────────────────────────────────────────────

VARIANTS = ["uniform", "lloyd_max", "turbo_mse", "turbo_prod"]
BITS     = [2, 4, 8]
K_LIST   = [1, 5, 10]


# ── Embedding das queries ──────────────────────────────────────────────────────

def embed_queries(
    query_texts: list[str],
    model_name: str | None = None,
    device: str | None = None,
) -> np.ndarray:
    """
    Embeda os textos das queries usando o mesmo modelo/normalização do corpus.
    Retorna [num_q, D] float32.
    """
    import yaml
    from dotenv import load_dotenv
    load_dotenv()

    if model_name is None:
        cfg = yaml.safe_load(open("configs/embedding.yaml")) or {}
        model_name = os.getenv("EMBEDDING_MODEL") or cfg.get("model", "BAAI/bge-small-en-v1.5")
    if device is None:
        device = os.getenv("EMBEDDING_DEVICE", "cpu")

    from sentence_transformers import SentenceTransformer
    console.print(f"  [cyan]Embedando {len(query_texts)} queries[/cyan]  modelo={model_name}  device={device}")
    model = SentenceTransformer(model_name, device=device)
    vecs = model.encode(
        query_texts,
        normalize_embeddings=True,
        convert_to_numpy=True,
        show_progress_bar=False,
        batch_size=64,
    )
    return vecs.astype(np.float32)


# ── Tamanho teórico dos embeddings ─────────────────────────────────────────────

def _embed_size_mb(variant: str, bits: int, N: int, D: int) -> float:
    """Bytes de dados de embedding por vetor × N, em MB."""
    if variant == "baseline_f32":
        bpv = D * 4
    elif variant == "baseline_f16":
        bpv = D * 2
    elif variant in ("uniform", "lloyd_max", "turbo_mse"):
        bpv = math.ceil(D * bits / 8) + 2           # índices packed + norma f16
    elif variant == "turbo_prod":
        mse_bits = bits - 1
        bpv = (math.ceil(D * mse_bits / 8) if mse_bits > 0 else 0) + 2 + math.ceil(D / 8) + 2
    else:
        bpv = D * 4
    return N * bpv / 1_048_576


# ── Busca em um índice ─────────────────────────────────────────────────────────

def _search_index(
    index: "faiss.Index",
    Q: np.ndarray,
    k: int,
    corpus_ids: list[str],
) -> list[list[str]]:
    """Busca top-k e mapeia índices FAISS para corpus IDs."""
    _, I = index.search(Q, k)
    return [
        [corpus_ids[j] for j in row if 0 <= j < len(corpus_ids)]
        for row in I
    ]


# ── Pipeline principal ─────────────────────────────────────────────────────────

def run_retrieval_bench(topk: int = 10) -> pd.DataFrame:
    """Entry point chamado pelo CLI."""

    console.print("\n[bold cyan]Fase 5 — Benchmark de Retrieval[/bold cyan]\n")

    # ── Carrega dados ──────────────────────────────────────────────────────────
    corpus = [json.loads(l) for l in Path("data/corpus.jsonl").read_text().splitlines()]
    queries_raw = [json.loads(l) for l in Path("data/queries.jsonl").read_text().splitlines()]
    corpus_ids = [d["id"] for d in corpus]
    N, D = len(corpus), np.load("embeddings/baseline_f32.npy").shape[1]

    console.print(f"  Corpus : {N} chunks  |  dim={D}")
    console.print(f"  Queries: {len(queries_raw)}")

    q_texts   = [q["query"]        for q in queries_raw]
    q_relevant = [q["relevant_ids"] for q in queries_raw]

    # ── Embeda queries ─────────────────────────────────────────────────────────
    Q = embed_queries(q_texts)
    console.print()

    # ── Lista de variantes a avaliar ───────────────────────────────────────────
    tasks: list[tuple[str, int, Path]] = []

    f32_path = Path("indexes/faiss_f32.index")
    f16_path = Path("indexes/faiss_f16.index")

    if not f32_path.exists():
        console.print("[yellow]  Índices não encontrados. Construindo agora…[/yellow]")
        from src.retrieval.faiss_store import build_all_indexes
        build_all_indexes()
        console.print()

    tasks.append(("baseline_f32", 32, f32_path))
    tasks.append(("baseline_f16", 16, f16_path))
    for v in VARIANTS:
        for b in BITS:
            tasks.append((v, b, Path(f"indexes/faiss_{v}_{b}bit.index")))

    # ── Avalia cada variante ───────────────────────────────────────────────────
    rows: list[dict] = []
    k_max = max(K_LIST + [topk, 50])   # top-50 para ranks detalhados
    per_query_ranks: dict[str, list[int]] = {}  # chave = "variant_bits"

    for variant, bits, index_path in track(tasks, description="Avaliando variantes…"):
        if not index_path.exists():
            console.print(f"  [yellow]⚠ {index_path.name} não encontrado — pulando[/yellow]")
            continue

        index = load_index(index_path)

        # Resultados
        retrieved = _search_index(index, Q, k_max, corpus_ids)

        # Rank por query (posição do 1º relevante; 9999 se não encontrado no top-50)
        key = f"{variant}_{bits}"
        ranks: list[int] = []
        for ret, rel in zip(retrieved, q_relevant):
            rel_set = set(rel)
            rank = next((r + 1 for r, d in enumerate(ret) if d in rel_set), 9999)
            ranks.append(rank)
        per_query_ranks[key] = ranks

        # Métricas de qualidade
        row: dict = {"variant": variant, "bits": bits}
        for k in K_LIST:
            row[f"recall_at_{k}"] = round(recall_at_k(retrieved, q_relevant, k), 4)
        row["mrr"] = round(mrr(retrieved, q_relevant), 4)

        # Latência
        lat = mean_latency_ms(
            lambda q, k: index.search(q, k),
            Q, k=topk, n_runs=5,
        )
        row["latency_ms"] = round(lat, 4)

        # Tamanhos
        row["index_size_mb"]  = round(index_path.stat().st_size / 1_048_576, 4)
        row["embed_size_mb"]  = round(_embed_size_mb(variant, bits, N, D), 4)
        f32_mb = _embed_size_mb("baseline_f32", 32, N, D)
        row["compression_vs_f32"] = round(f32_mb / row["embed_size_mb"], 2)

        rows.append(row)

    df = pd.DataFrame(rows)

    # Ordena
    order_map = {"baseline_f32": 0, "baseline_f16": 1,
                 "uniform": 2, "lloyd_max": 3, "turbo_mse": 4, "turbo_prod": 5}
    df["_ord"] = df["variant"].map(order_map).fillna(99)
    df = df.sort_values(["_ord", "bits"], ascending=[True, False]).drop(columns="_ord")
    df = df.reset_index(drop=True)

    # ── Salva CSVs ─────────────────────────────────────────────────────────────
    Path("reports").mkdir(exist_ok=True)
    csv_path = Path("reports/benchmark_results.csv")
    df.to_csv(csv_path, index=False)
    console.print(f"\n[green]✓ CSV salvo:[/green] {csv_path}  ({len(df)} linhas)")

    # Salva ranks por query para relatório e gráfico 7
    ranks_df = pd.DataFrame(per_query_ranks)
    ranks_df["query"] = [q["query"][:80] for q in queries_raw]
    ranks_df["relevant_id"] = [q["relevant_ids"][0] for q in queries_raw]
    ranks_path = Path("reports/per_query_ranks.csv")
    ranks_df.to_csv(ranks_path, index=False)
    console.print(f"[green]✓ CSV salvo:[/green] {ranks_path}  ({len(ranks_df)} linhas)\n")

    # Salva query embeddings para reutilização
    np.save("embeddings/query_embeddings.npy", Q)
    console.print(f"[green]✓ Query embeddings salvos:[/green] embeddings/query_embeddings.npy\n")

    # ── Exibe tabela ───────────────────────────────────────────────────────────
    _print_table(df)

    # ── Gráficos ───────────────────────────────────────────────────────────────
    Path("charts").mkdir(exist_ok=True)
    _plot_recall_vs_bits(df)
    _plot_tradeoff(df)

    return df


# ── Exibição ───────────────────────────────────────────────────────────────────

def _print_table(df: pd.DataFrame) -> None:
    t = Table(title="Benchmark de Retrieval", show_lines=True)
    t.add_column("Variante",        style="cyan", min_width=14)
    t.add_column("bits",            justify="right", min_width=4)
    t.add_column("R@1",             justify="right", min_width=6)
    t.add_column("R@5",             justify="right", min_width=6)
    t.add_column("R@10",            justify="right", min_width=6)
    t.add_column("MRR",             justify="right", min_width=6)
    t.add_column("ms/q",            justify="right", min_width=7)
    t.add_column("MB (vetor)",      justify="right", min_width=10)
    t.add_column("Compress.",       justify="right", min_width=9)

    for _, row in df.iterrows():
        style = ""
        if row["variant"] in ("turbo_mse", "turbo_prod") and row["bits"] == 4:
            style = "bold green"
        t.add_row(
            str(row["variant"]),
            str(int(row["bits"])),
            f"{row['recall_at_1']:.3f}",
            f"{row['recall_at_5']:.3f}",
            f"{row['recall_at_10']:.3f}",
            f"{row['mrr']:.3f}",
            f"{row['latency_ms']:.3f}",
            f"{row['embed_size_mb']:.3f}",
            f"{row['compression_vs_f32']:.1f}×",
            style=style,
        )

    console.print(t)


# ── Gráficos ───────────────────────────────────────────────────────────────────

def _plot_recall_vs_bits(df: pd.DataFrame) -> None:
    """Line chart: Recall@10 vs bits para cada variante."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    variants = ["uniform", "lloyd_max", "turbo_mse", "turbo_prod"]
    colors   = ["#4878CF", "#6ACC65", "#D65F5F", "#B47CC7"]
    labels   = ["Uniform", "Lloyd-Max", "TurboQuantMSE", "TurboQuantProd"]
    bits_list = [2, 4, 8]

    fig, axes = plt.subplots(1, 3, figsize=(14, 4.5), sharey=False)
    k_vals = [1, 5, 10]

    for ax, k in zip(axes, k_vals):
        col = f"recall_at_{k}"
        for var, color, label in zip(variants, colors, labels):
            sub = df[df["variant"] == var].set_index("bits")
            ys = [sub.loc[b, col] if b in sub.index else float("nan") for b in bits_list]
            ax.plot(bits_list, ys, marker="o", color=color, label=label, linewidth=2)

        # Baselines
        for bname, bstyle, bcol in [("baseline_f32", "--", "black"), ("baseline_f16", ":", "gray")]:
            brow = df[df["variant"] == bname]
            if not brow.empty:
                val = brow[col].values[0]
                ax.axhline(val, linestyle=bstyle, color=bcol, linewidth=1.2,
                           label=bname.replace("baseline_", ""))

        ax.set_xticks(bits_list)
        ax.set_xticklabels([f"{b}b" for b in bits_list])
        ax.set_xlabel("Bits por dimensão", fontsize=10)
        ax.set_ylabel(f"Recall@{k}", fontsize=10)
        ax.set_title(f"Recall@{k} vs Bits", fontsize=11, fontweight="bold")
        ax.set_ylim(0, 1.05)
        ax.grid(alpha=0.3)
        ax.legend(fontsize=8)

    fig.suptitle("Qualidade de Retrieval por Variante e Bits", fontsize=13, fontweight="bold")
    fig.tight_layout()
    out = Path("charts/recall_vs_bits.png")
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    console.print(f"[green]✓ Gráfico salvo:[/green] {out}")


def _plot_tradeoff(df: pd.DataFrame) -> None:
    """Scatter plot: Recall@10 vs embed_size_mb (Pareto frontier)."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    variants = ["baseline_f32", "baseline_f16", "uniform", "lloyd_max", "turbo_mse", "turbo_prod"]
    colors   = ["black", "gray", "#4878CF", "#6ACC65", "#D65F5F", "#B47CC7"]
    markers  = ["*", "D", "o", "s", "^", "P"]

    fig, ax = plt.subplots(figsize=(9, 6))

    # Coleta todos os pontos para fronteira de Pareto
    all_pts: list[tuple[float, float]] = []

    for var, color, marker in zip(variants, colors, markers):
        sub = df[df["variant"] == var]
        if sub.empty:
            continue
        xs = sub["embed_size_mb"].values
        ys = sub["recall_at_10"].values
        bits_vals = sub["bits"].values

        ax.scatter(xs, ys, color=color, marker=marker, s=80, zorder=5, label=var.replace("baseline_", ""))

        for x, y, b in zip(xs, ys, bits_vals):
            label_txt = f"{b}b" if var not in ("baseline_f32", "baseline_f16") else var.replace("baseline_", "")
            ax.annotate(
                label_txt, (x, y),
                textcoords="offset points", xytext=(5, 5),
                fontsize=7, color=color,
            )
            all_pts.append((x, y))

    # Fronteira de Pareto (maior recall para menor memória)
    pts = sorted(all_pts, key=lambda p: p[0])
    pareto: list[tuple[float, float]] = []
    best_y = -1.0
    for x, y in pts:
        if y > best_y:
            pareto.append((x, y))
            best_y = y
    if len(pareto) > 1:
        px, py = zip(*pareto)
        ax.step(px, py, where="post", color="orange", linewidth=1.5,
                linestyle="--", label="Fronteira de Pareto", zorder=3)

    ax.set_xscale("log")
    ax.set_xlabel("Tamanho dos embeddings (MB) — escala log", fontsize=11)
    ax.set_ylabel("Recall@10", fontsize=11)
    ax.set_title("Trade-off: Qualidade de Retrieval × Memória", fontsize=12, fontweight="bold")
    ax.legend(fontsize=9, loc="lower right")
    ax.grid(alpha=0.3)
    fig.tight_layout()

    out = Path("charts/tradeoff_recall_memory.png")
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    console.print(f"[green]✓ Gráfico salvo:[/green] {out}")
