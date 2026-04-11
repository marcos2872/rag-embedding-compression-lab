# Vector Databases: Architecture, Comparison, and Use Cases

## What Is a Vector Database?

A vector database is a database management system specifically designed to store, index, and query high-dimensional vector data. Unlike traditional relational databases that store structured tabular data or document databases that store JSON objects, vector databases are optimized for approximate nearest neighbor search over dense numerical vectors.

The rise of vector databases is directly tied to the adoption of machine learning models that represent data as vectors. Text embeddings, image embeddings, audio fingerprints, recommendation system user and item embeddings, and many other ML-generated representations require efficient storage and retrieval. Traditional databases are not equipped to handle these workloads efficiently.

A vector database must support two fundamental operations: inserting new vectors with associated metadata, and searching for the k nearest vectors to a query vector. Modern vector databases add many features on top of these basics: metadata filtering, hybrid search, vector updates and deletions, access control, replication, and horizontal scaling.

## Qdrant

Qdrant is an open-source vector database written in Rust, designed for high performance and production reliability. It is available as a self-hosted solution and as a managed cloud service.

Qdrant's data model centers around collections, which contain points. Each point has an id, a vector, and an optional payload (arbitrary JSON metadata). Multiple named vectors per point are supported, enabling storing different embeddings of the same document (e.g., dense and sparse) in the same point.

Qdrant implements HNSW as its primary indexing algorithm, with careful tuning for production workloads. It supports scalar quantization (int8) and product quantization natively, enabling significant memory reduction without requiring external preprocessing.

Qdrant's filtering capabilities are particularly strong. Payload filters can be combined with vector search to restrict results to documents matching specific criteria. Filters are applied during HNSW graph traversal, not as a post-processing step, which maintains search quality even with highly selective filters.

Binary quantization support in Qdrant converts float32 vectors to binary representations, achieving up to 32x compression. Combined with oversampling and rescoring, Qdrant's binary quantization achieves high recall with dramatically reduced memory.

## Weaviate

Weaviate is an open-source vector database with a graph-like data model and built-in support for multiple media types including text, images, and audio. It is designed for generative AI applications and provides tight integration with embedding model APIs.

Weaviate organizes data into classes (equivalent to tables), where each object has properties and one or more vectors. Cross-references between objects create a graph structure that can be traversed during search.

The generative search feature in Weaviate integrates directly with language model APIs (OpenAI, Cohere, Hugging Face, and others) to generate answers from retrieved context within the database query itself. This simplifies RAG implementation by eliminating the need to separately retrieve context and call the LLM.

Weaviate's vectorizer modules automatically generate embeddings when objects are inserted, using configured model integrations. This tight coupling simplifies the ingestion pipeline at the cost of flexibility.

The HNSW implementation in Weaviate supports segment-based storage for very large corpora. Vectors are partitioned across segments that can be loaded and unloaded from memory on demand, enabling datasets much larger than available RAM.

## Pinecone

Pinecone is a managed vector database service that provides a simple API for vector operations without requiring infrastructure management. It is designed for production deployments where scalability, availability, and low operational overhead are priorities.

Pinecone's serverless architecture scales automatically with usage. Users pay for storage and query compute separately, making it cost-effective for workloads with variable query rates.

Namespaces in Pinecone enable multi-tenancy by partitioning a single index into isolated segments. Each namespace is searched independently, enabling separate collections for different users or use cases within the same index.

Pinecone supports metadata filtering with a MongoDB-style query language. Filters are applied server-side during search, returning only results that match the filter criteria.

The sparse-dense hybrid search feature combines dense vector similarity with sparse keyword-based similarity in a single query. The alpha parameter controls the balance between dense and sparse components.

## Chroma

Chroma is an open-source embedding database focused on developer experience and simplicity. It is designed to be easy to embed in Python applications for prototyping and experimentation.

Chroma's simple Python API supports creating collections, adding documents with embeddings, and querying for similar documents. The entire database can be run in-memory or persisted to disk in a local directory.

Embedding functions can be passed to Chroma collections to automatically generate embeddings from text on insert and query. Built-in support for OpenAI, Cohere, Google, and Hugging Face embeddings makes getting started very easy.

Chroma uses HNSW from the hnswlib library for approximate nearest neighbor search. For small collections, exact search is used automatically. The index is rebuilt when new items are added, which is efficient for static or slowly-changing corpora.

The metadata filtering in Chroma supports simple equality and range filters on string and numeric metadata. More complex filtering is performed after retrieval.

## Milvus

Milvus is a cloud-native open-source vector database built for scale. It was developed at Zilliz and is a CNCF graduated project, reflecting its adoption in production enterprise environments.

Milvus's architecture separates storage from compute, enabling independent scaling of storage nodes and query nodes. Data is organized into segments that are automatically optimized and compacted. The persistent storage layer supports S3, GCS, and HDFS backends.

Milvus supports multiple index types including FLAT, IVF_FLAT, IVF_SQ8, IVF_PQ, HNSW, ANNOY, and DiskANN. The wide range of index options enables optimization for different memory-throughput-accuracy tradeoffs.

