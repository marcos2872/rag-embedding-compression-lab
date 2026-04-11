"""
src/benchmark/reports.py
--------------------------
Fase 6 — Relatório Markdown com análise qualitativa das queries.

Gera reports/retrieval_examples.md com:
  - Top 5 queries que MAIS perderam qualidade (f32 encontrou, turbo_mse_4 não)
  - Top 5 queries que MANTIVERAM qualidade (todas as variantes acertaram)
  - Análise: estatísticas gerais sobre degradação
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from rich.console import Console

console = Console()

_F32_COL  = "baseline_f32_32"
_MSE4_COL = "turbo_mse_4"
_UNI2_COL = "uniform_2"
_TOP_K    = 5


# ── Entry point ────────────────────────────────────────────────────────────────

def generate_report() -> None:
    """Gera reports/retrieval_examples.md e reports/notes.md."""
    ranks_path = Path("reports/per_query_ranks.csv")
    bench_path = Path("reports/benchmark_results.csv")

    if not ranks_path.exists():
        console.print(f"[red]{ranks_path} não encontrado. Execute: make retrieval-bench[/red]")
        raise SystemExit(1)

    ranks = pd.read_csv(ranks_path)
    bench = pd.read_csv(bench_path)
    console.print("\n[bold cyan]Fase 6 — Gerando relatórios[/bold cyan]\n")

    if _F32_COL not in ranks.columns:
        console.print("[yellow]⚠ Coluna baseline_f32 não encontrada no CSV de ranks[/yellow]")
        return

    available  = _available_rank_cols(ranks)
    n          = len(ranks)
    worst5, best_rows = _find_examples(ranks, available)
    stats      = _compute_variant_stats(ranks, available, n)
    lines      = _build_markdown_lines(worst5, best_rows, stats, n)

    Path("reports").mkdir(exist_ok=True)
    out = Path("reports/retrieval_examples.md")
    out.write_text("\n".join(lines), encoding="utf-8")
    console.print(f"[green]✓ Relatório salvo:[/green] {out}")

    _write_notes(bench, stats, n)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _available_rank_cols(ranks: pd.DataFrame) -> list[str]:
    """Retorna colunas de rank disponíveis no CSV."""
    candidates = [_F32_COL, _MSE4_COL, "turbo_mse_2", "turbo_prod_4", _UNI2_COL]
    return [c for c in candidates if c in ranks.columns]


def _find_examples(
    ranks: pd.DataFrame,
    available: list[str],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Retorna (worst5, best_rows): queries degradadas e mantidas."""
    f32_ok = ranks[_F32_COL] <= _TOP_K

    if _MSE4_COL in ranks.columns:
        mse4_fail = ranks[_MSE4_COL] > _TOP_K
        degraded  = ranks[f32_ok & mse4_fail].copy()
        degraded["rank_f32"]  = degraded[_F32_COL]
        degraded["rank_mse4"] = degraded[_MSE4_COL]
        worst5 = degraded.nlargest(5, "rank_mse4")[
            ["query", "relevant_id", "rank_f32", "rank_mse4"]
        ]
    else:
        worst5 = pd.DataFrame(columns=["query", "relevant_id", "rank_f32"])

    all_ok = f32_ok
    for col in available:
        all_ok = all_ok & (ranks[col] <= _TOP_K)
    best_rows = ranks[all_ok][["query", "relevant_id"] + available].head(5)

    return worst5, best_rows


def _compute_variant_stats(
    ranks: pd.DataFrame,
    available: list[str],
    n: int,
) -> dict[str, dict]:
    """Calcula Hit@k, Not Found e mediana de rank por variante."""
    stats: dict[str, dict] = {}
    for col in available:
        if col not in ranks.columns:
            continue
        r = ranks[col]
        stats[col] = {
            "hit_at_1":    int((r == 1).sum()),
            "hit_at_5":    int((r <= 5).sum()),
            "hit_at_10":   int((r <= 10).sum()),
            "not_found":   int((r > 50).sum()),
            "median_rank": float(r[r <= 50].median()) if (r <= 50).any() else 999.0,
        }
    return stats


