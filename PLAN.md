# Plano de Execução — RAG Embedding Compression Lab

> Baseado no paper **TurboQuant** e no roadmap do `perplexity.md`.  
> Objetivo central: **quanto de memória dá para economizar nos embeddings sem estragar o retrieval?**

---

## Visão Geral das Fases

```
FASE 0 → Scaffold do projeto (estrutura, deps, configs)
FASE 1 → Corpus & Queries (dados + ground truth)
FASE 2 → Embeddings baseline (float32 / float16)
FASE 3 → Quantização (Uniforme → Lloyd-Max → QJL)
FASE 4 → Benchmark de distorção (MSE, cosine error, IP error)
FASE 5 → Benchmark de retrieval (Recall@k, MRR, latência, memória)
FASE 6 → Relatórios & Visualizações (tabelas + gráficos)
FASE 7 → Mini pipeline RAG (busca → contexto → resposta)
```

Cada fase tem **entradas**, **saídas** e **critério de conclusão** claros.

---

## FASE 0 — Scaffold do Projeto

### Estrutura de diretórios

```
rag-embedding-compression-lab/
├── PLAN.md                        ← este arquivo
├── README.md
├── pyproject.toml
├── .env.example
├── configs/
│   ├── dataset.yaml               ← parâmetros do corpus
│   ├── embedding.yaml             ← modelo e batch size
│   └── benchmark.yaml             ← topk, bits, seeds
├── data/
│   ├── raw/                       ← documentos originais (txt, md, pdf)
│   ├── processed/                 ← chunks já limpos
│   ├── corpus.jsonl               ← {id, text, metadata}
│   └── queries.jsonl              ← {query, relevant_ids}
├── embeddings/
│   ├── baseline_f32.npy           ← float32 [N, D]
│   ├── baseline_f16.npy           ← float16 [N, D]
│   ├── quantized_2bit.npz         ← {idx, norms, state_meta}
│   ├── quantized_4bit.npz
│   └── quantized_8bit.npz
├── indexes/
│   ├── faiss_f32.index
│   ├── faiss_f16.index
│   ├── faiss_2bit.index           ← vetores dequantizados como f32
│   ├── faiss_4bit.index
│   └── faiss_8bit.index
├── src/
│   ├── main.py                    ← CLI principal (typer)
│   ├── ingest.py                  ← carrega raw → corpus.jsonl
│   ├── chunking.py                ← split de texto em chunks
│   ├── embed.py                   ← gera embeddings via sentence-transformers
│   ├── quantization/
│   │   ├── __init__.py
│   │   ├── rotation.py            ← fit_rotation (QR ortogonal)
│   │   ├── scalar_uniform.py      ← Versão A: uniforme com min/max
│   │   ├── lloyd_max.py           ← Versão B: codebook Lloyd-Max + Beta dist
│   │   ├── turboquant_mse.py      ← Versão C: TurboQuantMSE completo
│   │   ├── turboquant_prod.py     ← Versão D: TurboQuantProd (MSE + QJL)
│   │   └── storage.py             ← serialização/desserialização .npz
│   ├── retrieval/
│   │   ├── faiss_store.py         ← build_index, save, load
│   │   ├── search.py              ← top_k_search(query_vec, k)
│   │   └── metrics.py             ← recall_at_k, mrr, latency
│   ├── benchmark/
│   │   ├── distortion.py          ← mse, cosine_error, ip_error
│   │   ├── retrieval_bench.py     ← roda todos os índices e coleta métricas
│   │   ├── memory.py              ← tamanho dos arquivos e arrays em RAM
│   │   └── reports.py             ← gera CSV + Markdown
│   ├── visualization/
│   │   ├── plots.py               ← todas as funções de gráfico
│   │   └── dashboard.py           ← gera HTML estático com todos os gráficos
│   └── rag/
│       ├── pipeline.py            ← busca + montagem de contexto
│       └── prompting.py           ← template de prompt + chamada LLM/mock
├── reports/
│   ├── benchmark_results.csv      ← linha por (variante, bits, métrica, valor)
│   ├── distortion_results.csv
│   ├── retrieval_examples.md      ← queries que quebraram vs que mantiveram
│   └── notes.md
├── charts/                        ← PNGs e HTMLs gerados automaticamente
│   ├── recall_vs_bits.png
│   ├── mse_vs_bits.png
│   ├── memory_vs_bits.png
│   ├── latency_vs_bits.png
│   ├── tradeoff_recall_memory.png
│   ├── ip_error_heatmap.png
│   └── dashboard.html
└── notebooks/
    └── exploration.ipynb          ← experimentos livres
```

### Arquivo `pyproject.toml`

```toml
[project]
name = "rag-embedding-compression-lab"
version = "0.1.0"
requires-python = ">=3.10"

dependencies = [
  "numpy>=1.26",
  "pandas>=2.0",
  "scipy>=1.11",           # Lloyd-Max precisa de Beta distribution
  "faiss-cpu>=1.7",
  "sentence-transformers>=2.7",
  "scikit-learn>=1.4",
  "typer[all]>=0.12",
  "rich>=13",
  "pyyaml>=6",
  "matplotlib>=3.8",
  "seaborn>=0.13",
  "plotly>=5.20",          # gráficos interativos HTML
  "kaleido>=0.2",          # export PNG do plotly
  "tqdm>=4.66",
  "python-dotenv>=1.0",
  "pymupdf>=1.24",          # extração de texto de PDF (fitz)
]

[project.scripts]
lab = "src.main:app"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.uv]
dev-dependencies = [
  "ipykernel>=6",
  "jupyter>=1",
]
```

### Makefile

