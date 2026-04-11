# AGENTS.md

> Arquivo gerado por `/init` com análise automática. Edite manualmente para ajustar convenções.

## Projeto

- **Nome:** rag-embedding-compression-lab
- **Descrição:** Lab de pesquisa que implementa e compara quatro métodos de compressão/quantização de embeddings para sistemas RAG (uniform, lloyd_max, turbo_mse, turbo_prod), medindo o trade-off entre taxa de compressão de memória e qualidade de retrieval.

## Stack

- **Linguagem(s):** Python ≥ 3.10
- **Frameworks:** sentence-transformers (embeddings), FAISS (busca vetorial), Typer (CLI), Plotly + Matplotlib (visualizações), scikit-learn, SciPy, OpenAI (LLM demo), PyMuPDF (ingestão de PDF)

## Gerenciamento de Dependências

- **Instalar tudo:** `uv sync`
- **Adicionar pacote:** `uv add <pacote>`
- **Remover pacote:** `uv remove <pacote>`

## Comandos Essenciais

- **Setup completo (instalar + .env + pastas):** `make setup`
- **Apenas instalar deps:** `make env`
- **Pipeline completo (fases 1–6):** `make all`
- **Fase 1 — Ingestão de corpus:** `make ingest`
- **Fase 1 — Geração de queries:** `make queries`
- **Fase 1 — Geração de queries com pseudo ground truth:** `make queries-pseudo`
- **Fase 1 — Verificar chunks gerados:** `make ingest-check`
- **Fase 2 — Embeddings float32/float16:** `make embed`
- **Fase 2 — Info do device/modelo:** `make embed-info`
- **Fase 3 — Quantizar uniform:** `make quantize-uniform`
- **Fase 3 — Quantizar lloyd_max:** `make quantize-lloyd`
- **Fase 3 — Quantizar turbo_mse:** `make quantize-mse`
- **Fase 3 — Quantizar turbo_prod:** `make quantize-prod`
- **Fase 3 — Quantizar todas as variantes:** `make quantize-all`
- **Fase 4 — Benchmark de distorção:** `make distortion-bench`
- **Fase 5 — Construir índices FAISS:** `make build-indexes`
- **Fase 5 — Benchmark de retrieval:** `make retrieval-bench`
- **Fases 4+5 — Benchmarks completos:** `make all-bench`
- **Fase 6 — Gráficos e dashboard:** `make visualize`
- **Fase 6 — Relatório Markdown:** `make report`
- **Fase 7 — Demo RAG:** `make rag-demo QUERY="sua pergunta"`
- **Limpar artefatos gerados:** `make clean`
- **Listar todos os targets:** `make help`

## Estrutura de Diretórios

- **Código principal:** `src/`
- **Testes:** `tests/` ⚠️ não encontrado
- **Dados brutos:** `data/raw/`
- **Corpus / queries gerados:** `data/`
- **Embeddings gerados:** `embeddings/`
- **Índices FAISS:** `indexes/`
- **Relatórios CSV/MD:** `reports/`
- **Gráficos e dashboard:** `charts/`
- **Configurações YAML:** `configs/`
- **Notebooks Jupyter:** `notebooks/`

## Módulos

- **`src/main.py`** — CLI principal (Typer): expõe todos os comandos das 7 fases via `lab <comando>`
- **`src/ingest.py`** — Fase 1: lê PDFs/TXT/MD de `data/raw/`, faz chunking e gera `corpus.jsonl`
- **`src/chunking.py`** — Lógica de chunking de documentos com tamanho e sobreposição configuráveis
- **`src/embed.py`** — Fase 2: gera embeddings float32/float16 com BAAI/bge-small-en-v1.5 (local, sem API)
- **`src/quantization/`** — Fase 3: orquestra as quatro variantes de quantização; entry point `quantize_pipeline(variant, bits)`
- **`src/quantization/scalar_uniform.py`** — Variante A: quantização uniforme com bins min/max global e bit-packing via `numpy.packbits`
- **`src/quantization/lloyd_max.py`** — Variante B: codebook Lloyd-Max (distribuição esférica) sem rotação
- **`src/quantization/turboquant_mse.py`** — Variante C: TurboQuant com rotação ortogonal + Lloyd-Max (minimiza MSE)
- **`src/quantization/turboquant_prod.py`** — Variante D: TurboQuant com rotação + Lloyd-Max + QJL no resíduo (minimiza erro de produto interno)
- **`src/quantization/rotation.py`** — Rotação ortogonal aleatória (QR de Haar) compartilhada pelas variantes turbo
- **`src/quantization/storage.py`** — Serialização/deserialização dos embeddings quantizados em `.npz`
- **`src/benchmark/distortion.py`** — Fase 4: calcula MSE, cosine error e IP error por variante → `reports/distortion_results.csv`
- **`src/benchmark/retrieval_bench.py`** — Fase 5: calcula Recall@k, MRR, latência e uso de memória → `reports/benchmark_results.csv`
- **`src/benchmark/reports.py`** — Fase 6: gera relatório Markdown com análise por query
- **`src/retrieval/faiss_store.py`** — Fase 5: constrói e consulta índices FAISS (IndexFlatIP) para cada variante
- **`src/retrieval/metrics.py`** — Calcula métricas de retrieval (Recall@k, MRR, rank por query)
- **`src/visualization/plots.py`** — Fase 6: gera gráficos estáticos em `charts/`
- **`src/visualization/dashboard.py`** — Fase 6: gera `charts/dashboard.html` interativo (Plotly)
- **`src/rag/pipeline.py`** — Fase 7: pipeline RAG end-to-end comparando variantes lado a lado
- **`src/rag/prompting.py`** — Fase 7: templates de prompt e integração com Ollama/OpenAI

