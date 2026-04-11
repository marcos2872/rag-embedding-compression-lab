## Relatório de QA — Qualidade de Software
**Data:** 2026-04-11
**Escopo:** repositório completo (`src/`)
**Analista:** Agente QA

---

### 1. Resumo da Funcionalidade

Pipeline de pesquisa modular em 7 fases para comparar métodos de compressão/quantização de embeddings em sistemas RAG:

- **Fase 1** (`ingest.py`, `chunking.py`): ingestão de PDF/TXT/MD → `corpus.jsonl`; geração de queries com estratégias `first_sentence` e `pseudo`
- **Fase 2** (`embed.py`): geração de embeddings float32/float16 com modelo local BAAI/bge-small-en-v1.5
- **Fase 3** (`quantization/`): 4 variantes de quantização (uniform, lloyd_max, turbo_mse, turbo_prod) × 3 níveis de bits (2, 4, 8)
- **Fase 4** (`benchmark/distortion.py`): métricas de distorção (MSE, cosine error, IP errors)
- **Fase 5** (`retrieval/`, `benchmark/retrieval_bench.py`): índices FAISS + Recall@k, MRR, latência
- **Fase 6** (`visualization/`): gráficos e dashboard HTML
- **Fase 7** (`rag/`): demo RAG comparativo com múltiplos backends LLM

---

### 2. Resultado dos Linters Automáticos

#### Ruff (Python)
```
All checks passed!
```
Nenhum problema encontrado.

#### Testes (pytest)
```
ERROR: file or directory not found: tests/
collected 0 items — no tests ran
```
**Sem testes automatizados.** Diretório `tests/` não existe.

---

### 3. Bugs e Inconsistências

#### Risco ALTO

- **[ALTO] `src/benchmark/retrieval_bench.py`:145–147 e `src/rag/pipeline.py`:168 — `splitlines()` sem filtro de linhas vazias**
  - Risco: qualquer linha em branco no arquivo `.jsonl` (ex: linha final do arquivo gerado por alguns editores) causa `json.JSONDecodeError: Expecting value: line 1 column 1 (char 0)`, abortando o benchmark ou o demo RAG com traceback não tratado.
  - Cenário de teste: criar um `corpus.jsonl` com uma linha vazia no final e executar `make retrieval-bench` ou `make rag-demo QUERY="..."`.
  - Confirmado via `python -c "import json; json.loads('')"` → `JSONDecodeError`.
  - Contraste: `src/ingest.py` usa corretamente `for line in f if line.strip()`. As 3 ocorrências problemáticas usam `.read_text().splitlines()` sem filtro.
  - Sugestão: substituir por `[json.loads(l) for l in Path(...).read_text(...).splitlines() if l.strip()]`

---

#### Risco MÉDIO

- **[MÉDIO] `src/quantization/storage.py`:104,143,178,227 — `np.load(..., allow_pickle=True)` desnecessário**
  - Risco: `allow_pickle=True` abre vetor de ataque se o arquivo `.npz` vier de fonte não-confiável (desserialização arbitrária de objetos Python via pickle). No contexto atual os arquivos são gerados localmente, então o risco prático é baixo, mas a flag não é necessária: o único campo que poderia exigir pickle é `variant = np.array("uniform")` (string escalar), e a NumPy aceita arrays de string sem pickle desde a versão 1.16+.
  - Cenário de teste: substituir `allow_pickle=False` e verificar que `data["variant"]` ainda é lido corretamente (esperado: sim).
  - Sugestão: remover `allow_pickle=True` de todos os `np.load` em `storage.py`.

- **[MÉDIO] `src/benchmark/retrieval_bench.py`:69 e `src/rag/pipeline.py`:170 — arquivo YAML aberto sem `with`**
  - Risco: `yaml.safe_load(open("configs/embedding.yaml"))` não fecha o file descriptor explicitamente. Em execuções longas ou com muitas chamadas (ex: múltiplas variantes no demo), pode esgotar descritores de arquivo em sistemas com limite baixo (ulimit -n). Além disso, se `configs/embedding.yaml` não existir, o `FileNotFoundError` propaga-se não tratado, abortando silenciosamente a fase.
  - Cenário de teste: remover `configs/embedding.yaml` e executar `make retrieval-bench`.
  - Sugestão:
    ```python
    with open("configs/embedding.yaml") as f:
        cfg = yaml.safe_load(f) or {}
    ```
    (padrão já usado corretamente em `src/main.py:46` e `src/embed.py`)

