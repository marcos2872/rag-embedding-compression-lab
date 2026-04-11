"""
src/rag/pipeline.py
---------------------
Pipeline RAG completo — Fase 7.

Fluxo por variante:
  query (texto)
    → embed_query()   [sentence-transformers, mesmo modelo do corpus]
    → index.search()  [IndexFlatIP do FAISS, já construído na Fase 5]
    → top-k chunks    [texto + score + metadados]
    → build_context() [concatena chunks com separador]
    → call_llm()      [mock | Ollama | OpenAI-compatible]
    → resposta formatada

Nomes de variante aceitos pelo CLI:
  f32, f16,
  uniform_2bit, uniform_4bit, uniform_8bit,
  lloyd_max_2bit, ..., turbo_mse_4bit, ..., turbo_prod_8bit
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

import numpy as np
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

console = Console()

# ── Mapeamento de nome → arquivo de índice ─────────────────────────────────────

def _index_path(variant: str) -> Path:
    """Converte nome de variante para caminho do arquivo .index."""
    variant = variant.strip().lower()
    if variant in ("f32", "baseline_f32"):
        return Path("indexes/faiss_f32.index")
    if variant in ("f16", "baseline_f16"):
        return Path("indexes/faiss_f16.index")
    # Ex: "turbo_mse_4bit", "uniform_2bit"
    return Path(f"indexes/faiss_{variant}.index")


# ── RAGPipeline ────────────────────────────────────────────────────────────────

class RAGPipeline:
    """
    Pipeline RAG single-variant.

    Parâmetros
    ----------
    variant   : nome da variante (ex: "f32", "turbo_mse_4bit")
    corpus    : lista de dicts com 'id', 'text', 'metadata'
    model     : SentenceTransformer já carregado
    """

    def __init__(
        self,
        variant: str,
        corpus: list[dict],
        model,
    ) -> None:
        import faiss

        self.variant  = variant
        self.corpus   = corpus
        self.model    = model
        self.id2doc   = {d["id"]: d for d in corpus}

        idx_path = _index_path(variant)
        if not idx_path.exists():
            raise FileNotFoundError(
                f"Índice não encontrado: {idx_path}\n"
                "Execute: make build-indexes"
            )
        self.index = faiss.read_index(str(idx_path))

    def embed_query(self, query: str) -> np.ndarray:
        """Embeda a query com o mesmo modelo/normalização do corpus."""
        vec = self.model.encode(
            [query],
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        return vec.astype(np.float32)

    def search(self, query: str, k: int = 5) -> list[dict]:
        """
        Busca top-k documentos relevantes.

        Retorna lista de dicts com:
          id, text, score, metadata, rank
        """
        q_vec = self.embed_query(query)
        scores, indices = self.index.search(q_vec, k)

        results = []
        for rank, (score, idx) in enumerate(zip(scores[0], indices[0]), start=1):
            if idx < 0 or idx >= len(self.corpus):
                continue
            doc = self.corpus[idx]
            results.append({
                "rank":     rank,
                "id":       doc["id"],
                "text":     doc["text"],
                "score":    float(score),
                "metadata": doc.get("metadata", {}),
            })
        return results

    def build_context(self, results: list[dict], max_chunks: int = 5) -> str:
        """Concatena os chunks recuperados como contexto para o LLM."""
        parts = []
        for r in results[:max_chunks]:
            source = r["metadata"].get("source", "?")
            parts.append(f"[{r['rank']}] (fonte: {source})\n{r['text']}")
        return "\n\n---\n\n".join(parts)

    def answer(
        self,
        query: str,
        k: int = 5,
        llm_backend: Optional[str] = None,
        llm_model: Optional[str] = None,
    ) -> dict:
        """
        Executa o pipeline completo e retorna um dict com todos os detalhes.
        """
        from src.rag.prompting import call_llm

        results = self.search(query, k=k)
        context = self.build_context(results, max_chunks=k)
        chunk_texts = [r["text"] for r in results]

        answer_text, backend_used = call_llm(
            query         = query,
            context       = context,
            context_chunks= chunk_texts,
            backend       = llm_backend,
            model         = llm_model,
        )

        return {
            "query":        query,
            "variant":      self.variant,
            "results":      results,
            "context":      context,
            "answer":       answer_text,
            "backend":      backend_used,
            "docs_used":    [r["id"] for r in results],
        }


# ── Carregamento compartilhado ─────────────────────────────────────────────────

def _load_shared(model_name: Optional[str] = None, device: Optional[str] = None):
    """Carrega corpus e modelo uma única vez para uso por múltiplos pipelines."""
    import yaml
    from dotenv import load_dotenv
    load_dotenv()

    corpus_path = os.getenv("CORPUS_PATH", "data/corpus.jsonl")
    corpus = [json.loads(l) for l in Path(corpus_path).read_text().splitlines()]

    cfg = yaml.safe_load(open("configs/embedding.yaml")) or {}
    mname  = model_name or os.getenv("EMBEDDING_MODEL") or cfg.get("model", "BAAI/bge-small-en-v1.5")
    device = device or os.getenv("EMBEDDING_DEVICE", "cpu")

    from sentence_transformers import SentenceTransformer
    console.print(f"  [cyan]Carregando modelo:[/cyan] {mname}  device={device}")
    model = SentenceTransformer(mname, device=device)

    return corpus, model


# ── Demo CLI ───────────────────────────────────────────────────────────────────

def run_demo(
    query: str,
    variants: list[str],
    k: int = 5,
    llm_backend: Optional[str] = None,
    llm_model: Optional[str] = None,
) -> None:
    """
    Executa o demo RAG para múltiplas variantes e exibe comparação.
    Chamado pelo comando `make rag-demo QUERY="..."`.
    """
    console.print(f"\n[bold cyan]RAG Demo — Fase 7[/bold cyan]\n")
    console.print(Panel(f"[bold]{query}[/bold]", title="Query", border_style="cyan"))
    console.print()

    corpus, model = _load_shared()
    console.print(f"  [dim]Corpus: {len(corpus)} chunks[/dim]\n")

    # Cria um pipeline por variante
    pipelines: dict[str, RAGPipeline] = {}
    for v in variants:
        try:
            pipelines[v] = RAGPipeline(variant=v, corpus=corpus, model=model)
        except FileNotFoundError as e:
            console.print(f"  [yellow]⚠ {v}: {e}[/yellow]")

    if not pipelines:
        console.print("[red]Nenhum índice encontrado. Execute: make build-indexes[/red]")
        return

    # Executa cada pipeline
    # Pequena pausa entre chamadas para evitar rate-limit em APIs com tier gratuito
    import time
    all_results: dict[str, dict] = {}
    for i, (v, pipe) in enumerate(pipelines.items()):
        if i > 0:
            time.sleep(1.5)   # 1.5s entre chamadas — suficiente para a maioria dos free-tiers
        console.print(f"  [cyan]Buscando:[/cyan] {v}…")
        all_results[v] = pipe.answer(query, k=k, llm_backend=llm_backend, llm_model=llm_model)

    console.print()

    # ── Tabela de documentos recuperados ──────────────────────────────────────
    _print_results_table(query, all_results, k)

    # ── Tabela de respostas ────────────────────────────────────────────────────
    _print_answers(all_results)

    # ── Análise de divergência ─────────────────────────────────────────────────
    _print_divergence(all_results)


def _print_results_table(query: str, all_results: dict, k: int) -> None:
    """Tabela comparativa dos documentos recuperados por cada variante."""
    t = Table(
        title=f"Top-{k} documentos recuperados por variante",
        show_lines=True, expand=True,
    )
    t.add_column("Rank", justify="center", width=5)

    variants = list(all_results.keys())
    for v in variants:
        t.add_column(v, min_width=28)

    # Referência: IDs do f32 (ou primeira variante)
    ref_ids = {r["id"] for r in all_results[variants[0]]["results"]}

    for rank in range(1, k + 1):
        row = [str(rank)]
        for v in variants:
            results = all_results[v]["results"]
            if rank - 1 < len(results):
                r   = results[rank - 1]
                doc_id = r["id"]
                score  = r["score"]
                source = r["metadata"].get("source", "?")[:25]
                text_preview = r["text"][:60].replace("\n", " ") + "…"

                # Verde se igual ao f32, vermelho se diferente
                in_ref = doc_id in ref_ids
                color  = "green" if (v == variants[0] or in_ref) else "yellow"
                cell   = Text()
                cell.append(f"{score:.3f}  ", style="dim")
                cell.append(f"{doc_id}\n", style=f"bold {color}")
                cell.append(f"{source}\n", style="dim")
                cell.append(text_preview, style="dim")
            else:
                cell = Text("—", style="dim")
            row.append(cell)

        t.add_row(*row)

    console.print(t)
    console.print()


def _print_answers(all_results: dict) -> None:
    """Painel com as respostas geradas por cada variante."""
    for v, data in all_results.items():
        backend = data["backend"]
        answer = data["answer"]

        # Separa erro de fallback (linha com ⚠) do corpo da resposta
        error_line = ""
        if "\n\n[⚠" in answer:
            body, error_line = answer.rsplit("\n\n[⚠", 1)
            error_line = "[⚠" + error_line
        else:
            body = answer

        # Trunca só o corpo, nunca a mensagem de erro
        if len(body) > 400:
            body = body[:400] + "…"

        display = body + (f"\n\n[yellow]{error_line}[/yellow]" if error_line else "")

        border = "red" if error_line else "dim"
        console.print(Panel(
            display,
            title=f"[bold cyan]{v}[/bold cyan]  [dim](LLM: {backend})[/dim]",
            border_style=border,
            padding=(0, 1),
        ))
    console.print()


def _print_divergence(all_results: dict) -> None:
    """Analisa se as variantes retornaram documentos diferentes do f32."""
    variants = list(all_results.keys())
    if len(variants) < 2:
        return

    ref_v    = variants[0]
    ref_ids  = [r["id"] for r in all_results[ref_v]["results"]]
    ref_set  = set(ref_ids)

    t = Table(title="Divergência em relação ao float32", show_lines=True)
    t.add_column("Variante",      style="cyan")
    t.add_column("Docs em comum", justify="center")
    t.add_column("Docs diferentes", justify="center")
    t.add_column("Top-1 idêntico?", justify="center")
    t.add_column("Status")

    for v in variants[1:]:
        v_ids = [r["id"] for r in all_results[v]["results"]]
        common   = len(set(v_ids) & ref_set)
        diff     = len(set(v_ids) - ref_set)
        top1_ok  = (v_ids[0] == ref_ids[0]) if v_ids and ref_ids else False
        k_total  = len(ref_ids)

        pct = common / k_total * 100 if k_total else 0
        if pct >= 80:
            status = "[green]✓ Qualidade mantida[/green]"
        elif pct >= 60:
            status = "[yellow]⚠ Degradação leve[/yellow]"
        else:
            status = "[red]✗ Degradação severa[/red]"

        t.add_row(
            v,
            f"{common}/{k_total} ({pct:.0f}%)",
            str(diff),
            "[green]Sim[/green]" if top1_ok else "[red]Não[/red]",
            status,
        )

    console.print(t)
    console.print()
