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

queries:        ## Gera queries.jsonl (first_sentence não precisa de embeddings)
	$(PYTHON) -m $(SRC) queries --strategy first_sentence --max-queries 200

queries-pseudo: ## Gera queries.jsonl com pseudo ground truth (top-1 f32, requer Fase 2)
	$(PYTHON) -m $(SRC) queries --strategy pseudo --topk 1

ingest-check:   ## Mostra quantos chunks foram gerados por arquivo
	@$(PYTHON) -c "\
import json, collections; \
from pathlib import Path; \
p = Path('data/corpus.jsonl'); \
lines = p.read_text().splitlines() if p.exists() else []; \
chunks = [json.loads(l) for l in lines]; \
counts = collections.Counter(c['metadata']['source'] for c in chunks); \
[print(f'  {n:4d} chunks  {src}') for src, n in sorted(counts.items())]; \
print(f'  ────────────────'); \
print(f'  {len(chunks):4d} total') \
"

## ── fase 2: embeddings ─────────────────────────────────────────────────
embed:          ## Gera baseline_f32.npy e baseline_f16.npy
	$(PYTHON) -m $(SRC) embed $(if $(DEVICE),--device $(DEVICE),)

embed-info:     ## Mostra device disponível e modelo configurado
	@$(PYTHON) -c "\
import torch, os; \
from pathlib import Path; \
from dotenv import load_dotenv; \
load_dotenv(); \
model = os.getenv('EMBEDDING_MODEL', 'BAAI/bge-small-en-v1.5'); \
cuda = torch.cuda.is_available(); \
rocm = torch.version.hip is not None; \
mps  = hasattr(torch.backends, 'mps') and torch.backends.mps.is_available(); \
kfd  = Path('/dev/kfd').exists(); \
device = 'cuda' if cuda else ('mps' if mps else 'cpu'); \
print(f'  Modelo : {model}'); \
print(f'  Device : {device}'); \
print(f'  CUDA   : {cuda}'); \
print(f'  ROCm   : {rocm}  (build ROCm: {torch.version.hip})'); \
print(f'  MPS    : {mps}'); \
print(f'  /dev/kfd: {kfd}  (AMD GPU kernel module)'); \
(print('  AVISO  : RX 580 (gfx803) nao suportado pelo PyTorch ROCm >= 5.0 → usando CPU') if kfd and not cuda else None) \
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
visualize:      ## Gera todos os gráficos em charts/
	$(PYTHON) -m $(SRC) visualize

report:         ## Gera relatório Markdown com exemplos de queries
	$(PYTHON) -m $(SRC) report

## ── fase 7: rag demo ───────────────────────────────────────────────────
rag-demo:       ## Demo interativo RAG (QUERY obrigatória; opcional: VARIANTS, K, BACKEND, MODEL)
	@test -n "$(QUERY)" || (echo "Uso: make rag-demo QUERY='sua pergunta'" && exit 1)
	$(PYTHON) -m $(SRC) rag-demo \
	  --query "$(QUERY)" \
	  $(if $(VARIANTS),--variants $(VARIANTS),--variants f32,turbo_mse_4bit,uniform_2bit) \
	  $(if $(K),--k $(K),) \
	  $(if $(BACKEND),--backend $(BACKEND),) \
	  $(if $(MODEL),--model $(MODEL),)

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
	  | awk 'BEGIN {FS = ":.*##"}; {printf "  \033[36m%-22s\033[0m %s\n", $$1, $$2}'
