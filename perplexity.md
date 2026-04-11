Posso — aqui vai um plano **prático e enxuto** para seu projeto de **RAG com compressão de embeddings**, pensado para ir de benchmark local até um mini-RAG funcional. Como o paper mostra TurboQuant forte em nearest neighbor search, com foco em recall@k e tempo de indexação, esse recorte faz bastante sentido para estudar primeiro. [ppl-ai-file-upload.s3.amazonaws](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/133115618/ee7b7153-3df5-4aa9-9713-75413833e0df/2504.19874v1.pdf)

Como você curte stack mais open source e mão na massa, vou propor algo em **Python + FAISS**, com opção de evoluir depois para Qdrant e serviço HTTP se quiser integrar ao seu ecossistema maior. [ppl-ai-file-upload.s3.amazonaws](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/133115618/ee7b7153-3df5-4aa9-9713-75413833e0df/2504.19874v1.pdf)

## Objetivo

Você vai construir um laboratório chamado **rag-embedding-compression-lab** para responder uma pergunta central: **quanto de memória dá para economizar nos embeddings sem estragar o retrieval?** Essa pergunta está alinhada com o uso de quantização vetorial em RAG e bancos vetoriais descrito no paper. [ppl-ai-file-upload.s3.amazonaws](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/133115618/ee7b7153-3df5-4aa9-9713-75413833e0df/2504.19874v1.pdf)

O MVP não precisa gerar resposta com LLM no começo; primeiro você mede qualidade de recuperação, porque recall top-k é a base do problema que o artigo avalia em nearest neighbor search. [ppl-ai-file-upload.s3.amazonaws](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/133115618/ee7b7153-3df5-4aa9-9713-75413833e0df/2504.19874v1.pdf)

## Arquitetura

A estrutura abaixo separa ingestão, embeddings, quantização e benchmark, o que facilita repetir experimentos e trocar componentes depois. [ppl-ai-file-upload.s3.amazonaws](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/133115618/ee7b7153-3df5-4aa9-9713-75413833e0df/2504.19874v1.pdf)

```text
rag-embedding-compression-lab/
├─ README.md
├─ pyproject.toml
├─ .env.example
├─ configs/
│  ├─ dataset.yaml
│  ├─ embedding.yaml
│  └─ benchmark.yaml
├─ data/
│  ├─ raw/
│  ├─ processed/
│  ├─ corpus.jsonl
│  └─ queries.jsonl
├─ embeddings/
│  ├─ baseline_f32.npy
│  ├─ baseline_f16.npy
│  ├─ quantized_2bit.npz
│  ├─ quantized_4bit.npz
│  └─ quantized_8bit.npz
├─ indexes/
│  ├─ faiss_f32.index
│  ├─ faiss_f16.index
│  └─ faiss_quantized/
├─ src/
│  ├─ main.py
│  ├─ ingest.py
│  ├─ chunking.py
│  ├─ embed.py
│  ├─ quantization/
│  │  ├─ __init__.py
│  │  ├─ random_rotation.py
│  │  ├─ scalar_quantizer.py
│  │  ├─ turboquant_like.py
│  │  └─ storage.py
│  ├─ retrieval/
│  │  ├─ faiss_store.py
│  │  ├─ search.py
│  │  └─ metrics.py
│  ├─ benchmark/
│  │  ├─ run_benchmark.py
│  │  ├─ memory.py
│  │  └─ reports.py
│  └─ rag/
│     ├─ pipeline.py
│     └─ prompting.py
├─ reports/
│  ├─ benchmark_results.csv
│  ├─ retrieval_examples.md
│  └─ notes.md
└─ notebooks/
   └─ exploration.ipynb
```

## Escopo do MVP

A primeira versão deve comparar três bases:
- **float32** como baseline de referência;
- **float16** como baseline barato e realista;
- **quantizada** com sua implementação inspirada em TurboQuant, começando por 2, 4 e 8 bits por coordenada. [ppl-ai-file-upload.s3.amazonaws](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/133115618/ee7b7153-3df5-4aa9-9713-75413833e0df/2504.19874v1.pdf)

