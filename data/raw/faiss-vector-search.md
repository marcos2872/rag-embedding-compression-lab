# FAISS: Vector Search at Scale

## Introduction to FAISS

FAISS (Facebook AI Similarity Search) is an open-source library developed by Meta AI Research for efficient similarity search and dense vector clustering. It provides highly optimized algorithms for searching in large collections of high-dimensional vectors, with implementations that take advantage of SIMD instructions (AVX, AVX-512) and GPU acceleration via CUDA.

The core problem FAISS solves is: given a large dataset of N vectors in d-dimensional space and a query vector, find the k most similar vectors quickly. For small N (up to a few million) and reasonable d (up to a few thousand), FAISS can return exact results faster than naive implementations by factors of 10x to 1000x. For very large N, FAISS provides approximate search methods that trade a small amount of accuracy for much larger speedups.

FAISS supports multiple similarity metrics. Inner product (IP) is used when vectors are already normalized to unit length, where it is equivalent to cosine similarity. L2 distance is used for unnormalized vectors. The choice of metric affects which index types are available and how the index should be built.

## Index Types and Their Tradeoffs

FAISS provides a rich family of index types, each suited to different requirements for memory, speed, and accuracy.

IndexFlatIP and IndexFlatL2 are the brute-force exact search indexes. They store all vectors in float32 and exhaustively compute distances between the query and every stored vector. This guarantees perfect recall but requires O(N) time per query and O(N * d * 4) bytes of memory. For N=100,000 vectors of dimension 384, this requires 150 MB of memory and can perform searches in milliseconds on modern hardware.

IndexIVFFlat (Inverted File Flat) partitions the vector space into nlist Voronoi cells using k-means clustering. At search time, only the nprobe nearest cells are searched, reducing the number of distance computations. With nlist=1000 and nprobe=10, roughly 1% of vectors are compared to the query, achieving approximately 100x speedup with typically 95-99% recall retention.

IndexIVFPQ (Inverted File with Product Quantization) combines the IVF partitioning with product quantization of residual vectors. Product quantization represents each vector as a sequence of indices into per-subspace codebooks, dramatically reducing memory. With M=8 subspaces and K=256 codewords each, a 384-dimensional float32 vector requires 1536 bytes uncompressed but only 8 bytes with PQ, achieving 192x compression. The tradeoff is reduced recall due to quantization noise.

HNSW (Hierarchical Navigable Small World) builds a multi-layer graph where each node connects to M neighbors at each layer. Search traverses the graph from a random entry point, greedily moving to the nearest neighbor until convergence. HNSW offers excellent recall (>99%) and fast queries but requires 40-80 bytes of graph overhead per vector in addition to the vector storage.

LSH (Locality Sensitive Hashing) projects vectors onto random hyperplanes and groups vectors that project to the same side. It provides very fast approximate search but with lower recall than HNSW or IVF methods for the same memory budget.

## Building and Searching FAISS Indexes

Building a FAISS index involves several steps. First, the index object is created with the appropriate type and parameters. Then, if the index type requires training (like IVF), the index is trained on a representative subset of the vectors to establish the quantization codebooks or Voronoi cells. Finally, the vectors are added to the index in batches.

For IndexFlatIP, the process is simple because no training is required. The vectors are added directly and the index is ready to use immediately. This makes IndexFlatIP suitable for dynamic corpora where vectors are added incrementally.

For IndexIVFFlat, training is necessary to learn the Voronoi cell centroids via k-means. The training set should ideally contain at least 30 * nlist samples to ensure good cell coverage. If fewer samples are available, a smaller nlist should be used.

The add operation inserts vectors into the index. FAISS supports batch addition, which is much faster than adding vectors one by one. Typical batch sizes are 10,000 to 100,000 vectors.

Search is performed by calling the index's search method with a query vector or a batch of query vectors. FAISS supports batch queries, which is important for throughput-oriented applications. The search returns the distances and indices of the k nearest neighbors for each query.

## GPU Acceleration

FAISS provides GPU implementations of its most important index types through the faiss.gpu module. GPU search can be 10x to 100x faster than CPU search for large indexes, making it essential for high-throughput applications.

The GPU implementations support IndexFlatIP, IndexFlatL2, IndexIVFFlat, and IndexIVFPQ. The typical workflow involves creating a CPU index, transferring it to GPU using faiss.index_cpu_to_gpu, and then performing search on the GPU index.

Multiple GPUs can be used in parallel to handle even larger indexes. FAISS provides faiss.index_cpu_to_all_gpus to automatically replicate an index across all available GPUs, with queries distributed across GPUs for load balancing.

For very large indexes that exceed GPU memory, a multi-CPU approach using multiple FAISS index shards may be more practical than GPU acceleration.

## Serialization and Deployment

FAISS indexes can be serialized to disk using faiss.write_index and loaded back using faiss.read_index. This allows pre-built indexes to be stored and loaded on demand without rebuilding from scratch.

For production deployments, index files should be treated as versioned artifacts that are rebuilt whenever the underlying corpus changes significantly. Incremental updates are possible with some index types but may degrade performance over time as the index structure becomes suboptimal.

