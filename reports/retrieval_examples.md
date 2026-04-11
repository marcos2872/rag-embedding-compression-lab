# RAG Embedding Compression Lab — Análise de Retrieval por Query

**Corpus:** 200 queries analisadas
**Critério de acerto:** relevante no top-5

---

## Queries que MANTIVERAM qualidade

_Todas as variantes encontraram o documento relevante no top-5._

| # | Query (trunc.) | Relevant ID |
|---|---|---|
| 1 | distortion in their geometric structure.… | `2504-19874v1-p01-c0001` |
| 2 | least distortion achievable by block source codes, now known as vector quan- tiz… | `2504-19874v1-p02-c0001` |
| 3 | latency. This latency is primarily attributed to communication bottlenecks betwe… | `2504-19874v1-p02-c0003` |
| 4 | cache, the size of which scales with both model size (number of layers and atten… | `2504-19874v1-p02-c0005` |
| 5 | computation, making them unsuitable for real-time AI applications like KV cache … | `2504-19874v1-p02-c0009` |

---

## Queries que QUEBRARAM (f32 achou, turbo_mse_4 não)

_f32 achou em top-5, turbo_mse_4bit não achou._

| # | Query (trunc.) | Relevant ID | Rank f32 | Rank mse_4 |
|---|---|---|---|---|
| 1 | eliminating the need for preprocessing.… | `2504-19874v1-p04-c0009` | 4 | 6 |
| 2 | do not explicitly provide a query set.… | `2504-19874v1-p19-c0007` | 5 | 6 |

---

## Estatísticas gerais

| Variante | Hit@1 | Hit@5 | Hit@10 | Not Found | Mediana Rank |
|---|---|---|---|---|---|
| baseline f32 32 | 159/200 (79.5%) | 179/200 (89.5%) | 187/200 (93.5%) | 6/200 (3.0%) | 1.0 |
| turbo mse 4 | 159/200 (79.5%) | 178/200 (89.0%) | 185/200 (92.5%) | 6/200 (3.0%) | 1.0 |
| turbo mse 2 | 145/200 (72.5%) | 179/200 (89.5%) | 185/200 (92.5%) | 5/200 (2.5%) | 1.0 |
| turbo prod 4 | 151/200 (75.5%) | 177/200 (88.5%) | 183/200 (91.5%) | 5/200 (2.5%) | 1.0 |
| uniform 2 | 31/200 (15.5%) | 64/200 (32.0%) | 85/200 (42.5%) | 54/200 (27.0%) | 7.0 |

---

## Padrões observados

- **turbo_mse 4-bit** retém **98.9%** do Recall@10 do float32 usando apenas **1/8 da memória** (~7.9× compressão).
- **uniform 2-bit** retém apenas **45.5%** do Recall@10 — compressão agressiva sem rotação destrói a qualidade.
- **turbo_mse 2-bit** ainda retém **98.9%** do Recall@10 com 15× compressão.

---

_Relatório gerado automaticamente pelo RAG Embedding Compression Lab._