```makefile
# ── variáveis ──────────────────────────────────────────────────────────
PYTHON   := uv run python
RUN      := uv run
SRC      := src.main

.PHONY: setup env ingest queries ingest-check embed embed-info \
        quantize-all quantize-uniform quantize-lloyd quantize-mse quantize-prod \
        distortion-bench build-indexes retrieval-bench \
        visualize report rag-demo \
        all-bench clean help

## ── setup ──────────────────────────────────────────────────────────────
setup:          ## Instala dependências com uv e copia .env
	uv sync
	@[ -f .env ] || cp .env.example .env && echo "✓ .env criado"
	@mkdir -p data/raw data/processed embeddings indexes reports charts

env:            ## Só instala dependências (sem criar .env)
	uv sync

## ── fase 1: dados ──────────────────────────────────────────────────────
ingest:         ## Processa data/raw/ → corpus.jsonl (pdf + txt + md)
	$(PYTHON) -m $(SRC) ingest --input data/raw/

queries:        ## Gera queries.jsonl com pseudo ground truth (top-1 f32)
	$(PYTHON) -m $(SRC) queries --strategy pseudo --topk 1

ingest-check:   ## Mostra quantos chunks foram gerados por arquivo
	@$(PYTHON) -c "
import json, collections
from pathlib import Path
lines = Path('data/corpus.jsonl').read_text().splitlines()
chunks = [json.loads(l) for l in lines]
counts = collections.Counter(c['metadata']['source'] for c in chunks)
for src, n in sorted(counts.items()): print(f'  {n:4d} chunks  {src}')
print(f'  ────────────────')
print(f'  {len(chunks):4d} total')
"

## ── fase 2: embeddings ─────────────────────────────────────────────────
embed:          ## Gera baseline_f32.npy e baseline_f16.npy (aceita DEVICE=cpu|cuda|mps)
	$(PYTHON) -m $(SRC) embed $(if $(DEVICE),--device $(DEVICE),)

embed-info:     ## Mostra device disponível e modelo configurado
	@$(PYTHON) -c "
import torch, os
from dotenv import load_dotenv
load_dotenv()
model = os.getenv('EMBEDDING_MODEL', 'BAAI/bge-small-en-v1.5')
cuda = torch.cuda.is_available()
mps  = hasattr(torch.backends, 'mps') and torch.backends.mps.is_available()
device = 'cuda' if cuda else ('mps' if mps else 'cpu')
print(f'  Modelo : {model}')
print(f'  Device : {device}')
print(f'  CUDA   : {cuda}')
print(f'  MPS    : {mps}')
"

## ── fase 3: quantização ────────────────────────────────────────────────
quantize-uniform: ## Quantização uniforme em 2, 4 e 8 bits
	$(PYTHON) -m $(SRC) quantize --variant uniform --bits 8
	$(PYTHON) -m $(SRC) quantize --variant uniform --bits 4
	$(PYTHON) -m $(SRC) quantize --variant uniform --bits 2

quantize-lloyd:   ## Codebook Lloyd-Max em 2, 4 e 8 bits
	$(PYTHON) -m $(SRC) quantize --variant lloyd_max --bits 8
	$(PYTHON) -m $(SRC) quantize --variant lloyd_max --bits 4
	$(PYTHON) -m $(SRC) quantize --variant lloyd_max --bits 2

quantize-mse:     ## TurboQuantMSE em 2, 4 e 8 bits
	$(PYTHON) -m $(SRC) quantize --variant turbo_mse --bits 8
	$(PYTHON) -m $(SRC) quantize --variant turbo_mse --bits 4
	$(PYTHON) -m $(SRC) quantize --variant turbo_mse --bits 2

quantize-prod:    ## TurboQuantProd em 2, 4 e 8 bits
	$(PYTHON) -m $(SRC) quantize --variant turbo_prod --bits 8
	$(PYTHON) -m $(SRC) quantize --variant turbo_prod --bits 4
	$(PYTHON) -m $(SRC) quantize --variant turbo_prod --bits 2

quantize-all: quantize-uniform quantize-lloyd quantize-mse quantize-prod
	@echo "✓ Todas as variantes quantizadas"

## ── fase 4: distorção ──────────────────────────────────────────────────
distortion-bench: ## MSE, cosine error e IP error por variante
	$(PYTHON) -m $(SRC) distortion-bench

## ── fase 5: retrieval ──────────────────────────────────────────────────
build-indexes:  ## Constrói índices FAISS para todas as variantes
	$(PYTHON) -m $(SRC) build-indexes

retrieval-bench: ## Recall@k, MRR, latência e memória por variante
	$(PYTHON) -m $(SRC) retrieval-bench --topk 10

## ── fase 6: visualizações ──────────────────────────────────────────────
visualize:      ## Gera todos os 9 gráficos em charts/
	$(PYTHON) -m $(SRC) visualize

report:         ## Gera relatório Markdown com exemplos de queries
	$(PYTHON) -m $(SRC) report

## ── fase 7: rag demo ───────────────────────────────────────────────────
rag-demo:       ## Demo interativo RAG (QUERY obrigatória)
	@test -n "$(QUERY)" || (echo "Uso: make rag-demo QUERY='sua pergunta'" && exit 1)
	$(PYTHON) -m $(SRC) rag-demo --query "$(QUERY)" --variants f32,turbo_mse_4bit,uniform_2bit

## ── pipelines completos ────────────────────────────────────────────────
all-bench: distortion-bench build-indexes retrieval-bench
	@echo "✓ Benchmarks completos → reports/"

all: ingest queries embed quantize-all all-bench visualize report
	@echo "✓ Pipeline completo finalizado"

## ── utilidades ─────────────────────────────────────────────────────────
clean:          ## Remove artefatos gerados (mantém data/raw)
	rm -rf embeddings/*.npy embeddings/*.npz
	rm -rf indexes/*.index
	rm -rf reports/*.csv reports/*.md
	rm -rf charts/*.png charts/*.html

help:           ## Lista todos os targets disponíveis
	@grep -E '^[a-zA-Z_-]+:.*##' $(MAKEFILE_LIST) \
	  | awk 'BEGIN {FS = ":.*##"}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'
```

### Arquivo `.env.example`

```env
EMBEDDING_MODEL=BAAI/bge-small-en-v1.5
EMBEDDING_BATCH_SIZE=64
EMBEDDING_DEVICE=cpu          # cpu | cuda | mps
RANDOM_SEED=42
QJL_SEED=123
CORPUS_PATH=data/corpus.jsonl
QUERIES_PATH=data/queries.jsonl
```

### Arquivos de configuração `configs/`

**`configs/dataset.yaml`**
```yaml
corpus_path: data/corpus.jsonl
queries_path: data/queries.jsonl
chunk_size: 256          # tokens
chunk_overlap: 32
min_chunk_length: 50     # descartar chunks muito curtos
```

**`configs/embedding.yaml`**
```yaml
model: BAAI/bge-small-en-v1.5    # dim=384  ← baixado do HuggingFace Hub na 1ª execução
# alternativas:
#   BAAI/bge-base-en-v1.5          dim=768   (~430 MB)
#   BAAI/bge-small-en-v1.5         dim=384   (~130 MB)  ← recomendado para CPU
#   nomic-ai/nomic-embed-text-v1   dim=768   (~550 MB)
batch_size: 64
normalize: true                   # normalizar para esfera unitária
device: cpu                       # cpu | cuda | mps (Apple Silicon)
cache_dir: null                   # null = usar ~/.cache/huggingface/hub
```

**`configs/benchmark.yaml`**
```yaml
bits_list: [2, 4, 8]
top_k_list: [1, 5, 10]
random_seed: 42
qjl_seed: 123
num_queries: 100                  # queries a usar no benchmark
variants:
  - name: baseline_f32
    type: float32
  - name: baseline_f16
    type: float16
  - name: uniform_2bit
    type: uniform
    bits: 2
  - name: uniform_4bit
    type: uniform
    bits: 4
  - name: uniform_8bit
    type: uniform
    bits: 8
  - name: lloydmax_2bit
    type: lloyd_max
    bits: 2
  - name: lloydmax_4bit
    type: lloyd_max
    bits: 4
  - name: lloydmax_8bit
    type: lloyd_max
    bits: 8
  - name: turbomse_2bit
    type: turbo_mse
    bits: 2
  - name: turbomse_4bit
    type: turbo_mse
    bits: 4
  - name: turbomse_8bit
    type: turbo_mse
    bits: 8
  - name: turboprod_2bit
    type: turbo_prod
    bits: 2
  - name: turboprod_4bit
    type: turbo_prod
    bits: 4
  - name: turboprod_8bit
    type: turbo_prod
    bits: 8
```

**Critério de conclusão da Fase 0:**  
`make setup` termina sem erros. `uv sync` instalou todas as dependências. Estrutura de diretórios criada.