Index memory mapping is supported for some index types, allowing the index to be loaded without copying all data into RAM. This is useful when multiple processes need to share the same index.

The faiss.write_index_binary and faiss.read_index_binary functions handle binary indexes (IndexBinaryFlat, IndexBinaryIVF) which store vectors as bit strings and use Hamming distance for comparisons.

## FAISS and Embedding Compression

FAISS's built-in product quantization provides a baseline embedding compression technique. However, PQ has some limitations for embedding retrieval compared to more recent methods like TurboQuant.

Product quantization decomposes each vector into independent subvectors, which means the quantization of each subspace does not account for correlations between subspaces. This suboptimality can be partially addressed by using Optimized Product Quantization (OPQ), which applies a rotation to the vectors before PQ to reduce inter-subspace correlations.

However, the core insight of TurboQuant and related work is that for the specific task of maximum inner product search on normalized embeddings, scalar quantization after random rotation can match or exceed PQ quality with simpler implementation and more predictable compression ratios.

A key practical advantage of external quantization (quantizing embeddings before inserting into FAISS) over FAISS's built-in PQ is that the compression ratios are transparent and controllable. With 4-bit scalar quantization and bit packing, exactly N * d * 4/8 bytes are used for storage, with no overhead from FAISS index structures. The tradeoff is that search always requires dequantizing the stored vectors back to float32 before computing distances, unless a specialized quantized distance computation is implemented.

## Integrating FAISS with RAG Pipelines

In a RAG pipeline, FAISS typically serves as the embedding store and similarity search engine for the document corpus. The integration involves building the index during corpus ingestion and querying the index during retrieval.

For the ingestion step, embeddings are generated in batches using a sentence transformer or similar model, then added to the FAISS index. When the corpus is complete, the index is written to disk. For very large corpora, the index can be built incrementally across multiple machines and merged.

For the retrieval step, the query is embedded using the same model (crucial for compatibility), and the embedding is passed to FAISS search. The returned document indices are used to look up the corresponding text chunks in the corpus, which are then assembled into the context for the language model.

Metadata filtering (retrieving only documents that match certain criteria) is not natively supported by FAISS. The typical approach is to retrieve more candidates than needed (over-retrieve), then apply metadata filters to the results. Alternatively, separate indexes can be maintained for different document subsets.

Hybrid search that combines FAISS dense retrieval with BM25 sparse retrieval requires running both retrievers and merging the results. Reciprocal Rank Fusion is a simple and effective way to merge ranked results from multiple retrievers without requiring score normalization.

## Performance Benchmarks and Tuning

The performance of FAISS depends heavily on the index type, the hardware, and the tuning parameters. Several benchmarks have established rough performance expectations.

For exact search with IndexFlatIP on CPU, a single core can search approximately 1,000 to 10,000 queries per second for a corpus of 100,000 vectors in 384 dimensions, depending on CPU architecture and SIMD support. Query throughput scales linearly with CPU cores for embarrassingly parallel workloads.

For approximate search with IndexIVFFlat using nprobe=10, throughput increases by roughly 50x-100x compared to exact search, with recall typically above 95% for well-tuned nlist values. The recall-speed tradeoff can be tuned by adjusting nprobe.

GPU search with IndexFlatIP can achieve 1,000,000+ queries per second for a corpus of 1,000,000 vectors, making it suitable for serving latency-sensitive applications at high throughput.

Memory usage is a critical consideration for large-scale deployments. Float32 vectors for a corpus of 10 million documents in 384 dimensions require approximately 14.6 GB of memory. With 4-bit external quantization, this drops to approximately 1.8 GB, enabling the index to fit in GPU memory even for very large corpora.

Batch size for queries significantly affects throughput. FAISS is highly optimized for batched queries, where a matrix of query vectors is searched simultaneously. Batch sizes of 64 to 1024 queries typically maximize throughput by maximizing CPU SIMD or GPU utilization.

The number of threads used by FAISS can be controlled via faiss.omp_set_num_threads. Setting this to the number of physical CPU cores (not hyperthreaded logical cores) typically maximizes performance without contention.

## ANN Benchmarks and Index Selection

The ann-benchmarks.com website provides standardized comparisons of approximate nearest neighbor search algorithms across multiple datasets and hardware configurations. These benchmarks help practitioners select the right index type for their use case.

For most embedding retrieval applications, HNSW typically achieves the best recall-throughput tradeoff. It consistently dominates in the recall vs queries-per-second Pareto frontier across most datasets. The main disadvantage of HNSW is its memory overhead: approximately 50-100 bytes of graph data per vector in addition to the vector storage.

IndexIVFFlat with appropriate nlist and nprobe values achieves competitive recall at lower memory cost than HNSW. It is preferred when memory is the primary constraint.

IndexIVFPQ achieves the best recall at very low memory budgets, making it suitable for deploying large corpora on memory-constrained hardware. For corpora that exceed available RAM, IndexIVFPQ is often the only viable option.

The choice between these options should be driven by profiling on the actual corpus and hardware, as performance can vary significantly with embedding distributions, hardware cache sizes, and access patterns.
