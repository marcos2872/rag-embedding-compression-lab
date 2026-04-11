# Retrieval-Augmented Generation (RAG): Architecture and Best Practices

## Overview of RAG Systems

Retrieval-Augmented Generation, commonly known as RAG, is an architectural pattern for building question-answering and document-grounded generation systems. The core idea is to augment the context of a language model at inference time with information retrieved from an external knowledge base, rather than relying solely on the information baked into the model's parameters during training.

The motivation for RAG comes from fundamental limitations of purely parametric language models. Although large language models like GPT-4, Claude, and Llama encode enormous amounts of world knowledge in their parameters, they suffer from several problems that make them unreliable for knowledge-intensive tasks.

First, parametric models have a knowledge cutoff date. Any events or information published after training are simply unknown to the model. Second, models tend to hallucinate plausible-sounding but factually incorrect information, especially for obscure or highly specific facts. Third, it is extremely expensive to update a large model's knowledge by retraining or fine-tuning, whereas updating a retrieval index is fast and cheap.

RAG addresses these problems by separating the retrieval of relevant information from its synthesis into a natural language response. The retrieval component can be updated independently and continuously, while the language model serves as a sophisticated reader and writer that operates on whatever context is provided.

## Core Components of a RAG Pipeline

A complete RAG pipeline consists of several interconnected components that work together to answer queries from a knowledge base.

The ingestion pipeline is responsible for preparing raw documents for retrieval. This involves loading documents from various sources (PDFs, web pages, databases, etc.), splitting them into appropriately sized chunks, generating embeddings for each chunk, and storing the embeddings in a vector index. This pipeline runs offline, before any queries arrive.

The retrieval component handles online query processing. When a query arrives, it is embedded using the same model used to embed the documents. The query embedding is then used to search the vector index for the most similar document chunks. The top-k results are returned along with their similarity scores.

The context assembly component takes the retrieved chunks and formats them into a prompt for the language model. This typically involves concatenating the text of the retrieved chunks with appropriate separators, adding the user's query, and including any system instructions about how the model should use the retrieved context.

The generation component passes the assembled prompt to a language model and generates the final response. The model is expected to synthesize information from the retrieved context to answer the user's question, rather than relying on its parametric knowledge.

A reranking component is often added between retrieval and generation to improve the quality of the retrieved context. Rerankers are typically cross-encoder models that take a (query, document) pair as input and output a relevance score. Although rerankers are slower than embedding-based retrieval, they are more accurate and can significantly improve RAG quality.

## The Ingestion Pipeline in Detail

The ingestion pipeline is where document understanding and processing take place. Its quality has a large impact on the overall RAG system performance.

Document loading handles the diversity of input formats. PDF parsing with libraries like PyMuPDF extracts text along with page numbers and layout information. HTML parsing removes boilerplate navigation and advertisements to extract the main content. Markdown and plain text files can be loaded directly. Some systems also handle tabular data from spreadsheets or databases.

Chunking is the process of splitting documents into segments that can be embedded and retrieved independently. The choice of chunking strategy has a significant impact on retrieval quality. Fixed-size character or word chunking is simple and fast but may split sentences awkwardly. Sentence-based chunking respects sentence boundaries but produces variable-size chunks. Semantic chunking uses a model to identify natural topic boundaries and produce more coherent chunks.

The chunk size parameter involves a fundamental tradeoff. Smaller chunks are more precise and allow retrieval of specific facts but miss broader context. Larger chunks provide more context but are less precise and may include irrelevant information that dilutes the relevance signal. A common heuristic is to use chunks of 256 to 512 tokens for retrieval and to include neighboring chunks as context when generating the final response.

Overlap between consecutive chunks helps avoid losing important information at chunk boundaries. With an overlap of 32 words, the end of each chunk is repeated at the beginning of the next, ensuring that a sentence split across a boundary will appear in at least one complete chunk.

Metadata attachment enriches each chunk with information about its source. This might include the document title, author, date, page number, section heading, and URL. Metadata can be used for filtering during retrieval (e.g., only retrieve documents from a specific date range) and for citation in the generated response.

## Vector Indexing and Search

The vector index is the data structure that enables efficient similarity search over the embedding space. For small corpora (up to a few hundred thousand documents), an exact search using FAISS IndexFlatIP or IndexFlatL2 is practical and produces perfect recall. For larger corpora, approximate nearest neighbor search must be used to maintain acceptable latency.

FAISS (Facebook AI Similarity Search) is the most widely used library for dense vector search. It provides a range of index types with different tradeoffs between memory usage, search speed, and recall accuracy. IndexFlatIP performs exact inner product search and serves as the gold standard for quality comparison. IndexIVFFlat partitions the space into Voronoi cells using k-means clustering, enabling sub-linear search time by only examining a subset of cells. IndexIVFPQ combines inverted file partitioning with product quantization to dramatically reduce memory usage.

Hierarchical Navigable Small World (HNSW) graphs, implemented in libraries like hnswlib and supported by FAISS, offer excellent search performance and recall by maintaining a multi-layer graph structure. HNSW is often preferred for production systems because it provides a good balance of speed, recall, and memory efficiency.

