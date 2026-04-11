"""
src/benchmark/distortion.py
-----------------------------
Fase 4 — Benchmark de distorção.

Mede quanto cada variante de quantização deforma os vetores ANTES de testar retrieval.

Métricas calculadas para cada variante × bits:
  MSE          — erro geométrico médio (||x - x̂||² médio)
  cosine_error — quanto a direção mudou  (1 - cos_sim médio)
  ip_bias      — viés sistemático no produto interno  E[q·x̂ - q·x]
  ip_mae       — magnitude média do erro de IP  E[|q·x̂ - q·x|]
  ip_variance  — variância do erro de IP  Var[q·x̂ - q·x]

Como as queries são extraídas:
  queries.jsonl contém relevant_ids → índices no corpus → embeddings em baseline_f32.
  Isso evita re-embedar texto e garante queries do mesmo espaço vetorial.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from rich.console import Console
from rich.progress import track

console = Console()


# ── Métricas individuais ───────────────────────────────────────────────────────

def mse(X_orig: np.ndarray, X_hat: np.ndarray) -> float:
    """MSE médio sobre todos os vetores: mean(||x - x̂||²)."""
    return float(np.mean((X_orig - X_hat) ** 2))


def cosine_error(X_orig: np.ndarray, X_hat: np.ndarray) -> float:
    """
    Erro de cosseno: 1 - cosine_similarity médio.
    Para vetores normalizados: cosine_sim = dot product.
    Valor positivo = perda de direção.
    """
    norms_orig = np.linalg.norm(X_orig, axis=1, keepdims=True)
    norms_hat  = np.linalg.norm(X_hat,  axis=1, keepdims=True)
    # Evita divisão por zero
    safe_orig = np.where(norms_orig == 0, 1.0, norms_orig)
    safe_hat  = np.where(norms_hat  == 0, 1.0, norms_hat)
    cos_sim = np.einsum(
        "ij,ij->i",
        X_orig / safe_orig,
        X_hat  / safe_hat,
    )
    return float(1.0 - np.mean(cos_sim))


def ip_errors(
    X_orig: np.ndarray,
    X_hat: np.ndarray,
    Q: np.ndarray,
) -> dict[str, float]:
    """
    Erros de produto interno entre query embeddings Q e documentos X.

    Calcula para cada par (query_i, doc_j):
      error_{ij} = (Q_i · X_hat_j) - (Q_i · X_orig_j)

    Retorna: {bias, mae, variance} sobre todos os pares.

    Q      : [num_q, D]
    X_orig : [N, D]
    X_hat  : [N, D]
    """
    # [num_q, N] — produtos internos exatos e aproximados
    ip_orig = Q @ X_orig.T
    ip_hat  = Q @ X_hat.T
    errors  = ip_hat - ip_orig          # [num_q, N]

    return {
        "ip_bias":     float(np.mean(errors)),
        "ip_mae":      float(np.mean(np.abs(errors))),
        "ip_variance": float(np.var(errors)),
    }


# ── Carregamento de variantes ──────────────────────────────────────────────────

def _dequantize_variant(variant: str, bits: int) -> np.ndarray | None:
    """
    Carrega e dequantiza uma variante específica.
    Retorna array [N, D] float32 ou None se o arquivo não existir.
    """
    from src.quantization.loader import load_and_dequantize
    return load_and_dequantize(variant, bits)


# ── Query matrix ───────────────────────────────────────────────────────────────

def build_query_matrix(
    X_orig: np.ndarray,
    queries_path: str | Path = "data/queries.jsonl",
    corpus_path:  str | Path = "data/corpus.jsonl",
    n_queries: int = 100,
    seed: int = 42,
) -> np.ndarray:
    """
    Constrói uma matriz de query vectors usando embeddings já calculados.

    Estratégia: lê queries.jsonl → relevant_ids → índice no corpus →
    usa os vetores correspondentes de baseline_f32 como queries.
    Isso evita re-embedar e garante vetores no mesmo espaço.

    Retorna Q : [n_queries, D] float32
    """
    # Mapa id → índice no corpus
    id_to_idx: dict[str, int] = {}
    with open(corpus_path, encoding="utf-8") as f:
        for i, line in enumerate(f):
            doc = json.loads(line)
            id_to_idx[doc["id"]] = i

    # Coleta índices a partir dos relevant_ids das queries
    query_indices: list[int] = []
    with open(queries_path, encoding="utf-8") as f:
        for line in f:
            q = json.loads(line)
            for rid in q["relevant_ids"]:
                if rid in id_to_idx:
                    query_indices.append(id_to_idx[rid])
                    break  # 1 vetor por query

    if not query_indices:
        # Fallback: amostra aleatória do corpus
        rng = np.random.default_rng(seed)
        query_indices = rng.choice(len(X_orig), size=min(n_queries, len(X_orig)), replace=False).tolist()

    # Remove duplicatas mantendo ordem
    seen: set[int] = set()
    unique: list[int] = []
    for idx in query_indices:
        if idx not in seen:
            seen.add(idx)
            unique.append(idx)

    # Limita a n_queries
    rng = np.random.default_rng(seed)
    if len(unique) > n_queries:
        chosen = rng.choice(len(unique), size=n_queries, replace=False)
        unique = [unique[i] for i in sorted(chosen)]

    console.print(f"  [cyan]Query vectors:[/cyan] {len(unique)} vetores extraídos do corpus")
    return X_orig[unique].copy()


# ── Pipeline principal ─────────────────────────────────────────────────────────

VARIANTS = ["uniform", "lloyd_max", "turbo_mse", "turbo_prod"]
BITS     = [2, 4, 8]


def compute_distortion_table(
    X_orig: np.ndarray,
    Q: np.ndarray,
) -> pd.DataFrame:
    """
    Calcula todas as métricas de distorção para todas as variantes.
    Inclui baselines f32 e f16.

    Retorna DataFrame com colunas:
      variant, bits, mse, cosine_error, ip_bias, ip_mae, ip_variance
    """
    rows: list[dict] = []

    # — Baselines —
    rows.append({
        "variant": "baseline_f32", "bits": 32,
        "mse": 0.0, "cosine_error": 0.0,
        "ip_bias": 0.0, "ip_mae": 0.0, "ip_variance": 0.0,
    })

    X_f16 = np.load("embeddings/baseline_f16.npy").astype(np.float32)
    ip_f16 = ip_errors(X_orig, X_f16, Q)
    rows.append({
        "variant": "baseline_f16", "bits": 16,
        "mse":          mse(X_orig, X_f16),
        "cosine_error": cosine_error(X_orig, X_f16),
        **ip_f16,
    })

    # — Variantes quantizadas —
    all_tasks = [(v, b) for v in VARIANTS for b in BITS]

    for variant, bits in track(all_tasks, description="Calculando métricas…"):
        X_hat = _dequantize_variant(variant, bits)
        if X_hat is None:
            console.print(f"  [yellow]⚠ {variant}_{bits}bit não encontrado — pulando[/yellow]")
            continue

        ip_m = ip_errors(X_orig, X_hat, Q)
        rows.append({
            "variant":      variant,
            "bits":         bits,
            "mse":          mse(X_orig, X_hat),
            "cosine_error": cosine_error(X_orig, X_hat),
            **ip_m,
        })

    df = pd.DataFrame(rows)
    # Ordena: baselines primeiro, depois por bits decrescente dentro de cada variante
    order = {"baseline_f32": 0, "baseline_f16": 1,
             "uniform": 2, "lloyd_max": 3, "turbo_mse": 4, "turbo_prod": 5}
    df["_order"] = df["variant"].map(order).fillna(99)
    df = df.sort_values(["_order", "bits"], ascending=[True, False]).drop(columns="_order")
    return df.reset_index(drop=True)


def run_distortion_bench() -> pd.DataFrame:
    """Entry point chamado pelo CLI. Gera CSV + 2 gráficos."""
    import os

    console.print("\n[bold cyan]Fase 4 — Benchmark de Distorção[/bold cyan]\n")

    # Carrega embeddings originais
    X_orig = np.load("embeddings/baseline_f32.npy").astype(np.float32)
    console.print(f"  Embeddings: {X_orig.shape}  dtype={X_orig.dtype}")

    # Constrói query matrix
    seed = int(os.getenv("RANDOM_SEED", "42"))
    Q = build_query_matrix(X_orig, seed=seed)
    console.print()

    # Calcula métricas
    df = compute_distortion_table(X_orig, Q)

    # Salva CSV
    Path("reports").mkdir(exist_ok=True)
    csv_path = Path("reports/distortion_results.csv")
    df.to_csv(csv_path, index=False, float_format="%.8f")
    console.print(f"\n[green]✓ CSV salvo:[/green] {csv_path}  ({len(df)} linhas)\n")

    # Exibe tabela resumo
    _print_table(df)

    # Gera gráficos
    Path("charts").mkdir(exist_ok=True)
    _plot_mse_vs_bits(df)
    _plot_ip_heatmap(df)

    return df


# ── Exibição ───────────────────────────────────────────────────────────────────

def _print_table(df: pd.DataFrame) -> None:
    from rich.table import Table

    t = Table(title="Distorção por variante", show_lines=True)
    t.add_column("Variante",      style="cyan",   min_width=15)
    t.add_column("bits",          justify="right", min_width=4)
    t.add_column("MSE",           justify="right", min_width=10)
    t.add_column("Cosine Error",  justify="right", min_width=12)
    t.add_column("IP Bias",       justify="right", min_width=10)
    t.add_column("IP MAE",        justify="right", min_width=10)
    t.add_column("IP Variance",   justify="right", min_width=12)

    for _, row in df.iterrows():
        def fmt(v: float) -> str:
            if v == 0.0:
                return "0.0"
            return f"{v:.6f}"

        # Destaca turbo_mse e turbo_prod a 4-bit
        style = ""
        if row["variant"] in ("turbo_mse", "turbo_prod") and row["bits"] == 4:
            style = "bold green"

        t.add_row(
            row["variant"], str(int(row["bits"])),
            fmt(row["mse"]),
            fmt(row["cosine_error"]),
            fmt(row["ip_bias"]),
            fmt(row["ip_mae"]),
            fmt(row["ip_variance"]),
            style=style,
        )

    console.print(t)


# ── Gráficos ───────────────────────────────────────────────────────────────────

def _plot_mse_vs_bits(df: pd.DataFrame) -> None:
    """
    Gráfico de barras agrupado: MSE (escala log) por bits, uma barra por variante.
    Salva em charts/mse_vs_bits.png.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.ticker as mticker
    import numpy as np

    variants    = ["uniform", "lloyd_max", "turbo_mse", "turbo_prod"]
    bits_list   = [8, 4, 2]
    colors      = ["#4878CF", "#6ACC65", "#D65F5F", "#B47CC7"]
    labels      = ["Uniform", "Lloyd-Max", "TurboQuantMSE", "TurboQuantProd"]

    x      = np.arange(len(bits_list))
    width  = 0.18
    fig, ax = plt.subplots(figsize=(9, 5))

    for i, (var, color, label) in enumerate(zip(variants, colors, labels, strict=True)):
        sub = df[df["variant"] == var].set_index("bits")
        vals = [sub.loc[b, "mse"] if b in sub.index else np.nan for b in bits_list]
        offset = (i - 1.5) * width
        ax.bar(x + offset, vals, width, label=label, color=color, alpha=0.85, edgecolor="white")

    # Baselines como linhas horizontais
    f16_mse = df[df["variant"] == "baseline_f16"]["mse"].values
    if len(f16_mse) > 0 and f16_mse[0] > 0:
        ax.axhline(f16_mse[0], color="gray", linestyle="--", linewidth=1.2, label=f"float16 ({f16_mse[0]:.2e})")

    ax.set_yscale("log")
    ax.set_xticks(x)
    ax.set_xticklabels([f"{b}-bit" for b in bits_list], fontsize=11)
    ax.set_xlabel("Bits por dimensão", fontsize=12)
    ax.set_ylabel("MSE (escala log)", fontsize=12)
    ax.set_title("MSE por variante e nível de bits", fontsize=13, fontweight="bold")
    ax.legend(fontsize=9, loc="upper right")
    ax.yaxis.set_major_formatter(mticker.LogFormatterSciNotation())
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()

    out = Path("charts/mse_vs_bits.png")
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    console.print(f"[green]✓ Gráfico salvo:[/green] {out}")