Dynamic schema support allows adding new fields to a collection after creation without data migration. Partitioning allows dividing a collection into segments that can be searched independently for workload isolation.

The GPU index types in Milvus (GPU_IVF_FLAT, GPU_IVF_PQ, GPU_CAGRA) provide significantly higher throughput for large-scale search workloads. The GPU_CAGRA index type, based on the CAGRA algorithm from NVIDIA, achieves state-of-the-art recall-throughput tradeoffs on GPU hardware.

## pgvector: Vector Search in PostgreSQL

pgvector is a PostgreSQL extension that adds native vector similarity search capabilities to the world's most popular open-source relational database. It enables storing and searching vectors without leaving the PostgreSQL ecosystem.

The extension adds a vector data type that can store dense float32 vectors of any dimension. Three index types are supported: exact brute-force search (no index), IVFFlat approximate search, and HNSW approximate search.

The key advantage of pgvector is the ability to combine vector search with arbitrary SQL queries. A query can join vector similarity results with relational data, apply complex filter expressions, and take advantage of PostgreSQL's full SQL capabilities. This eliminates the need for a separate vector database when the application already uses PostgreSQL.

pgvector's HNSW implementation was added in version 0.5.0 and significantly improved the recall-throughput tradeoff compared to the earlier IVFFlat-only implementation. For most use cases, HNSW with default settings achieves >99% recall while searching 10x faster than brute force.

The limitation of pgvector is that it does not scale as well as dedicated vector databases for very large corpora or high query throughput. For corpora beyond 10-50 million vectors or throughput requirements above a few thousand queries per second per instance, dedicated vector databases are more appropriate.

## Comparison of Vector Databases

Choosing a vector database depends on multiple factors: corpus size, query throughput requirements, filtering complexity, operational constraints, and cost.

For development and prototyping, Chroma is the easiest to get started with due to its simple Python API and zero infrastructure requirements. FAISS is a lower-level alternative that provides maximum flexibility but requires more code.

For self-hosted production deployments, Qdrant and Milvus are leading choices. Qdrant excels for workloads with complex metadata filtering and binary quantization. Milvus offers more index types and better support for GPU acceleration.

For managed cloud deployments where operational simplicity is a priority, Pinecone is the most mature option. Weaviate Cloud and Qdrant Cloud are alternatives with different feature sets.

For teams already invested in PostgreSQL, pgvector offers seamless integration at the cost of lower maximum scale.

All major vector databases support the HNSW algorithm, which has emerged as the dominant approach for high-quality approximate nearest neighbor search. The differences between products are primarily in: metadata filtering quality during search traversal, support for GPU acceleration, hybrid search capabilities, operational tooling, and pricing.

## Hybrid Search Architecture

Hybrid search combines dense vector retrieval with sparse keyword retrieval to leverage the complementary strengths of both approaches. Dense retrieval captures semantic similarity but may miss exact keyword matches. Sparse retrieval excels at exact matches but cannot handle semantic variation.

The standard approach is to run both retrieval systems independently and then merge the results. Reciprocal Rank Fusion (RRF) is the most widely used merging method. For each document in either result set, its RRF score is the sum of 1/(k + rank_i) across all lists it appears in, where k is a smoothing constant (typically 60) and rank_i is its rank in list i. RRF is robust to differences in score scales across retrievers.

Learned merging methods train a model to predict relevance scores from the features of both retrievers. These methods can outperform RRF but require labeled training data and add complexity.

SPLADE is a sparse retrieval model that produces sparse vector representations with vocabulary-sized dimensions. Unlike BM25 which is term-frequency based, SPLADE vectors capture semantic expansion: a document about "cardiac treatment" may have high weights for both "cardiac" and "heart" in its SPLADE vector. SPLADE can be stored in the same inverted index infrastructure as BM25 while providing semantic capabilities.

## Memory Architecture for Embedding Storage

The memory architecture for embedding storage has significant practical implications. Modern server hardware typically has 256 GB to 1 TB of DRAM, 4 to 16 TB of NVMe SSD storage, and optionally GPU memory.

For a corpus of 10 million documents with float32 embeddings (dimension 384), the embeddings alone require 14.6 GB of DRAM. The vector index overhead (HNSW graph, IVF cells, etc.) can add another 50-100% on top. For float32 at this scale, the total memory requirement is 25-30 GB.

With 4-bit quantization, the embedding storage drops to 1.8 GB, but the FAISS index still stores vectors in float32 (unless using IndexIVFPQ). The benefit of quantization is primarily for storing embeddings to disk and for loading them into a custom search system that can work with quantized representations.

DiskANN is an algorithm that enables high-quality approximate nearest neighbor search directly from SSD storage, avoiding the need to keep the entire index in DRAM. It builds a graph index where each node stores its compressed (product quantized) representation, enabling cache-efficient traversal with SSD page reads. This enables corpora with billions of vectors to be searched efficiently even when DRAM is insufficient to hold the full index.

Tiered memory architectures use combinations of GPU HBM, DRAM, and NVMe storage with intelligent caching to achieve high throughput at lower cost than keeping everything in DRAM. Vector databases like Milvus support configuring these memory tiers explicitly.