def _build_markdown_lines(
    worst5: pd.DataFrame,
    best_rows: pd.DataFrame,
    stats: dict[str, dict],
    n: int,
) -> list[str]:
    """Monta todas as linhas do arquivo Markdown de análise."""
    def pct(x: int) -> str:
        return f"{x}/{n} ({x/n*100:.1f}%)"

    lines: list[str] = [
        "# RAG Embedding Compression Lab — Análise de Retrieval por Query",
        "",
        f"**Corpus:** {n} queries analisadas",
        f"**Critério de acerto:** relevante no top-{_TOP_K}",
        "", "---", "",
        "## Queries que MANTIVERAM qualidade", "",
        "_Todas as variantes encontraram o documento relevante no top-5._", "",
    ]

    if not best_rows.empty:
        lines += ["| # | Query (trunc.) | Relevant ID |", "|---|---|---|"]
        for i, (_, row) in enumerate(best_rows.iterrows(), 1):
            q = str(row["query"])[:90].replace("|", "\\|")
            lines.append(f"| {i} | {q}… | `{row['relevant_id']}` |")
    else:
        lines.append("_Nenhuma query manteve qualidade em todas as variantes._")

    lines += [
        "", "---", "",
        "## Queries que QUEBRARAM (f32 achou, turbo_mse_4 não)", "",
        f"_f32 achou em top-{_TOP_K}, turbo_mse_4bit não achou._", "",
    ]

    if not worst5.empty:
        lines += ["| # | Query (trunc.) | Relevant ID | Rank f32 | Rank mse_4 |",
                  "|---|---|---|---|---|"]
        for i, (_, row) in enumerate(worst5.iterrows(), 1):
            q = str(row["query"])[:90].replace("|", "\\|")
            lines.append(
                f"| {i} | {q}… | `{row['relevant_id']}` | "
                f"{int(row['rank_f32'])} | {int(row['rank_mse4'])} |"
            )
    else:
        lines.append("_Nenhuma query quebrou._")

    lines += ["", "---", "", "## Estatísticas gerais", ""]
    lines += ["| Variante | Hit@1 | Hit@5 | Hit@10 | Not Found | Mediana Rank |",
              "|---|---|---|---|---|---|"]
    for col, s in stats.items():
        var_lbl = col.replace("_", " ")
        lines.append(
            f"| {var_lbl} | {pct(s['hit_at_1'])} | {pct(s['hit_at_5'])} | "
            f"{pct(s['hit_at_10'])} | {pct(s['not_found'])} | {s['median_rank']:.1f} |"
        )

    lines += ["", "---", "", "## Padrões observados", ""]
    lines += _auto_analysis(stats, n)
    lines += ["", "---", "", "_Relatório gerado automaticamente pelo RAG Embedding Compression Lab._"]
    return lines


def _auto_analysis(stats: dict[str, dict], n: int) -> list[str]:
    """Gera bullets de análise automática comparando variantes com f32."""
    lines: list[str] = []
    f32_h10 = stats.get(_F32_COL, {}).get("hit_at_10", 0) / n if n else 0

    if _MSE4_COL in stats and f32_h10 > 0:
        retention = stats[_MSE4_COL]["hit_at_10"] / n / f32_h10
        lines.append(
            f"- **turbo_mse 4-bit** retém **{retention*100:.1f}%** do Recall@10 do float32 "
            "usando apenas **1/8 da memória** (~7.9× compressão)."
        )
    if _UNI2_COL in stats and f32_h10 > 0:
        ratio = stats[_UNI2_COL]["hit_at_10"] / n / f32_h10
        lines.append(
            f"- **uniform 2-bit** retém apenas **{ratio*100:.1f}%** do Recall@10 "
            "— compressão agressiva sem rotação destrói a qualidade."
        )
    if "turbo_mse_2" in stats and f32_h10 > 0:
        ratio = stats["turbo_mse_2"]["hit_at_10"] / n / f32_h10
        lines.append(
            f"- **turbo_mse 2-bit** ainda retém **{ratio*100:.1f}%** do Recall@10 "
            "com 15× compressão."
        )
    return lines


# ── Notes ──────────────────────────────────────────────────────────────────────

def _write_notes(bench: pd.DataFrame, stats: dict, n: int) -> None:
    """Escreve reports/notes.md com análise do benchmark geral."""
    out = Path("reports/notes.md")

    f32_r10 = bench[bench["variant"] == "baseline_f32"]["recall_at_10"].values
    if len(f32_r10) == 0:
        return
    f32_r10 = float(f32_r10[0])

    sweet = bench[bench["variant"].isin(["turbo_mse", "turbo_prod"])].copy()
    sweet["recall_loss"] = f32_r10 - sweet["recall_at_10"]
    candidates  = sweet[sweet["recall_loss"] <= 0.005]
    sweet_spot  = sweet.loc[candidates["compression_vs_f32"].idxmax()] \
        if not candidates.empty else None

    lines = [
        "# Notes — RAG Embedding Compression Lab", "",
        "## Configuração",
        "- Corpus: `data/corpus.jsonl`",
        "- Modelo: `BAAI/bge-small-en-v1.5` (dim=384)",
        f"- Queries: {n} (estratégia `first_sentence`)",
        "", "## Resultados chave", "",
    ]

    if sweet_spot is not None:
        lines.append(
            f"- **Sweet spot:** `{sweet_spot['variant']}_{int(sweet_spot['bits'])}-bit` "
            f"— {sweet_spot['compression_vs_f32']:.1f}× compressão, "
            f"Recall@10={sweet_spot['recall_at_10']:.3f} "
            f"(Δ={sweet_spot['recall_at_10']-f32_r10:+.3f} vs f32)"
        )

    lines += [
        "", "## Próximos passos",
        "- [ ] Fase 7: demo RAG interativo (`make rag-demo`)",
        "- [ ] Testar com corpus maior (>10k chunks)",
        "- [ ] Comparar com FAISS IndexIVFPQ",
        "- [ ] Fine-tuning do modelo de embedding no domínio",
        "", "---",
        "_Gerado automaticamente pelo RAG Embedding Compression Lab._",
    ]

    out.write_text("\n".join(lines), encoding="utf-8")
    console.print(f"[green]✓ Notes salvo:[/green] {out}")