def _plot_ip_heatmap(df: pd.DataFrame) -> None:
    """
    Heatmap: linhas = métricas de IP, colunas = variante_bits.
    Verde = erro baixo, vermelho = erro alto.
    Salva em charts/ip_error_heatmap.png.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    # Seleciona apenas variantes quantizadas (sem baselines)
    quant_df = df[~df["variant"].str.startswith("baseline")].copy()
    quant_df["label"] = quant_df["variant"].str.replace("_", "\n") + "\n" + quant_df["bits"].astype(str) + "b"

    metrics = ["ip_bias", "ip_mae", "ip_variance"]
    metric_labels = ["IP Bias", "IP MAE", "IP Variance"]

    data = quant_df[metrics].values.T   # [3, num_variants]
    col_labels = quant_df["label"].tolist()

    fig, ax = plt.subplots(figsize=(max(10, len(col_labels) * 0.85), 4))

    # Normaliza por coluna (0=melhor, 1=pior) para coloração
    data_norm = np.zeros_like(data, dtype=float)
    for i in range(data.shape[0]):
        row = data[i]
        val_range = row.max() - row.min()
        data_norm[i] = (row - row.min()) / val_range if val_range > 0 else np.zeros_like(row)

    im = ax.imshow(data_norm, cmap="RdYlGn_r", aspect="auto", vmin=0, vmax=1)

    # Anota células com valor real
    for i in range(data.shape[0]):
        for j in range(data.shape[1]):
            v = data[i, j]
            txt = f"{v:.1e}" if abs(v) < 0.001 else f"{v:.4f}"
            ax.text(j, i, txt, ha="center", va="center", fontsize=7,
                    color="black" if data_norm[i, j] < 0.75 else "white")

    ax.set_xticks(range(len(col_labels)))
    ax.set_xticklabels(col_labels, fontsize=8)
    ax.set_yticks(range(len(metrics)))
    ax.set_yticklabels(metric_labels, fontsize=10)
    ax.set_title("Erros de Produto Interno por variante e bits\n(verde=baixo, vermelho=alto)", fontsize=11, fontweight="bold")
    fig.colorbar(im, ax=ax, label="Intensidade normalizada", fraction=0.02, pad=0.02)
    fig.tight_layout()

    out = Path("charts/ip_error_heatmap.png")
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    console.print(f"[green]✓ Gráfico salvo:[/green] {out}")