No paper, TurboQuant usa rotação aleatória e quantização escalar por coordenada no caso MSE, e isso já é suficiente para você montar um protótipo didático antes de tentar reproduzir tudo fielmente. [ppl-ai-file-upload.s3.amazonaws](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/133115618/ee7b7153-3df5-4aa9-9713-75413833e0df/2504.19874v1.pdf)

## Roadmap de 7 dias

### Dia 1
Monte corpus e queries. Pode ser docs técnicas, FAQs, notas, ou um conjunto pequeno de textos do domínio que você conhece bem.

Crie dois arquivos:
- `corpus.jsonl`: `id`, `text`, `metadata`
- `queries.jsonl`: `query`, `relevant_ids`

Se você não tiver ground truth no início, pode usar o top-k do float32 como pseudo-referência para começar, mas idealmente depois você substitui por pares query-documento validados. [ppl-ai-file-upload.s3.amazonaws](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/133115618/ee7b7153-3df5-4aa9-9713-75413833e0df/2504.19874v1.pdf)

### Dia 2
Gere embeddings locais e normalize tudo. O paper assume vetores em esfera unitária como caso padrão, então normalizar os embeddings ajuda a aproximar esse cenário e a comparar produto interno com cosseno de forma consistente. [ppl-ai-file-upload.s3.amazonaws](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/133115618/ee7b7153-3df5-4aa9-9713-75413833e0df/2504.19874v1.pdf)

Sugestão prática:
- BGE small/base
- E5 small/base
- Nomic embedding local

### Dia 3
Implemente a quantização básica:
- gerar matriz de rotação aleatória;
- aplicar rotação;
- quantizar cada coordenada;
- salvar índices/níveis;
- dequantizar e desfazer rotação. [ppl-ai-file-upload.s3.amazonaws](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/133115618/ee7b7153-3df5-4aa9-9713-75413833e0df/2504.19874v1.pdf)

Essa parte é o coração do estudo, porque reproduz a intuição central do TurboQuant MSE: a rotação torna as coordenadas mais bem comportadas para quantização escalar independente. [ppl-ai-file-upload.s3.amazonaws](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/133115618/ee7b7153-3df5-4aa9-9713-75413833e0df/2504.19874v1.pdf)

### Dia 4
Construa o benchmark de distorção:
- MSE entre vetor original e reconstruído;
- erro de similaridade cosseno;
- erro de produto interno entre query e documento. [ppl-ai-file-upload.s3.amazonaws](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/133115618/ee7b7153-3df5-4aa9-9713-75413833e0df/2504.19874v1.pdf)

O paper separa MSE de erro de produto interno justamente porque otimizar só reconstrução pode introduzir viés na estimativa de inner product em bit-width baixo. [ppl-ai-file-upload.s3.amazonaws](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/133115618/ee7b7153-3df5-4aa9-9713-75413833e0df/2504.19874v1.pdf)

### Dia 5
Monte os índices e rode retrieval top-k:
- índice baseline f32;
- índice f16;
- índice com vetores dequantizados da versão quantizada. [ppl-ai-file-upload.s3.amazonaws](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/133115618/ee7b7153-3df5-4aa9-9713-75413833e0df/2504.19874v1.pdf)

Aqui você mede:
- Recall@1
- Recall@5
- Recall@10
- MRR
- latência média por query
- memória total do índice. [ppl-ai-file-upload.s3.amazonaws](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/133115618/ee7b7153-3df5-4aa9-9713-75413833e0df/2504.19874v1.pdf)

### Dia 6
Crie relatórios:
- tabela por bit-width;
- exemplos de queries que pioraram;
- casos em que 4-bit ficou quase igual ao baseline;
- custo por 1.000 e por 1.000.000 vetores em memória estimada. [ppl-ai-file-upload.s3.amazonaws](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/133115618/ee7b7153-3df5-4aa9-9713-75413833e0df/2504.19874v1.pdf)

### Dia 7
Adicione um mini pipeline de RAG:
- busca top-k;
- concatenação dos chunks;
- resposta via LLM local ou mock simples;
- comparação qualitativa entre contexto baseline e contexto quantizado. [ppl-ai-file-upload.s3.amazonaws](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/133115618/ee7b7153-3df5-4aa9-9713-75413833e0df/2504.19874v1.pdf)

