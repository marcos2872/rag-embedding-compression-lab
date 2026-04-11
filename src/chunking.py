"""
src/chunking.py
---------------
Estratégia: sliding window por palavras.

Por que por palavras e não tokens?
  - PDF extraído via fitz tem espaçamento irregular.
  - Tokenizar com transformers é mais lento e não muda o resultado prático
    para chunk_size nessa faixa (256 palavras ≈ 340 tokens).
"""

from __future__ import annotations

import re
from typing import Optional


def _clean_text(text: str) -> str:
    """Remove espaços em branco excessivos e quebras de linha múltiplas."""
    # normaliza quebras de linha
    text = re.sub(r"\r\n", "\n", text)
    # múltiplas linhas em branco → apenas uma
    text = re.sub(r"\n{3,}", "\n\n", text)
    # espaços e tabs consecutivos → espaço único (preserva quebras de linha)
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


def sliding_window(
    text: str,
    chunk_size: int = 256,
    overlap: int = 32,
    min_chunk_length: int = 50,
) -> list[str]:
    """
    Divide `text` em chunks sobrepostos por palavras.

    Parâmetros
    ----------
    text : str
        Texto de entrada (pode conter quebras de linha).
    chunk_size : int
        Número de palavras por chunk (padrão 256).
    overlap : int
        Palavras de sobreposição entre chunks consecutivos (padrão 32).
    min_chunk_length : int
        Chunks com menos palavras que isso são descartados (padrão 50).

    Retorna
    -------
    list[str]
        Lista de strings — os chunks.
    """
    text = _clean_text(text)
    if not text:
        return []

    words = text.split()
    if len(words) < min_chunk_length:
        return []

    step = max(1, chunk_size - overlap)
    chunks: list[str] = []

    for start in range(0, len(words), step):
        window = words[start : start + chunk_size]
        if len(window) < min_chunk_length:
            # último fragmento muito pequeno — absorve no anterior se possível
            if chunks:
                # nada a fazer; descarta fragmento minúsculo
                pass
            break
        chunks.append(" ".join(window))

    return chunks
