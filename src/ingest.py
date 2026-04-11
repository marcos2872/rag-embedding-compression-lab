"""
src/ingest.py
-------------
Carrega arquivos de data/raw/ (PDF, TXT, MD), aplica chunking e
grava data/corpus.jsonl + data/processed/<nome>.jsonl por arquivo.

Formato de cada linha do corpus.jsonl:
  {
    "id": "<stem>-p<page>-c<chunk_idx>",
    "text": "...",
    "metadata": {
      "source": "arquivo.pdf",
      "page": 1,         # None para txt/md
      "chunk_idx": 0,
      "type": "pdf"      # "pdf" | "txt" | "md"
    }
  }
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from rich.console import Console
from rich.progress import track

from src.chunking import sliding_window

console = Console()

# ── Leitores por extensão ──────────────────────────────────────────────────────

def read_pdf(path: Path) -> list[dict]:
    """Extrai texto de um PDF página a página usando pymupdf (fitz)."""
    try:
        import fitz  # pymupdf
    except ImportError:
        console.print("[red]pymupdf não instalado. Execute: uv sync[/red]")
        raise

    doc = fitz.open(str(path))
    pages: list[dict] = []
    for i, page in enumerate(doc):
        text = page.get_text("text")
        if text.strip():
            pages.append({
                "text": text,
                "page": i + 1,
                "source": path.name,
            })
    doc.close()
    return pages


def read_txt(path: Path) -> list[dict]:
    """Lê um arquivo .txt como bloco único."""
    text = path.read_text(encoding="utf-8", errors="replace")
    return [{"text": text, "page": None, "source": path.name}]


def _strip_markdown(text: str) -> str:
    """Remove marcações Markdown comuns sem alterar o conteúdo textual."""
    # Headers  ## Título → Título
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)
    # Bold/italic
    text = re.sub(r"\*{1,3}(.+?)\*{1,3}", r"\1", text)
    text = re.sub(r"_{1,3}(.+?)_{1,3}", r"\1", text)
    # Inline code
    text = re.sub(r"`(.+?)`", r"\1", text)
    # Code blocks
    text = re.sub(r"```[\s\S]*?```", "", text)
    # Links [text](url) → text
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    # Images ![alt](url) → alt
    text = re.sub(r"!\[([^\]]*)\]\([^)]+\)", r"\1", text)
    # Horizontal rules
    text = re.sub(r"^[-*_]{3,}\s*$", "", text, flags=re.MULTILINE)
    # HTML tags
    text = re.sub(r"<[^>]+>", "", text)
    # Table separators
    text = re.sub(r"^\|[-| :]+\|$", "", text, flags=re.MULTILINE)
    return text


def read_md(path: Path) -> list[dict]:
    """Lê um arquivo .md, opcionalmente stripando marcação."""
    text = path.read_text(encoding="utf-8", errors="replace")
    text = _strip_markdown(text)
    return [{"text": text, "page": None, "source": path.name}]


# ── Funções auxiliares ─────────────────────────────────────────────────────────

def _make_id(stem: str, page: int | None, chunk_idx: int) -> str:
    """Gera id no formato <stem>-p<page>-c<chunk_idx>."""
    stem_clean = re.sub(r"[^a-zA-Z0-9_-]", "-", stem)
    page_str = f"p{page:02d}" if page is not None else "p00"
    return f"{stem_clean}-{page_str}-c{chunk_idx:04d}"


def _get_file_type(path: Path) -> str:
    return path.suffix.lower().lstrip(".")


READERS = {
    ".pdf": read_pdf,
    ".txt": read_txt,
    ".md": read_md,
}


# ── Pipeline principal ─────────────────────────────────────────────────────────

def ingest(
    input_dir: str | Path,
    output_path: str | Path = "data/corpus.jsonl",
    chunk_size: int = 256,
    chunk_overlap: int = 32,
    min_chunk_length: int = 50,
) -> int:
    """
    Varre `input_dir` em busca de .pdf, .txt e .md,
    aplica chunking e grava `output_path`.

    Retorna o número total de chunks gerados.
    """
    input_dir    = Path(input_dir)
    output_path  = Path(output_path)
    processed_dir = output_path.parent / "processed"
    processed_dir.mkdir(parents=True, exist_ok=True)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    files: list[Path] = []
    for ext in READERS:
        files.extend(sorted(input_dir.rglob(f"*{ext}")))

    if not files:
        console.print(f"[yellow]⚠ Nenhum arquivo .pdf/.txt/.md encontrado em {input_dir}[/yellow]")
        return 0

    console.print(f"\n[bold cyan]Ingestão:[/bold cyan] {len(files)} arquivo(s) encontrado(s) em {input_dir}\n")
    all_chunks: list[dict] = []

    for file_path in track(files, description="Processando arquivos…"):
        file_chunks = _process_single_file(
            file_path, chunk_size, chunk_overlap, min_chunk_length
        )
        if file_chunks is None:
            continue
        _write_jsonl(file_chunks, processed_dir / f"{file_path.stem}.jsonl")
        all_chunks.extend(file_chunks)
        console.print(
            f"  [green]✓[/green] {file_path.name:40s}  "
            f"[dim]{len(file_chunks):4d} chunks[/dim]"
        )

    _write_jsonl(all_chunks, output_path)
    console.print(
        f"\n[bold green]✓ corpus.jsonl gravado:[/bold green] "
        f"{len(all_chunks)} chunks em {output_path}"
    )
    return len(all_chunks)


def _process_single_file(
    file_path: Path,
    chunk_size: int,
    chunk_overlap: int,
    min_chunk_length: int,
) -> list[dict] | None:
    """
    Lê e chunka um único arquivo.
    Retorna lista de dicts ou None em caso de erro de leitura.
    """
    ext    = file_path.suffix.lower()
    reader = READERS.get(ext)
    if reader is None:
        return None

    file_type = _get_file_type(file_path)
    stem      = file_path.stem

    try:
        raw_blocks = reader(file_path)
    except Exception as exc:
        console.print(f"[red]  ✗ Erro ao ler {file_path.name}: {exc}[/red]")
        return None

    file_chunks: list[dict] = []
    for block in raw_blocks:
        page = block.get("page")
        for chunk_idx, chunk_text in enumerate(
            sliding_window(block["text"], chunk_size, chunk_overlap, min_chunk_length)
        ):
            file_chunks.append({
                "id":   _make_id(stem, page, chunk_idx),
                "text": chunk_text,
                "metadata": {
                    "source":    file_path.name,
                    "page":      page,
                    "chunk_idx": chunk_idx,
                    "type":      file_type,
                },
            })
    return file_chunks


def _write_jsonl(entries: list[dict], path: Path) -> None:
    """Escreve lista de dicts em formato JSONL."""
    with path.open("w", encoding="utf-8") as fh:
        for entry in entries:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")


# ── Carregadores utilitários ───────────────────────────────────────────────────

def load_corpus(corpus_path: str | Path = "data/corpus.jsonl") -> list[dict]:
    """Carrega corpus.jsonl e retorna lista de dicts."""
    corpus_path = Path(corpus_path)
    if not corpus_path.exists():
        raise FileNotFoundError(
            f"corpus.jsonl não encontrado em {corpus_path}. "
            "Execute: make ingest"
        )
    with corpus_path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


# ── Geração de queries ─────────────────────────────────────────────────────────

def queries_first_sentence(corpus: list[dict], max_queries: int) -> list[dict]:
    """
    Para cada chunk, extrai a primeira frase como query.
    Filtra queries duplicadas ou muito curtas.
    """
    seen: set[str] = set()
    pairs: list[dict] = []

    for doc in corpus:
        first = _extract_first_sentence(doc["text"])
        if len(first.split()) < 5:
            first = " ".join(doc["text"].split()[:15])
            if len(first.split()) < 5:
                continue
        query = first[:200]
        if query.lower() in seen:
            continue
        seen.add(query.lower())
        pairs.append({"query": query, "relevant_ids": [doc["id"]]})
        if len(pairs) >= max_queries:
            break

    return pairs


def _extract_first_sentence(text: str) -> str:
    """Extrai e limpa a primeira frase de um texto."""
    sentences = re.split(r"(?<=[.?!])\s+", text.strip())
    first = sentences[0].strip() if sentences else ""
    first = re.sub(r"[|`#*─┼┤├]", " ", first)
    return re.sub(r"\s+", " ", first).strip()


def queries_pseudo(
    corpus: list[dict],
    topk: int,
    max_queries: int,
    console_obj,
    seed: int = 42,
) -> list[dict]:
    """
    Pseudo ground truth: usa embedding f32 + FAISS top-k para determinar relevantes.
    Requer Fase 2 (embeddings gerados). Faz fallback para first_sentence se necessário.
    """
    import numpy as np

    emb_path = Path("embeddings/baseline_f32.npy")
    if not emb_path.exists():
        console_obj.print(
            "[yellow]⚠ embeddings/baseline_f32.npy não encontrado.[/yellow]\n"
            "  Execute [bold]make embed[/bold] antes de usar --strategy pseudo.\n"
            "  Usando 'first_sentence' como fallback."
        )
        return queries_first_sentence(corpus, max_queries)

    try:
        import faiss
    except ImportError:
        console_obj.print("[yellow]⚠ faiss-cpu não instalado. Usando 'first_sentence'.[/yellow]")
        return queries_first_sentence(corpus, max_queries)

    embeddings = np.load(str(emb_path)).astype("float32")
    n, dim = embeddings.shape
    console_obj.print(f"[cyan]Embeddings carregados:[/cyan] shape={embeddings.shape}")

    index = faiss.IndexFlatIP(dim)
    index.add(embeddings)
    rng = np.random.default_rng(seed)
    query_indices = rng.choice(n, size=min(max_queries, n), replace=False)

    pairs: list[dict] = []
    for qi in query_indices:
        _, results = index.search(embeddings[qi : qi + 1], topk + 1)
        relevant = [corpus[j]["id"] for j in results[0] if j != qi and 0 <= j < len(corpus)][:topk]
        if not relevant:
            relevant = [corpus[qi]["id"]]
        pairs.append({"query": corpus[qi]["text"][:200], "relevant_ids": relevant})

    return pairs
