"""
src/visualization/_dashboard_figs.py
---------------------------------------
Funções geradoras de figuras Plotly para o dashboard interativo.
Importado por src/visualization/dashboard.py.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

# ── Paleta compartilhada ───────────────────────────────────────────────────────
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

def _table_fig(bench: pd.DataFrame, dist: pd.DataFrame):
    import plotly.graph_objects as go

    merged = bench.copy()
    dist_sub = dist[~dist["variant"].str.startswith("baseline")][
        ["variant", "bits", "mse", "cosine_error", "ip_bias", "ip_mae"]
    ]
    merged = merged.merge(dist_sub, on=["variant", "bits"], how="left")

    def fmt(v):
        if pd.isna(v):
            return "—"
        if isinstance(v, float):
            return f"{v:.4f}"
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
        for x, y in zip(xs, ys, strict=True):
            all_pts.append((float(x), float(y)))

    # Fronteira de Pareto
    pts = sorted(set(all_pts))
    pareto, best_y = [], -1.0
    for x, y in pts:
        if y > best_y:
            pareto.append((x, y))
            best_y = y
    if len(pareto) > 1:
        px, py = zip(*pareto, strict=False)
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
        val_range = z[i].max() - z[i].min()
        z_norm[i] = (z[i] - z[i].min()) / val_range if val_range > 0 else np.zeros_like(z[i])

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



def _memory_fig(bench: pd.DataFrame):
    """Barras horizontais: embed_size_mb por variante+bits, cor = compressão."""
    import plotly.graph_objects as go

    # Gradiente manual: vermelho (baixa compressão) → verde (alta compressão)
    def _comp_to_color(comp: float) -> str:
        t = min(max((comp - 1.0) / 15.0, 0.0), 1.0)
        r = int(220 * (1 - t) + 39 * t)
        g = int(50  * (1 - t) + 174 * t)
        b = int(50  * (1 - t) + 96  * t)
        return f"rgb({r},{g},{b})"

    rows_sel = []
    order = ["baseline_f32", "baseline_f16"] + ["uniform", "lloyd_max", "turbo_mse", "turbo_prod"]
    for var in order:
        sub = bench[bench["variant"] == var].sort_values("bits", ascending=False)
        for _, r in sub.iterrows():
            rows_sel.append(r)

    labels_y, xs, comp_vals, bar_colors = [], [], [], []
    for r in rows_sel:
        var  = r["variant"]
        bits = int(r["bits"])
        mb   = r["embed_size_mb"]
        comp = r["compression_vs_f32"]
        lbl  = f"{var}  {bits}-bit" if not var.startswith("base") else var.replace("baseline_", "float")
        labels_y.append(lbl)
        xs.append(mb)
        comp_vals.append(comp)
        bar_colors.append(_comp_to_color(comp))

    fig = go.Figure(go.Bar(
        x=xs, y=labels_y, orientation="h",
        marker_color=bar_colors,
        marker_line_color="white", marker_line_width=1,
        text=[f"{mb:.3f} MB  ({c:.1f}×)" for mb, c in zip(xs, comp_vals, strict=True)],
        textposition="outside",
        hovertemplate="<b>%{y}</b><br>Tamanho: %{x:.3f} MB<br>Compressão: %{text}<extra></extra>",
    ))
    fig.update_layout(
        xaxis=dict(title="Tamanho (MB)", showgrid=True, gridcolor="#eeeeee"),
        yaxis=dict(autorange="reversed"),
        plot_bgcolor="white",
        height=max(350, len(labels_y) * 30),
        margin=dict(l=180, r=160, t=20, b=50),
    )
    return fig


def _degradation_fig(ranks_path):
    """Violin: distribuição do rank do relevante por variante."""
    import plotly.graph_objects as go

    if not ranks_path.exists():
        fig = go.Figure()
        fig.add_annotation(text="per_query_ranks.csv não encontrado.<br>Execute: make retrieval-bench",
                           xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False, font_size=14)
        fig.update_layout(height=200)
        return fig

    import pandas as _pd
    df = _pd.read_csv(str(ranks_path))

    focus = {
        "baseline_f32_32": ("float32 (baseline)", "#333333"),
        "turbo_mse_8":     ("turbo_mse 8-bit",    "#D65F5F"),
        "turbo_mse_4":     ("turbo_mse 4-bit",     "#D65F5F"),
        "turbo_mse_2":     ("turbo_mse 2-bit",     "#D65F5F"),
        "uniform_4":       ("uniform 4-bit",        "#4878CF"),
        "uniform_2":       ("uniform 2-bit",        "#4878CF"),
    }
    available = {k: v for k, v in focus.items() if k in df.columns}
    cap = 25

    fig = go.Figure()
    for col, (lbl, color) in available.items():
        vals = df[col].clip(upper=cap).tolist()
        fig.add_trace(go.Violin(
            y=vals, name=lbl,
            line_color=color, fillcolor=color, opacity=0.5,
            box_visible=True, meanline_visible=True,
            points="all", pointpos=0,
            marker=dict(size=3, opacity=0.4, color=color),
            hovertemplate=f"<b>{lbl}</b><br>Rank: %{{y}}<extra></extra>",
        ))

    fig.update_layout(
        yaxis=dict(
            title=f"Rank do relevante (cap={cap})",
            tickvals=[1, 5, 10, cap],
            ticktext=["1", "5", "10", f">{cap-1}"],
            showgrid=True, gridcolor="#eeeeee",
        ),
        xaxis=dict(showgrid=False),
        plot_bgcolor="white",
        showlegend=True,
        legend=dict(x=0.01, y=0.99),
        height=450,
        margin=dict(l=60, r=20, t=20, b=60),
    )
    return fig


def _latency_fig(bench: pd.DataFrame):
    """Barras: latência mediana (ms/query) por variante."""
    import plotly.graph_objects as go

    quant = bench[~bench["variant"].str.startswith("baseline")].copy()
    quant["label"] = quant["variant"].str.replace("_", " ") + " " + quant["bits"].astype(str) + "b"
    quant = quant.sort_values(["variant", "bits"], ascending=[True, False])

    base_lat = bench[bench["variant"] == "baseline_f32"]["latency_ms"].values[0]
    bar_colors = [COLORS.get(v, "#aaaaaa") for v in quant["variant"]]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=quant["label"], y=quant["latency_ms"],
        marker_color=bar_colors, opacity=0.85,
        marker_line_color="white", marker_line_width=1,
        text=[f"{v:.3f} ms" for v in quant["latency_ms"]],
        textposition="outside",
        hovertemplate="<b>%{x}</b><br>Latência: %{y:.4f} ms/query<extra></extra>",
    ))
    fig.add_hline(
        y=base_lat, line_dash="dash", line_color="#333333", line_width=1.5,
        annotation_text=f"  float32 ({base_lat:.3f} ms)",
        annotation_position="right",
        annotation_font_color="#333333",
    )
    fig.update_layout(
        xaxis=dict(title="Variante", showgrid=False, tickangle=-30),
        yaxis=dict(title="Latência mediana (ms/query)", showgrid=True, gridcolor="#eeeeee"),
        plot_bgcolor="white",
        height=420,
        margin=dict(l=60, r=80, t=20, b=90),
    )
    return fig