## Métricas principais

A tabela abaixo é suficiente para a V1 do projeto:

| Métrica | O que mede | Por que importa |
|---|---|---|
| Recall@k | Se o documento relevante aparece no top-k | Métrica principal de retrieval aproximado. [ppl-ai-file-upload.s3.amazonaws](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/133115618/ee7b7153-3df5-4aa9-9713-75413833e0df/2504.19874v1.pdf) |
| MRR | Posição do primeiro resultado relevante | Mostra se o ranking piorou. [ppl-ai-file-upload.s3.amazonaws](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/133115618/ee7b7153-3df5-4aa9-9713-75413833e0df/2504.19874v1.pdf) |
| MSE | Erro entre vetor original e reconstruído | Avalia perda geométrica básica. [ppl-ai-file-upload.s3.amazonaws](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/133115618/ee7b7153-3df5-4aa9-9713-75413833e0df/2504.19874v1.pdf) |
| Erro de inner product | Diferença na similaridade estimada | Importante porque busca vetorial depende disso. [ppl-ai-file-upload.s3.amazonaws](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/133115618/ee7b7153-3df5-4aa9-9713-75413833e0df/2504.19874v1.pdf) |
| Memória | Tamanho do índice/embeddings | Mostra o ganho prático. [ppl-ai-file-upload.s3.amazonaws](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/133115618/ee7b7153-3df5-4aa9-9713-75413833e0df/2504.19874v1.pdf) |
| Tempo de indexação | Tempo para construir a base | O paper destaca tempo de indexação quase zero no método proposto. [ppl-ai-file-upload.s3.amazonaws](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/133115618/ee7b7153-3df5-4aa9-9713-75413833e0df/2504.19874v1.pdf) |
| Latência de consulta | Tempo de top-k | Mede impacto operacional no RAG. [ppl-ai-file-upload.s3.amazonaws](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/133115618/ee7b7153-3df5-4aa9-9713-75413833e0df/2504.19874v1.pdf) |

## Estratégia de implementação

Para não travar, implemente em três etapas.

### V1
**Quantização uniforme simples por coordenada**, sem tentar ser perfeita teoricamente. Isso já te dá um baseline funcional.

Fluxo:
- normalize;
- rotate;
- clip opcional por faixa;
- uniform quantization;
- store integer bins;
- dequantize;
- inverse rotate.

### V2
Troque quantização uniforme por **codebook escalar por dimensão compartilhada**, inspirado no Lloyd-Max citado no paper. [ppl-ai-file-upload.s3.amazonaws](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/133115618/ee7b7153-3df5-4aa9-9713-75413833e0df/2504.19874v1.pdf)

### V3
Se quiser se aproximar mais da parte “inner product”, adicione uma versão residual inspirada no estágio extra descrito para reduzir viés em produto interno. [ppl-ai-file-upload.s3.amazonaws](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/133115618/ee7b7153-3df5-4aa9-9713-75413833e0df/2504.19874v1.pdf)

## Pseudocódigo do núcleo

Aqui está o núcleo conceitual do quantizador:

```python
def fit_rotation(dim, seed=42):
    rng = np.random.default_rng(seed)
    A = rng.normal(size=(dim, dim))
    Q, _ = np.linalg.qr(A)
    return Q

def quantize(X, R, bits=4):
    Xn = normalize_rows(X)
    Y = Xn @ R
    qmin, qmax = Y.min(), Y.max()
    levels = 2 ** bits - 1
    scale = (qmax - qmin) / max(levels, 1)
    Q = np.round((Y - qmin) / scale).astype(np.uint8)
    return {"Q": Q, "qmin": qmin, "scale": scale, "R": R}

def dequantize(pkg):
    Y_hat = pkg["Q"].astype(np.float32) * pkg["scale"] + pkg["qmin"]
    X_hat = Y_hat @ pkg["R"].T
    return normalize_rows(X_hat)
```

