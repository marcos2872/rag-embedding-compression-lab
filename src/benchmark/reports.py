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

import json
from pathlib import Path

import pandas as pd
from rich.console import Console

console = Console()


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

    # ── Identifica colunas disponíveis ─────────────────────────────────────────
    f32_col  = "baseline_f32_32"
    mse4_col = "turbo_mse_4"
    uni2_col = "uniform_2"

    available_cols = [c for c in [f32_col, mse4_col, "turbo_mse_2", "turbo_prod_4", uni2_col]
                      if c in ranks.columns]

    if f32_col not in ranks.columns:
        console.print("[yellow]⚠ Coluna baseline_f32 não encontrada no CSV de ranks[/yellow]")
        return

    # ── Queries que QUEBRARAM (f32 achou em top-5, turbo_mse_4 não) ───────────
    TOP_K = 5
    f32_ok   = ranks[f32_col] <= TOP_K

    if mse4_col in ranks.columns:
        mse4_fail = ranks[mse4_col] > TOP_K
        degraded  = ranks[f32_ok & mse4_fail].copy()
        degraded["rank_f32"]  = degraded[f32_col]
        degraded["rank_mse4"] = degraded[mse4_col]
        worst5 = degraded.nlargest(5, "rank_mse4")[["query", "relevant_id", "rank_f32", "rank_mse4"]]
    else:
        worst5 = pd.DataFrame(columns=["query", "relevant_id", "rank_f32"])

    # ── Queries que MANTIVERAM (todas as variantes disponíveis acertaram) ─────
    all_ok_mask = f32_ok
    for col in available_cols:
        if col in ranks.columns:
            all_ok_mask = all_ok_mask & (ranks[col] <= TOP_K)
    best_rows = ranks[all_ok_mask][["query", "relevant_id"] + available_cols].head(5)

    # ── Estatísticas ───────────────────────────────────────────────────────────
    n = len(ranks)
    stats: dict[str, dict] = {}
    for col in available_cols:
        if col not in ranks.columns:
            continue
        r = ranks[col]
        stats[col] = {
            "hit_at_1":  int((r == 1).sum()),
            "hit_at_5":  int((r <= 5).sum()),
            "hit_at_10": int((r <= 10).sum()),
            "not_found": int((r > 50).sum()),
            "median_rank": float(r[r <= 50].median()) if (r <= 50).any() else 999.0,
        }

    # ── Escreve markdown ───────────────────────────────────────────────────────
    Path("reports").mkdir(exist_ok=True)
    out = Path("reports/retrieval_examples.md")
    lines: list[str] = []

    lines += [
        "# RAG Embedding Compression Lab — Análise de Retrieval por Query",
        "",
        f"**Corpus:** {n} queries analisadas",
        f"**Critério de acerto:** relevante no top-{TOP_K}",
        "",
        "---",
        "",
        "## Queries que MANTIVERAM qualidade",
        "",
        "_Todas as variantes encontraram o documento relevante no top-5._",
        "",
    ]

    if not best_rows.empty:
        lines.append("| # | Query (trunc.) | Relevant ID |")
        lines.append("|---|---|---|")
        for i, (_, row) in enumerate(best_rows.iterrows(), 1):
            q = str(row["query"])[:90].replace("|", "\\|")
            lines.append(f"| {i} | {q}… | `{row['relevant_id']}` |")
    else:
        lines.append("_Nenhuma query manteve qualidade em todas as variantes._")

    lines += ["", "---", "", "## Queries que QUEBRARAM (f32 achou, turbo_mse_4 não)", "",
              f"_f32 achou em top-{TOP_K}, turbo_mse_4bit não achou._", ""]

    if not worst5.empty:
        lines.append("| # | Query (trunc.) | Relevant ID | Rank f32 | Rank mse_4 |")
        lines.append("|---|---|---|---|---|")
        for i, (_, row) in enumerate(worst5.iterrows(), 1):
            q = str(row["query"])[:90].replace("|", "\\|")
            lines.append(f"| {i} | {q}… | `{row['relevant_id']}` | {int(row['rank_f32'])} | {int(row['rank_mse4'])} |")
    else:
        lines.append("_Nenhuma query quebrou (todas as variantes mantiveram qualidade)._")

    lines += ["", "---", "", "## Estatísticas gerais", ""]
    lines.append("| Variante | Hit@1 | Hit@5 | Hit@10 | Not Found | Mediana Rank |")
    lines.append("|---|---|---|---|---|---|")
    for col, s in stats.items():
        var_lbl = col.replace("_", " ")
        pct = lambda x: f"{x}/{n} ({x/n*100:.1f}%)"
        lines.append(f"| {var_lbl} | {pct(s['hit_at_1'])} | {pct(s['hit_at_5'])} | "
                     f"{pct(s['hit_at_10'])} | {pct(s['not_found'])} | {s['median_rank']:.1f} |")

    lines += ["", "---", "", "## Padrões observados", ""]

    # Análise automática simples
    if mse4_col in stats and f32_col in stats:
        mse4_h10 = stats[mse4_col]["hit_at_10"] / n
        f32_h10  = stats[f32_col]["hit_at_10"] / n
        retention = mse4_h10 / f32_h10 if f32_h10 > 0 else 0
        lines.append(f"- **turbo_mse 4-bit** retém **{retention*100:.1f}%** do Recall@10 do float32 "
                     f"usando apenas **1/8 da memória** (~7.9× compressão).")

    if uni2_col in stats and f32_col in stats:
        uni2_h10 = stats[uni2_col]["hit_at_10"] / n
        f32_h10  = stats[f32_col]["hit_at_10"] / n
        lines.append(f"- **uniform 2-bit** retém apenas **{uni2_h10/f32_h10*100:.1f}%** do Recall@10 "
                     f"— compressão agressiva sem rotação destrói a qualidade.")

    if "turbo_mse_2" in stats:
        mse2_h10 = stats["turbo_mse_2"]["hit_at_10"] / n
        if f32_col in stats:
            f32_h10 = stats[f32_col]["hit_at_10"] / n
            lines.append(f"- **turbo_mse 2-bit** ainda retém **{mse2_h10/f32_h10*100:.1f}%** do Recall@10 "
                         f"com 15× compressão — demonstra a robustez da rotação ortogonal.")

    lines += ["", "---", "",
              f"_Relatório gerado automaticamente pelo RAG Embedding Compression Lab._"]

    out.write_text("\n".join(lines), encoding="utf-8")
    console.print(f"[green]✓ Relatório salvo:[/green] {out}")

    # ── notes.md ─────────────────────────────────────────────────────────────
    _write_notes(bench, stats, n)


