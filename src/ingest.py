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
import sys
from pathlib import Path
from typing import Optional

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

def _make_id(stem: str, page: Optional[int], chunk_idx: int) -> str:
    """Gera id no formato <stem>-p<page>-c<chunk_idx>."""
    stem_clean = re.sub(r"[^a-zA-Z0-9_-]", "-", stem)
    page_str = f"p{page:02d}" if page is not None else "p00"
    return f"{stem_clean}-{page_str}-c{chunk_idx:02d}"


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
    input_dir = Path(input_dir)
    output_path = Path(output_path)
    processed_dir = output_path.parent / "processed"
    processed_dir.mkdir(parents=True, exist_ok=True)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Coleta arquivos suportados
    files: list[Path] = []
    for ext in READERS:
        files.extend(sorted(input_dir.rglob(f"*{ext}")))

    if not files:
        console.print(
            f"[yellow]⚠ Nenhum arquivo .pdf/.txt/.md encontrado em {input_dir}[/yellow]"
        )
        return 0

    console.print(f"\n[bold cyan]Ingestão:[/bold cyan] {len(files)} arquivo(s) encontrado(s) em {input_dir}\n")

    all_chunks: list[dict] = []

    for file_path in track(files, description="Processando arquivos…"):
        ext = file_path.suffix.lower()
        reader = READERS.get(ext)
        if reader is None:
            continue

        file_type = _get_file_type(file_path)
        stem = file_path.stem

        try:
            raw_blocks = reader(file_path)
        except Exception as exc:
            console.print(f"[red]  ✗ Erro ao ler {file_path.name}: {exc}[/red]")
            continue

        file_chunks: list[dict] = []
        for block in raw_blocks:
            page = block.get("page")
            chunks = sliding_window(
                block["text"],
                chunk_size=chunk_size,
                overlap=chunk_overlap,
                min_chunk_length=min_chunk_length,
            )
            for chunk_idx, chunk_text in enumerate(chunks):
                doc_id = _make_id(stem, page, chunk_idx)
                entry = {
                    "id": doc_id,
                    "text": chunk_text,
                    "metadata": {
                        "source": file_path.name,
                        "page": page,
                        "chunk_idx": chunk_idx,
                        "type": file_type,
                    },
                }
                file_chunks.append(entry)

        # Salva arquivo processed intermediário
        proc_path = processed_dir / f"{stem}.jsonl"
        with proc_path.open("w", encoding="utf-8") as f:
            for entry in file_chunks:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")

        all_chunks.extend(file_chunks)
        console.print(
            f"  [green]✓[/green] {file_path.name:40s}  "
            f"[dim]{len(file_chunks):4d} chunks[/dim]"
        )

    # Grava corpus.jsonl unificado
    with output_path.open("w", encoding="utf-8") as f:
        for entry in all_chunks:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    console.print(
        f"\n[bold green]✓ corpus.jsonl gravado:[/bold green] "
        f"{len(all_chunks)} chunks em {output_path}"
    )
    return len(all_chunks)


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
