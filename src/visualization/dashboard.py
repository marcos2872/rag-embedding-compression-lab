"""
src/visualization/dashboard.py
--------------------------------
Gera charts/dashboard.html — dashboard interativo com Plotly.

Cada gráfico vem acompanhado de um card explicativo com:
  - O que mostra      : propósito do gráfico
  - Como ler          : guia de leitura visual
  - Impacto prático   : o que o resultado significa para o sistema RAG
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import numpy as np
from rich.console import Console

console = Console()

# ── Paleta ─────────────────────────────────────────────────────────────────────
COLORS = {
    "uniform":      "#4878CF",
    "lloyd_max":    "#6ACC65",
    "turbo_mse":    "#D65F5F",
    "turbo_prod":   "#B47CC7",
    "baseline_f32": "#333333",
    "baseline_f16": "#888888",
}
LABELS = {
    "uniform":      "Uniform",
    "lloyd_max":    "Lloyd-Max",
    "turbo_mse":    "TurboQuantMSE",
    "turbo_prod":   "TurboQuantProd",
    "baseline_f32": "float32",
    "baseline_f16": "float16",
}
VARIANTS  = ["uniform", "lloyd_max", "turbo_mse", "turbo_prod"]
BITS_LIST = [2, 4, 8]


# ── Descrições dos gráficos ─────────────────────────────────────────────────────
CHART_META = [
    {
        "id":    "overview",
        "icon":  "📋",
        "title": "Tabela de Resultados Completos",
        "what":  "Consolida em uma única tabela todas as métricas de benchmark de retrieval "
                 "(Recall@k, MRR, latência, tamanho em MB, compressão) e de distorção "
                 "(MSE, Cosine Error, IP Bias) para cada variante × bits.",
        "how":   "Cada linha é uma variante. As colunas de retrieval (R@1, R@5, R@10, MRR) "
                 "devem ser o mais altas possível; as de distorção (MSE, IP Bias) o mais "
                 "baixas possível. A coluna <b>Compr.</b> indica quantas vezes menos memória "
                 "a variante usa vs. float32.",
        "impact":"Use esta tabela como referência rápida para escolher a variante ideal para "
                 "o seu caso de uso. Procure linhas com alta compressão E alto Recall@10.",
        "badge": "referência",
        "badge_color": "#6c757d",
    },
    {
        "id":    "recall_line",
        "icon":  "📈",
        "title": "Recall@10 vs Bits — Quanto a qualidade cai ao comprimir?",
        "what":  "Mostra como o Recall@10 de cada variante varia conforme reduzimos o número "
                 "de bits de 8 para 2. As linhas tracejadas marcam os baselines float32 e float16.",
        "how":   "<b>Eixo X</b>: bits por dimensão (8→4→2). <b>Eixo Y</b>: Recall@10 "
                 "(0 = nenhum resultado correto, 1 = todos corretos). Linhas mais altas = "
                 "melhor qualidade para o mesmo nível de compressão. Passe o mouse sobre os "
                 "pontos para ver os valores exatos.",
        "impact":"<b>TurboQuantMSE a 4-bit</b> mantém Recall@10 igual ou superior ao float32 "
                 "com 8× menos memória — o sweet spot do paper TurboQuant. <b>Uniform a 2-bit</b> "
                 "colapsa: a rotação aleatória antes da quantização é o que diferencia os métodos.",
        "badge": "insight chave",
        "badge_color": "#d65f5f",
    },
    {
        "id":    "tradeoff",
        "icon":  "⭐",
        "title": "Trade-off: Qualidade × Memória — O gráfico mais importante",
        "what":  "Scatter plot onde cada ponto é uma configuração (variante + bits). "
                 "Mostra simultaneamente a qualidade de retrieval e o custo de memória. "
                 "A linha laranja é a <b>fronteira de Pareto</b>: pontos onde não é possível "
                 "melhorar qualidade sem aumentar memória.",
        "how":   "<b>Eixo X (log)</b>: quanto menor, mais economia de memória. "
                 "<b>Eixo Y</b>: Recall@10 — quanto maior, melhor. O ponto ideal está no "
                 "canto <b>superior esquerdo</b>. Pontos na fronteira de Pareto são as melhores "
                 "escolhas possíveis. Passe o mouse para ver a taxa de compressão exata.",
        "impact":"Pontos TurboQuantMSE ficam acima de Uniform e Lloyd-Max para a mesma "
                 "posição horizontal, provando que a rotação ortogonal é essencial. "
                 "<b>turbo_mse 4-bit é o sweet spot</b>: 7.9× compressão sem perda de qualidade.",
        "badge": "mais importante",
        "badge_color": "#e67e22",
    },
    {
        "id":    "mse",
        "icon":  "📐",
        "title": "MSE por Variante — Distorção Geométrica dos Vetores",
        "what":  "Mede o erro quadrático médio (MSE) entre os vetores originais float32 e os "
                 "vetores reconstruídos após quantização + dequantização. Indica o quanto a "
                 "geometria do espaço de embeddings é distorcida.",
        "how":   "<b>Eixo Y em escala log</b>: valores menores = menos distorção. "
                 "Cada grupo de barras representa um nível de bits (8→4→2). "
                 "Barras mais baixas dentro do mesmo grupo = variante mais fiel ao original. "
                 "Hover para ver o valor exato.",
        "impact":"Lloyd-Max sem rotação tem MSE alto apesar de usar o mesmo codebook que "
                 "TurboQuantMSE. Isso confirma que o <b>codebook ótimo sozinho não basta</b> — "
                 "a rotação é necessária para que a distribuição das coordenadas corresponda "
                 "ao codebook teórico.",
        "badge": "distorção geométrica",
        "badge_color": "#4878cf",
    },
    {
        "id":    "heatmap",
        "icon":  "🌡️",
        "title": "Heatmap de Erros de Produto Interno",
        "what":  "Mede três tipos de erro no produto interno (dot product) entre queries e "
                 "documentos: <b>IP Bias</b> (viés sistemático), <b>IP MAE</b> (magnitude "
                 "média do erro) e <b>IP Variance</b> (consistência do erro).",
        "how":   "<b>Verde</b> = erro baixo (bom). <b>Vermelho</b> = erro alto (ruim). "
                 "Cada coluna é uma variante+bits. As células mostram o valor real. "
                 "O <b>IP Bias</b> é especialmente importante: um viés alto significa que "
                 "os scores de similaridade são sistematicamente errados.",
        "impact":"<b>Lloyd-Max tem IP Bias altíssimo</b> (−0.13 a 8-bit) pois o codebook "
                 "recorta coordenadas grandes, criando viés. <b>TurboQuantMSE elimina esse "
                 "viés</b> com a rotação. <b>TurboQuantProd vai além</b>: o QJL corrige o "
                 "viés residual do MSE, mantendo IP Bias próximo de zero em todos os bits.",
        "badge": "viés de produto interno",
        "badge_color": "#6acc65",
    },
    {
        "id":    "compression",
        "icon":  "🗜️",
        "title": "Compressão × Perda de Recall — Identificando o Sweet Spot",
        "what":  "Gráfico dual-axis: as <b>barras</b> mostram a taxa de compressão de memória "
                 "(quanto menor o embedding, maior a barra); a <b>linha</b> mostra a queda "
                 "no Recall@10 em pontos percentuais em relação ao baseline float32.",
        "how":   "<b>Barras altas</b> = muita compressão (bom). <b>Linha próxima de zero</b> "
                 "= pouca perda de qualidade (bom). O sweet spot é onde a barra é alta E a "
                 "linha está perto de zero. Anotações em vermelho destacam quedas severas (>5pp).",
        "impact":"Qualquer variante com <b>queda < 1pp e compressão > 7×</b> é um candidato "
                 "viável para produção. Compressão agressiva (2-bit) sem rotação causa quedas "
                 "de 40+ pp — inutilizável. Com rotação (TurboQuantMSE 2-bit), a queda é < 2pp.",
        "badge": "decisão de produção",
        "badge_color": "#b47cc7",
    },
]


def generate_dashboard() -> None:
    """Lê CSVs e gera charts/dashboard.html."""
    try:
        import plotly.graph_objects as go
        from plotly.subplots import make_subplots
        import plotly.io as pio
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

    figs = [
        _table_fig(bench, dist),
        _recall_line_fig(bench),
        _tradeoff_fig(bench),
        _mse_bar_fig(dist),
        _ip_heatmap_fig(dist),
        _compression_fig(bench),
    ]
    labels = ["Tabela", "Recall vs Bits", "Trade-off", "MSE", "IP Heatmap", "Compressão"]
    for lbl in labels:
        console.print(f"  [green]✓[/green] {lbl}")

    _write_html(figs, bench, dist)
    console.print(f"\n[bold green]✓ Dashboard salvo:[/bold green] charts/dashboard.html")


# ── Figuras Plotly ─────────────────────────────────────────────────────────────

def _table_fig(bench: pd.DataFrame, dist: pd.DataFrame):
    import plotly.graph_objects as go

    merged = bench.copy()
    dist_sub = dist[~dist["variant"].str.startswith("baseline")][
        ["variant", "bits", "mse", "cosine_error", "ip_bias", "ip_mae"]
    ]
    merged = merged.merge(dist_sub, on=["variant", "bits"], how="left")

    def fmt(v):
        if pd.isna(v):             return "—"
        if isinstance(v, float):   return f"{v:.4f}"
        return str(v)

    headers  = ["Variante", "Bits", "R@1", "R@5", "R@10", "MRR",
                "ms/q", "MB(vetor)", "Compr.", "MSE", "Cosine Err", "IP Bias"]
    cols_map = ["variant", "bits", "recall_at_1", "recall_at_5", "recall_at_10",
                "mrr", "latency_ms", "embed_size_mb", "compression_vs_f32",
                "mse", "cosine_error", "ip_bias"]

    cell_vals = [[fmt(merged[c].iloc[i]) for i in range(len(merged))] for c in cols_map]

    fill_colors = []
    for i in range(len(merged)):
        var   = merged["variant"].iloc[i]
        hex_c = COLORS.get(var, "#ffffff")
        r, g, b = int(hex_c[1:3], 16), int(hex_c[3:5], 16), int(hex_c[5:7], 16)
        fill_colors.append(f"rgba({r},{g},{b},0.08)")

    fig = go.Figure(data=[go.Table(
        columnwidth=[120, 45, 55, 55, 55, 60, 55, 75, 65, 75, 85, 75],
        header=dict(
            values=headers,
            fill_color="#2c3e50",
            font=dict(color="white", size=11),
            align="center",
            height=32,
        ),
        cells=dict(
            values=cell_vals,
            align="center",
            font_size=10,
            fill_color=[fill_colors] * len(headers),
            height=28,
        ),
    )])
    fig.update_layout(
        height=520,
        margin=dict(l=0, r=0, t=10, b=0),
    )
    return fig


def _recall_line_fig(bench: pd.DataFrame):
    import plotly.graph_objects as go

    fig = go.Figure()
    for var in VARIANTS:
        sub = bench[bench["variant"] == var].sort_values("bits")
        fig.add_trace(go.Scatter(
            x=sub["bits"], y=sub["recall_at_10"],
            mode="lines+markers", name=LABELS[var],
            line=dict(color=COLORS[var], width=2.5),
            marker=dict(size=9),
            hovertemplate=(
                f"<b>{LABELS[var]}</b><br>"
                "Bits: %{x}<br>"
                "Recall@10: <b>%{y:.3f}</b><br>"
                "<extra></extra>"
            ),
        ))

    for bname in ("baseline_f32", "baseline_f16"):
        row = bench[bench["variant"] == bname]
        if not row.empty:
            val = row["recall_at_10"].values[0]
            fig.add_hline(
                y=val, line_dash="dash", line_color=COLORS[bname],
                annotation_text=f"  {LABELS[bname]} ({val:.3f})",
                annotation_position="right",
                annotation_font_color=COLORS[bname],
            )

    fig.update_layout(
        xaxis=dict(
            title="Bits por dimensão",
            tickvals=BITS_LIST, ticktext=[f"{b}-bit" for b in BITS_LIST],
            showgrid=True, gridcolor="#eeeeee",
        ),
        yaxis=dict(title="Recall@10", range=[0, 1.08], showgrid=True, gridcolor="#eeeeee"),
        legend=dict(x=0.01, y=0.05, bgcolor="rgba(255,255,255,0.8)", bordercolor="#dddddd", borderwidth=1),
        plot_bgcolor="white",
        height=400,
        margin=dict(l=60, r=80, t=20, b=50),
    )
    return fig


def _tradeoff_fig(bench: pd.DataFrame):
    import plotly.graph_objects as go

    fig = go.Figure()

    # Coleta pontos para a fronteira de Pareto
    all_pts: list[tuple[float, float]] = []

    for var in ["baseline_f32", "baseline_f16"] + VARIANTS:
        sub = bench[bench["variant"] == var]
        if sub.empty:
            continue

        xs   = sub["embed_size_mb"].values
        ys   = sub["recall_at_10"].values
        bts  = sub["bits"].values
        comp = sub["compression_vs_f32"].values
        sizes = np.clip(60 + bts * 18, 80, 220)

        text_labels = [
            f"{int(b)}b" if var not in ("baseline_f32", "baseline_f16")
            else LABELS[var]
            for b in bts
        ]

        fig.add_trace(go.Scatter(
            x=xs, y=ys,
            mode="markers+text",
            name=LABELS[var],
            marker=dict(
                color=COLORS[var], size=sizes,
                line=dict(width=1.5, color="white"),
                symbol="circle",
            ),
            text=text_labels,
            textposition="top right",
            textfont=dict(size=10, color=COLORS[var]),
            hovertemplate=(
                f"<b>{LABELS[var]}</b><br>"
                "Memória: <b>%{x:.3f} MB</b><br>"
                "Recall@10: <b>%{y:.3f}</b><br>"
                "Compressão: <b>%{customdata:.1f}×</b><br>"
                "<extra></extra>"
            ),
            customdata=comp,
        ))
        for x, y in zip(xs, ys):
            all_pts.append((float(x), float(y)))

    # Fronteira de Pareto
    pts = sorted(set(all_pts))
    pareto, best_y = [], -1.0
    for x, y in pts:
        if y > best_y:
            pareto.append((x, y))
            best_y = y
    if len(pareto) > 1:
        px, py = zip(*pareto)
        fig.add_trace(go.Scatter(
            x=px, y=py,
            mode="lines",
            name="Fronteira de Pareto",
            line=dict(color="#e67e22", width=2.5, dash="dash"),
            hoverinfo="skip",
        ))

    fig.update_layout(
        xaxis=dict(
            title="Tamanho dos embeddings (MB) — escala log",
            type="log", showgrid=True, gridcolor="#eeeeee",
        ),
        yaxis=dict(
            title="Recall@10",
            range=[0, 1.12], showgrid=True, gridcolor="#eeeeee",
        ),
        legend=dict(x=0.01, y=0.01, bgcolor="rgba(255,255,255,0.85)", bordercolor="#ddd", borderwidth=1),
        plot_bgcolor="white",
        height=480,
        margin=dict(l=60, r=40, t=20, b=60),
    )
    return fig


def _mse_bar_fig(dist: pd.DataFrame):
    import plotly.graph_objects as go

    fig = go.Figure()
    for var in VARIANTS:
        sub = dist[dist["variant"] == var].sort_values("bits", ascending=False)
        fig.add_trace(go.Bar(
            name=LABELS[var],
            x=[f"{int(b)}-bit" for b in sub["bits"]],
            y=sub["mse"],
            marker_color=COLORS[var],
            marker_line_color="white",
            marker_line_width=1,
            hovertemplate=(
                f"<b>{LABELS[var]}</b><br>"
                "Bits: %{x}<br>"
                "MSE: <b>%{y:.8f}</b><br>"
                "<extra></extra>"
            ),
        ))

    fig.update_layout(
        barmode="group",
        xaxis=dict(title="Bits por dimensão", showgrid=False),
        yaxis=dict(title="MSE (escala log)", type="log", showgrid=True, gridcolor="#eeeeee"),
        legend=dict(x=0.01, y=0.99, bgcolor="rgba(255,255,255,0.8)", bordercolor="#ddd", borderwidth=1),
        plot_bgcolor="white",
        height=400,
        margin=dict(l=60, r=20, t=20, b=50),
    )
    return fig


def _ip_heatmap_fig(dist: pd.DataFrame):
    import plotly.graph_objects as go

    quant = dist[~dist["variant"].str.startswith("baseline")].copy()
    quant["label"] = quant["variant"] + "_" + quant["bits"].astype(str) + "b"
    quant = quant.sort_values(["variant", "bits"], ascending=[True, False])

    metrics = ["ip_bias", "ip_mae", "ip_variance"]
    mlabels = ["IP Bias<br>(viés sistemático)", "IP MAE<br>(magnitude do erro)", "IP Variance<br>(consistência)"]
    z       = quant[metrics].values.T
    col_lbl = quant["label"].tolist()

    z_norm = np.zeros_like(z, dtype=float)
    for i in range(z.shape[0]):
        rng = z[i].max() - z[i].min()
        z_norm[i] = (z[i] - z[i].min()) / rng if rng > 0 else np.zeros_like(z[i])

    fig = go.Figure(data=go.Heatmap(
        z=z_norm,
        x=col_lbl,
        y=mlabels,
        colorscale="RdYlGn_r",
        showscale=True,
        colorbar=dict(title="Intensidade", tickvals=[0, 0.5, 1], ticktext=["Baixo", "Médio", "Alto"]),
        text=[[f"{v:.5f}" for v in row] for row in z],
        texttemplate="<b>%{text}</b>",
        textfont=dict(size=9),
        hovertemplate=(
            "Métrica: %{y}<br>"
            "Variante: %{x}<br>"
            "Valor: <b>%{text}</b><br>"
            "<extra></extra>"
        ),
    ))
    fig.update_layout(
        xaxis=dict(tickangle=-30, side="bottom"),
        yaxis=dict(autorange="reversed"),
        height=320,
        margin=dict(l=200, r=80, t=20, b=80),
        plot_bgcolor="white",
    )
    return fig


def _compression_fig(bench: pd.DataFrame):
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    quant = bench[~bench["variant"].str.startswith("baseline")].copy()
    quant["label"] = quant["variant"] + "_" + quant["bits"].astype(str) + "b"
    quant = quant.sort_values(["variant", "bits"], ascending=[True, False]).reset_index(drop=True)

    base_r10 = bench[bench["variant"] == "baseline_f32"]["recall_at_10"].values[0]
    quant["recall_loss_pp"] = (base_r10 - quant["recall_at_10"]) * 100

    bar_colors = [COLORS.get(v, "#aaaaaa") for v in quant["variant"]]

    fig = make_subplots(
        specs=[[{"secondary_y": True}]],
        shared_xaxes=True,
    )

    fig.add_trace(
        go.Bar(
            x=quant["label"],
            y=quant["compression_vs_f32"],
            name="Compressão (×)",
            marker_color=bar_colors,
            marker_line_color="white",
            marker_line_width=1,
            opacity=0.80,
            hovertemplate=(
                "<b>%{x}</b><br>"
                "Compressão: <b>%{y:.2f}×</b><br>"
                "<extra></extra>"
            ),
        ),
        secondary_y=False,
    )

    # Linha de queda de recall
    point_colors = ["#e74c3c" if v > 5 else "#27ae60" if v <= 1 else "#e67e22"
                    for v in quant["recall_loss_pp"]]
    fig.add_trace(
        go.Scatter(
            x=quant["label"],
            y=quant["recall_loss_pp"],
            name="Queda Recall@10 (pp)",
            mode="lines+markers",
            line=dict(color="#2c3e50", width=2.5),
            marker=dict(size=9, color=point_colors, line=dict(width=1, color="white")),
            hovertemplate=(
                "<b>%{x}</b><br>"
                "Queda: <b>%{y:.2f} pp</b><br>"
                "<extra></extra>"
            ),
        ),
        secondary_y=True,
    )

    # Anotações de quedas severas
    for _, row in quant[quant["recall_loss_pp"] > 5].iterrows():
        fig.add_annotation(
            x=row["label"],
            y=row["recall_loss_pp"],
            text=f"−{row['recall_loss_pp']:.1f}pp",
            showarrow=True,
            arrowhead=2,
            arrowcolor="#e74c3c",
            font=dict(color="#e74c3c", size=9, family="monospace"),
            yref="y2",
            ay=-30,
        )

    fig.add_hline(y=0, line_dash="dot", line_color="#27ae60", line_width=1.5,
                  secondary_y=True, annotation_text="sem perda", annotation_position="right",
                  annotation_font_color="#27ae60")

    fig.update_layout(
        plot_bgcolor="white",
        legend=dict(x=0.01, y=0.99, bgcolor="rgba(255,255,255,0.85)", bordercolor="#ddd", borderwidth=1),
        height=450,
        margin=dict(l=60, r=80, t=20, b=80),
    )
    fig.update_xaxes(showgrid=False, tickangle=-30)
    fig.update_yaxes(title_text="Taxa de compressão (×)", showgrid=True, gridcolor="#eeeeee", secondary_y=False)
    fig.update_yaxes(title_text="Queda no Recall@10 (pp)", secondary_y=True)
    return fig


# ── HTML assembler ─────────────────────────────────────────────────────────────

def _write_html(figs: list, bench: pd.DataFrame, dist: pd.DataFrame) -> None:
    import plotly.io as pio

    Path("charts").mkdir(exist_ok=True)
    out = Path("charts/dashboard.html")

    # Calcula métricas para o summary card
    f32_r10  = bench[bench["variant"] == "baseline_f32"]["recall_at_10"].values
    f32_r10  = float(f32_r10[0]) if len(f32_r10) else 0.0
    best_row = bench[bench["recall_at_10"] >= f32_r10 * 0.99].nlargest(1, "compression_vs_f32")
    sweet_label = f"{best_row['variant'].values[0]} {int(best_row['bits'].values[0])}-bit" if not best_row.empty else "N/A"
    sweet_comp  = float(best_row["compression_vs_f32"].values[0]) if not best_row.empty else 1.0
    uniform_2   = bench[(bench["variant"] == "uniform") & (bench["bits"] == 2)]["recall_at_10"]
    uniform_2   = float(uniform_2.values[0]) if not uniform_2.empty else 0.0

    # Inclui Plotly via CDN apenas no primeiro gráfico
    plotly_divs = []
    for i, fig in enumerate(figs):
        include_js = (i == 0)
        plotly_divs.append(pio.to_html(fig, full_html=False, include_plotlyjs="cdn" if include_js else False))

    html = _HTML_TEMPLATE.format(
        sweet_label=sweet_label,
        sweet_comp=f"{sweet_comp:.1f}",
        f32_r10=f"{f32_r10:.3f}",
        uniform_2_r10=f"{uniform_2:.3f}",
        n_variants=len(bench),
        sections=_build_sections(plotly_divs),
    )
    out.write_text(html, encoding="utf-8")


# ── Legenda de variantes e bits ────────────────────────────────────────────────
_LEGEND_HTML = """
<section id="legend" class="chart-section" style="margin-bottom:32px">
  <div class="section-header">
    <span class="section-icon">📖</span>
    <h2 class="section-title">Guia de Leitura — Variantes e Níveis de Bits</h2>
    <span class="badge" style="background:#2980b9">glossário</span>
  </div>

  <!-- Variantes -->
  <div style="padding:20px 24px 8px">
    <h3 style="font-size:.95rem;font-weight:700;color:#2c3e50;margin-bottom:14px;text-transform:uppercase;letter-spacing:.5px">
      Variantes de Quantização
    </h3>
    <div class="legend-grid">

      <div class="legend-card" style="--lc:#333333">
        <div class="lc-header">
          <span class="lc-dot"></span>
          <span class="lc-name">baseline_f32</span>
          <span class="lc-badge" style="background:#e8f4fd;color:#2980b9">refer&ecirc;ncia</span>
        </div>
        <div class="lc-body">
          <b>Embeddings originais em float32</b> (32 bits por valor).
          Nenhuma compressão aplicada. Serve como teto de qualidade:
          todos os resultados são comparados contra este baseline.
        </div>
        <div class="lc-formula">1 vetor &times; dim &times; <b>4 bytes</b> = 1536 B (dim=384)</div>
      </div>

      <div class="legend-card" style="--lc:#888888">
        <div class="lc-header">
          <span class="lc-dot"></span>
          <span class="lc-name">baseline_f16</span>
          <span class="lc-badge" style="background:#f5f5f5;color:#555">compress&atilde;o simples</span>
        </div>
        <div class="lc-body">
          <b>Float16 (meia precis&atilde;o)</b>: divide cada valor de 32 bits para 16 bits
          simplesmente reduzindo a precis&atilde;o num&eacute;rica. Sem transformação do vetor.
          Compressão de <b>2&times;</b> com perda mínima de qualidade.
        </div>
        <div class="lc-formula">1 vetor &times; dim &times; <b>2 bytes</b> = 768 B</div>
      </div>

      <div class="legend-card" style="--lc:#4878CF">
        <div class="lc-header">
          <span class="lc-dot"></span>
          <span class="lc-name">uniform</span>
          <span class="lc-badge" style="background:#eef3fb;color:#4878CF">baseline quantização</span>
        </div>
        <div class="lc-body">
          <b>Quantização escalar uniforme</b>: divide o intervalo [min, max] de todos
          os valores em 2<sup>bits</sup> &minus; 1 bins de largura igual, e armazena o
          índice de cada bin. <em>N&atilde;o aplica rotação</em>. M&eacute;todo mais simples, serve
          como baseline para comparar com os m&eacute;todos mais avan&ccedil;ados.
        </div>
        <div class="lc-formula">bins uniformes &bull; sem rota&ccedil;&atilde;o &bull; dados-dependente (min/max global)</div>
      </div>

      <div class="legend-card" style="--lc:#6ACC65">
        <div class="lc-header">
          <span class="lc-dot"></span>
          <span class="lc-name">lloyd_max</span>
          <span class="lc-badge" style="background:#eefbee;color:#27ae60">codebook &oacute;timo</span>
        </div>
        <div class="lc-body">
          <b>Codebook Lloyd-Max</b>: em vez de bins uniformes, calcula os
          2<sup>bits</sup> centroides que minimizam o MSE para a distribuição
          teórica das coordenadas de um vetor unitário em S<sup>d-1</sup>
          (distribuição Beta concentrada em torno de zero).
          <em>N&atilde;o aplica rotação</em>, por isso o codebook funciona mal sem ela
          — a distribuição real não corresponde à teórica.
        </div>
        <div class="lc-formula">bins &oacute;timos (Lloyd-Max) &bull; sem rota&ccedil;&atilde;o &bull; dados-independente</div>
      </div>

      <div class="legend-card" style="--lc:#D65F5F">
        <div class="lc-header">
          <span class="lc-dot"></span>
          <span class="lc-name">turbo_mse</span>
          <span class="lc-badge" style="background:#fdf0f0;color:#c0392b">TurboQuant MSE</span>
        </div>
        <div class="lc-body">
          <b>TurboQuantMSE</b> (paper TurboQuant): aplica uma <b>rotação ortogonal
          aleatória</b> ao vetor antes de quantizar. A rotação equaliza a energia
          entre todas as dimens&otilde;es, fazendo com que cada coordenada siga
          <em>exatamente</em> a distribuição teórica do codebook Lloyd-Max.
          Resultado: mesmo codebook, qualidade <em>muito</em> superior ao lloyd_max puro.
        </div>
        <div class="lc-formula"><b>rotação Q</b> + codebook Lloyd-Max &bull; dados-independente &bull; reconstruç&atilde;o: Q<sup>T</sup> &times; dequant(idx)</div>
      </div>

      <div class="legend-card" style="--lc:#B47CC7">
        <div class="lc-header">
          <span class="lc-dot"></span>
          <span class="lc-name">turbo_prod</span>
          <span class="lc-badge" style="background:#f9f0fd;color:#8e44ad">TurboQuant Prod</span>
        </div>
        <div class="lc-body">
          <b>TurboQuantProd</b>: extens&atilde;o do MSE que adiciona um segundo passo de
          compress&atilde;o do <em>resíduo</em> usando <b>QJL</b>
          (Johnson-Lindenstrauss Quantizado). Usa (b-1) bits para a parte MSE
          e 1 bit por dimens&atilde;o para o resíduo (sinal de uma projeç&atilde;o gaussiana).
          Elimina o vi&eacute;s de produto interno que o TurboQuantMSE introduz,
          produzindo estimativas de similaridade mais precisas.
        </div>
        <div class="lc-formula">rotaç&atilde;o Q + Lloyd-Max(<b>b-1</b> bits) + QJL resíduo(<b>1</b> bit) &bull; vi&eacute;s &asymp; 0</div>
      </div>

    </div>
  </div>

  <!-- Bits -->
  <div style="padding:16px 24px 20px;border-top:1px solid #f0f2f5">
    <h3 style="font-size:.95rem;font-weight:700;color:#2c3e50;margin-bottom:14px;text-transform:uppercase;letter-spacing:.5px">
      Níveis de Bits — O que significa cada valor
    </h3>
    <div class="bits-grid">

      <div class="bits-card">
        <div class="bits-val">32</div>
        <div class="bits-label">Float32 (baseline)</div>
        <div class="bits-bar"><div class="bits-fill" style="width:100%;background:#333"></div></div>
        <div class="bits-desc">
          Representação padrão de ponto flutuante (IEEE 754).
          <b>1536 bytes/vetor</b> para dim=384. Precisão total,
          sem nenhuma compressão. Baseline de referência.
        </div>
      </div>

      <div class="bits-card">
        <div class="bits-val">16</div>
        <div class="bits-label">Float16 (baseline)</div>
        <div class="bits-bar"><div class="bits-fill" style="width:50%;background:#888"></div></div>
        <div class="bits-desc">
          Meia precisão. <b>768 bytes/vetor</b> (2&times; menor).
          Trunca mantissa de 23 para 10 bits. Perda de qualidade
          mínima. Compressão trivial sem algoritmo especial.
        </div>
      </div>

      <div class="bits-card highlight">
        <div class="bits-val">8</div>
        <div class="bits-label">8-bit quantizado</div>
        <div class="bits-bar"><div class="bits-fill" style="width:25%;background:#D65F5F"></div></div>
        <div class="bits-desc">
          256 níveis possíveis por dimensão.
          <b>386 bytes/vetor</b> (4&times; menor).
          Qualidade próxima do float32 para todos os métodos.
          Ponto de entrada conservador para produção.
        </div>
      </div>

      <div class="bits-card highlight sweet">
        <div class="bits-val">4</div>
        <div class="bits-label">4-bit quantizado</div>
        <div class="bits-bar"><div class="bits-fill" style="width:12.5%;background:#27ae60"></div></div>
        <div class="bits-desc">
          16 níveis possíveis por dimensão.
          <b>194 bytes/vetor</b> (8&times; menor).
          <span style="color:#27ae60;font-weight:700">Sweet spot do paper TurboQuant</span>:
          TurboQuantMSE 4-bit mantém qualidade igual ao float32
          com 8&times; menos memória.
        </div>
      </div>

      <div class="bits-card">
        <div class="bits-val">2</div>
        <div class="bits-label">2-bit quantizado</div>
        <div class="bits-bar"><div class="bits-fill" style="width:6.25%;background:#e67e22"></div></div>
        <div class="bits-desc">
          4 níveis possíveis por dimensão.
          <b>98 bytes/vetor</b> (16&times; menor).
          Compressão extrema: <em>uniform 2-bit</em> colapsa
          (Recall@10 cai >40pp). TurboQuantMSE aguenta
          com perda &lt;2pp gra&ccedil;as &agrave; rotação ortogonal.
        </div>
      </div>

    </div>
  </div>

  <!-- Como os métodos se comparam -->
  <div style="padding:0 24px 20px;border-top:1px solid #f0f2f5">
    <h3 style="font-size:.95rem;font-weight:700;color:#2c3e50;margin:16px 0 14px;text-transform:uppercase;letter-spacing:.5px">
      Relação entre os Métodos
    </h3>
    <div class="pipeline-row">
      <div class="pipe-step" style="--pc:#4878CF">
        <div class="pipe-icon">①</div>
        <div class="pipe-name">uniform</div>
        <div class="pipe-desc">bins iguais<br>sem rotação</div>
      </div>
      <div class="pipe-arrow">→ <span>+ codebook<br>&oacute;timo</span></div>
      <div class="pipe-step" style="--pc:#6ACC65">
        <div class="pipe-icon">②</div>
        <div class="pipe-name">lloyd_max</div>
        <div class="pipe-desc">bins &oacute;timos<br>sem rotação</div>
      </div>
      <div class="pipe-arrow">→ <span>+ rotação<br>ortogonal</span></div>
      <div class="pipe-step" style="--pc:#D65F5F">
        <div class="pipe-icon">③</div>
        <div class="pipe-name">turbo_mse</div>
        <div class="pipe-desc">rotação +<br>bins &oacute;timos</div>
      </div>
      <div class="pipe-arrow">→ <span>+ QJL<br>resíduo</span></div>
      <div class="pipe-step" style="--pc:#B47CC7">
        <div class="pipe-icon">④</div>
        <div class="pipe-name">turbo_prod</div>
        <div class="pipe-desc">rotação +<br>bins + QJL</div>
      </div>
    </div>
    <p style="font-size:.82rem;color:#7f8c8d;margin-top:10px;padding:0 4px">
      Cada seta adiciona um componente do paper TurboQuant.
      A rotação ortogonal (②→③) &eacute; o insight mais importante:
      aumenta o Cosine Sim médio de ~0.79 para ~0.98 no 4-bit
      sem alterar a taxa de compressão.
    </p>
  </div>

