"""
src/rag/prompting.py
----------------------
Template de prompt e chamada ao LLM.

Backends suportados (em ordem de preferência):
  1. Mock   — resposta extrativa do top-1 chunk (sem dependência externa)
  2. Ollama — URL configurável via OLLAMA_BASE_URL (padrão: http://localhost:11434)
  3. OpenAI-compatible — qualquer base_url + api_key nas variáveis de ambiente

Variáveis de ambiente relevantes:
  LLM_BACKEND     = "mock" | "ollama" | "openai"   (padrão: auto-detect)
  LLM_MODEL       = nome do modelo (ex: "llama3.2", "gpt-4o-mini")
  OLLAMA_BASE_URL = URL base do Ollama (padrão: http://localhost:11434)
  OPENAI_BASE_URL = URL base da API compatível com OpenAI
  OPENAI_API_KEY  = chave de API
"""

from __future__ import annotations

import os
import textwrap
from typing import Optional

PROMPT_TEMPLATE = """\
Você é um assistente preciso. Use APENAS as informações do contexto abaixo para responder.
Se o contexto não contiver a resposta, diga "Não encontrei essa informação no contexto."

Contexto:
{context}

Pergunta: {query}

Resposta:"""


def format_prompt(query: str, context: str) -> str:
    return PROMPT_TEMPLATE.format(query=query.strip(), context=context.strip())


# ── Auto-detect backend ────────────────────────────────────────────────────────

def _ollama_url() -> str:
    """Retorna a URL base do Ollama, configurável via OLLAMA_BASE_URL."""
    return os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")


def _detect_backend() -> str:
    """Retorna o backend disponível: 'mock', 'ollama' ou 'openai'."""
    override = os.getenv("LLM_BACKEND", "").lower()
    if override in ("mock", "ollama", "openai"):
        return override

    # Tenta Ollama (usa URL configurada)
    try:
        import urllib.request
        urllib.request.urlopen(f"{_ollama_url()}/api/tags", timeout=1)
        return "ollama"
    except Exception:
        pass

    # Tenta OpenAI-compatible
    if os.getenv("OPENAI_API_KEY"):
        return "openai"

    return "mock"


# ── Backends ───────────────────────────────────────────────────────────────────

def _call_mock(prompt: str, context_chunks: list[str]) -> str:
    """
    Resposta extrativa: retorna as primeiras 3 frases do chunk mais relevante.
    Não requer nenhuma dependência externa.
    """
    if not context_chunks:
        return "Não encontrei informações relevantes no corpus."

    top = context_chunks[0]
    # Extrai as primeiras ~200 palavras como resposta
    words = top.split()
    snippet = " ".join(words[:60])
    if len(words) > 60:
        snippet += "…"
    return f"[Mock — baseado no contexto recuperado]\n\n{snippet}"


def _call_ollama(prompt: str, model: Optional[str] = None) -> str:
    """Envia prompt ao Ollama. URL configurável via OLLAMA_BASE_URL."""
    import json
    import urllib.request

    model   = model or os.getenv("LLM_MODEL", "llama3.2")
    url     = f"{_ollama_url()}/api/generate"
    payload = json.dumps({
        "model":  model,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.1, "num_predict": 512},
    }).encode()

    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        data = json.loads(r.read())

    response = data.get("response", "").strip()
    if not response:
        raise ValueError(f"Ollama retornou resposta vazia. Modelo: {model}. URL: {url}")
    return response


def _call_openai(prompt: str, model: Optional[str] = None) -> str:
    """Envia prompt a qualquer API compatível com OpenAI (inclui OpenRouter)."""
    try:
        from openai import OpenAI
    except ImportError:
        raise RuntimeError("openai não instalado — execute: uv add openai")

    api_key  = os.getenv("OPENAI_API_KEY", "")
    base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    model    = model or os.getenv("LLM_MODEL", "gpt-4o-mini")

    if not api_key or api_key.startswith("sk-or-v1-troque"):
        raise ValueError(
            "OPENAI_API_KEY não configurada.\n"
            "Edite o .env e coloque sua chave real do OpenRouter."
        )

    # OpenRouter recomenda enviar estes headers opcionais
    extra_headers = {}
    if "openrouter" in base_url:
        extra_headers = {
            "HTTP-Referer": "https://github.com/rag-embedding-compression-lab",
            "X-Title": "RAG Embedding Compression Lab",
        }

    client = OpenAI(base_url=base_url, api_key=api_key)
    resp = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1,
        max_tokens=512,
        extra_headers=extra_headers,
    )

    # content pode ser None em respostas de erro ou content-filter
    content = resp.choices[0].message.content if resp.choices else None
    if not content:
        # Tenta extrair mensagem de erro do campo nativo do OpenRouter
        err = getattr(resp, "error", None)
        detail = str(err) if err else f"choices={resp.choices}"
        raise ValueError(f"OpenRouter retornou resposta vazia. Detalhe: {detail}")

    return content.strip()


# ── Entry point ────────────────────────────────────────────────────────────────

def call_llm(
    query: str,
    context: str,
    context_chunks: list[str],
    backend: Optional[str] = None,
    model: Optional[str] = None,
) -> tuple[str, str]:
    """
    Chama o LLM e retorna (answer, backend_used).

    Parâmetros
    ----------
    query          : pergunta do usuário
    context        : string formatada com todos os chunks
    context_chunks : lista de textos dos chunks (para mock extrativo)
    backend        : forçar backend específico ou None para auto-detect
    model          : nome do modelo ou None para usar o default
    """
    b = backend or _detect_backend()
    prompt = format_prompt(query, context)

    if b == "ollama":
        try:
            answer = _call_ollama(prompt, model)
            return answer, "ollama"
        except Exception as e:
            answer = _call_mock(prompt, context_chunks)
            return answer + f"\n\n[⚠ Ollama falhou: {e} → usando mock]", "mock"

    if b == "openai":
        try:
            answer = _call_openai(prompt, model)
            return answer, "openai"
        except Exception as e:
            answer = _call_mock(prompt, context_chunks)
            return answer + f"\n\n[⚠ OpenAI falhou: {e} → usando mock]", "mock"

    answer = _call_mock(prompt, context_chunks)
    return answer, "mock"
