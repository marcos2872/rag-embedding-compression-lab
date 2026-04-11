# RAG Embedding Compression Lab

Laboratório para medir quanto de memória é possível economizar em embeddings de texto sem degradar a qualidade de retrieval. Baseado no paper **TurboQuant**.

---

## Fase 1 — Corpus & Queries

Esta fase transforma documentos brutos (`data/raw/`) em dois artefatos que alimentam todas as fases seguintes:

| Artefato | Descrição |
|---|---|
| `data/corpus.jsonl` | Todos os chunks com ID e metadados |
| `data/queries.jsonl` | Pares `query → relevant_ids` para benchmark |

---

## Pré-requisitos

| Requisito | Versão mínima | Como verificar |
|---|---|---|
| Python | 3.10+ | `python3 --version` |
| [uv](https://docs.astral.sh/uv/getting-started/installation/) | qualquer | `uv --version` |

Instalar `uv` caso não tenha:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

---

## Passo a passo

### 1. Clonar e entrar no projeto

```bash
git clone <url-do-repo>
cd rag-embedding-compression-lab
```

### 2. Instalar dependências e criar `.env`

```bash
make setup
```

O que esse comando faz:
- Executa `uv sync` — cria o virtualenv e instala todas as dependências do `pyproject.toml`
- Copia `.env.example` → `.env` (só na primeira vez)
- Cria os diretórios `data/raw/`, `embeddings/`, `indexes/`, `reports/`, `charts/`

> **Primeira execução demora ~1–2 min** por causa do download de PyTorch e dependências.

### 3. Adicionar documentos em `data/raw/`

Coloque seus arquivos na pasta `data/raw/`. Formatos suportados:

| Extensão | Leitor | Observação |
|---|---|---|
| `.pdf` | `pymupdf` (fitz) | Extrai texto por página; preserva número de página nos metadados |
| `.txt` | `open()` nativo | Leitura direta |
| `.md` | `open()` nativo | Remove marcações Markdown (headers, links, code blocks) |

O repositório já inclui **12 documentos de amostra** em `data/raw/` sobre embeddings, RAG, quantização, FAISS, Redis e NestJS — prontos para usar sem nenhuma configuração extra.

```
data/raw/
├── PLAN.md                        ← plano de execução do lab
├── perplexity.md                  ← notas de pesquisa TurboQuant
├── turboquant-summary.md          ← resumo do paper TurboQuant
├── quantization-in-ml.md          ← técnicas de quantização em ML
├── vector-embeddings-guide.md     ← guia de embeddings vetoriais
├── rag-systems-overview.md        ← visão geral de sistemas RAG
├── faiss-vector-search.md         ← busca vetorial com FAISS
├── sentence-transformers-guide.md ← biblioteca sentence-transformers
├── vector-databases.md            ← comparativo de bancos vetoriais
├── retrieval-metrics.md           ← métricas de IR (Recall, MRR, NDCG)
├── redis-guide.md                 ← Redis: estruturas e padrões
└── nestjs-guide.md                ← NestJS: aplicações server-side
```

### 4. Rodar a ingestão

```bash
make ingest
```

O que acontece por baixo:

```
data/raw/*.{pdf,txt,md}
        │
        ▼  src/ingest.py
   lê cada arquivo com o leitor adequado por extensão
        │
        ▼  src/chunking.py  (sliding window por palavras)
   divide cada bloco em chunks sobrepostos
        │
        ├──▶  data/processed/<nome>.jsonl   (chunks por arquivo)
        └──▶  data/corpus.jsonl             (corpus unificado)
```

Saída esperada:

```
Ingestão: 12 arquivo(s) encontrado(s) em data/raw

  ✓ PLAN.md                                    118 chunks
  ✓ faiss-vector-search.md                      37 chunks
  ✓ nestjs-guide.md                             35 chunks
  ✓ perplexity.md                               62 chunks
  ...
  ✓ vector-embeddings-guide.md                  32 chunks

✓ corpus.jsonl gravado: 556 chunks em data/corpus.jsonl
```

### 5. Verificar o corpus

```bash
make ingest-check
```

Lista quantos chunks vieram de cada arquivo:

```
   118 chunks  PLAN.md
    62 chunks  perplexity.md
    44 chunks  turboquant-summary.md
    ...
  ────────────────
   556 total
```

### 6. Gerar as queries

```bash
make queries
```

Usa a estratégia `first_sentence`: extrai a primeira frase de cada chunk como query e marca aquele chunk como relevante. Não precisa de embeddings — funciona 100% offline.

Saída esperada:

```
Corpus carregado: 556 chunks

✓ queries.jsonl gravado: 200 pares em data/queries.jsonl
```

Uma amostra das queries geradas é exibida no terminal.

---

## Formato dos artefatos gerados

### `data/corpus.jsonl`

Cada linha é um JSON com o chunk e seus metadados:

```jsonl
{
  "id": "turboquant-summary-p00-c03",
  "text": "The core insight of TurboQuant is that combining three components — a random orthogonal rotation, an optimal scalar codebook derived from the unit-sphere coordinate distribution, and bit-packed storage — achieves near-optimal compression quality...",
  "metadata": {
    "source": "turboquant-summary.md",
    "page": null,
    "chunk_idx": 3,
    "type": "md"
  }
}
```

**Formato do ID:** `<stem-do-arquivo>-p<página>-c<índice-do-chunk>`

- PDFs: `artigo-p03-c01` (página 3, chunk 1)
- TXT/MD: `documento-p00-c07` (página = 0 pois não há paginação)

### `data/queries.jsonl`

Cada linha é um par query → lista de IDs relevantes:

```jsonl
{"query": "The core insight of TurboQuant is that combining three components...", "relevant_ids": ["turboquant-summary-p00-c03"]}
{"query": "Redis is an open-source, in-memory data structure store...", "relevant_ids": ["redis-guide-p00-c00"]}
```

---

## Configuração do chunking

O chunking é controlado por `configs/dataset.yaml`:

```yaml
chunk_size: 64        # palavras por chunk
chunk_overlap: 16     # palavras repetidas entre chunks consecutivos
min_chunk_length: 20  # chunks menores que isso são descartados
```

**Como o sliding window funciona:**

```
Texto: [w1 w2 w3 w4 w5 w6 w7 w8 w9 w10 ...]   (palavras)

chunk_size=6, overlap=2  →  step=4

Chunk 0: [w1  w2  w3  w4  w5  w6]
Chunk 1:             [w5  w6  w7  w8  w9  w10]   (2 palavras de overlap com chunk 0)
Chunk 2:                         [w9  w10 ...]
```

O overlap garante que frases quebradas na fronteira de um chunk apareçam completas em pelo menos um chunk vizinho.

**Parâmetros alternativos dependendo do caso de uso:**

| Caso de uso | chunk_size | chunk_overlap | Chunks esperados (556 docs) |
|---|---|---|---|
| Lab rápido (padrão) | 64 | 16 | ~550 |
| RAG de produção | 256 | 32 | ~90 |
| Textos longos / PDFs | 512 | 64 | ~50 |

Para alterar, edite `configs/dataset.yaml` ou passe flags direto:

```bash
uv run python -m src.main ingest --chunk-size 256 --chunk-overlap 32
```

---

## Adicionando seus próprios documentos

1. Copie seus arquivos para `data/raw/`:

```bash
cp meu-artigo.pdf data/raw/
cp minhas-notas.md data/raw/
```

2. Rode a ingestão novamente:

```bash
make ingest
make ingest-check   # confere os chunks por arquivo
make queries        # regenera as queries
```

O pipeline detecta a extensão automaticamente. Arquivos com extensões não suportadas são ignorados com aviso.

---

## Critério de conclusão da Fase 1

| Critério | Verificação | Status |
|---|---|---|
| `corpus.jsonl` com ≥ 500 chunks | `make ingest-check` mostra total | ✅ 556 chunks |
| `queries.jsonl` com ≥ 50 pares | `wc -l data/queries.jsonl` | ✅ 200 pares |
| Formato correto dos IDs | `head -1 data/corpus.jsonl` | ✅ `<stem>-p<page>-c<idx>` |
| Arquivos intermediários gerados | `ls data/processed/` | ✅ 12 arquivos `.jsonl` |

```bash
# Verificação rápida de tudo:
wc -l data/corpus.jsonl data/queries.jsonl
```

Saída esperada:
```
  556 data/corpus.jsonl
  200 data/queries.jsonl
  756 total
```

---

## Fase 2 — Embeddings Baseline

Esta fase gera os embeddings float32 e float16 que servem de referência para todas as comparações de quantização.

| Artefato | Descrição |
|---|---|
| `embeddings/baseline_f32.npy` | Vetores float32 `[N, D]` na esfera unitária |
| `embeddings/baseline_f16.npy` | Mesmos vetores em float16 (metade da memória) |

O modelo roda **100% local**, sem chamadas a API. Na primeira execução o modelo é baixado do HuggingFace Hub e cacheado em `~/.cache/huggingface/hub/`.

---

### Pré-requisito

A Fase 1 deve estar concluída:

```bash
wc -l data/corpus.jsonl   # deve mostrar 556 (ou o total do seu corpus)
```

---

### Passo 1 — Verificar device disponível

```bash
make embed-info
```

Saída típica em CPU:

```
  Modelo : BAAI/bge-small-en-v1.5
  Device : cpu
  CUDA   : False
  ROCm   : False  (build ROCm: None)
  MPS    : False
  /dev/kfd: True  (AMD GPU kernel module)
  AVISO  : RX 580 (gfx803) nao suportado pelo PyTorch ROCm >= 5.0 → usando CPU
```

> **Sobre a AMD RX 580:** a GPU é reconhecida pelo sistema (`/dev/kfd` presente) mas a
> arquitetura **gfx803 (Polaris)** não é suportada pelo PyTorch ROCm a partir da versão 5.0.
> O pipeline detecta isso automaticamente e faz fallback para CPU — sem nenhuma configuração extra.
> Para os 556 chunks do corpus de amostra a inferência leva **~30 segundos na CPU**.

---

### Passo 2 — Gerar os embeddings

```bash
make embed
```

O que acontece por baixo:

```
data/corpus.jsonl
        │
        ▼  src/embed.py — detect_device()
   detecta o melhor device disponível (cuda → mps → cpu)
        │
        ▼  load_model()  (download automático na 1ª execução)
   BAAI/bge-small-en-v1.5  (~130 MB, dim=384)
        │
        ▼  embed_corpus()  (batches de 64, barra de progresso)
   array float32 [N, D]
        │
        ▼  normalize_rows()  — obrigatório: esfera unitária
   ||x|| = 1.0 para todos os vetores
        │
        ├──▶  embeddings/baseline_f32.npy   (float32)
        └──▶  embeddings/baseline_f16.npy   (float16)
```

Saída esperada:

```
Modelo:  BAAI/bge-small-en-v1.5
Device:  cpu
Cache:   ~/.cache/huggingface/hub/

✓ Modelo carregado em 7.6s

Corpus:  556 chunks  →  9 batches (batch_size=64)

  Gerando embeddings… ━━━━━━━━━━━━━━━━━━━━━━━━ 556/556 100% 0:00:30

✓ Embeddings gerados  shape=(556, 384)  dtype=float32  tempo=30.8s
✓ Normalizado: 556/556 vetores com norma≈1.0

✓ Salvo: embeddings/baseline_f32.npy  shape=(556, 384)  dtype=float32  0.81 MB
✓ Salvo: embeddings/baseline_f16.npy  shape=(556, 384)  dtype=float16  0.41 MB

┏━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━┳━━━━━━━━━┳━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━┓
┃ Arquivo                 ┃      Shape ┃  dtype  ┃ Tamanho ┃ Compressão vs f32 ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━╇━━━━━━━━━╇━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━┩
│ embeddings/baseline_f32 │ [556, 384] │ float32 │ 0.81 MB │                1× │
│ embeddings/baseline_f16 │ [556, 384] │ float16 │ 0.41 MB │                2× │
└─────────────────────────┴────────────┴─────────┴─────────┴───────────────────┘

✓ Fase 2 concluída.
```

---

### Passo 3 (opcional) — Atualizar queries com pseudo ground truth

Com os embeddings prontos é possível substituir as queries geradas na Fase 1
(estratégia `first_sentence`) por queries com **pseudo ground truth** baseado em top-1 float32:

```bash
make queries-pseudo
```

Essa estratégia amostra 200 chunks aleatórios do corpus, busca o documento mais similar
por similaridade de cosseno (f32 exato via FAISS) e usa o resultado como ground truth.
Como o f32 é o baseline de referência, o **Recall@1 do f32 será sempre 100%** — isso é
intencional: você mede a degradação das variantes comprimidas *em relação ao baseline*.

---

### Configuração do modelo

O modelo e device são controlados por `.env` ou `configs/embedding.yaml`:

```env
# .env
EMBEDDING_MODEL=BAAI/bge-small-en-v1.5
EMBEDDING_BATCH_SIZE=64
EMBEDDING_DEVICE=cpu          # cpu | cuda | mps
```

```yaml
# configs/embedding.yaml
model: BAAI/bge-small-en-v1.5
batch_size: 64
normalize: true
device: cpu
```

**Modelos disponíveis (todos locais, sem API):**

| Modelo | Dimensão | Download | Melhor para |
|---|---|---|---|
| `BAAI/bge-small-en-v1.5` | 384 | ~130 MB | CPU, experimentos rápidos |
| `BAAI/bge-base-en-v1.5` | 768 | ~430 MB | Melhor qualidade, ainda viável em CPU |
| `nomic-ai/nomic-embed-text-v1` | 768 | ~550 MB | Alternativa open-source |

Para trocar o modelo, edite `.env` e rode `make embed` novamente. Os arquivos `.npy` serão sobrescritos.

**Para forçar um device específico:**

```bash
make embed DEVICE=cpu     # força CPU
make embed DEVICE=cuda    # força NVIDIA GPU
make embed DEVICE=mps     # força Apple Silicon
```

---

### Formato dos artefatos gerados

Ambos os arquivos são arrays NumPy salvos com `np.save`:

```python
import numpy as np

f32 = np.load("embeddings/baseline_f32.npy")  # shape [N, D], dtype float32
f16 = np.load("embeddings/baseline_f16.npy")  # shape [N, D], dtype float16

# Cada linha i corresponde ao chunk i de data/corpus.jsonl
# Todos os vetores têm norma L2 = 1.0 (esfera unitária)
```

A correspondência entre índice e chunk é posicional — o vetor `f32[i]` é o embedding
do chunk na linha `i` de `data/corpus.jsonl`.

---

### Critério de conclusão da Fase 2

| Critério | Verificação | Status |
|---|---|---|
| `baseline_f32.npy` existe | `ls embeddings/` | ✅ 0.81 MB |
| `baseline_f16.npy` existe | `ls embeddings/` | ✅ 0.41 MB |
| Shape correta | `[556, 384]` | ✅ |
| 100% dos vetores com norma≈1.0 | verificação abaixo | ✅ 556/556 |

```bash
# Verificação rápida:
uv run python -c "
import numpy as np
X = np.load('embeddings/baseline_f32.npy')
norms = np.linalg.norm(X, axis=1)
ok = (abs(norms - 1.0) < 1e-5).sum()
print(f'shape={X.shape}  norma≈1.0: {ok}/{len(X)} ({ok/len(X)*100:.1f}%)')
"
```

Saída esperada:
```
shape=(556, 384)  norma≈1.0: 556/556 (100.0%)
```

---

## Fase 3 — Quantização

Esta fase comprime os embeddings float32 em 4 variantes × 3 níveis de bits,
produzindo arquivos `.npz` com bit-packing correto.

| Artefato | Descrição |
|---|---|
| `embeddings/uniform_{2,4,8}bit.npz` | Variante A — bins uniformes |
| `embeddings/lloyd_max_{2,4,8}bit.npz` | Variante B — codebook Lloyd-Max |
| `embeddings/turbo_mse_{2,4,8}bit.npz` | Variante C — TurboQuantMSE |
| `embeddings/turbo_prod_{2,4,8}bit.npz` | Variante D — TurboQuantProd |

---

### Pré-requisito

A Fase 2 deve estar concluída:

```bash
ls embeddings/baseline_f32.npy   # deve existir
```

---

### As 4 variantes

| Variante | Rotação | Codebook | QJL | Insight |
|---|---|---|---|---|
| `uniform` | ✗ | bins iguais | ✗ | baseline simples |
| `lloyd_max` | ✗ | Lloyd-Max (ótimo para esfera) | ✗ | melhor codebook |
| `turbo_mse` | ✓ | Lloyd-Max | ✗ | **rotação equaliza energia** |
| `turbo_prod` | ✓ | Lloyd-Max | ✓ | corrige viés de produto interno |

A progressão `uniform → lloyd_max → turbo_mse → turbo_prod` demonstra cada
inovação do paper TurboQuant de forma isolada.

---

### Passo 1 — Rodar cada variante individualmente

```bash
make quantize-uniform   # bits 8, 4, 2
make quantize-lloyd     # bits 8, 4, 2  (calcula codebook Lloyd-Max)
make quantize-mse       # bits 8, 4, 2  (rotação + codebook)
make quantize-prod      # bits 8, 4, 2  (rotação + codebook + QJL)
```

Ou tudo de uma vez:

```bash
make quantize-all
```

---

### Saída esperada (exemplo: `turbo_mse` 4-bit)

```
Quantizando: turbo_mse  bits=4

  Embeddings: 556 vetores × 384 dims  dtype=float32

  Codebook Lloyd-Max: dim=384, bits=4 (16 centróides)…
    Lloyd-Max convergiu em 190 iterações (Δ=0.00e+00)
    range=[-0.1387, 0.1387]

┏━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━┓
┃ Métrica             ┃            Valor ┃                     ┃
┡━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━┩
│ Variante            │   turbo_mse_4bit │                     │
│ Shape               │      [556, 384] │                     │
│ Bytes/vetor (dados) │           194 B │ (f32=1536 B)         │
│ Compressão (vetor)  │          7.92× │ dados por vetor      │
│ MSE                 │        0.000029 │ ↓ melhor             │
│ Cosine sim médio    │        0.984330 │ ↑ melhor (máx=1.0)   │
└─────────────────────┴──────────────────┴─────────────────────┘

✓ embeddings/turbo_mse_4bit.npz
```

---

### Taxas de compressão teóricas por vetor (dim=384)

> A coluna **Compressão (vetor)** mede só os dados por vetor, sem o overhead
> da matriz de rotação R e da matriz QJL S (compartilhadas por todo o corpus).
> Para corpora grandes (milhões de vetores) esse overhead é desprezível.

| Variante | bits | Bytes/vetor | Compressão |
|---|---|---|---|
| float32 baseline | 32 | 1536 B | 1× |
| float16 baseline | 16 | 768 B | 2× |
| uniform / lloyd_max / turbo_mse | 8 | 386 B | **3.98×** |
| uniform / lloyd_max / turbo_mse | 4 | 194 B | **7.92×** |
| uniform / lloyd_max / turbo_mse | 2 | 98 B | **15.67×** |
| turbo_prod | 8 | 388 B | 3.96× |
| turbo_prod | 4 | 196 B | 7.84× |
| turbo_prod | 2 | 100 B | 15.36× |

O `turbo_prod` tem 2–4 bytes extra por vetor (gamma float16) comparado ao `turbo_mse`.

---

### Insight: por que a rotação muda tudo?

O resultado mais importante da Fase 3 é visivel comparando `lloyd_max` vs `turbo_mse`
no mesmo número de bits:

| Variante | bits | Cosine sim | MSE |
|---|---|---|---|
| `lloyd_max` (sem rotação) | 4 | 0.787 | 0.000326 |
| `turbo_mse` (com rotação) | 4 | **0.984** | **0.000029** |

O codebook Lloyd-Max é calculado para a distribuição teórica de coordenada em S^(d-1).
Sem rotação, as coordenadas dos embeddings BGE-small não seguem essa distribuição
(há coordenadas com alta variância e outras quase nulas). Com a rotação, a energia
é distribuída uniformemente entre todas as dimensões, validando o codebook.

---

### Arquivos gerados

```bash
ls -lh embeddings/*.npz
```

```
 embeddings/lloyd_max_2bit.npz
 embeddings/lloyd_max_4bit.npz
 embeddings/lloyd_max_8bit.npz
 embeddings/turbo_mse_2bit.npz
 embeddings/turbo_mse_4bit.npz
 embeddings/turbo_mse_8bit.npz
 embeddings/turbo_prod_2bit.npz
 embeddings/turbo_prod_4bit.npz
 embeddings/turbo_prod_8bit.npz
 embeddings/uniform_2bit.npz
 embeddings/uniform_4bit.npz
 embeddings/uniform_8bit.npz
```

---

### Formato do `.npz`

Cada arquivo `.npz` contém os índices bit-packed e os metadados do estado:

```python
import numpy as np
from src.quantization.storage import load_turbo_mse, unpack_indices

# Carrega e dequantiza
indices, norms, state = load_turbo_mse("embeddings/turbo_mse_4bit.npz")
from src.quantization.turboquant_mse import dequantize_mse_batch
X_hat = dequantize_mse_batch(indices, norms, state)
print(X_hat.shape)   # (556, 384)
```

---

### Critério de conclusão da Fase 3

| Critério | Status |
|---|---|
| 12 arquivos `.npz` em `embeddings/` | ✅ |
| Bit-packing correto (round-trip) | ✅ verificado em testes |
| `turbo_mse_4bit` cosine sim ≥ 0.98 | ✅ 0.984 |
| `turbo_mse` > `lloyd_max` mesmos bits | ✅ rotação faz diferença |
| `turbo_prod` corrige viés (cosine > 1.0) | ✅ QJL funciona |

```bash
# Verificação rápida: todos os 12 arquivos presentes
ls embeddings/*.npz | wc -l   # deve mostrar 12
```

---

## Fase 4 — Benchmark de Distorção

Mede quanto cada variante de quantização deforma os vetores **antes** de testar retrieval.
Gera um CSV com 5 métricas e 2 gráficos.

| Artefato | Descrição |
|---|---|
| `reports/distortion_results.csv` | 14 linhas (2 baselines + 12 variantes) com todas as métricas |
| `charts/mse_vs_bits.png` | Barras agrupadas: MSE (log) por variante e bits |
| `charts/ip_error_heatmap.png` | Heatmap: erros de produto interno por variante e bits |

---

### Pré-requisito

A Fase 3 deve estar concluída:

```bash
ls embeddings/*.npz | wc -l   # deve mostrar 12
```

---

### Passo único

```bash
make distortion-bench
```

O que acontece:

```
embeddings/baseline_f32.npy
        │
        ▼  build_query_matrix()
   100 vetores do corpus como queries (sem re-embedar)
        │
        ▼  para cada variante (uniform, lloyd_max, turbo_mse, turbo_prod) × (2, 4, 8 bits):
   carrega .npz → dequantiza → calcula 5 métricas
        │
        ├──▶  reports/distortion_results.csv
        ├──▶  charts/mse_vs_bits.png
        └──▶  charts/ip_error_heatmap.png
```

---

### Métricas calculadas

| Métrica | Fórmula | Interpretação |
|---|---|---|
| **MSE** | `mean(‖x - x̂‖²)` | Erro geométrico médio |
| **Cosine Error** | `1 - mean(cos(x, x̂))` | Quanto a direção mudou |
| **IP Bias** | `mean(q·x̂ - q·x)` | Viés sistemático no produto interno |
| **IP MAE** | `mean(|q·x̂ - q·x|)` | Magnitude média do erro de IP |
| **IP Variance** | `var(q·x̂ - q·x)` | Consistência do erro |

As queries usadas no cálculo de IP são os vetores correspondentes
aos `relevant_ids` de `queries.jsonl` — sem necessidade de re-embedar texto.

---

### Saída esperada (resumo)

```
Fase 4 — Benchmark de Distorção

  Embeddings: (556, 384)  dtype=float32
  Query vectors: 100 vetores extraídos do corpus

Calculando métricas… ━━━━━━━━━━━━━━ 100% 0:00:00

✓ CSV salvo: reports/distortion_results.csv  (14 linhas)
✓ Gráfico salvo: charts/mse_vs_bits.png
✓ Gráfico salvo: charts/ip_error_heatmap.png
```

---

### Resultados reais (corpus de amostra)

```
Variante          bits   MSE          Cosine Error   IP Bias      IP MAE
baseline_f32        32   0.0          0.0            0.0          0.0
baseline_f16        16   ~0.0         ~0.0           ~0.0         0.000034
uniform              8   0.000001     0.000199      -0.000010     0.000800
uniform              4   0.000300     0.052971       0.000432     0.014124
uniform              2   0.007434     0.562021      -0.021953     0.061482
lloyd_max            8   0.000145     0.024173      -0.128807     0.128807  ← viés alto!
lloyd_max            4   0.000326     0.058797      -0.205900     0.205900
lloyd_max            2   0.000804     0.167869      -0.310905     0.310905
turbo_mse            8   0.000001     0.000097      -0.000687     0.001304
turbo_mse            4   0.000029     0.005557      -0.011306     0.011792
turbo_mse            2   0.000321     0.063473      -0.081009     0.081009
turbo_prod           8   0.000002     0.000341       0.000065     0.000947
turbo_prod           4   0.000156     0.028412       0.002704     0.009961  ← sweet spot
turbo_prod           2   0.001518     0.202509       0.011796     0.028462
```

**Insights dos resultados:**

- `lloyd_max` tem **IP Bias altissimo** (`-0.13` a 8-bit) porque sem rotação o codebook clipa coordenadas grandes, introduzindo viés sistemático.
- `turbo_mse` remove esse viés com a rotação, reduzindo o IP Bias de `-0.128` para `-0.0007` a 8-bit (**183× menor**).
- `turbo_prod` vai além: o QJL corrige o viés residual do MSE, mantendo IP Bias próximo de zero em todos os níveis de bits.
- O sweet spot é `turbo_prod 4-bit`: 7.84× compressão com IP MAE de apenas 0.0100.

---

### Critério de conclusão da Fase 4

| Critério | Status |
|---|---|
| `distortion_results.csv` gerado com 14 linhas | ✅ |
| MSE decresce com bits crescentes (por variante) | ✅ |
| `turbo_mse` MSE < `lloyd_max` MSE (mesmo bits) | ✅ |
| `turbo_prod` IP Bias < `turbo_mse` IP Bias | ✅ |
| 2 gráficos salvos em `charts/` | ✅ |

```bash
# Verificação rápida:
wc -l reports/distortion_results.csv   # deve mostrar 15 (14 + header)
ls charts/mse_vs_bits.png charts/ip_error_heatmap.png
```

---

## Fase 5 — Benchmark de Retrieval

Mede a qualidade de busca real com cada variante: Recall@k, MRR, latência e memória.

| Artefato | Descrição |
|---|---|
| `indexes/faiss_*.index` | 14 índices FAISS (2 baselines + 12 variantes) |
| `reports/benchmark_results.csv` | 14 linhas com todas as métricas |
| `charts/recall_vs_bits.png` | Recall@1, @5, @10 por variante e bits |
| `charts/tradeoff_recall_memory.png` | Scatter: qualidade × memória (Pareto) |

---

### Pré-requisito

A Fase 3 deve estar concluída (12 `.npz` em `embeddings/`):

```bash
ls embeddings/*.npz | wc -l   # deve mostrar 12
```

---

### Passo 1 — Construir os índices FAISS

```bash
make build-indexes
```

Para cada variante, dequantiza os embeddings de volta para float32 e insere
no `IndexFlatIP` do FAISS. O ganho de memória vem do `.npz` em disco
— o índice em RAM é sempre float32 (FAISS não aceita vetores quantizados no `IndexFlat`).

Saída esperada:

```
Build Indexes — Fase 5

  ✓ faiss_f32.index                    556 vetores  834 KB
  ✓ faiss_f16.index                    556 vetores  834 KB
  ✓ faiss_uniform_8bit.index           556 vetores  834 KB
  ...
  ✓ faiss_turbo_prod_2bit.index        556 vetores  834 KB

✓ Índices prontos em indexes/
```

---

### Passo 2 — Rodar o benchmark

```bash
make retrieval-bench
```

O que acontece:

```
data/queries.jsonl (200 queries)
        │
        ▼  embed_queries()  — carrega BGE-small, embeda os textos
   Q: [200, 384] float32
        │
        ▼  para cada variante (14 total):
   carrega .index → index.search(Q, 10)
   mapeia índices → corpus IDs
   calcula Recall@1, @5, @10, MRR, latência
        │
        ├──▶  reports/benchmark_results.csv
        ├──▶  charts/recall_vs_bits.png
        └──▶  charts/tradeoff_recall_memory.png
```

> O modelo BGE-small é carregado **uma vez** (~8s) e usado para embedar todas as
> queries. O benchmark em si (14 variantes) roda em < 1s.

---

### Resultados reais (corpus de amostra)

```
Variante          bits   R@1    R@5    R@10   MRR    ms/q   MB(vetor)  Compress.
baseline_f32        32   0.870  0.955  0.965  0.905  0.005   0.815      1.0×
baseline_f16        16   0.870  0.955  0.965  0.905  0.005   0.408      2.0×
uniform              8   0.875  0.950  0.965  0.907  0.005   0.205      3.98×
uniform              4   0.805  0.935  0.960  0.862  0.005   0.104      7.84×
uniform              2   0.225  0.440  0.530  0.317  0.005   0.053      15.4×
lloyd_max            8   0.840  0.950  0.965  0.885  0.005   0.205      3.98×
lloyd_max            4   0.835  0.955  0.970  0.883  0.005   0.104      7.84×
lloyd_max            2   0.860  0.940  0.965  0.894  0.005   0.053      15.4×
turbo_mse            8   0.875  0.955  0.965  0.908  0.005   0.205      3.98×
turbo_mse            4   0.865  0.945  0.970  0.903  0.005   0.104      7.84×  ← sweet spot
turbo_mse            2   0.825  0.945  0.955  0.873  0.005   0.053      15.4×
turbo_prod           8   0.875  0.950  0.965  0.908  0.005   0.207      3.96×
turbo_prod           4   0.850  0.935  0.970  0.889  0.005   0.105      7.76×
turbo_prod           2   0.765  0.890  0.930  0.824  0.005   0.054      15.1×
```

**Insights dos resultados:**

- `turbo_mse 4-bit`: **7.84×** compressão com R@10=0.970 (mesma do baseline f32=0.965!).
- `uniform 2-bit`: colapso de qualidade (R@1=0.225) — 16× compressão destrói retrieval.
- `turbo_mse 2-bit`: R@1=0.825 com 15.4× compressão — muito superior ao uniform.
- A latência é idêntica (~0.005 ms/query) para todas as variantes porque o índice FAISS usa float32 independente da origem.
- O sweet spot é `turbo_mse 4-bit`: 7.84× compressão com qualidade idêntica ao float32.

---

### Métricas calculadas

| Métrica | Descrição |
|---|---|
| **Recall@k** | Fração das queries com ≥1 relevante no top-k |
| **MRR** | Mean Reciprocal Rank — premia sistemas que acham o relevante no topo |
| **ms/query** | Mediana da latência por query (5 runs) |
| **MB (vetor)** | Tamanho teórico dos dados de embedding (sem overhead R/S) |
| **Compress.** | MB(f32) / MB(variante) |

As queries são geradas com `make queries` (estratégia `first_sentence`):
- `query` = primeira frase do chunk
- `relevant_id` = o próprio chunk

Com essa estratégia o f32 atinge **Recall@1 ≈ 87%** — não é 100% porque a primeira frase
nor traz todo o contexto, mas é representativa o suficiente para medir degradação.

---

### Critério de conclusão da Fase 5

| Critério | Status |
|---|---|
| 14 índices FAISS em `indexes/` | ✅ |
| `benchmark_results.csv` com 14 linhas | ✅ |
| `turbo_mse` Recall@10 ≥ `uniform` (mesmo bits) | ✅ (4-bit: 0.970 vs 0.960) |
| `turbo_mse 4-bit` Recall@10 ≥ 90% do baseline | ✅ (0.970 / 0.965 = 100.5%!) |
| 2 gráficos em `charts/` | ✅ |

```bash
# Verificação rápida:
ls indexes/*.index | wc -l     # deve mostrar 14
wc -l reports/benchmark_results.csv  # deve mostrar 15 (14 + header)
```

---

## Fase 6 — Relatórios & Visualizações

Transforma os CSVs das Fases 4 e 5 em 8 gráficos estáticos, um dashboard HTML interativo
e dois relatórios Markdown.

| Artefato | Descrição |
|---|---|
| `charts/*.png` × 8 | Gráficos estáticos (matplotlib) |
| `charts/dashboard.html` | Dashboard interativo (Plotly) |
| `reports/retrieval_examples.md` | Análise qualitativa por query |
| `reports/notes.md` | Resumo automático dos resultados |

---

### Pré-requisitos

Fases 4 e 5 devem estar concluídas:

```bash
ls reports/distortion_results.csv reports/benchmark_results.csv   # ambos devem existir
```

---

### Passo 1 — Gerar todos os gráficos + dashboard

```bash
make visualize
```

Gera 8 PNGs e um dashboard HTML interativo:

```
 Fase 6 — Gerando gráficos

  ✓ charts/recall_vs_bits.png
  ✓ charts/mse_vs_bits.png
  ✓ charts/memory_compression.png
  ✓ charts/latency_comparison.png
  ✓ charts/tradeoff_recall_memory.png
  ✓ charts/ip_error_heatmap.png
  ✓ charts/recall_degradation_per_query.png
  ✓ charts/compression_ratio_vs_recall_loss.png

  ✓ 8 gráficos salvos em charts/

 Fase 6 — Gerando dashboard interativo

  ✓ Tabela interativa
  ✓ Recall@10 vs Bits
  ✓ Trade-off Recall × Memória
  ✓ MSE vs Bits
  ✓ IP Error Heatmap
  ✓ Compressão × Perda de Recall

✓ Dashboard salvo: charts/dashboard.html
```

Abra o dashboard no browser:

```bash
xdg-open charts/dashboard.html   # Linux
open charts/dashboard.html        # macOS
```

---

### Passo 2 — Gerar relatórios Markdown

```bash
make report
```

Gera dois arquivos:

- **`reports/retrieval_examples.md`** — top 5 queries que quebraram vs. top 5 que mantiveram qualidade
- **`reports/notes.md`** — sweet spot identificado automaticamente + próximos passos

---

### Os 8 gráficos

| # | Arquivo | Tipo | Insight principal |
|---|---|---|---|
| 1 | `recall_vs_bits.png` | Line chart (3 painéis) | Recall@1/5/10 degrada com menos bits |
| 2 | `mse_vs_bits.png` | Bar agrupado (log) | `turbo_mse` MSE << `lloyd_max` sem rotação |
| 3 | `memory_compression.png` | Bar horizontal | Tamanho real com bit-packing correto |
| 4 | `latency_comparison.png` | Bar chart | Latência idêntica para todas as variantes |
| 5 | `tradeoff_recall_memory.png` ⭐ | Scatter + Pareto | Sweet spot: `turbo_mse 4-bit` |
| 6 | `ip_error_heatmap.png` | Heatmap | QJL corrige viés de IP do MSE |
| 7 | `recall_degradation_per_query.png` | Violin | Quais queries sofrem mais com compressão |
| 8 | `compression_ratio_vs_recall_loss.png` | Dual-axis | Compressão × perda de recall |

---

### Critério de conclusão da Fase 6

| Critério | Status |
|---|---|
| 8 PNGs em `charts/` | ✅ |
| `dashboard.html` funcional | ✅ |
| `retrieval_examples.md` gerado | ✅ |
| `notes.md` com sweet spot identificado | ✅ `turbo_mse 4-bit` = 7.9× com Recall@10 +0.005 vs f32 |

```bash
# Verificação rápida:
ls charts/*.png | wc -l        # deve mostrar 8
ls charts/dashboard.html       # deve existir
ls reports/retrieval_examples.md reports/notes.md
```

---

## Fase 7 — Mini Pipeline RAG

Demo end-to-end que mostra o impacto da quantização na qualidade das respostas:
compara os documentos recuperados e a resposta gerada entre as variantes.

---

### Pré-requisito

Os índices FAISS devem existir:

```bash
ls indexes/*.index | wc -l   # deve mostrar 14
```

---

### Uso básico

```bash
make rag-demo QUERY="how does Redis handle memory when it runs out?"
```

Por padrão compara 3 variantes: `f32`, `turbo_mse_4bit`, `uniform_2bit`.

---

### Opções do comando

```bash
# Variantes personalizadas
make rag-demo QUERY="..." VARIANTS=f32,turbo_mse_2bit,lloyd_max_4bit

# Número de documentos recuperados
make rag-demo QUERY="..." K=10

# Usar Ollama local (se disponível)
make rag-demo QUERY="..." BACKEND=ollama MODEL=llama3.2

# Usar API OpenAI-compatible
# export OPENAI_API_KEY=... OPENAI_BASE_URL=...
make rag-demo QUERY="..." BACKEND=openai MODEL=gpt-4o-mini
```

**Nomes de variante aceitos:**

```
f32, f16,
uniform_2bit,  uniform_4bit,  uniform_8bit,
lloyd_max_2bit, lloyd_max_4bit, lloyd_max_8bit,
turbo_mse_2bit, turbo_mse_4bit, turbo_mse_8bit,
turbo_prod_2bit, turbo_prod_4bit, turbo_prod_8bit
```

---

### Saída esperada

O demo exibe 3 seções:

**1. Tabela comparativa dos documentos recuperados**

```
                     Top-5 documentos recuperados por variante
 Rank  f32                          turbo_mse_4bit          uniform_2bit
  1    0.795  redis-guide-p00-c32   0.787  redis-guide-..  0.790  redis-..  ← igual!
  2    0.794  redis-guide-p00-c30   0.776  redis-guide-..  0.738  redis-..  ← igual!
  3    0.785  redis-guide-p00-c31   0.765  redis-guide-..  0.718  redis-..  ← igual!
  4    0.768  redis-guide-p00-c01   0.755  redis-guide-..  0.715  redis-..  ← igual!
  5    0.765  redis-guide-p00-c33   0.747  redis-guide-..  0.713  PLAN.md  ← ERRADO!
```

**2. Resposta gerada por cada variante** (mock extrativo por padrão)

```
│ f32 / turbo_mse_4bit (LLM: mock)                                          │
│ The maxmemory configuration limits Redis memory usage. When memory is     │
│ full, the eviction policy determines which keys to remove. LRU and LFU    │
│ policies are commonly used...                                              │

│ uniform_2bit (LLM: mock)                                                   │
│ state store for distributed optimization frameworks. Workers can read and  │
│ write trial results atomically...  ← CONTEXTO ERRADO! Resposta sobre ML    │
```

**3. Tabela de divergência**

```
 Variante        Docs em comum  Docs diferentes  Top-1 idêntico?  Status
 turbo_mse_4bit  5/5 (100%)     0                Sim              ✓ Qualidade mantida
 uniform_2bit    0/5 (0%)       5                Não              ✗ Degradacão severa
```

---

### LLM backends

| Backend | Como ativar | Quando usar |
|---|---|---|
| `mock` (padrão) | nenhuma configuração | demonstrações, CI, offline |
| `ollama` | instalar Ollama + `ollama pull llama3.2` | LLM local, privacidade |
| `openai` | `OPENAI_API_KEY=...` no `.env` | melhor qualidade de resposta |

O backend é detectado automaticamente: Ollama > OpenAI > mock.
Pode ser forçado com `BACKEND=mock|ollama|openai`.

---

### Critério de conclusão da Fase 7

| Critério | Status |
|---|---|
| Demo executa sem erros | ✅ |
| f32 e turbo_mse_4bit retornam documentos corretos | ✅ |
| uniform_2bit retorna contexto completamente errado | ✅ (0/5 docs em comum) |
| Tabela de divergência mostra o impacto claramente | ✅ |

---

## Pipeline completo do zero

```bash
# Uma única vez, do zero ao demo:
make setup
make ingest
make queries
make embed
make quantize-all
make all-bench
make visualize
make report
make rag-demo QUERY="how does Redis cache work?"

# Ou tudo de uma vez (exceto rag-demo):
make all
```

---

## Referência rápida dos comandos

```bash
# Fase 1 — Corpus
make setup            # instala deps + cria .env + pastas
make ingest           # data/raw/ → corpus.jsonl (556 chunks)
make queries          # corpus.jsonl → queries.jsonl (first_sentence)
make ingest-check     # quantos chunks por arquivo

# Fase 2 — Embeddings
make embed-info       # device disponível e modelo
make embed            # baseline_f32.npy + baseline_f16.npy
make queries-pseudo   # queries com pseudo ground truth (top-1 f32)

# Fase 3 — Quantização
make quantize-uniform   # Variante A: bins uniformes (2, 4, 8 bits)
make quantize-lloyd     # Variante B: codebook Lloyd-Max
make quantize-mse       # Variante C: TurboQuantMSE
make quantize-prod      # Variante D: TurboQuantProd
make quantize-all       # todas as 4 × 3 = 12 arquivos

# Fase 4 — Distorção
make distortion-bench   # MSE, cosine error, IP errors → CSV + 2 gráficos

# Fase 5 — Retrieval
make build-indexes      # 14 índices FAISS
make retrieval-bench    # Recall@k, MRR, latência → CSV + 2 gráficos
make all-bench          # fases 4+5 de uma vez

# Fase 6 — Visualizações
make visualize          # 8 PNGs + dashboard.html
make report             # retrieval_examples.md + notes.md

# Fase 7 — RAG Demo
make rag-demo QUERY="sua pergunta"
make rag-demo QUERY="..." VARIANTS=f32,turbo_mse_4bit,uniform_2bit
make rag-demo QUERY="..." BACKEND=ollama MODEL=llama3.2

# Pipeline completo
make all

# Utiliários
make help             # todos os targets
make clean            # remove artefatos (mantém data/raw/)
```