## Arquitetura

- **Estilo:** Pipeline modular de 7 fases
- **Descrição:** Cada fase é independente e produz artefatos em disco (`.jsonl`, `.npy`, `.npz`, `.index`, `.csv`, `.png`, `.html`) consumidos pela fase seguinte. `src/main.py` orquestra todas as fases via CLI Typer; o Makefile encadeia os comandos para pipelines completos.

```
data/raw/  →[ingest]→  corpus.jsonl  →[embed]→  baseline_f32.npy
  →[quantize]→  <variant>_<bits>bit.npz  →[distortion-bench + retrieval-bench]→  reports/
  →[visualize]→  charts/  →[rag-demo]→  resposta comparativa
```

## Variáveis de Ambiente

> Copie `.env.example` para `.env` e ajuste os valores.

- **Embedding:** `EMBEDDING_MODEL`, `EMBEDDING_BATCH_SIZE`, `EMBEDDING_DEVICE`, `RANDOM_SEED`, `QJL_SEED`, `CORPUS_PATH`, `QUERIES_PATH`
- **LLM (RAG demo):** `LLM_BACKEND`, `LLM_MODEL`, `OLLAMA_BASE_URL` *(opcional)*, `OPENAI_BASE_URL` *(opcional)*, `OPENAI_API_KEY` *(opcional)*

## Testes

- **Framework:** pytest *(não configurado — adicionar como dev dependency: `uv add --dev pytest pytest-cov`)*
- **Diretório:** `tests/` ⚠️ não encontrado
- **Executar todos:** `uv run pytest tests/`
- **Com cobertura:** `uv run pytest tests/ --cov=src --cov-report=term-missing`

## Convenções de Código

- **Tamanho máximo de função:** 40 linhas
- **Tamanho máximo de arquivo:** 300 linhas
- **Aninhamento máximo:** 3 níveis
- **Docstrings / comentários:** Português brasileiro
- **Identificadores (variáveis, funções, classes):** Inglês
- Python: `X | None`, `list[str]` — nunca `Optional`/`Union` de `typing`
- Prefira `np.random.default_rng(seed)` em vez de `np.random.seed()` (API moderna do NumPy)
- Variantes de quantização seguem o padrão: `fit_<variant>`, `quantize_<variant>`, `dequantize_<variant>`
- Artefatos em disco sempre nomeados como `<variant>_<bits>bit.npz`
- Configurações carregadas via `configs/*.yaml` + variáveis de ambiente (`.env`); nunca hardcode de caminhos

## Commits

Este projeto segue o padrão **Conventional Commits**.
Antes de commitar, carregue a skill de commit:

```
/skill:git-commit-push
```

Ou siga diretamente as regras em `.agents/skills/git-commit-push/SKILL.md`.

## Agentes e Skills

| Agente    | Função                                         | Modo                   |
|-----------|------------------------------------------------|------------------------|
| `build`   | Implementa funcionalidades e corrige bugs      | escrita completa       |
| `ask`     | Responde perguntas somente-leitura             | somente-leitura        |
| `plan`    | Cria planos detalhados em `.pi/plans/`         | escrita em .pi/plans/  |
| `quality` | Auditoria de qualidade de código               | bash + leitura         |
| `qa`      | Análise de bugs e edge cases                   | bash + leitura         |
| `test`    | Cria e mantém testes automatizados             | escrita em tests/      |
| `doc`     | Cria documentação técnica em `docs/`           | escrita em docs/       |