Specialized vector databases like Qdrant, Weaviate, Pinecone, Milvus, and Chroma are built on top of these core algorithms and add features needed for production deployments: persistent storage, real-time updates, metadata filtering, hybrid search combining dense and sparse retrieval, access control, and horizontal scaling.

## Hybrid Search

Pure dense retrieval with embeddings is powerful but misses an important class of queries: exact keyword matches, product codes, proper nouns, and technical terms that appear verbatim in relevant documents. Traditional BM25 sparse retrieval excels at these cases but struggles with semantic matching.

Hybrid search combines dense and sparse retrieval to get the benefits of both approaches. The most common approach is to run both retrievers in parallel and then merge and rerank their results using a method like Reciprocal Rank Fusion (RRF). RRF combines rankings from multiple retrievers without requiring score normalization, making it robust and easy to implement.

Some systems use learned sparse retrieval methods like SPLADE that produce sparse embeddings with vocabulary-sized vectors but still capture semantic information. These models offer a middle ground between BM25 and dense retrieval.

## Prompt Engineering for RAG

The way retrieved context is presented to the language model significantly affects generation quality. Several best practices have emerged from research and practice.

Context length management is critical because language models have finite context windows. Selecting and pruning retrieved chunks to fit within the context window while maximizing relevance is an active research area. Simply truncating the context may discard important information, while including everything may dilute the signal.

Context ordering affects generation quality due to the "lost in the middle" phenomenon documented in research: language models tend to better attend to information at the beginning and end of long contexts than in the middle. Placing the most relevant chunks first or last, rather than in the middle, can improve answer quality.

Citation generation encourages the model to ground its answer in specific retrieved passages by explicitly instructing it to cite the source of each claim. This reduces hallucination and allows users to verify answers.

Faithfulness constraints can be included in system prompts to instruct the model to only answer from the provided context and to explicitly state when the context does not contain sufficient information. This reduces the model's tendency to fill in gaps with parametric knowledge.

## Evaluation of RAG Systems

Evaluating RAG systems requires assessing multiple components: retrieval quality, generation faithfulness, and overall answer quality.

Retrieval quality is measured with standard information retrieval metrics: Recall@k, MRR, and NDCG. Ground truth relevance labels are needed, either from human annotation or from synthetic datasets where query-document pairs are known.

Faithfulness measures whether the generated answer is supported by the retrieved context, independent of whether the answer is factually correct. A faithful answer only makes claims that can be verified from the retrieved documents. Tools like RAGAS and TruEra automate faithfulness evaluation using language model judges.

Answer relevance measures whether the generated answer actually addresses the user's question. Even a faithful answer that quotes extensively from retrieved documents may not directly answer what was asked.

Context precision measures what fraction of the retrieved documents are actually relevant to the query. High context precision reduces noise in the prompt and improves generation quality.

End-to-end accuracy can be measured on question answering benchmarks with known answers, such as Natural Questions, TriviaQA, or domain-specific benchmarks. The final answer is compared to the ground truth answer using exact match or fuzzy string matching.

## Common Failure Modes

Understanding RAG failure modes is essential for building robust systems.

Retrieval failures occur when relevant documents are not returned in the top-k results. This can happen because the embedding model fails to capture the semantic relationship between the query and the relevant document, or because the relevant document is not in the corpus at all. Increasing k helps but adds noise to the context.

Context window overflow happens when too many chunks are retrieved or when individual chunks are too large to fit everything in the prompt. Effective chunking and context selection strategies are needed to handle this.

Conflicting information in the retrieved context can confuse the generation model. If different retrieved documents make contradictory claims about the same fact, the model may generate inconsistent or uncertain answers.

Temporal conflicts arise when retrieved documents contain outdated information alongside current information. Without explicit timestamps and recency weighting in retrieval, the model may serve outdated facts.

Query-document style mismatch occurs when the query is phrased very differently from how information is written in the corpus. A formal academic question might fail to retrieve informal but relevant blog posts, or vice versa.

## Advanced RAG Architectures

Research has produced many extensions to the basic RAG architecture that address its limitations.

Multi-hop reasoning enables answering questions that require combining information from multiple documents. For example, answering "what is the capital of the country where TurboQuant was invented?" requires first finding where TurboQuant was invented, then finding the capital of that country. Multi-hop RAG systems decompose the query, retrieve for each sub-question, and combine the results.

Iterative retrieval alternates between retrieval and generation, using the intermediate generation outputs to refine subsequent retrieval queries. This is especially useful for complex questions where the model needs to explore the knowledge base interactively.

Query expansion and rewriting use a language model to reformulate the user's original query into a form more likely to match the embedding style of the corpus. This addresses the vocabulary mismatch problem where queries and documents use different terminology.

Self-RAG is a fine-tuning approach where the model learns to decide when to retrieve, what to retrieve, and how to evaluate the quality of retrieved passages, producing more faithful and accurate responses.

RAG-Fusion runs multiple queries derived from the original question in parallel and combines their results using reciprocal rank fusion, improving coverage and robustness.