---

## FASE 1 — Corpus & Queries

### Objetivo
Criar `corpus.jsonl` com documentos e `queries.jsonl` com pares query → documentos relevantes.

### Tipos de arquivo suportados em `data/raw/`

| Extensão | Leitor | Observação |
|----------|--------|------------|
| `.pdf` | `pymupdf` (fitz) | Extrai texto por página, preserva número de página nos metadados |
| `.txt` | built-in `open()` | Leitura direta |
| `.md` | built-in `open()` | Remove marcação opcional, leitura direta |

Coloque os arquivos em `data/raw/` e rode `make ingest`. O pipeline detecta a extensão automaticamente.

```
data/raw/
├── artigo-turboquant.pdf       ← PDF com múltiplas páginas
├── docs-redis.md               ← Markdown
└── notas-nestjs.txt            ← Texto puro
```

### Pipeline de ingestão

```
data/raw/*.{pdf,txt,md}
        │
        ▼
  src/ingest.py
   ├── .pdf  →  read_pdf()     # pymupdf: texto por página
   ├── .txt  →  read_txt()     # open() direto
   └── .md   →  read_md()      # open() + strip markdown opcional
        │
        ▼
  src/chunking.py
   └── sliding_window(text, chunk_size=256, overlap=32)
        │
        ▼
  data/processed/<nome-do-arquivo>.jsonl   ← chunks intermediários
        │
        ▼
  data/corpus.jsonl   ← todos os chunks unificados
```

### `src/ingest.py`

```python
"""
Funções principais:

  read_pdf(path) → list[dict]
    Usa pymupdf (fitz) para extrair texto página a página.
    Retorna: [{"text": "...", "page": 1, "source": "arquivo.pdf"}, ...]

    Implementação:
      import fitz  # pymupdf
      doc = fitz.open(path)
      pages = []
      for i, page in enumerate(doc):
          text = page.get_text("text")       # texto puro da página
          if text.strip():                    # ignora páginas vazias/imagens
              pages.append({
                  "text": text,
                  "page": i + 1,
                  "source": Path(path).name,
              })
      return pages

  read_txt(path) → list[dict]
    Retorna: [{"text": conteúdo_inteiro, "page": None, "source": nome}]

  read_md(path) → list[dict]
    Igual ao txt; opcionalmente remove headers/links com re.sub

  ingest(input_dir, output_path, chunk_size, chunk_overlap):
    1. Varre input_dir recursivamente por .pdf, .txt, .md
    2. Chama o leitor correto por extensão
    3. Para cada página/bloco: aplica chunking
    4. Gera IDs no formato  <stem>-p<page>-c<chunk_idx>
       ex: "artigo-turboquant-p03-c01"
    5. Salva em corpus.jsonl
"""
```

### `src/chunking.py`

```python
"""
Estratégia: sliding window por palavras (mais simples e robusto que tokens
para textos extraídos de PDF, que às vezes têm quebras de linha irregulares).

função: sliding_window(text, chunk_size=256, overlap=32)
  → lista de strings (os chunks)

Detalhes:
  - Divide por palavras: words = text.split()
  - Janela deslizante: words[i : i+chunk_size]
  - Passo: chunk_size - overlap
  - Descarta chunks com menos de min_chunk_length palavras (configurável)
  - Reconecta palavras com " ".join(window)

Por que por palavras e não tokens?
  - PDF extraído via fitz tem espaçamento irregular
  - Tokenizar com transformers é mais lento e não muda o resultado prático
    para chunk_size nessa faixa (256 palavras ≈ 340 tokens)
"""
```

### Formato de saída do `corpus.jsonl`

Cada linha é um chunk com metadados completos de origem:

```jsonl
{"id": "artigo-turboquant-p01-c00", "text": "TurboQuant propõe uma abordagem...", "metadata": {"source": "artigo-turboquant.pdf", "page": 1, "chunk_idx": 0, "type": "pdf"}}
{"id": "artigo-turboquant-p01-c01", "text": "A rotação aleatória garante que...",  "metadata": {"source": "artigo-turboquant.pdf", "page": 1, "chunk_idx": 1, "type": "pdf"}}
{"id": "artigo-turboquant-p02-c00", "text": "O codebook Lloyd-Max é calculado...", "metadata": {"source": "artigo-turboquant.pdf", "page": 2, "chunk_idx": 0, "type": "pdf"}}
{"id": "docs-redis-p00-c00",         "text": "Redis é um banco de dados...",         "metadata": {"source": "docs-redis.md",            "page": null, "chunk_idx": 0, "type": "md"}}
```

### Geração de `queries.jsonl`

**Estratégia 1 (manual):** escreva 50–100 perguntas e anote quais chunks respondem.

**Estratégia 2 (pseudo ground truth):** use float32 + topk=1 como proxy inicial.  
*Você substitui por anotação real depois do experimento.*

**Estratégia 3 (sintética com LLM local):**
```python
# Para cada chunk, pedir ao LLM: "Escreva uma pergunta que este texto responde"
# Salvar query + id do chunk como ground truth
```

### Formato final do `queries.jsonl`

```jsonl
{"query": "o que é TurboQuant?",                        "relevant_ids": ["artigo-turboquant-p01-c00"]}
{"query": "como o codebook Lloyd-Max é calculado?",      "relevant_ids": ["artigo-turboquant-p02-c00"]}
{"query": "para que serve o Redis?",                     "relevant_ids": ["docs-redis-p00-c00", "docs-redis-p00-c01"]}
```

### Comandos

```bash
make ingest
make queries
```

**Critério de conclusão da Fase 1:**  
`corpus.jsonl` com ≥500 linhas. `queries.jsonl` com ≥50 pares query → ids.

---

## FASE 2 — Embeddings Baseline

### Onde o modelo roda

O modelo de embedding roda **localmente na sua máquina**, sem nenhuma chamada a API externa.
A biblioteca `sentence-transformers` baixa o modelo do HuggingFace Hub na primeira execução e
cacheia em disco. Execuções seguintes usam o cache diretamente.

```
Primeira execução:
  make embed
    └── sentence-transformers baixa o modelo
         └── HuggingFace Hub  (internet necessária só aqui)
              └── salva em ~/.cache/huggingface/hub/
                   └── carrega na RAM / VRAM
                        └── infere em batches localmente

Execuções seguintes:
  make embed
    └── lê direto de ~/.cache/huggingface/hub/  (sem internet)
         └── carrega e infere localmente
```

### Opções de device

| Device | Quando usar | Velocidade estimada (BGE-small, 500 chunks) |
|--------|-------------|---------------------------------------------|
| `cpu` | padrão, qualquer máquina | ~30–60 s |
| `cuda` | NVIDIA GPU disponível | ~2–5 s |
| `mps` | Apple Silicon (M1/M2/M3) | ~5–10 s |

Configurar em `.env`:
```env
EMBEDDING_DEVICE=cpu    # troque por cuda ou mps se tiver
```

Ou passar direto no make:
```bash
make embed DEVICE=cuda
```

### Modelos recomendados (todos locais)