- **[MÉDIO] `src/quantization/__init__.py`:121,142 — `os.getenv("RANDOM_SEED", 42)` com default inteiro**
  - Risco: `os.getenv()` retorna `str | None`; passar `42` (int) como default faz `os.getenv` retornar `int` quando a variável não está definida. `int(42)` funciona, mas é semanticamente inconsistente com o contrato da API (`os.getenv` deve retornar `str | None`). Além disso, linters de tipo (`mypy`) reportarão isso como erro pois `int(os.getenv(..., 42))` tem tipo `int(int | str)` — ambíguo.
  - Também ocorre em `src/benchmark/distortion.py:230`.
  - Sugestão: `int(os.getenv("RANDOM_SEED", "42"))` (default como string).

- **[MÉDIO] `src/rag/pipeline.py`:219 — `time.sleep(1.5)` hardcoded entre chamadas LLM**
  - Risco: para o backend `mock` (sem rate-limit), a espera de 1,5 s por variante é completamente desnecessária e degrada a experiência do usuário. Para 5 variantes, adiciona 6 s ao demo sem motivo.
  - Sugestão: aplicar o sleep apenas quando `backend in ("ollama", "openai")`, verificável antes da chamada ou depois de detectar o backend.

---

#### Risco BAIXO

- **[BAIXO] Múltiplos arquivos excedem o limite de 300 linhas declarado no AGENTS.md**
  - Arquivos acima do limite:
    - `src/visualization/_dashboard_html.py`: 983 linhas
    - `src/visualization/_dashboard_figs.py`: 518 linhas
    - `src/visualization/plots.py`: 491 linhas
    - `src/benchmark/distortion.py`: 393 linhas
    - `src/benchmark/retrieval_bench.py`: 389 linhas
    - `src/rag/pipeline.py`: 350 linhas
    - `src/embed.py`: 348 linhas
    - `src/ingest.py`: 311 linhas
  - Risco: manutenção dificultada; violação explícita das convenções declaradas.
  - Sugestão: extrair helpers de visualização em sub-módulos separados (ex: `plots_distortion.py`, `plots_retrieval.py`).

- **[BAIXO] Múltiplas funções excedem 40 linhas (limite do AGENTS.md)**
  - Exemplos mais críticos:
    - `lloyd_max_codebook` (71 linhas) — `src/quantization/lloyd_max.py:77`
    - `detect_device` (70 linhas) — `src/embed.py:55`
    - `embed_corpus` (63 linhas) — `src/embed.py:165`
    - `_build_markdown_lines` (60 linhas) — `src/benchmark/reports.py:115`
    - `_compression_fig` (84 linhas) — `src/visualization/_dashboard_figs.py:293`
    - `_tradeoff_fig` (81 linhas) — `src/visualization/_dashboard_figs.py:133`
  - Sugestão: extrair sub-funções auxiliares para cada bloco lógico distinto.

- **[BAIXO] `src/rag/prompting.py`:191,199 — `except Exception as e` sem log formal**
  - As exceções de Ollama e OpenAI são capturadas e injetadas na string de resposta como texto de usuário (`[⚠ Ollama falhou: {e} → usando mock]`). Isso expõe detalhes internos de erro (stack/URL/chaves parciais) diretamente no output do usuário final.
  - Sugestão: logar via `console.print` (já disponível no módulo) e exibir ao usuário apenas uma mensagem sanitizada.

