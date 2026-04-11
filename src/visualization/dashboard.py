"""
src/visualization/dashboard.py
--------------------------------
Gera charts/dashboard.html — dashboard interativo com Plotly.

Módulos auxiliares:
  _dashboard_figs.py  — funções geradoras de figuras Plotly
  _dashboard_html.py  — template HTML e montagem do arquivo final
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from rich.console import Console

from src.visualization._dashboard_figs import (
    _compression_fig,
    _degradation_fig,
    _ip_heatmap_fig,
    _latency_fig,
    _memory_fig,
    _mse_bar_fig,
    _recall_line_fig,
    _table_fig,
    _tradeoff_fig,
)
from src.visualization._dashboard_html import CHART_META, _write_html  # noqa: F401

console = Console()


def generate_dashboard() -> None:
    """Lê CSVs e gera charts/dashboard.html."""
    try:
        import plotly.graph_objects  # noqa: F401
    except ImportError:
        console.print("[red]plotly não instalado. Execute: uv sync[/red]")
        raise

    bench_path = Path("reports/benchmark_results.csv")
    dist_path  = Path("reports/distortion_results.csv")

    if not bench_path.exists() or not dist_path.exists():
        console.print("[red]CSVs não encontrados. Execute: make all-bench[/red]")
        raise SystemExit(1)

    bench = pd.read_csv(bench_path)
    dist  = pd.read_csv(dist_path)

    console.print("\n[bold cyan]Fase 6 — Gerando dashboard interativo[/bold cyan]\n")

    ranks_path = Path("reports/per_query_ranks.csv")
    figs = [
        _table_fig(bench, dist),
        _recall_line_fig(bench),
        _tradeoff_fig(bench),
        _mse_bar_fig(dist),
        _ip_heatmap_fig(dist),
        _compression_fig(bench),
        _memory_fig(bench),
        _degradation_fig(ranks_path),
        _latency_fig(bench),
    ]
    labels = [
        "Tabela", "Recall vs Bits", "Trade-off ⭐", "MSE",
        "IP Heatmap", "Compressão × Recall", "Memória", "Degradação por Query", "Latência",
    ]
    for lbl in labels:
        console.print(f"  [green]✓[/green] {lbl}")

    _write_html(figs, bench, dist)
    console.print("\n[bold green]✓ Dashboard salvo:[/bold green] charts/dashboard.html")