Isso não é o TurboQuant completo, mas já segue a direção de **rotação + quantização escalar + reconstrução**, que é exatamente o bloco conceitual que você quer estudar agora. [ppl-ai-file-upload.s3.amazonaws](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/133115618/ee7b7153-3df5-4aa9-9713-75413833e0df/2504.19874v1.pdf)

## CLI sugerida

Como você parece curtir fluxo de engenharia mais scriptável, eu faria uma CLI simples.

Exemplos:
```bash
python -m src.main ingest --input data/raw/docs/
python -m src.main embed --model BAAI/bge-small-en-v1.5
python -m src.main quantize --bits 2
python -m src.main quantize --bits 4
python -m src.main quantize --bits 8
python -m src.main benchmark --topk 10
python -m src.main rag-demo --query "como funciona o cache redis?"
```

## Formato dos dados

### `corpus.jsonl`
```json
{"id":"doc-001","text":"Redis is an in-memory data store...","metadata":{"source":"docs","topic":"redis"}}
{"id":"doc-002","text":"NestJS provides a modular architecture...","metadata":{"source":"docs","topic":"nestjs"}}
```

### `queries.jsonl`
```json
{"query":"what is redis used for?","relevant_ids":["doc-001"]}
{"query":"how does dependency injection work in nestjs?","relevant_ids":["doc-002"]}
```

Se quiser manter tudo em português, melhor ainda para testar um cenário mais próximo do que você pode usar depois em docs internas.

## Dependências

Uma base boa para começar:

```toml
[project]
name = "rag-embedding-compression-lab"
version = "0.1.0"

dependencies = [
  "numpy",
  "pandas",
  "faiss-cpu",
  "sentence-transformers",
  "scikit-learn",
  "typer",
  "rich",
  "pyyaml"
]
```

Se quiser mais próximo de produção depois:
- `qdrant-client`
- `fastapi`
- `uvicorn`

## Critério de sucesso

Para a V1, eu usaria estes critérios:
- 4-bit mantém Recall@10 próximo do float32;
- ganho de memória claramente mensurável;
- latência de consulta não piora de forma absurda;
- você consegue apontar queries que quebram e entender por quê. [ppl-ai-file-upload.s3.amazonaws](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/133115618/ee7b7153-3df5-4aa9-9713-75413833e0df/2504.19874v1.pdf)

O paper mostra que a proposta foi forte justamente em recall top-k em bases altas dimensões, então seu laboratório precisa priorizar **preservação do ranking**, não só compressão por si só. [ppl-ai-file-upload.s3.amazonaws](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/133115618/ee7b7153-3df5-4aa9-9713-75413833e0df/2504.19874v1.pdf)

## Ordem recomendada

Minha recomendação prática é:
1. Faça **float32 vs float16** primeiro.
2. Depois implemente **quantização 8-bit**.
3. Depois **4-bit**.
4. Só então teste **2-bit**. [ppl-ai-file-upload.s3.amazonaws](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/133115618/ee7b7153-3df5-4aa9-9713-75413833e0df/2504.19874v1.pdf)

Isso evita que você comece num regime muito agressivo, onde tudo quebra e você perde visibilidade do comportamento.

## Próximo passo

Se você quiser, no próximo envio eu posso te entregar o **esqueleto inicial do projeto em Python**, já com:
- `pyproject.toml`
- estrutura de `src/`
- loader de corpus
- geração de embeddings
- quantizador inicial
- benchmark de Recall@k

Aí você literalmente já começa colando os arquivos no repositório. [ppl-ai-file-upload.s3.amazonaws](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/133115618/ee7b7153-3df5-4aa9-9713-75413833e0df/2504.19874v1.pdf)


Sim — e dá para escrever um **pseudocódigo bem mais fiel ao TurboQuant do paper**, separado em duas versões: **TurboQuantMSE** e **TurboQuantProd**. O paper define exatamente essa estrutura: uma versão otimizada para MSE com **rotação aleatória + quantização escalar por coordenada usando codebook Lloyd-Max para a distribuição Beta induzida pela rotação**, e uma versão para produto interno com **TurboQuantMSE de \(b-1\) bits + QJL de 1 bit no resíduo** para remover viés. [ppl-ai-file-upload.s3.amazonaws](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/133115618/ee7b7153-3df5-4aa9-9713-75413833e0df/2504.19874v1.pdf)