def _write_notes(bench: pd.DataFrame, stats: dict, n: int) -> None:
    """Escreve reports/notes.md com análise do benchmark geral."""
    out = Path("reports/notes.md")

    f32_r10 = bench[bench["variant"] == "baseline_f32"]["recall_at_10"].values
    if len(f32_r10) == 0:
        return
    f32_r10 = f32_r10[0]

    sweet = bench[bench["variant"].isin(["turbo_mse", "turbo_prod"])].copy()
    sweet["recall_loss"] = f32_r10 - sweet["recall_at_10"]
    sweet_spot = sweet.loc[sweet[sweet["recall_loss"] <= 0.005]["compression_vs_f32"].idxmax()] \
        if not sweet[sweet["recall_loss"] <= 0.005].empty else None

    lines = [
        "# Notes — RAG Embedding Compression Lab",
        "",
        "## Configuração",
        f"- Corpus: `data/corpus.jsonl`",
        f"- Modelo: `BAAI/bge-small-en-v1.5` (dim=384)",
        f"- Queries: {n} (estratégia `first_sentence`)",
        "",
        "## Resultados chave",
        "",
    ]

    if sweet_spot is not None:
        lines.append(
            f"- **Sweet spot:** `{sweet_spot['variant']}_{int(sweet_spot['bits'])}-bit` "
            f"— {sweet_spot['compression_vs_f32']:.1f}× compressão, "
            f"Recall@10={sweet_spot['recall_at_10']:.3f} "
            f"(Δ={sweet_spot['recall_at_10']-f32_r10:+.3f} vs f32)"
        )

    lines += [
        "",
        "## Próximos passos",
        "- [ ] Fase 7: demo RAG interativo (`make rag-demo`)",
        "- [ ] Testar com corpus maior (>10k chunks)",
        "- [ ] Comparar com FAISS IndexIVFPQ",
        "- [ ] Fine-tuning do modelo de embedding no domínio",
        "",
        "---",
        "_Gerado automaticamente pelo RAG Embedding Compression Lab._",
    ]

    out.write_text("\n".join(lines), encoding="utf-8")
    console.print(f"[green]✓ Notes salvo:[/green] {out}")
