"""
src/visualization/plots.py
----------------------------
Fase 6 — Todos os 8 gráficos estáticos do lab.

Gráficos gerados:
  1. recall_vs_bits.png              — Recall@k × bits por variante
  2. mse_vs_bits.png                 — MSE (log) × bits por variante
  3. memory_compression.png          — Barras horizontais de tamanho em MB
  4. latency_comparison.png          — Latência por variante
  5. tradeoff_recall_memory.png ⭐   — Scatter qualidade × memória (Pareto)
  6. ip_error_heatmap.png            — Heatmap de erros de produto interno
  7. recall_degradation_per_query.png— Violin/box: rank do relevante por variante
  8. compression_ratio_vs_recall_loss.png — Dual-axis: compressão × perda de recall
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd
from rich.console import Console

console = Console()

# ── Paleta e labels ────────────────────────────────────────────────────────────
VARIANTS = ["uniform", "lloyd_max", "turbo_mse", "turbo_prod"]
COLORS   = {"uniform": "#4878CF", "lloyd_max": "#6ACC65",
            "turbo_mse": "#D65F5F", "turbo_prod": "#B47CC7",
            "baseline_f32": "black", "baseline_f16": "#888888"}
LABELS   = {"uniform": "Uniform", "lloyd_max": "Lloyd-Max",
            "turbo_mse": "TurboQuantMSE", "turbo_prod": "TurboQuantProd",
            "baseline_f32": "float32", "baseline_f16": "float16"}
MARKERS  = {"uniform": "o", "lloyd_max": "s", "turbo_mse": "^",
            "turbo_prod": "P", "baseline_f32": "*", "baseline_f16": "D"}
BITS_LIST = [2, 4, 8]


def _savefig(fig: plt.Figure, name: str) -> None:
    out = Path(f"charts/{name}")
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    console.print(f"  [green]✓[/green] {out}")


# ══════════════════════════════════════════════════════════════════════════════
# 1. Recall @ k vs Bits
# ══════════════════════════════════════════════════════════════════════════════

def plot_recall_vs_bits(bench: pd.DataFrame) -> None:
    """Line chart: Recall@1/5/10 × bits — uma linha por variante."""
    fig, axes = plt.subplots(1, 3, figsize=(15, 5), sharey=False)

    for ax, k in zip(axes, [1, 5, 10], strict=True):
        col = f"recall_at_{k}"
        for var in VARIANTS:
            sub = bench[bench["variant"] == var].set_index("bits")
            ys  = [sub.loc[b, col] if b in sub.index else np.nan for b in BITS_LIST]
            ax.plot(BITS_LIST, ys, marker=MARKERS[var], color=COLORS[var],
                    label=LABELS[var], linewidth=2.2, markersize=7)

        for bname, ls in [("baseline_f32", "--"), ("baseline_f16", ":")]:
            row = bench[bench["variant"] == bname]
            if not row.empty:
                val = row[col].values[0]
                ax.axhline(val, linestyle=ls, color=COLORS[bname], linewidth=1.3,
                           label=LABELS[bname], alpha=0.8)

        ax.set_xticks(BITS_LIST)
        ax.set_xticklabels([f"{b}-bit" for b in BITS_LIST])
        ax.set_xlabel("Bits por dimensão", fontsize=11)
        ax.set_ylabel(f"Recall@{k}", fontsize=11)
        ax.set_title(f"Recall@{k} vs Bits", fontsize=12, fontweight="bold")
        ax.set_ylim(0, 1.08)
        ax.grid(alpha=0.3)
        ax.legend(fontsize=8, loc="lower right")

    fig.suptitle("Qualidade de Retrieval por Variante e Nível de Bits",
                 fontsize=14, fontweight="bold", y=1.01)
    fig.tight_layout()
    _savefig(fig, "recall_vs_bits.png")


# ══════════════════════════════════════════════════════════════════════════════
# 2. MSE vs Bits
# ══════════════════════════════════════════════════════════════════════════════

def plot_mse_vs_bits(dist: pd.DataFrame) -> None:
    """Bar chart agrupado: MSE (log) por bits × variante."""
    x     = np.arange(len(BITS_LIST))
    width = 0.18
    fig, ax = plt.subplots(figsize=(9, 5))

    for i, var in enumerate(VARIANTS):
        sub  = dist[dist["variant"] == var].set_index("bits")
        vals = [sub.loc[b, "mse"] if b in sub.index else np.nan for b in BITS_LIST]
        ax.bar(x + (i - 1.5) * width, vals, width,
               label=LABELS[var], color=COLORS[var], alpha=0.85, edgecolor="white")

    # baseline f16
    row = dist[dist["variant"] == "baseline_f16"]
    if not row.empty and row["mse"].values[0] > 0:
        ax.axhline(row["mse"].values[0], color=COLORS["baseline_f16"],
                   linestyle=":", linewidth=1.3, label="float16")

    ax.set_yscale("log")
    ax.set_xticks(x)
    ax.set_xticklabels([f"{b}-bit" for b in BITS_LIST], fontsize=11)
    ax.set_xlabel("Bits por dimensão", fontsize=12)
    ax.set_ylabel("MSE (escala log)", fontsize=12)
    ax.set_title("Distorção Geométrica (MSE) por Variante e Bits",
                 fontsize=13, fontweight="bold")
    ax.legend(fontsize=9)
    ax.yaxis.set_major_formatter(mticker.LogFormatterSciNotation())
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    _savefig(fig, "mse_vs_bits.png")


# ══════════════════════════════════════════════════════════════════════════════
# 3. Compressão de Memória
# ══════════════════════════════════════════════════════════════════════════════

def plot_memory_compression(bench: pd.DataFrame) -> None:
    """Barras horizontais: embed_size_mb por variante+bits, cor = compressão."""
    # Monta lista ordenada: f32, f16, depois variantes por bits desc
    rows_sel = []
    for var in ["baseline_f32", "baseline_f16"] + VARIANTS:
        sub = bench[bench["variant"] == var].sort_values("bits", ascending=False)
        for _, r in sub.iterrows():
            rows_sel.append(r)

    labels_y = []
    xs       = []
    colors_b = []
    compressions = []

    cmap = plt.cm.RdYlGn
    for r in rows_sel:
        var = r["variant"]
        bits = int(r["bits"])
        mb   = r["embed_size_mb"]
        comp = r["compression_vs_f32"]
        lbl  = f"{var}  {bits}-bit" if var.startswith("base") is False else var.replace("baseline_", "float")
        labels_y.append(lbl)
        xs.append(mb)
        compressions.append(comp)
        # Cor: comp normalizada [1x, 16x] → [0,1]
        colors_b.append(cmap(min((comp - 1) / 15, 1.0)))

    n  = len(labels_y)
    y  = np.arange(n)
    fig, ax = plt.subplots(figsize=(10, max(6, n * 0.42)))

    ax.barh(y, xs, color=colors_b, edgecolor="white", height=0.7)

    for i, (mb, comp) in enumerate(zip(xs, compressions, strict=True)):
        ax.text(mb + 0.003, i, f"{mb:.3f} MB  ({comp:.1f}×)",
                va="center", fontsize=8.5, color="#333333")

    ax.set_yticks(y)
    ax.set_yticklabels(labels_y, fontsize=9)
    ax.set_xlabel("Tamanho dos embeddings (MB)", fontsize=11)
    ax.set_title("Compressão de Memória por Variante\n(dados de embedding, sem overhead compartilhado)",
                 fontsize=12, fontweight="bold")
    ax.set_xlim(0, max(xs) * 1.35)
    ax.invert_yaxis()
    ax.grid(axis="x", alpha=0.3)

    sm = plt.cm.ScalarMappable(cmap=cmap, norm=plt.Normalize(1, 16))
    sm.set_array([])
    fig.colorbar(sm, ax=ax, label="Taxa de compressão (×)", fraction=0.02, pad=0.02)
    fig.tight_layout()
    _savefig(fig, "memory_compression.png")


# ══════════════════════════════════════════════════════════════════════════════
# 4. Latência por variante
# ══════════════════════════════════════════════════════════════════════════════

def plot_latency(bench: pd.DataFrame) -> None:
    """Bar chart: latência mediana (ms/query) por variante+bits."""
    quant = bench[~bench["variant"].str.startswith("baseline")].copy()
    quant["label"] = quant["variant"].str.replace("_", "\n") + "\n" + quant["bits"].astype(str) + "b"
    base_f32 = bench[bench["variant"] == "baseline_f32"]["latency_ms"].values[0]

    fig, ax = plt.subplots(figsize=(12, 4.5))
    colors_bar = [COLORS.get(v, "#aaaaaa") for v in quant["variant"]]
    ax.bar(quant["label"], quant["latency_ms"], color=colors_bar, alpha=0.85, edgecolor="white")
    ax.axhline(base_f32, color="black", linestyle="--", linewidth=1.3, label=f"float32 ({base_f32:.3f} ms)")

    ax.set_ylabel("Latência mediana (ms/query)", fontsize=11)
    ax.set_xlabel("Variante", fontsize=11)
    ax.set_title("Latência de Busca — Quantização não aumenta latência\n(índices FAISS sempre em float32)",
                 fontsize=12, fontweight="bold")
    ax.legend(fontsize=9)
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    _savefig(fig, "latency_comparison.png")


# ══════════════════════════════════════════════════════════════════════════════
# 5. Trade-off Recall × Memória  ⭐
# ══════════════════════════════════════════════════════════════════════════════

def plot_tradeoff(bench: pd.DataFrame) -> None:
    """Scatter ⭐: Recall@10 × embed_size_mb com fronteira de Pareto."""
    fig, ax = plt.subplots(figsize=(10, 6))

    all_pts: list[tuple[float, float]] = []

    for var in ["baseline_f32", "baseline_f16"] + VARIANTS:
        sub = bench[bench["variant"] == var]
        if sub.empty:
            continue
        xs   = sub["embed_size_mb"].values
        ys   = sub["recall_at_10"].values
        bts  = sub["bits"].values
        sizes = [160 + b * 12 for b in bts]

        ax.scatter(xs, ys, color=COLORS[var], marker=MARKERS[var],
                   s=sizes, zorder=5, label=LABELS[var], edgecolors="white", linewidths=0.8)

        for x, y, b in zip(xs, ys, bts, strict=True):
            tag = f"{b}b" if var not in ("baseline_f32", "baseline_f16") else LABELS[var]
            ax.annotate(tag, (x, y), textcoords="offset points",
                        xytext=(6, 4), fontsize=8, color=COLORS[var])
            all_pts.append((x, y))

    # Fronteira de Pareto
    pts = sorted(set(all_pts))
    pareto, best_y = [], -1.0
    for x, y in pts:
        if y > best_y:
            pareto.append((x, y))
            best_y = y
    if len(pareto) > 1:
        px, py = zip(*pareto, strict=False)
        ax.step(px, py, where="post", color="#FF8C00", linewidth=2,
                linestyle="--", label="Fronteira de Pareto", zorder=3)

    ax.set_xscale("log")
    ax.set_xlabel("Tamanho dos embeddings — MB (escala log)", fontsize=12)
    ax.set_ylabel("Recall@10", fontsize=12)
    ax.set_title("⭐ Trade-off: Qualidade de Retrieval × Memória",
                 fontsize=13, fontweight="bold")
    ax.set_ylim(0, 1.08)
    ax.legend(fontsize=9, loc="lower right")
    ax.grid(alpha=0.3)
    fig.tight_layout()
    _savefig(fig, "tradeoff_recall_memory.png")


# ══════════════════════════════════════════════════════════════════════════════
# 6. IP Error Heatmap
# ══════════════════════════════════════════════════════════════════════════════

def plot_ip_heatmap(dist: pd.DataFrame) -> None:
    """Heatmap: erros de produto interno por variante+bits."""
    quant = dist[~dist["variant"].str.startswith("baseline")].copy()
    quant["label"] = quant["variant"].str.replace("_", "\n") + "\n" + quant["bits"].astype(str) + "b"
    quant = quant.sort_values(["variant", "bits"], ascending=[True, False])

    metrics = ["ip_bias", "ip_mae", "ip_variance"]
    mlabels = ["IP Bias", "IP MAE", "IP Variance"]
    data     = quant[metrics].values.T   # [3, n_variants]
    col_lbls = quant["label"].tolist()

    fig, ax = plt.subplots(figsize=(max(10, len(col_lbls) * 0.9), 4.5))

    # Normaliza por linha (0=melhor, 1=pior)
    norm_data = np.zeros_like(data, dtype=float)
    for i in range(data.shape[0]):
        r = data[i]
        val_range = r.max() - r.min()
        norm_data[i] = (r - r.min()) / val_range if val_range > 0 else np.zeros_like(r)

    im = ax.imshow(norm_data, cmap="RdYlGn_r", aspect="auto", vmin=0, vmax=1)

    for i in range(data.shape[0]):
        for j in range(data.shape[1]):
            v   = data[i, j]
            txt = f"{v:.1e}" if abs(v) < 0.001 else f"{v:.4f}"
            bright = norm_data[i, j] > 0.65
            ax.text(j, i, txt, ha="center", va="center", fontsize=7.5,
                    color="white" if bright else "black", fontweight="bold" if bright else "normal")

    ax.set_xticks(range(len(col_lbls)))
    ax.set_xticklabels(col_lbls, fontsize=8.5)
    ax.set_yticks(range(len(metrics)))
    ax.set_yticklabels(mlabels, fontsize=11)
    ax.set_title("Erros de Produto Interno por Variante e Bits\n(verde = erro baixo, vermelho = erro alto)",
                 fontsize=12, fontweight="bold")
    fig.colorbar(im, ax=ax, label="Intensidade (normalizada por métrica)",
                 fraction=0.02, pad=0.02)
    fig.tight_layout()
    _savefig(fig, "ip_error_heatmap.png")


# ══════════════════════════════════════════════════════════════════════════════
# 7. Degradação de Recall por Query
# ══════════════════════════════════════════════════════════════════════════════

def plot_recall_degradation(ranks_path: str | Path = "reports/per_query_ranks.csv") -> None:
    """
    Violin/strip plot: distribuição do rank do relevante por variante.
    Compara f32, turbo_mse_4, uniform_4 e uniform_2.
    """
    path = Path(ranks_path)
    if not path.exists():
        console.print(f"  [yellow]⚠ {path} não encontrado — pulando gráfico 7[/yellow]")
        return

    df = pd.read_csv(path)

    # Escolhe variantes representativas para comparação
    focus = {
        "baseline_f32": "float32\n(baseline)",
        "turbo_mse_8":  "turbo_mse\n8-bit",
        "turbo_mse_4":  "turbo_mse\n4-bit",
        "turbo_mse_2":  "turbo_mse\n2-bit",
        "uniform_4":    "uniform\n4-bit",
        "uniform_2":    "uniform\n2-bit",
    }
    available = {k: v for k, v in focus.items() if k in df.columns}
    if not available:
        console.print("  [yellow]⚠ Colunas de variantes não encontradas — pulando gráfico 7[/yellow]")
        return

    # Capa ranks em 20 para visualização (20+ = "não encontrado")
    cap = 20
    data_plot = []
    lbls      = []
    colors_vl = []
    color_map = {"float32\n(baseline)": "black", "turbo_mse\n8-bit": "#D65F5F",
                 "turbo_mse\n4-bit": "#D65F5F", "turbo_mse\n2-bit": "#D65F5F",
                 "uniform\n4-bit": "#4878CF", "uniform\n2-bit": "#4878CF"}

    for col, lbl in available.items():
        vals = np.minimum(df[col].values, cap).astype(float)
        data_plot.append(vals)
        lbls.append(lbl)
        colors_vl.append(color_map.get(lbl, "#888888"))

    fig, ax = plt.subplots(figsize=(11, 5))

    parts = ax.violinplot(data_plot, positions=range(len(data_plot)),
                          showmedians=True, showextrema=True)
    for pc, c in zip(parts["bodies"], colors_vl, strict=False):
        pc.set_facecolor(c)
        pc.set_alpha(0.6)
    parts["cmedians"].set_color("white")
    parts["cmedians"].set_linewidth(2)

    # Jitter strip
    rng = np.random.default_rng(42)
    for i, vals in enumerate(data_plot):
        jx = rng.uniform(-0.12, 0.12, len(vals)) + i
        ax.scatter(jx, vals, alpha=0.25, s=12,
                   color=colors_vl[i], zorder=2)

    ax.set_xticks(range(len(lbls)))
    ax.set_xticklabels(lbls, fontsize=9)
    ax.set_ylabel(f"Rank do documento relevante (cap={cap})", fontsize=11)
    ax.set_yticks([1, 5, 10, cap])
    ax.set_yticklabels(["1", "5", "10", f">{cap-1}"])
    ax.set_title("Distribuição de Rank do Relevante por Variante\n(menor = melhor; rank=1 → encontrou na 1ª posição)",
                 fontsize=12, fontweight="bold")
    ax.axhline(1, color="green", linestyle=":", alpha=0.5, linewidth=1)
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    _savefig(fig, "recall_degradation_per_query.png")


# ══════════════════════════════════════════════════════════════════════════════
# 8. Compressão × Perda de Recall
# ══════════════════════════════════════════════════════════════════════════════

def plot_compression_vs_recall_loss(bench: pd.DataFrame) -> None:
    """
    Dual-axis: barras = taxa de compressão, linha = queda no Recall@10 vs f32.
    """
    quant = bench[~bench["variant"].str.startswith("baseline")].copy()
    quant["label"] = (quant["variant"].str.replace("_", "\n")
                      + "\n" + quant["bits"].astype(str) + "b")
    quant = quant.sort_values(["variant", "bits"], ascending=[True, False]).reset_index(drop=True)

    base_r10 = bench[bench["variant"] == "baseline_f32"]["recall_at_10"].values[0]
    quant["recall_loss_pp"] = (base_r10 - quant["recall_at_10"]) * 100  # pontos %

    fig, ax1 = plt.subplots(figsize=(13, 5))
    ax2 = ax1.twinx()

    x = np.arange(len(quant))
    bar_colors = [COLORS.get(v, "#aaaaaa") for v in quant["variant"]]
    ax1.bar(x, quant["compression_vs_f32"], color=bar_colors,
               alpha=0.75, edgecolor="white", width=0.6)

    ax2.plot(x, quant["recall_loss_pp"], color="#333333", marker="o",
             linewidth=2, markersize=6, zorder=5, label="Queda Recall@10 (pp)")
    ax2.axhline(0, color="green", linestyle="--", linewidth=1.2, alpha=0.7)

    # Anota pontos críticos
    for i, (_comp, loss) in enumerate(zip(quant["compression_vs_f32"], quant["recall_loss_pp"], strict=True)):
        if abs(loss) > 5:
            ax2.annotate(f"{loss:+.1f}pp", (i, loss),
                         textcoords="offset points", xytext=(0, 8),
                         fontsize=7.5, ha="center", color="red", fontweight="bold")

    ax1.set_xticks(x)
    ax1.set_xticklabels(quant["label"], fontsize=8)
    ax1.set_ylabel("Taxa de compressão (×)", fontsize=11, color="#555555")
    ax2.set_ylabel("Queda no Recall@10 vs float32 (pp)", fontsize=11)
    ax2.tick_params(axis="y", labelcolor="#333333")

    # Legenda combinada
    from matplotlib.patches import Patch
    legend_handles = (
        [Patch(color=COLORS[v], alpha=0.75, label=LABELS[v]) for v in VARIANTS]
        + [plt.Line2D([0], [0], color="#333333", marker="o", label="Queda Recall@10")]
    )
    ax1.legend(handles=legend_handles, fontsize=8, loc="upper left")
    ax1.set_title("Compressão × Perda de Recall — Identificando o Sweet Spot",
                  fontsize=12, fontweight="bold")
    ax1.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    _savefig(fig, "compression_ratio_vs_recall_loss.png")


# ══════════════════════════════════════════════════════════════════════════════
# Entry point
# ══════════════════════════════════════════════════════════════════════════════

def generate_all_plots() -> None:
    """Gera todos os 8 gráficos estáticos e imprime sumário."""
    from rich.table import Table

    bench_path = Path("reports/benchmark_results.csv")
    dist_path  = Path("reports/distortion_results.csv")
    ranks_path = Path("reports/per_query_ranks.csv")

    if not bench_path.exists():
        console.print(f"[red]{bench_path} não encontrado. Execute: make retrieval-bench[/red]")
        raise SystemExit(1)
    if not dist_path.exists():
        console.print(f"[red]{dist_path} não encontrado. Execute: make distortion-bench[/red]")
        raise SystemExit(1)

    bench = pd.read_csv(bench_path)
    dist  = pd.read_csv(dist_path)

    Path("charts").mkdir(exist_ok=True)
    console.print("\n[bold cyan]Fase 6 — Gerando gráficos[/bold cyan]\n")

    plot_recall_vs_bits(bench)
    plot_mse_vs_bits(dist)
    plot_memory_compression(bench)
    plot_latency(bench)
    plot_tradeoff(bench)
    plot_ip_heatmap(dist)
    plot_recall_degradation(ranks_path)
    plot_compression_vs_recall_loss(bench)

    console.print()

    # Sumário
    t = Table(title="Sumário — charts/", show_lines=True)
    t.add_column("#",      justify="right", style="dim")
    t.add_column("Arquivo",              style="cyan")
    t.add_column("Tipo")
    t.add_column("Insight principal")
    rows = [
        ("1", "recall_vs_bits.png",               "Line chart",       "Recall@k degrada com menos bits"),
        ("2", "mse_vs_bits.png",                   "Bar agrupado",     "MSE: turbo << lloyd_max (rotação importa)"),
        ("3", "memory_compression.png",            "Bar horizontal",   "Tamanho real com bit-packing correto"),
        ("4", "latency_comparison.png",            "Bar chart",        "Latência idêntica para todas as variantes"),
        ("5", "tradeoff_recall_memory.png ⭐",     "Scatter + Pareto", "Sweet spot: turbo_mse 4-bit"),
        ("6", "ip_error_heatmap.png",              "Heatmap",          "QJL corrige viés de IP do MSE"),
        ("7", "recall_degradation_per_query.png",  "Violin",           "Quais queries sofrem mais"),
        ("8", "compression_ratio_vs_recall_loss.png", "Dual-axis",     "Compressão × perda de recall"),
    ]
    for r in rows:
        t.add_row(*r)
    console.print(t)
    console.print("\n[bold green]✓ 8 gráficos salvos em charts/[/bold green]")