O seu código está no caminho certo conceitualmente, mas ainda simplifica pontos centrais: no TurboQuant completo não se usa min/max do lote para escalar uniformemente; em vez disso, usa-se **um codebook pré-computado por bit-width e dimensão/distribuição** e, para inner product, existe uma **segunda etapa no resíduo com QJL**. [ppl-ai-file-upload.s3.amazonaws](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/133115618/ee7b7153-3df5-4aa9-9713-75413833e0df/2504.19874v1.pdf)

## Núcleo real

A estrutura do paper é esta:

| Variante | Ideia central | Saída |
|---|---|---|
| TurboQuantMSE | Rotaciona \(x\), quantiza cada coordenada pelo centróide mais próximo de um codebook escalar ótimo | Índices dos centróides por coordenada. [ppl-ai-file-upload.s3.amazonaws](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/133115618/ee7b7153-3df5-4aa9-9713-75413833e0df/2504.19874v1.pdf) |
| TurboQuantProd | Usa TurboQuantMSE com \(b-1\) bits, calcula resíduo, aplica QJL de 1 bit no resíduo | Índices MSE + sinais QJL + norma do resíduo. [ppl-ai-file-upload.s3.amazonaws](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/133115618/ee7b7153-3df5-4aa9-9713-75413833e0df/2504.19874v1.pdf) |

O paper descreve o MSE quantizer no Algoritmo 1 e o inner-product quantizer no Algoritmo 2 exatamente dessa forma. [ppl-ai-file-upload.s3.amazonaws](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/133115618/ee7b7153-3df5-4aa9-9713-75413833e0df/2504.19874v1.pdf)

## Diferença do seu código

No seu pseudocódigo atual, você faz:
- normalização por linha,
- rotação,
- quantização escalar uniforme com `qmin/qmax`,
- reconstrução via `R.T`. [ppl-ai-file-upload.s3.amazonaws](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/133115618/ee7b7153-3df5-4aa9-9713-75413833e0df/2504.19874v1.pdf)

Isso captura a ideia geral, mas o TurboQuant completo troca a parte de `qmin/qmax + scale` por:
- **codebook escalar ótimo** \(c_1,\dots,c_{2^b}\),
- **atribuição ao centróide mais próximo** por coordenada,
- e, para produto interno, **QJL no resíduo**. [ppl-ai-file-upload.s3.amazonaws](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/133115618/ee7b7153-3df5-4aa9-9713-75413833e0df/2504.19874v1.pdf)

## Pseudocódigo MSE

Abaixo está uma versão fiel ao algoritmo conceitual do paper, mas escrita em estilo implementável.