| Modelo | Dim | Tamanho download | Melhor para |
|--------|-----|-----------------|-------------|
| `BAAI/bge-small-en-v1.5` | 384 | ~130 MB | CPU, experimentos rápidos |
| `BAAI/bge-base-en-v1.5` | 768 | ~430 MB | melhor qualidade, ainda viável em CPU |
| `nomic-ai/nomic-embed-text-v1` | 768 | ~550 MB | alternativa open-source |

O modelo é configurado em `configs/embedding.yaml` ou via `EMBEDDING_MODEL` no `.env`.

### Objetivo
Gerar e salvar embeddings **float32** e **float16** normalizados.

### `src/embed.py`

```python
"""
Funções principais:

  load_model(model_name, device, cache_dir=None) → SentenceTransformer
    - Baixa do HuggingFace Hub na 1ª execução, cacheia em ~/.cache/huggingface/hub/
    - device: "cpu" | "cuda" | "mps"
    - Detecta device automaticamente se não especificado:
        if torch.cuda.is_available()   → "cuda"
        elif torch.backends.mps.is_available() → "mps"
        else → "cpu"

  embed_corpus(corpus_path, model, batch_size) → np.ndarray [N, D]
    - Lê corpus.jsonl, extrai campo "text"
    - Infere em batches de batch_size (padrão 64)
    - Mostra barra de progresso com tqdm
    - Retorna array float32 [N, D]

  normalize_rows(X) → X / ||X||
    - Necessário: o paper assume vetores na esfera unitária

  save_embeddings(X, path, dtype)    # .npy
  load_embeddings(path) → np.ndarray
"""
```

### Fluxo

```
corpus.jsonl
    ↓ embed_corpus()
float32 array [N, D]
    ↓ normalize_rows()           ← importante: esfera unitária como o paper assume
    ↓ save → embeddings/baseline_f32.npy
    ↓ astype(float16)
    ↓ save → embeddings/baseline_f16.npy
```

### Comandos

```bash
make embed                   # usa EMBEDDING_DEVICE do .env
make embed DEVICE=cuda       # força GPU NVIDIA
make embed DEVICE=mps        # força Apple Silicon
make embed DEVICE=cpu        # força CPU

# Saída esperada:
# Device: cpu  |  Modelo: BAAI/bge-small-en-v1.5  |  Cache: ~/.cache/huggingface/hub/
# Embedding 523 chunks [batch=64]  100%|██████████| 9/9 [00:47<00:00]
# ✓ Normalizado: 522/523 vetores com norma=1.0
# ✓ Salvo: embeddings/baseline_f32.npy  (0.73 MB)
# ✓ Salvo: embeddings/baseline_f16.npy  (0.37 MB)
```

### Medições desta fase (salvar em `reports/`)

| Arquivo | Dimensão | dtype | Tamanho em disco | RAM estimada |
|---------|----------|-------|-----------------|-------------|
| baseline_f32.npy | [N, D] | float32 | N×D×4 bytes | mesmo |
| baseline_f16.npy | [N, D] | float16 | N×D×2 bytes | mesmo |

**Critério de conclusão da Fase 2:**  
Dois arquivos `.npy` salvos. Verificação: `np.allclose(norm(f32), 1.0)` para ≥99% dos vetores.

---

## FASE 3 — Implementação da Quantização

Esta é a fase central. Implementar 4 variantes em ordem crescente de fidelidade ao paper.

### Variante A — `scalar_uniform.py` (ponto de partida)

```python
"""
Algoritmo:
  1. normalize(x)
  2. y = R @ x          # rotação aleatória
  3. scale = (ymax - ymin) / (2^bits - 1)
  4. Q = round((y - ymin) / scale)    # uint8 ou uint4
  5. Armazenar: Q (inteiros), ymin, scale, norma_original

Reconstrução:
  1. y_hat = Q * scale + ymin
  2. x_hat = R.T @ y_hat
  3. reescalar por norma_original
"""
```

### Variante B — `lloyd_max.py` (codebook ótimo)

> ⚠️ **PROBLEMA 1 E 2 CORRIGIDOS AQUI** — O plano original tinha `beta_pdf_for_rotated_coordinate` retornando `pass` e chamava `initialize_centroids_from_quantiles` que nunca foi definida. Ambas precisam de implementação real.