- **[BAIXO] `src/ingest.py`:100 — formato de ID `chunk_idx:02d` não escalonável**
  - `_make_id` usa `f"{chunk_idx:02d}"`, que produz `c00`–`c99` com dois dígitos. Para documentos muito longos (>100 chunks), o formato passa a ter 3 dígitos (`c100`, `c101`...). Não causa colisão (confirmado em teste), mas a inconsistência de formatação torna ordenação lexicográfica dos IDs incorreta para chunks ≥ 100.
  - Sugestão: usar `f"{chunk_idx:04d}"` para garantir ordenação correta até 9999 chunks.

- **[BAIXO] `src/benchmark/retrieval_bench.py`:145–148 — leitura dupla do corpus em memória**
  - `_load_retrieval_inputs` faz `.read_text()` completo do `corpus.jsonl` para uma list comprehension. Para corpora grandes (>100 MB), isso carrega tudo na RAM de uma vez.
  - Sugestão: usar leitura linha a linha (como em `src/ingest.py:load_corpus`).

---

### 4. Vulnerabilidades de Segurança

- **[BAIXO] `src/quantization/storage.py` — `allow_pickle=True` em `np.load`**
  - Conforme descrito em Bugs/MÉDIO: se um arquivo `.npz` externo/malicioso for colocado em `embeddings/`, a desserialização pode executar código arbitrário.
  - Mitigação atual: arquivos são gerados localmente pelo próprio pipeline. Sem exposição a inputs externos.
  - Sugestão: remover `allow_pickle=True`.

- **[BAIXO] `src/rag/prompting.py`:191,199 — vazamento de detalhes de erro de API**
  - Mensagens de exceção de `_call_ollama` e `_call_openai` são expostas ao usuário via string de resposta. Dependendo da exceção, podem incluir URLs internas, nomes de modelo ou fragmentos de configuração.
  - Sugestão: logar a exceção internamente e exibir mensagem genérica ao usuário.

---

### 5. Cobertura de Testes

**Sem testes automatizados.** O diretório `tests/` não existe e `pytest` não encontrou nenhum teste.

Áreas críticas sem cobertura:

| Módulo | Funcionalidade sem teste | Risco |
|---|---|---|
| `src/chunking.py` | `sliding_window` com texto vazio, chunk_size=0, overlap≥chunk_size | MÉDIO |
| `src/quantization/scalar_uniform.py` | `quantize_uniform` / `dequantize_uniform` round-trip | ALTO |
| `src/quantization/storage.py` | pack/unpack round-trip para 2, 4, 8 bits | ALTO |
| `src/quantization/lloyd_max.py` | convergência do codebook, `quantize_lloyd` limites de índice | ALTO |
| `src/ingest.py` | `_make_id` colisões, `queries_first_sentence` com corpus vazio | MÉDIO |
| `src/retrieval/metrics.py` | `recall_at_k` com retrieved vazio, `mrr` com 0 relevantes | MÉDIO |
| `src/embed.py` | `normalize_rows` com vetores nulos | BAIXO |

**Sugestão de setup de testes:**
```bash
uv add --dev pytest pytest-cov
mkdir tests
touch tests/__init__.py
```

---

### 6. Resumo Executivo

| Categoria | Contagem |
|---|---|
| Bugs ALTO | 1 |
| Bugs MÉDIO | 3 |
| Bugs BAIXO | 5 |
| Vulnerabilidades | 2 (BAIXO) |
| Arquivos acima do limite de linhas | 8 |
| Funções acima do limite de linhas | ~25 |
| Cobertura de testes | 0% |

**Pontos positivos:**
- Código bem documentado (docstrings em PT-BR, comentários matemáticos detalhados)
- Ruff passa limpo: sem erros de lint
- Uso correto de `np.random.default_rng(seed)` (API moderna)
- Sem `Optional[X]` nem `List[X]` do `typing` — usa `X | None` e `list[X]` corretamente
- Tratamento de erros presente nos pontos críticos (leitura de arquivo, GPU, APIs externas)
- Sem credenciais ou segredos hardcoded no código

**Principal ação recomendada:** corrigir o bug de `splitlines()` sem filtro (risco ALTO) e criar uma suíte de testes mínima para as funções de quantização (pack/unpack round-trip).