</section>
"""


def _build_sections(plotly_divs: list[str]) -> str:
    parts = [_LEGEND_HTML]   # legenda sempre primeiro
    for meta, div in zip(CHART_META, plotly_divs):
        badge_html = (
            f'<span class="badge" style="background:{meta["badge_color"]}">'
            f'{meta["badge"]}</span>'
        )
        parts.append(f"""
<section id="{meta['id']}" class="chart-section">
  <div class="section-header">
    <span class="section-icon">{meta['icon']}</span>
    <h2 class="section-title">{meta['title']}</h2>
    {badge_html}
  </div>

  <div class="desc-grid">
    <div class="desc-card what">
      <div class="desc-label">📌 O que mostra</div>
      <div class="desc-body">{meta['what']}</div>
    </div>
    <div class="desc-card how">
      <div class="desc-label">🔍 Como ler</div>
      <div class="desc-body">{meta['how']}</div>
    </div>
    <div class="desc-card impact">
      <div class="desc-label">⚡ Impacto prático</div>
      <div class="desc-body">{meta['impact']}</div>
    </div>
  </div>

  <div class="chart-wrap">
    {div}
  </div>
</section>
""")
    return "\n".join(parts)


# ── Template HTML ──────────────────────────────────────────────────────────────

_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>RAG Embedding Compression Lab — Dashboard</title>
<style>
/* ── Reset & Base ─────────────────────────────────── */
*, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  background: #f0f2f5;
  color: #2c3e50;
  line-height: 1.6;
}}

/* ── Header ───────────────────────────────────────── */
header {{
  background: linear-gradient(135deg, #1a252f 0%, #2c3e50 60%, #34495e 100%);
  color: white;
  padding: 28px 40px 20px;
}}
header h1 {{
  font-size: 1.6rem;
  font-weight: 700;
  letter-spacing: -0.3px;
  margin-bottom: 6px;
}}
header p {{
  color: #bdc3c7;
  font-size: 0.9rem;
}}
.header-chips {{
  display: flex;
  gap: 10px;
  margin-top: 14px;
  flex-wrap: wrap;
}}
.chip {{
  background: rgba(255,255,255,0.12);
  border: 1px solid rgba(255,255,255,0.2);
  border-radius: 20px;
  padding: 3px 12px;
  font-size: 0.78rem;
  color: #ecf0f1;
}}

/* ── Summary Cards ────────────────────────────────── */
.summary-bar {{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 14px;
  padding: 20px 40px;
  background: #e8ecf0;
  border-bottom: 1px solid #d5dde5;
}}
.summary-card {{
  background: white;
  border-radius: 10px;
  padding: 16px 20px;
  box-shadow: 0 1px 4px rgba(0,0,0,0.07);
  border-left: 4px solid var(--accent, #4878CF);
}}
.summary-card .label {{ font-size: 0.75rem; color: #7f8c8d; text-transform: uppercase; letter-spacing: 0.5px; }}
.summary-card .value {{ font-size: 1.6rem; font-weight: 700; color: var(--accent, #4878CF); margin: 2px 0; }}
.summary-card .sub   {{ font-size: 0.78rem; color: #95a5a6; }}

/* ── Nav ──────────────────────────────────────────── */
nav {{
  background: white;
  border-bottom: 1px solid #e0e4e8;
  padding: 0 40px;
  position: sticky;
  top: 0;
  z-index: 100;
  box-shadow: 0 2px 8px rgba(0,0,0,0.06);
}}
nav ul {{
  display: flex;
  list-style: none;
  gap: 0;
  overflow-x: auto;
  scrollbar-width: none;
}}
nav ul::-webkit-scrollbar {{ display: none; }}
nav a {{
  display: block;
  padding: 14px 18px;
  text-decoration: none;
  color: #7f8c8d;
  font-size: 0.85rem;
  font-weight: 500;
  border-bottom: 3px solid transparent;
  white-space: nowrap;
  transition: color .2s, border-color .2s;
}}
nav a:hover {{ color: #2c3e50; border-color: #bdc3c7; }}

/* ── Main content ─────────────────────────────────── */
main {{ padding: 24px 40px 60px; max-width: 1400px; margin: 0 auto; }}

/* ── Section ──────────────────────────────────────── */
.chart-section {{
  background: white;
  border-radius: 12px;
  box-shadow: 0 1px 6px rgba(0,0,0,0.08);
  margin-bottom: 32px;
  overflow: hidden;
}}
.section-header {{
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 18px 24px 14px;
  border-bottom: 1px solid #f0f2f5;
  flex-wrap: wrap;
}}
.section-icon {{ font-size: 1.5rem; }}
.section-title {{
  font-size: 1.1rem;
  font-weight: 700;
  color: #2c3e50;
  flex: 1;
}}
.badge {{
  padding: 3px 11px;
  border-radius: 12px;
  font-size: 0.72rem;
  font-weight: 600;
  color: white;
  text-transform: uppercase;
  letter-spacing: 0.4px;
}}

/* ── Description cards ────────────────────────────── */
.desc-grid {{
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 0;
  border-bottom: 1px solid #f0f2f5;
}}
@media (max-width: 860px) {{
  .desc-grid {{ grid-template-columns: 1fr; }}
}}
.desc-card {{
  padding: 16px 22px;
  border-right: 1px solid #f0f2f5;
  font-size: 0.85rem;
  color: #4a5568;
}}
.desc-card:last-child {{ border-right: none; }}
.desc-label {{
  font-weight: 700;
  font-size: 0.78rem;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 7px;
  color: #2c3e50;
}}
.desc-card.what   {{ background: #fafbff; }}
.desc-card.how    {{ background: #fffaf5; }}
.desc-card.impact {{ background: #f5fff8; }}

/* ── Chart wrapper ────────────────────────────────── */
.chart-wrap {{ padding: 12px 16px 4px; }}
/* ── Legend cards ────────────────────────────────── */
.legend-grid {{
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 14px;
  margin-bottom: 4px;
}}
.legend-card {{
  border: 1.5px solid #e8ecf0;
  border-left: 4px solid var(--lc, #ccc);
  border-radius: 8px;
  padding: 14px 16px;
  background: #fafbfc;
}}
.lc-header {{
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}}
.lc-dot {{
  width: 12px; height: 12px;
  border-radius: 50%;
  background: var(--lc, #ccc);
  flex-shrink: 0;
}}
.lc-name {{
  font-family: "SFMono-Regular", Consolas, monospace;
  font-size: .88rem;
  font-weight: 700;
  color: #2c3e50;
}}
.lc-badge {{
  margin-left: auto;
  padding: 2px 8px;
  border-radius: 10px;
  font-size: .7rem;
  font-weight: 600;
}}
.lc-body {{
  font-size: .83rem;
  color: #4a5568;
  line-height: 1.55;
  margin-bottom: 8px;
}}
.lc-formula {{
  font-size: .75rem;
  color: #7f8c8d;
  background: #f0f2f5;
  border-radius: 4px;
  padding: 5px 9px;
  font-family: "SFMono-Regular", Consolas, monospace;
}}

/* ── Bits cards ─────────────────────────────────────── */
.bits-grid {{
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(190px, 1fr));
  gap: 12px;
}}
.bits-card {{
  border: 1.5px solid #e8ecf0;
  border-radius: 8px;
  padding: 14px;
  background: #fafbfc;
}}
.bits-card.highlight {{ border-color: #d0dff5; background: #f7faff; }}
.bits-card.sweet      {{ border-color: #b7e4c7; background: #f0fdf4; }}
.bits-val {{
  font-size: 2.2rem;
  font-weight: 800;
  color: #2c3e50;
  line-height: 1;
}}
.bits-label {{ font-size: .78rem; color: #7f8c8d; margin: 3px 0 8px; }}
.bits-bar {{
  height: 6px;
  background: #e8ecf0;
  border-radius: 3px;
  margin-bottom: 10px;
  overflow: hidden;
}}
.bits-fill {{ height: 100%; border-radius: 3px; }}
.bits-desc {{ font-size: .8rem; color: #4a5568; line-height: 1.5; }}

/* ── Pipeline row ─────────────────────────────────── */
.pipeline-row {{
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  padding: 4px 0;
}}
.pipe-step {{
  border: 2px solid var(--pc, #ccc);
  border-radius: 10px;
  padding: 10px 14px;
  text-align: center;
  min-width: 100px;
  background: #fafbfc;
}}
.pipe-icon {{ font-size: 1.1rem; margin-bottom: 3px; }}
.pipe-name {{
  font-family: monospace;
  font-size: .82rem;
  font-weight: 700;
  color: var(--pc, #333);
}}
.pipe-desc {{ font-size: .73rem; color: #7f8c8d; margin-top: 3px; line-height: 1.4; }}
.pipe-arrow {{ color: #bdc3c7; font-size: 1.1rem; text-align: center; flex-shrink: 0; }}
.pipe-arrow span {{ font-size: .7rem; color: #7f8c8d; display: block; line-height: 1.3; }}



/* ── Footer ───────────────────────────────────────── */
footer {{
  text-align: center;
  color: #95a5a6;
  font-size: 0.8rem;
  padding: 20px;
  border-top: 1px solid #e0e4e8;
  background: white;
}}
</style>
</head>
<body>

<!-- ── Header ──────────────────────────────────────────── -->
<header>
  <h1>📊 RAG Embedding Compression Lab — Dashboard</h1>
  <p>Análise completa do impacto da quantização de embeddings na qualidade de retrieval</p>
  <div class="header-chips">
    <span class="chip">📄 {n_variants} configurações analisadas</span>
    <span class="chip">🤖 Modelo: BAAI/bge-small-en-v1.5 (dim=384)</span>
    <span class="chip">4 variantes × 3 bits</span>
    <span class="chip">TurboQuant</span>
  </div>
</header>

<!-- ── Summary Bar ─────────────────────────────────────── -->
<div class="summary-bar">
  <div class="summary-card" style="--accent:#27ae60">
    <div class="label">Sweet Spot</div>
    <div class="value" style="font-size:1.15rem">{sweet_label}</div>
    <div class="sub">{sweet_comp}× compressão, Recall@10 ≈ float32</div>
  </div>
  <div class="summary-card" style="--accent:#2980b9">
    <div class="label">Baseline float32</div>
    <div class="value">{f32_r10}</div>
    <div class="sub">Recall@10 de referência</div>
  </div>
  <div class="summary-card" style="--accent:#e74c3c">
    <div class="label">Uniform 2-bit R@10</div>
    <div class="value">{uniform_2_r10}</div>
    <div class="sub">Sem rotação = colapso de qualidade</div>
  </div>
  <div class="summary-card" style="--accent:#8e44ad">
    <div class="label">Métrica principal</div>
    <div class="value">Recall@10</div>
    <div class="sub">Fração de queries com relevante no top-10</div>
  </div>
</div>

<!-- ── Nav ─────────────────────────────────────────────── -->
<nav>
  <ul>
    <li><a href="#legend" style="color:#2980b9;font-weight:600">📖 Legenda</a></li>
    <li><a href="#overview">📋 Tabela</a></li>
    <li><a href="#recall_line">📈 Recall vs Bits</a></li>
    <li><a href="#tradeoff">⭐ Trade-off</a></li>
    <li><a href="#mse">📐 MSE</a></li>
    <li><a href="#heatmap">🌡️ IP Heatmap</a></li>
    <li><a href="#compression">🗜️ Compressão</a></li>
  </ul>
</nav>

<!-- ── Main ────────────────────────────────────────────── -->
<main>
{sections}
</main>

<!-- ── Footer ──────────────────────────────────────────── -->
<footer>
  RAG Embedding Compression Lab &nbsp;·&nbsp; Gerado por <code>make visualize</code>
  &nbsp;·&nbsp; Baseado no paper TurboQuant
</footer>

</body>
</html>
"""