```python
"""
Diferença da Variante A:
- Em vez de qmin/qmax uniforme, resolve Lloyd-Max 1D para a
  distribuição Beta escalada de [-1, 1] que a coordenada
  rotacionada segue.
- Resulta em centróides não-uniformes otimizados para MSE.
- O codebook depende apenas de (dim, bits) — é independente dos dados.
  Deve ser pré-computado uma vez e reutilizado para todos os vetores.

Funções:
  - beta_coordinate_pdf(x, dim)          # densidade real, implementada com scipy
  - lloyd_max_codebook(dim, bits,        # resolve iterativamente
                       num_grid=200_000,
                       num_iters=200) → centroids [2^bits]
  - quantize_to_codebook(y, centroids)   # argmin por coordenada → idx uint8/uint4
  - dequantize_from_codebook(idx, centroids) → y_hat
"""

# ── IMPLEMENTAÇÃO CORRETA DA PDF ────────────────────────────────────────────
# Fórmula: f(x) = C_d * (1 - x²)^((d-3)/2)  para x ∈ [-1, 1]
# onde C_d = Γ(d/2) / (√π * Γ((d-1)/2))
# Esta é a densidade marginal de uma coordenada de vetor uniforme em S^(d-1).
#
# Equivalência com scipy.stats.beta:
#   Se X ~ Beta(a, a) em [0,1] com a = (d-1)/2,
#   então Y = 2X - 1 tem exatamente essa distribuição em [-1, 1].
#
# Implementação:
#
# from scipy.special import gamma as G
# import numpy as np
#
# def beta_coordinate_pdf(x, dim):
#     """Densidade marginal de uma coordenada de ponto uniforme em S^(d-1)."""
#     x = np.asarray(x, dtype=np.float64)
#     d = dim
#     # normalização
#     Cd = G(d / 2) / (np.sqrt(np.pi) * G((d - 1) / 2))
#     exponent = (d - 3) / 2
#     pdf = np.where(np.abs(x) < 1.0, Cd * (1 - x**2)**exponent, 0.0)
#     return pdf  # array shape igual ao de x
#
# Nota: para d=384, o expoente é (384-3)/2 = 190.5 → distribuição muito
# concentrada em torno de 0. Os centróides do Lloyd-Max ficarão muito
# próximos de zero e densamente espaçados no centro.

# ── INICIALIZAÇÃO DE CENTRÓIDES (substitui initialize_centroids_from_quantiles) ──
# A função que o plano original chamava sem definir:
#
# def _init_centroids_from_quantiles(xs, pdf, K):
#     """Inicializa K centróides pelos quantis da distribuição discreta."""
#     cdf = np.cumsum(pdf)
#     cdf /= cdf[-1]
#     quantile_targets = (np.arange(K) + 0.5) / K  # quantis uniformes
#     centroids = np.interp(quantile_targets, cdf, xs)
#     return centroids

### Variante C — `turboquant_mse.py` (TurboQuantMSE completo)

> ⚠️ **PROBLEMA 3 CORRIGIDO AQUI** — O plano original armazenava índices como `uint8` mesmo para 2-bit e 4-bit. Sem bit-packing, a compressão real é a metade da esperada.

```python
"""
Combina:
- fit_rotation(dim, seed) → matriz ortogonal Q via QR
- lloyd_max_codebook(dim, bits) → centroids
- quantize_mse(x, state) → {idx_packed: bytes, norm: float16}
- dequantize_mse(pkg, state) → x_hat

BIT-PACKING OBRIGATÓRIO para obter as taxas de compressão corretas:
  - 2-bit: 4 índices por uint8 → dim=384 → 384*(2/8) = 96 bytes por vetor
  - 4-bit: 2 índices por uint8 → dim=384 → 384*(4/8) = 192 bytes por vetor
  - 8-bit: 1 índice por uint8 → dim=384 → 384*(8/8) = 384 bytes por vetor
  - float32 baseline:           dim=384 → 384*4     = 1536 bytes por vetor

Sem bit-packing (índice por uint8 sempre):
  - 2-bit usaria 384 bytes  → compressão real 4x   (não 16x)
  - 4-bit usaria 384 bytes  → compressão real 4x   (não 8x)
  Os gráficos de memória ficariam completamente errados!

Implementação correta:
  pack(indices, bits):   np.packbits(unpack_to_bits(indices, bits))
  unpack(packed, bits, dim): np.unpackbits(packed)[:dim*bits].reshape(dim, bits)

State salvo em disco:
  - R: matriz de rotação [D, D] float32   (ou seed para economizar 570 KB)
  - codebook: [2^bits] float32
  - dim, bits, seed
"""
```

### Variante D — `turboquant_prod.py` (TurboQuantProd = MSE + QJL)

> ⚠️ **PROBLEMA 4 CORRIGIDO AQUI** — O plano original armazenava `signs` como `int8` (1 byte por sinal), desperdiçando 7 bits por coordenada. O correto é `np.packbits`.

```python
"""
TurboQuantProd(b bits total):
  - Parte 1: TurboQuantMSE com (b-1) bits
  - Parte 2: QJL no resíduo com 1 bit

QJL:
  - S: matriz gaussiana [D, D]
  - quantize: signs = sign(S @ r)                # {+1, -1} por coordenada
  - armazenamento: np.packbits((signs + 1) // 2) # 1 bit por coordenada!
  - dequantize: r_hat = √(π/2)/D * γ * S.T @ signs_float
  - γ = ||r||_2  (armazenada como float16)

Memória por vetor com TurboQuantProd 4-bit (dim=384):
  - Índices MSE (3 bits × 384):  384*(3/8) = 144 bytes   (packing de 3-bit é irregular)
  - Prático: usar 4-bit packing → 192 bytes para MSE com 3 bits efetivos
  - QJL signs (1 bit × 384):     384/8     =  48 bytes
  - γ norma do resíduo:                    =   2 bytes (float16)
  - Total:                                 = ~242 bytes
  - float32 baseline:            384*4     = 1536 bytes → compressão ~6.4x

Implementação correta dos signs:
  pack_signs(signs):   np.packbits(np.where(signs >= 0, 1, 0))
  unpack_signs(packed, dim): (np.unpackbits(packed)[:dim].astype(np.float32) * 2) - 1

Por que importa:
  - TurboQuantMSE puro tem viés na estimativa de inner product
  - O resíduo QJL remove esse viés (Algoritmo 2 do paper)
  - Para b=1: mse_bits=0 (sem parte MSE), só QJL → 48 bytes vs 1536 (32x)
  - Para b=2: mse_bits=1, codebook de 2 centróides + QJL
  - Para b=4: mse_bits=3, codebook de 8 centróides + QJL (sweet spot do paper)
  - Para b=8: mse_bits=7, codebook de 128 centróides + QJL
"""
```

### `storage.py` — Serialização

> ⚠️ **PROBLEMA 3 E 4 RESOLVIDOS AQUI** — Bit-packing centralizado neste módulo.

```python
"""
save_quantized(pkg_list, state, path):
  Salva em .npz:
    - "indices_packed": array [N, ceil(D*bits/8)] uint8  ← bit-packed!
    - "norms": array [N] float16
    - "codebook": array [2^bits] float32
    - "R": array [D, D] float32  (ou só o seed + dim para reconstruir)
    - "bits": int
    - "dim": int
    - "variant": str
    # Para TurboQuantProd, adicional:
    - "signs_packed": array [N, ceil(D/8)] uint8  ← np.packbits dos signs!
    - "gammas": array [N] float16

Funções de packing (corretas):

  pack_indices(indices_2d, bits):
    # indices_2d: [N, D] com valores 0..2^bits-1
    # Converte para bits e empacota com np.packbits
    # Retorna [N, ceil(D*bits/8)] uint8
    flat_bits = []
    for row in indices_2d:
        for idx in row:
            bits_for_idx = format(idx, f'0{bits}b')
            flat_bits.extend([int(b) for b in bits_for_idx])
    return np.packbits(flat_bits).reshape(N, -1)

  unpack_indices(packed, bits, dim):
    # Inverso: retorna [N, D] int32

  pack_signs(signs_2d):
    # signs_2d: [N, D] com valores +1 ou -1
    binary = (signs_2d + 1) // 2  # +1→1, -1→0
    return np.packbits(binary, axis=1)  # [N, ceil(D/8)] uint8

  unpack_signs(packed, dim):
    # Retorna [N, D] float32 com valores +1.0 ou -1.0
    bits = np.unpackbits(packed, axis=1)[:, :dim]
    return (bits.astype(np.float32) * 2) - 1

load_quantized(path) → pkg_list, state
"""

# Tamanhos reais em disco (dim=384, N vetores) com packing correto:
# ┌──────────────────────┬────────────────┬──────────────┐
# │ Variante             │ Bytes/vetor    │ vs float32   │
# ├──────────────────────┼────────────────┼──────────────┤
# │ float32              │ 1536           │ 1x           │
# │ float16              │  768           │ 2x           │
# │ turbo_mse_8bit       │  384 (packed)  │ 4x           │
# │ turbo_mse_4bit       │  192 (packed)  │ 8x           │
# │ turbo_mse_2bit       │   96 (packed)  │ 16x          │
# │ turbo_prod_4bit      │  192+48+2=242  │ ~6.4x        │
# │ turbo_prod_2bit      │   96+48+2=146  │ ~10.5x       │
# └──────────────────────┴────────────────┴──────────────┘
# Nota: turbo_prod tem overhead dos signs QJL (48 bytes) e gamma (2 bytes)
```

### Comandos

```bash
make quantize-uniform   # roda 2, 4 e 8 bits
make quantize-lloyd     # roda 2, 4 e 8 bits
make quantize-mse       # roda 2, 4 e 8 bits
make quantize-prod      # roda 2, 4 e 8 bits

