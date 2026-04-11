# Notes — RAG Embedding Compression Lab

## Configuração
- Corpus: `data/corpus.jsonl`
- Modelo: `BAAI/bge-small-en-v1.5` (dim=384)
- Queries: 200 (estratégia `first_sentence`)

## Resultados chave

- **Sweet spot:** `turbo_mse_8-bit` — 4.0× compressão, Recall@10=0.945 (Δ=+0.000 vs f32)

## Próximos passos
- [ ] Fase 7: demo RAG interativo (`make rag-demo`)
- [ ] Testar com corpus maior (>10k chunks)
- [ ] Comparar com FAISS IndexIVFPQ
- [ ] Fine-tuning do modelo de embedding no domínio

---
_Gerado automaticamente pelo RAG Embedding Compression Lab._