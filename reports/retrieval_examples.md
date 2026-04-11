# RAG Embedding Compression Lab — Análise de Retrieval por Query

**Corpus:** 200 queries analisadas
**Critério de acerto:** relevante no top-5

---

## Queries que MANTIVERAM qualidade

_Todas as variantes encontraram o documento relevante no top-5._

| # | Query (trunc.) | Relevant ID |
|---|---|---|
| 1 | SINOPSE DA PRIMEIRA EDIÇÃO1 Se você gosta de viagens lá e de volta, para fora do… | `O-Hobbit-J-R-R--Tolkien-p13-c00` |
| 2 | o Sr. Bilbo Bolseiro visitou várias pessoas notáveis; conversou com o dragão Sma… | `O-Hobbit-J-R-R--Tolkien-p13-c03` |
| 3 | PREFÁCIO1 O Hobbit foi publicado pela primeira vez em 21 de setembro de 1937.… | `O-Hobbit-J-R-R--Tolkien-p14-c00` |
| 4 | mas é bem possível que “a primeira cópia rabiscada que não foi além do primeiro … | `O-Hobbit-J-R-R--Tolkien-p15-c04` |
| 5 | Allen & Unwin Ltda. e, depois de um monte de correspondências, eles resolveram p… | `O-Hobbit-J-R-R--Tolkien-p15-c07` |

---

## Queries que QUEBRARAM (f32 achou, turbo_mse_4 não)

_f32 achou em top-5, turbo_mse_4bit não achou._

| # | Query (trunc.) | Relevant ID | Rank f32 | Rank mse_4 |
|---|---|---|---|---|
| 1 | em cima do outro. Mais anãos, quatro mais! E lá estava Gandalf atrás deles, apoi… | `O-Hobbit-J-R-R--Tolkien-p35-c02` | 5 | 15 |
| 2 | navios, navegar para outras costas!… | `O-Hobbit-J-R-R--Tolkien-p31-c04` | 1 | 10 |

---

## Estatísticas gerais

| Variante | Hit@1 | Hit@5 | Hit@10 | Not Found | Mediana Rank |
|---|---|---|---|---|---|
| baseline f32 32 | 166/200 (83.0%) | 188/200 (94.0%) | 189/200 (94.5%) | 4/200 (2.0%) | 1.0 |
| turbo mse 4 | 168/200 (84.0%) | 186/200 (93.0%) | 188/200 (94.0%) | 5/200 (2.5%) | 1.0 |
| turbo mse 2 | 155/200 (77.5%) | 180/200 (90.0%) | 187/200 (93.5%) | 7/200 (3.5%) | 1.0 |
| turbo prod 4 | 162/200 (81.0%) | 182/200 (91.0%) | 188/200 (94.0%) | 5/200 (2.5%) | 1.0 |
| uniform 2 | 6/200 (3.0%) | 21/200 (10.5%) | 24/200 (12.0%) | 163/200 (81.5%) | 5.0 |

---

## Padrões observados

- **turbo_mse 4-bit** retém **99.5%** do Recall@10 do float32 usando apenas **1/8 da memória** (~7.9× compressão).
- **uniform 2-bit** retém apenas **12.7%** do Recall@10 — compressão agressiva sem rotação destrói a qualidade.
- **turbo_mse 2-bit** ainda retém **98.9%** do Recall@10 com 15× compressão — demonstra a robustez da rotação ortogonal.

---

_Relatório gerado automaticamente pelo RAG Embedding Compression Lab._