make quantize-all       # atalho para todos acima
```

**Critério de conclusão da Fase 3:**  
Para cada variante e bits: `dequantize(quantize(x))` retorna vetor com similaridade cosseno ≥ threshold esperado com `x` original.

---

## FASE 4 — Benchmark de Distorção

### Objetivo
Medir quanto cada variante deforma os vetores, **antes** de testar retrieval.

### `src/benchmark/distortion.py`

```python
"""
Funções:
  mse(X_orig, X_hat)
    → MSE médio sobre todos os vetores

  cosine_error(X_orig, X_hat)
    → 1 - cosine_similarity médio (positivo = perda)

  ip_error(X_orig, X_hat, Q_queries)
    → diferença média entre dot(q, x_orig) e dot(q, x_hat)
    → também calcular: viés (bias = E[ip_hat - ip_true]) e variância
    → calculado para um subconjunto de queries de teste

  distortion_table(X_orig, variants_dict, Q_queries)
    → DataFrame com colunas: variant, bits, mse, cosine_error,
                              ip_bias, ip_variance, ip_mae
"""
```

### Métricas desta fase

| Métrica | Fórmula | Interpretação |
|---------|---------|---------------|
| MSE | `mean(||x - x̂||²)` | Erro geométrico médio |
| Cosine Error | `1 - mean(cos(x, x̂))` | Quanto a direção mudou |
| IP Bias | `mean(q·x̂ - q·x)` | Viés sistemático no produto interno |
| IP MAE | `mean(|q·x̂ - q·x|)` | Magnitude do erro no produto interno |
| IP Variance | `var(q·x̂ - q·x)` | Consistência do erro |

### Saída esperada

**`reports/distortion_results.csv`**
```csv
variant,bits,mse,cosine_error,ip_bias,ip_mae,ip_variance
baseline_f32,32,0.0,0.0,0.0,0.0,0.0
baseline_f16,16,0.000001,0.000001,0.000001,0.000001,0.0
uniform,2,0.085,0.042,0.031,0.035,0.0012
uniform,4,0.012,0.006,0.004,0.005,0.00008
uniform,8,0.0001,0.00005,0.00003,0.00004,0.000001
lloyd_max,2,...
...
```

### Comandos

```bash
make distortion-bench
# → reports/distortion_results.csv
# → charts/mse_vs_bits.png
# → charts/ip_error_heatmap.png
```

**Critério de conclusão da Fase 4:**  
CSV gerado. Tendência esperada: MSE decresce com bits crescentes. Lloyd-Max < Uniform para mesmo bits.

---

## FASE 5 — Benchmark de Retrieval

### Objetivo
Medir qualidade de busca top-k real com cada variante de índice.

### `src/retrieval/faiss_store.py`

```python
"""
build_index(embeddings: np.ndarray, index_type="Flat") → faiss.Index
  - IndexFlatIP para produto interno (vetores normalizados = equivale a cosseno)
  - Treinar e popular o índice

save_index(index, path)
load_index(path) → faiss.Index

Índices a construir:
  - faiss_f32.index     ← baseline_f32.npy
  - faiss_f16.index     ← baseline_f16 convertido para f32 antes de inserir
  - faiss_Xbit_VAR.index ← dequantize(quantized) → f32 antes de inserir
"""
```

### `src/retrieval/metrics.py`

```python
"""
recall_at_k(results, ground_truth, k)
  → fração de queries onde ≥1 id relevante aparece no top-k

mrr(results, ground_truth)
  → mean(1/rank_do_primeiro_relevante)

mean_latency(search_fn, query_vecs, n_runs=3)
  → tempo médio em ms por query

index_memory_mb(index_path)
  → tamanho do arquivo .index em MB

retrieval_report(all_variants, queries_jsonl, k_list=[1,5,10])
  → DataFrame com colunas: variant, bits, recall@1, recall@5, recall@10,
                            mrr, latency_ms, index_size_mb
"""
```

### `src/benchmark/retrieval_bench.py`

```python
"""
Fluxo:
  1. Carregar queries.jsonl
  2. Gerar embedding das queries (mesmo modelo, mesmo normalize)
  3. Para cada variante:
     a. Carregar índice
     b. Para cada query: buscar top-10
     c. Calcular recall@1, @5, @10, MRR
     d. Medir latência
     e. Medir tamanho do índice
  4. Agregar em DataFrame
  5. Salvar reports/benchmark_results.csv
  6. Imprimir tabela com rich
"""
```

### Saída esperada

> ⚠️ **PROBLEMA 5 CORRIGIDO AQUI** — Os valores de memória estavam errados sem bit-packing. Abaixo os números corretos para N=500 vetores, dim=384.

**`reports/benchmark_results.csv`**
```csv
variant,bits,recall_at_1,recall_at_5,recall_at_10,mrr,latency_ms,embed_size_mb,compression_vs_f32
baseline_f32,32,0.82,0.94,0.97,0.87,1.2,0.73,1.0x
baseline_f16,16,0.81,0.93,0.96,0.86,1.1,0.37,2.0x
uniform,8,0.80,0.92,0.95,0.85,1.0,0.18,4.0x
uniform,4,0.74,0.88,0.92,0.80,1.0,0.09,8.0x
uniform,2,0.59,0.75,0.82,0.69,1.0,0.046,16.0x
lloyd_max,4,0.77,0.90,0.94,0.82,1.0,0.09,8.0x
turbo_mse,4,0.79,0.92,0.95,0.84,1.0,0.09,8.0x
turbo_prod,4,0.80,0.93,0.96,0.85,1.0,0.115,6.4x
...
```
# Nota: embed_size_mb = N * bytes_por_vetor / 1_048_576
# N=500, dim=384:
#   f32:         500 * 1536 / 1M = 0.73 MB
#   4-bit packed: 500 *  192 / 1M = 0.09 MB (8x)
#   turbo_prod_4: 500 *  242 / 1M = 0.115 MB (6.4x)

### Comandos

```bash
make build-indexes
make retrieval-bench
# → reports/benchmark_results.csv
# → charts/recall_vs_bits.png
# → charts/tradeoff_recall_memory.png

make all-bench   # distortion-bench + build-indexes + retrieval-bench
```

**Critério de conclusão da Fase 5:**  
CSV gerado com todas as variantes. turbo_mse/prod ≥ uniform para mesmo bits.

---

## FASE 6 — Relatórios & Visualizações

Esta é a fase que transforma os CSVs em insights visuais.

### `src/visualization/plots.py`

Cada função gera um gráfico específico e salva em `charts/`.

---

#### Gráfico 1 — `recall_vs_bits.png`
**Tipo:** Line chart com múltiplas séries  
**Eixo X:** bits (2, 4, 8, 16, 32)  
**Eixo Y:** Recall@k (k=1, 5, 10 como linhas diferentes)  
**Séries:** uma linha por variante (uniform, lloyd_max, turbo_mse, turbo_prod)  
**Referências:** linhas horizontais tracejadas para f32 e f16  
**Insight:** mostra quanto recall se perde ao comprimir

```
Recall@10
  1.0 ┤ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ (f32 ref)
  0.9 ┤        ╭──────────────── turbo_prod
  0.8 ┤      ╭─╯ ╭────────────── turbo_mse
  0.7 ┤    ╭─╯  ╭╯ ╭──────────── lloyd_max
  0.6 ┤  ╭─╯   ╯  ╭╯ ─────────── uniform
      └──┴─────────────────────
        2   4   8  16  32  bits