```python
# ------------------------------------------------------------
# TURBOQUANT MSE
# ------------------------------------------------------------

def fit_rotation(dim, seed=42):
    rng = np.random.default_rng(seed)
    A = rng.normal(size=(dim, dim))
    Q, _ = np.linalg.qr(A)
    return Q.astype(np.float32)


def beta_pdf_for_rotated_coordinate(x, dim):
    # f(x) = Gamma(d/2) / (sqrt(pi) * Gamma((d-1)/2)) * (1 - x^2)^((d-3)/2), x in [-1, 1]
    # usar scipy.special.gamma numa implementação real
    pass


def lloyd_max_scalar_codebook(dim, bits, num_grid=200000, num_iters=200):
    """
    Resolve o problema contínuo 1D de k-means descrito na Eq. (4):
    encontrar 2^bits centróides ótimos para a distribuição da coordenada
    após rotação aleatória.
    """
    K = 2 ** bits

    # grade 1D no intervalo permitido
    xs = np.linspace(-1.0, 1.0, num_grid, dtype=np.float64)
    pdf = beta_pdf_for_rotated_coordinate(xs, dim)
    pdf = pdf / pdf.sum()

    # inicialização simples: quantis simétricos
    centroids = initialize_centroids_from_quantiles(xs, pdf, K)

    for _ in range(num_iters):
        # fronteiras de Voronoi = pontos médios entre centróides consecutivos
        boundaries = np.empty(K + 1, dtype=np.float64)
        boundaries[0] = -1.0
        boundaries[-1] = 1.0
        for i in range(1, K):
            boundaries[i] = 0.5 * (centroids[i - 1] + centroids[i])

        new_centroids = np.copy(centroids)

        # atualiza cada centróide pela média condicional ponderada no bucket
        for k in range(K):
            mask = (xs >= boundaries[k]) & (xs < boundaries[k + 1] if k < K - 1 else xs <= boundaries[k + 1])
            w = pdf[mask]
            z = xs[mask]

            if w.sum() > 0:
                new_centroids[k] = (w * z).sum() / w.sum()

        if np.allclose(new_centroids, centroids, atol=1e-8):
            break

        centroids = new_centroids

    return np.sort(centroids.astype(np.float32))


def build_turboquant_mse(dim, bits, seed=42):
    R = fit_rotation(dim, seed=seed)
    codebook = lloyd_max_scalar_codebook(dim, bits)
    return {
        "dim": dim,
        "bits": bits,
        "R": R,
        "codebook": codebook,
    }


def quantize_mse(x, state):
    """
    x: vetor 1D de dimensão d
    pressuposto teórico do paper: x na esfera unitária
    """
    R = state["R"]
    codebook = state["codebook"]

    norm = np.linalg.norm(x)
    if norm == 0:
        raise ValueError("zero vector não é suportado")
    x_unit = x / norm

    y = R @ x_unit

    # índice do centróide mais próximo para cada coordenada
    # saída: d inteiros de b bits
    idx = np.argmin(np.abs(y[:, None] - codebook[None, :]), axis=1).astype(np.uint16)

    return {
        "idx": idx,
        "norm": np.float32(norm),
    }


def dequantize_mse(pkg, state):
    R = state["R"]
    codebook = state["codebook"]

    idx = pkg["idx"]
    norm = pkg["norm"]

    y_hat = codebook[idx]
    x_hat_unit = R.T @ y_hat

    # o paper observa que, se os vetores não forem unitários,
    # pode-se armazenar a norma e reescalar na reconstrução
    x_hat = x_hat_unit * norm
    return x_hat.astype(np.float32)
```

Esse pseudocódigo segue o Algoritmo 1: gerar rotação aleatória, construir codebook ótimo para a coordenada rotacionada, quantizar cada coordenada ao centróide mais próximo e depois rotacionar de volta com \(\Pi^\top\). [ppl-ai-file-upload.s3.amazonaws](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/133115618/ee7b7153-3df5-4aa9-9713-75413833e0df/2504.19874v1.pdf)

## Pseudocódigo Prod

Agora a versão fiel ao **TurboQuantProd**, que o paper define como **TurboQuantMSE com \(b-1\) bits + QJL no resíduo**. [ppl-ai-file-upload.s3.amazonaws](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/133115618/ee7b7153-3df5-4aa9-9713-75413833e0df/2504.19874v1.pdf)

```python
# ------------------------------------------------------------
# QJL
# ------------------------------------------------------------

def build_qjl(dim, seed=123):
    rng = np.random.default_rng(seed)
    S = rng.normal(size=(dim, dim)).astype(np.float32)
    return {"S": S, "dim": dim}


def qjl_quantize(r, qjl_state):
    S = qjl_state["S"]
    proj = S @ r
    signs = np.where(proj >= 0, 1, -1).astype(np.int8)
    gamma = np.float32(np.linalg.norm(r))
    return {
        "signs": signs,
        "gamma": gamma,
    }


def qjl_dequantize(pkg, qjl_state):
    S = qjl_state["S"]
    d = qjl_state["dim"]

    signs = pkg["signs"].astype(np.float32)
    gamma = pkg["gamma"]

    r_hat = np.sqrt(np.pi / 2.0) / d * gamma * (S.T @ signs)
    return r_hat.astype(np.float32)
```

A definição de QJL no paper é exatamente \(Q_{qjl}(x)=\mathrm{sign}(Sx)\) e a dequantização é \(\sqrt{\pi/2}/d \cdot S^\top z\); no TurboQuantProd, isso é aplicado ao resíduo e multiplicado pela norma do resíduo \(\gamma\). [ppl-ai-file-upload.s3.amazonaws](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/133115618/ee7b7153-3df5-4aa9-9713-75413833e0df/2504.19874v1.pdf)

