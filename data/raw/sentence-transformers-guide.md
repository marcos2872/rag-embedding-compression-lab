# Sentence Transformers and Embedding Model Libraries

## The sentence-transformers Library

The sentence-transformers library, developed by Nils Reimers and Iryna Gurevych at TU Darmstadt, provides a convenient Python interface for generating high-quality sentence and document embeddings using pre-trained transformer models. It handles tokenization, batching, inference, and pooling automatically, making it the de facto standard for embedding generation in research and production applications.

The library is built on top of Hugging Face Transformers and inherits its support for loading models from the Hugging Face Hub, converting between model formats, and running inference on CPU, CUDA, and Apple Silicon (MPS) backends.

Installing sentence-transformers via pip or uv installs all necessary dependencies, including torch, transformers, and tokenizers. The first time a model is loaded, it is automatically downloaded from the Hugging Face Hub and cached in the user's home directory under .cache/huggingface/hub. Subsequent loads use the cached model, enabling fully offline operation after the initial download.

## Creating a SentenceTransformer Model

A SentenceTransformer model is instantiated by passing the model name or path to the constructor. The model is downloaded if not cached and then loaded into memory. The device argument controls which hardware accelerator to use.

The most common pooling strategies are mean pooling (averaging all token embeddings), CLS pooling (using the first token's embedding), and max pooling (taking the element-wise maximum). Most modern models use mean pooling as it generally produces better sentence-level representations than CLS pooling.

The normalize_embeddings argument in the encode method controls whether output embeddings are normalized to unit L2 norm. Normalization is essential for cosine similarity computation and should always be enabled for retrieval applications where embeddings will be compared using inner products or cosine similarity.

## Batch Inference and Performance

The encode method supports batched inference through the batch_size argument. Larger batches reduce per-sample inference overhead but require more memory. For CPU inference with a small model like BGE-small (130 MB), batch sizes of 32 to 128 typically maximize throughput. For GPU inference, batch sizes of 64 to 512 may be appropriate depending on GPU memory.

The show_progress_bar argument displays a tqdm progress bar during inference, which is useful for tracking progress when embedding large corpora. For production code, this should be disabled to avoid cluttering logs.

The convert_to_numpy argument returns numpy arrays instead of PyTorch tensors, which is typically what is needed for downstream processing with numpy-based quantization and FAISS indexing code.

For very large corpora that do not fit in memory, embeddings can be generated in chunks and written to disk incrementally using numpy.save or numpy.memmap. The final embeddings can then be concatenated by memory-mapping all chunks.

## Model Selection Guidelines

Choosing the right embedding model depends on the specific use case, available hardware, and quality requirements.

For CPU-only deployment with limited memory, BAAI/bge-small-en-v1.5 with 384 dimensions and 130 MB is the recommended starting point. It achieves competitive performance on MTEB retrieval tasks and can embed hundreds of documents per second on a modern CPU.

For higher quality at the cost of more memory and compute, BAAI/bge-base-en-v1.5 (768 dimensions, 430 MB) provides better retrieval quality. The base model is particularly beneficial for longer documents where its larger capacity better captures document-level semantics.

For multilingual applications, paraphrase-multilingual-mpnet-base-v2 and multilingual-e5-base support over 50 languages. The E5 models require prepending "query: " or "passage: " prefixes to enable their instruction-following capability.

For maximum quality with no resource constraints, BAAI/bge-large-en-v1.5 (1024 dimensions, ~1.3 GB) or proprietary API models like OpenAI text-embedding-3-large may be appropriate. These models achieve the highest MTEB scores but at substantially higher inference cost.

## Fine-tuning Embedding Models

The sentence-transformers library also supports fine-tuning pre-trained models on domain-specific data. Fine-tuning is valuable when the target domain differs significantly from the model's training data, such as medical literature, legal documents, or specialized technical domains.

Fine-tuning uses a loss function that captures the desired properties of the embeddings. MultipleNegativesRankingLoss is the most commonly used loss for retrieval fine-tuning. It takes as input pairs of (query, relevant_document) and treats all other documents in the batch as negatives, optimizing the model to produce higher similarity scores for relevant pairs than for negatives.

The NTXentLoss and ContrastiveLoss functions offer alternative formulations that may work better for specific data distributions. CoSENTLoss can be used when soft relevance labels are available rather than binary relevant/not relevant labels.

Training data for embedding fine-tuning typically comes from existing question-answer pairs, paraphrase datasets, or synthetic data generated by a language model. The quality of training data has a larger impact on fine-tuning success than the specific loss function chosen.

## Handling Long Documents

Transformer models have maximum input lengths, typically 512 tokens for most sentence-transformer models. Documents longer than this limit must be handled explicitly.

The simplest approach is truncation: documents are truncated to the maximum length, which loses information about the second half of long documents. This is adequate when documents are generally short and the occasional truncation does not significantly impact retrieval quality.

Chunking, as described in other sections of this corpus, is the standard approach for long documents in RAG systems. Each chunk is embedded independently, and the chunk embeddings are stored and searched.

Max pooling over chunk embeddings computes the element-wise maximum of all chunk embeddings for a document. This aggregated embedding can represent the document for retrieval. However, max pooling may not work well with all models.

Mean pooling over chunk embeddings averages all chunk embeddings. This is equivalent to computing a document-level embedding from the average of its part embeddings. The quality depends heavily on whether the model's representation space supports meaningful averaging.

For some models, a hierarchical approach works well: embed each sentence, then embed the sequence of sentence embeddings to produce a document embedding. This requires a model specifically designed for this purpose.

## Evaluating Embedding Models

The sentence-transformers library provides integration with the MTEB benchmark for systematic evaluation of embedding model quality. The MTEB evaluation covers 56 datasets across classification, clustering, pair classification, reranking, retrieval, semantic textual similarity, and summarization tasks.

For retrieval-specific evaluation, the InformationRetrievalEvaluator from sentence-transformers computes Recall@k, MRR, NDCG, and MAP on a corpus with known query-document relevance pairs. This evaluator is used internally in the RAG embedding compression lab to compare float32 embeddings against quantized embeddings.

The evaluator handles the complete pipeline: embedding queries and documents, building a search index, running searches, and computing all metrics. It serves as a convenient end-to-end test harness for the retrieval components of the lab.

## Integration with PyTorch and Hugging Face Ecosystem

Sentence-transformers models are fully compatible with the PyTorch and Hugging Face ecosystems. The underlying model can be accessed as a standard transformers AutoModel, enabling techniques like gradient checkpointing, mixed precision inference, and export to ONNX or TorchScript for deployment.

The Accelerate library from Hugging Face can be used for distributed inference across multiple GPUs or nodes. PEFT (Parameter-Efficient Fine-Tuning) with LoRA adapters allows efficient domain adaptation without modifying the full model weights.

The Hugging Face Hub provides a central registry of pre-trained models, fine-tuned models, and their evaluation results. The MTEB leaderboard, hosted on the Hub, provides a continuously updated ranking of models on all 56 tasks. This makes it easy to identify the best model for a given task and hardware budget.

The safetensors format, which is the default for new Hub model uploads, provides faster and safer loading compared to pickle-based PyTorch save files. Sentence-transformers supports loading safetensors models natively.

## Memory Management for Large-Scale Embedding

When generating embeddings for large corpora, memory management becomes important. A naive approach that loads all documents and generates all embeddings before saving will run out of memory for large corpora.

A streaming approach reads documents in batches, generates embeddings for each batch, and writes the embeddings to disk before loading the next batch. This can be implemented using Python generators and numpy memory-mapped arrays.

For corpora larger than available disk space on the primary drive, distributed storage can be used. Embeddings can be sharded across multiple files, with each shard containing a contiguous range of document indices.

For distributed index building, embeddings can be generated in parallel on multiple machines and then merged. FAISS supports reading and merging multiple index files, enabling distributed index construction.

Progress tracking and checkpointing are important for long-running embedding jobs. Saving a checkpoint after every 100,000 documents and resuming from the last checkpoint enables recovery from failures without losing all progress.

The memory footprint of the sentence-transformers model itself is fixed (130 MB for BGE-small). The memory for embeddings grows with the number of documents. For 1 million documents with 384 dimensions in float32, embedding memory is approximately 1.5 GB. This is separate from the model memory and should be planned for explicitly.