```

---

#### Gráfico 2 — `mse_vs_bits.png`
**Tipo:** Bar chart agrupado  
**Eixo X:** variantes  
**Eixo Y:** MSE (escala log)  
**Grupos de barras:** um grupo por bits (2, 4, 8)  
**Insight:** lloyd_max e turbo têm MSE menor que uniform para mesmo bits

---

#### Gráfico 3 — `memory_compression.png`
**Tipo:** Bar chart horizontal  
**Eixo X:** tamanho em MB  
**Eixo Y:** variante + bits  
**Cores:** gradiente por taxa de compressão vs f32  
**Anotações:** "16x menor", "8x menor" etc.  
**Insight:** ganho absoluto de memória

```
# Valores corretos para N=500, dim=384 COM bit-packing:
baseline_f32    ████████████████████  0.73 MB (1x)
baseline_f16    ██████████            0.37 MB (2x)
turbo_mse_8bit  █████                 0.18 MB (4x)
turbo_mse_4bit  ██▌                   0.09 MB (8x)
turbo_prod_4bit ███                   0.115 MB (6.4x)  ← overhead dos signs QJL
turbo_mse_2bit  █▎                    0.046 MB (16x)

# ERRADO (sem bit-packing, índices como uint8 por coordenada):
# uniform_4bit → 500 * 384 * 1 byte = 0.18 MB  ← apenas 4x, não 8x!
# uniform_2bit → 500 * 384 * 1 byte = 0.18 MB  ← apenas 4x, não 16x!
```

---

#### Gráfico 4 — `latency_comparison.png`
**Tipo:** Box plot ou bar com error bars  
**Eixo X:** variante  
**Eixo Y:** latência em ms  
**Insight:** quantização não deve aumentar latência de busca pois se busca nos vetores dequantizados

---

#### Gráfico 5 — `tradeoff_recall_memory.png` ⭐ (gráfico principal)
**Tipo:** Scatter plot  
**Eixo X:** tamanho do índice em MB (escala log)  
**Eixo Y:** Recall@10  
**Ponto:** cada (variante, bits) é um ponto  
**Cor:** variante de quantização  
**Tamanho do ponto:** número de bits  
**Anotações:** labels em cada ponto  
**Curva de Pareto:** linha conectando os pontos ótimos  
**Insight:** qual variante tem melhor recall para dado tamanho?

```
Recall@10
  0.97 ●  f32 (2.0 MB)
  0.96    ● f16 (1.0 MB)
  0.94          ● turbo_prod_8bit
  0.90                 ● turbo_mse_4bit
  0.84                         ● uniform_4bit
  0.78                                  ● uniform_2bit
       └────────────────────────────────────────
       0.1      0.5      1.0     2.0 MB (log)
```

---

#### Gráfico 6 — `ip_error_heatmap.png`
**Tipo:** Heatmap  
**Eixo X:** variantes  
**Eixo Y:** métricas (IP Bias, IP MAE, IP Variance)  
**Células:** valor + cor (verde=baixo erro, vermelho=alto erro)  
**Insight:** TurboQuantProd deve ter menor IP Bias que TurboQuantMSE

---

#### Gráfico 7 — `recall_degradation_per_query.png`
**Tipo:** Histogram ou violin plot  
**Distribuição:** por query, qual foi a posição do documento relevante em cada variante  
**Séries:** f32 vs turbo_mse_4bit vs uniform_4bit  
**Insight:** quais queries sofrem mais com compressão

---

#### Gráfico 8 — `compression_ratio_vs_recall_loss.png`
**Tipo:** Dual-axis bar+line  
**Eixo X:** variante + bits  
**Eixo Y esquerdo:** taxa de compressão (x vezes menor que f32)  
**Eixo Y direito:** queda no Recall@10 vs f32 (em pontos percentuais)  
**Insight:** identificar o "sweet spot" — maior compressão com menor perda

---

### `src/visualization/dashboard.py`

```python
"""
Gera charts/dashboard.html com plotly.
Inclui todos os gráficos interativos numa página única:
- Dropdowns para filtrar por bits/variante
- Tabela interativa com todos os resultados
- Tooltips com detalhes de cada ponto
"""
```

### `src/benchmark/reports.py`

```python
"""
Gera reports/retrieval_examples.md com:
- Top 5 queries que MAIS perderam qualidade (f32 → turbo_4bit)
- Top 5 queries que MANTIVERAM qualidade (0% de perda)
- Análise: há padrão nos textos que quebram vs os que aguentam?
"""
```

### Comandos

```bash
make visualize
# → Gera todos os 9 gráficos em charts/
# → Gera charts/dashboard.html
# → Imprime summary no terminal com rich

make report
# → reports/retrieval_examples.md
# → reports/notes.md com análise automática
```

**Critério de conclusão da Fase 6:**  
`charts/` com 8 PNGs + `dashboard.html`. Tabela de resultados impressa no terminal.

---

## FASE 7 — Mini Pipeline RAG

### Objetivo
Mostrar o efeito end-to-end: contexto com quantização degradada pode mudar a resposta.

### `src/rag/pipeline.py`

```python
"""
RAGPipeline:
  __init__(index, corpus, model, llm=None)

  search(query: str, k: int = 5, variant: str = "turbo_mse_4bit")
    → [{"id", "text", "score", "metadata"}]

  build_context(results) → str
    → concatena chunks com separadores

  answer(query: str, k: int = 5, variant: str = "...")
    → {"query", "context", "answer", "variant", "docs_used"}
"""
```

### `src/rag/prompting.py`

```python
"""
Template de prompt:
  Contexto:
  {context}

  Pergunta: {query}

  Resposta baseada apenas no contexto acima:

LLM: pode ser mock simples que retorna o primeiro chunk,
     ou integrar com Ollama local (llama3, mistral),
     ou OpenAI-compatible API.
"""
```

### Comparação qualitativa

```bash
make rag-demo QUERY="como funciona o cache redis?"

# Saída formatada (rich table):
# ┌─────────────────┬────────────────────────────────────────────────────┐
# │ Variante        │ Top-3 documentos recuperados                       │
# ├─────────────────┼────────────────────────────────────────────────────┤
# │ f32 (baseline)  │ doc-001 (score=0.91), doc-003 (0.87), doc-007 (0.82) │
# │ turbo_mse_4bit  │ doc-001 (0.89), doc-003 (0.85), doc-007 (0.80)    │
# │ uniform_2bit    │ doc-012 (0.74), doc-001 (0.71), doc-033 (0.68)    │
# └─────────────────┴────────────────────────────────────────────────────┘
```

**Critério de conclusão da Fase 7:**  
Demo funcional. Pelo menos 1 caso onde uniform_2bit retorna contexto errado vs f32 correto.

---

## Ordem de Execução Recomendada

### Sequência prática (evita armadilhas)

```bash
# ── SETUP ───────────────────────────────────────────────────────────────
make setup          # uv sync + cria .env + cria pastas

# ── FASE 1: Dados ───────────────────────────────────────────────────────
make ingest         # data/raw/ → corpus.jsonl
make queries        # pseudo ground truth via top-1 f32

# ── FASE 2: Embeddings ──────────────────────────────────────────────────
make embed          # baseline_f32.npy + baseline_f16.npy

# ── FASE 3: Quantização (ordem crescente de complexidade) ───────────────
make quantize-uniform  # mais simples, valida o pipeline primeiro
make quantize-lloyd    # adiciona codebook ótimo
make quantize-mse      # TurboQuantMSE completo
make quantize-prod     # TurboQuantProd = MSE + QJL