## TurboQuant completo

Agora juntando as duas partes:

```python
# ------------------------------------------------------------
# TURBOQUANT PROD
# ------------------------------------------------------------

def build_turboquant_prod(dim, bits, seed_rotation=42, seed_qjl=123):
    if bits < 1:
        raise ValueError("bits deve ser >= 1")

    mse_bits = max(bits - 1, 0)

    mse_state = build_turboquant_mse(dim, mse_bits, seed=seed_rotation) if mse_bits > 0 else None
    qjl_state = build_qjl(dim, seed=seed_qjl)

    return {
        "dim": dim,
        "bits": bits,
        "mse_bits": mse_bits,
        "mse_state": mse_state,
        "qjl_state": qjl_state,
    }


def quantize_prod(x, state):
    mse_state = state["mse_state"]
    qjl_state = state["qjl_state"]

    norm = np.linalg.norm(x)
    if norm == 0:
        raise ValueError("zero vector não é suportado")
    x_unit = x / norm

    if mse_state is not None:
        mse_pkg = quantize_mse(x_unit, mse_state)
        x_mse_hat = dequantize_mse(mse_pkg, mse_state)
    else:
        mse_pkg = None
        x_mse_hat = np.zeros_like(x_unit, dtype=np.float32)

    r = x_unit - x_mse_hat
    qjl_pkg = qjl_quantize(r, qjl_state)

    return {
        "mse_pkg": mse_pkg,
        "qjl_signs": qjl_pkg["signs"],
        "gamma": qjl_pkg["gamma"],
        "norm": np.float32(norm),
    }


def dequantize_prod(pkg, state):
    mse_state = state["mse_state"]
    qjl_state = state["qjl_state"]

    if mse_state is not None and pkg["mse_pkg"] is not None:
        x_mse_hat = dequantize_mse(pkg["mse_pkg"], mse_state)
    else:
        x_mse_hat = np.zeros(state["dim"], dtype=np.float32)

    r_hat = qjl_dequantize(
        {"signs": pkg["qjl_signs"], "gamma": pkg["gamma"]},
        qjl_state
    )

    x_hat_unit = x_mse_hat + r_hat
    x_hat = x_hat_unit * pkg["norm"]
    return x_hat.astype(np.float32)
```

Isso espelha o Algoritmo 2: quantiza com a versão MSE de \(b-1\) bits, calcula o resíduo \(r=x-\hat{x}_{mse}\), aplica `sign(S @ r)` e na reconstrução soma a parte MSE com a reconstrução QJL do resíduo. [ppl-ai-file-upload.s3.amazonaws](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/133115618/ee7b7153-3df5-4aa9-9713-75413833e0df/2504.19874v1.pdf)

## Pseudocódigo mais abstrato

Se você quiser algo mais “de paper” e menos “de Python”, fica assim:

```text
Pré-processamento TurboQuantMSE(d, b):
  1. Gerar matriz de rotação aleatória Π ∈ R^(d×d)
  2. Resolver o problema de Lloyd-Max 1D para a distribuição
     da coordenada rotacionada em S^(d-1)
  3. Obter codebook C = {c1, ..., c_(2^b)}

Quantmse(x):
  1. Normalizar x para norma 1
  2. y ← Π x
  3. Para cada coordenada j:
       idx_j ← argmin_k |y_j - c_k|
  4. Retornar idx e, opcionalmente, ||x||

DeQuantmse(idx):
  1. Para cada coordenada j:
       ŷ_j ← c_(idx_j)
  2. x̂ ← Π^T ŷ
  3. Reescalar por ||x||, se armazenado
  4. Retornar x̂
```

E a versão de produto interno:

```text
Pré-processamento TurboQuantProd(d, b):
  1. Instanciar TurboQuantMSE(d, b-1)
  2. Gerar matriz gaussiana S ∈ R^(d×d)

Quantprod(x):
  1. idx ← Quantmse(x)
  2. x̂_mse ← DeQuantmse(idx)
  3. r ← x - x̂_mse
  4. q ← sign(S r)
  5. γ ← ||r||_2
  6. Retornar (idx, q, γ)

DeQuantprod(idx, q, γ):
  1. x̂_mse ← DeQuantmse(idx)
  2. r̂ ← (sqrt(π/2) / d) · γ · S^T q
  3. x̂ ← x̂_mse + r̂
  4. Retornar x̂
```

Isso é praticamente a tradução operacional dos algoritmos apresentados no paper. [ppl-ai-file-upload.s3.amazonaws](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/133115618/ee7b7153-3df5-4aa9-9713-75413833e0df/2504.19874v1.pdf)

## O que faltava

Os pontos mais importantes que faltavam no seu pseudocódigo eram estes:

- **Codebook ótimo em vez de escala uniforme global**: o paper usa centróides de Lloyd-Max para a distribuição da coordenada rotacionada, não quantização uniforme por `min/max`. [ppl-ai-file-upload.s3.amazonaws](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/133115618/ee7b7153-3df5-4aa9-9713-75413833e0df/2504.19874v1.pdf)
- **Distribuição alvo correta**: após rotação aleatória, cada coordenada segue a distribuição de uma coordenada de ponto uniforme na esfera, descrita por uma Beta escalada em \([-1,1]\). [ppl-ai-file-upload.s3.amazonaws](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/133115618/ee7b7153-3df5-4aa9-9713-75413833e0df/2504.19874v1.pdf)
- **Bit budget do produto interno**: para \(b\) bits totais, o método de inner product usa \(b-1\) bits no MSE e 1 bit no resíduo via QJL. [ppl-ai-file-upload.s3.amazonaws](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/133115618/ee7b7153-3df5-4aa9-9713-75413833e0df/2504.19874v1.pdf)
- **Desbias para inner product**: a motivação dessa segunda etapa é que o quantizador MSE puro é enviesado para estimar produto interno, especialmente em baixa precisão. [ppl-ai-file-upload.s3.amazonaws](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/133115618/ee7b7153-3df5-4aa9-9713-75413833e0df/2504.19874v1.pdf)

## Versão prática

Se o seu objetivo é estudar e implementar logo, eu te recomendaria esta sequência prática:

- **Versão A**: seu quantizador uniforme com rotação, porque é simples.
- **Versão B**: trocar `qmin/qmax` por **codebook Lloyd-Max**.
- **Versão C**: adicionar **QJL no resíduo**.
- **Versão D**: medir MSE, bias e variância de inner product em embeddings reais. [ppl-ai-file-upload.s3.amazonaws](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/133115618/ee7b7153-3df5-4aa9-9713-75413833e0df/2504.19874v1.pdf)

Essa ordem te dá um caminho incremental sem perder fidelidade com o paper.

## Observação importante

Há um detalhe teórico/prático: o paper assume vetores na esfera unitária e comenta que, para vetores fora dessa condição, você pode **armazenar a norma separadamente** e reescalar na reconstrução. Então, em embeddings reais, o jeito mais fiel é: [ppl-ai-file-upload.s3.amazonaws](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/133115618/ee7b7153-3df5-4aa9-9713-75413833e0df/2504.19874v1.pdf)
- normalizar para quantizar,
- guardar a norma,
- reconstruir,
- multiplicar de volta pela norma. [ppl-ai-file-upload.s3.amazonaws](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/133115618/ee7b7153-3df5-4aa9-9713-75413833e0df/2504.19874v1.pdf)

Se quiser, no próximo passo eu posso te entregar uma destas duas opções:

## Próximo passo

- **Opção 1:** transformar isso em **código Python real e executável** com NumPy/Scipy.
- **Opção 2:** fazer uma **versão otimizada para embeddings/banco vetorial**, já com API tipo `fit / encode / decode / search`.

Se quiser, eu também posso montar a versão **“TurboQuant simplificado vs TurboQuant paper”** lado a lado para ficar didático. [ppl-ai-file-upload.s3.amazonaws](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/133115618/ee7b7153-3df5-4aa9-9713-75413833e0df/2504.19874v1.pdf)