# ── FASE 4 + 5: Benchmarks ──────────────────────────────────────────────
make all-bench      # distortion-bench + build-indexes + retrieval-bench

# ── FASE 6: Resultados ──────────────────────────────────────────────────
make visualize      # 9 gráficos + dashboard.html
make report         # markdown com análise das queries

# ── FASE 7: Demo RAG ────────────────────────────────────────────────────
make rag-demo QUERY="sua pergunta aqui"

# ── Pipeline completo de uma vez ────────────────────────────────────────
make all

# ── Ajuda ───────────────────────────────────────────────────────────────
make help
```

---

## Tabela de Gráficos Produzidos

| # | Arquivo | Tipo | Eixo X | Eixo Y | Pergunta respondida |
|---|---------|------|--------|--------|---------------------|
| 1 | `recall_vs_bits.png` | Line | bits | Recall@k | Quanto o recall cai por bits? |
| 2 | `mse_vs_bits.png` | Bar agrupado | variante | MSE (log) | Qual variante distorce menos? |
| 3 | `memory_compression.png` | Bar horizontal | variante+bits | MB | Quanto de memória se ganha? |
| 4 | `latency_comparison.png` | Box plot | variante | ms/query | Quantização afeta latência? |
| 5 | `tradeoff_recall_memory.png` ⭐ | Scatter | MB (log) | Recall@10 | Qual o sweet spot? |
| 6 | `ip_error_heatmap.png` | Heatmap | variante | métricas IP | Prod corrige o viés do MSE? |
| 7 | `recall_degradation_per_query.png` | Violin | variante | rank do relevante | Quais queries sofrem mais? |
| 8 | `compression_ratio_vs_recall_loss.png` | Dual-axis | variante+bits | compressão / queda | Onde está o equilíbrio? |
| 9 | `dashboard.html` | Interativo | — | — | Exploração livre de todos os dados |

---

## Critérios de Sucesso do Projeto (V1)

| Critério | Threshold esperado |
|----------|--------------------|
| turbo_mse 4-bit Recall@10 vs f32 | ≥ 90% do baseline |
| turbo_prod 4-bit IP Bias | < 50% do bias do turbo_mse 4-bit |
| lloyd_max MSE vs uniform (mesmo bits) | lloyd_max ≤ 80% do MSE uniform |
| Ganho de memória turbo_mse 4-bit vs f32 | ≥ 8x (com bit-packing correto) |
| Ganho de memória turbo_prod 4-bit vs f32 | ~6.4x (overhead QJL signs + gamma) |
| Latência de busca (qualquer variante) | não piora > 2x vs f32 |
| Dashboard HTML funcional | abre no browser sem erros |

---

## Dependências entre Fases

```
FASE 0 ──────────────────────────────────────────────────────────── (independente)
  └──→ FASE 1 (ingest + queries) ────────────────────────────────── (precisa de Fase 0)
         └──→ FASE 2 (embeddings) ──────────────────────────────── (precisa de Fase 1)
                └──→ FASE 3 (quantização) ──────────────────────── (precisa de Fase 2)
                       ├──→ FASE 4 (distortion bench) ─────────── (precisa de Fase 3)
                       └──→ FASE 5 (retrieval bench) ──────────── (precisa de Fase 3)
                              ├──→ FASE 6 (visualizações) ──────── (precisa de Fase 4+5)
                              └──→ FASE 7 (RAG demo) ───────────── (precisa de Fase 5)
```

---

## Resumo dos 5 Problemas Corrigidos

| # | Problema | Onde ocorria | Impacto | Correção |
|---|----------|-------------|---------|----------|
| 1 | `beta_pdf_for_rotated_coordinate` retornava `pass` | `lloyd_max.py` | Lloyd-Max não funciona sem a PDF real | Usar `scipy.special.gamma` com fórmula `C_d * (1-x²)^((d-3)/2)` |
| 2 | `initialize_centroids_from_quantiles` indefinida | `lloyd_max.py` | `NameError` em tempo de execução | Implementar com `np.interp` sobre a CDF empírica da distribuição |
| 3 | Índices de 2-bit e 4-bit armazenados como `uint8` | `storage.py`, `turboquant_mse.py` | Compressão real 2-4x menor que o anunciado; gráficos de memória errados | Usar `np.packbits` para empacotar múltiplos índices por byte |
| 4 | Signs do QJL armazenados como `int8` (1 byte/sign) | `storage.py`, `turboquant_prod.py` | 8x mais memória usada do que o necessário para os signs | Usar `np.packbits` → 1 bit por sign → `ceil(dim/8)` bytes |
| 5 | Valores esperados no CSV de benchmark errados | `PLAN.md` (documentação) | Expectativas irreais de compressão; teste de critério de sucesso falharia | Recalcular com bit-packing; turbo_prod_4bit é ~6.4x (não 8x) por ter overhead dos signs |

---

## Notas de Implementação Importantes

### Sobre normalização
- Sempre normalizar **antes** de quantizar e **ao carregar** do índice
- O paper assume vetores na esfera unitária — guardar a norma original separadamente
- `faiss.IndexFlatIP` com vetores normalizados = busca por cosseno

### Sobre o codebook Lloyd-Max
- Pré-computar **uma vez** por `(dim, bits)` e reutilizar
- A distribuição Beta da coordenada depende apenas de `dim`, não dos dados
- Para `dim=384` (BGE-small): a distribuição é muito estreita, centroids bem próximos de 0

### Sobre TurboQuantProd
- Para `bits=2`: 1 bit MSE + 1 bit QJL → caso extremo, esperado degradar mais
- Para `bits=4`: 3 bits MSE + 1 bit QJL → sweet spot do paper
- Para `bits=8`: 7 bits MSE + 1 bit QJL → próximo de f16 na prática

### Sobre FAISS
- Inserir sempre em `float32` (FAISS não aceita float16 em IndexFlat)
- Para variantes quantizadas: dequantizar → f32 → inserir no índice
- O "ganho" de memória é no **armazenamento em disco**, não no índice FAISS em si
- Para índice FAISS comprimido usar `IndexIVFPQ` (extensão futura, V2)

### Sobre ground truth
- Se usar pseudo ground truth (top-1 f32), o Recall@1 do f32 será sempre 100%
- Isso é correto: você está medindo degradação relativa ao baseline
- Para estudo mais sério, substituir por pares anotados manualmente

---

## Extensões Futuras (V2 / V3)

| Extensão | Complexidade | Valor |
|----------|-------------|-------|
| FAISS IVFxPQ (quantização nativa do FAISS) | Média | Comparar com TurboQuant |
| Qdrant com Binary Quantization | Baixa | Benchmark em serviço real |
| PCA antes da rotação | Baixa | Reduzir dimensão + quantizar |
| Busca diretamente nos vetores quantizados (sem dequantizar) | Alta | Ganho real de latência |
| Múltiplos modelos de embedding (BGE vs E5 vs Nomic) | Baixa | Sensibilidade ao modelo |
| Dataset maior (BEIR, MS MARCO, NQ) | Média | Validação estatística |
| API HTTP com FastAPI | Média | Integração com outros sistemas |
