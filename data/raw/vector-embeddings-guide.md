# Introduction to Text Embeddings and Semantic Search

## What Are Text Embeddings?

Text embeddings are dense numerical representations of text that capture semantic meaning. Unlike traditional keyword-based representations such as TF-IDF or BM25, embeddings map words, sentences, and documents to points in a high-dimensional vector space where semantically similar texts are placed close together.

The key insight behind text embeddings is that language models trained on large corpora learn to represent meaning geometrically. Words and phrases that appear in similar contexts end up with similar vector representations. This means that "cat" and "feline" will have vectors that are more similar to each other than "cat" and "automobile," even though they share no characters in common.

Modern text embedding models are typically based on transformer architectures, specifically variants of BERT (Bidirectional Encoder Representations from Transformers). These models were originally designed for natural language understanding tasks but were found to produce excellent general-purpose text representations.

## How Embedding Models Work

An embedding model takes a piece of text as input and produces a fixed-size vector as output. For example, the BAAI/bge-small-en-v1.5 model produces vectors of dimension 384, while larger models like bge-base produce 768-dimensional vectors.

The process of generating an embedding works as follows. First, the input text is tokenized into subword units using a vocabulary of around 30,000 to 50,000 tokens. Then the transformer processes these tokens through multiple attention layers, each of which allows every token to attend to every other token in the sequence. Finally, the last hidden states are pooled, usually by taking the mean of all token representations or by using the special CLS token, to produce a single vector representing the entire input.

Training embedding models involves contrastive learning objectives. The model is presented with pairs of semantically similar texts (positives) and dissimilar texts (negatives). It learns to minimize the distance between positive pairs and maximize the distance between negative pairs in the embedding space. This training signal comes from curated datasets of question-answer pairs, paraphrases, and natural language inference data.

## Properties of Good Embeddings

High-quality embeddings have several desirable properties. First, they should be semantically faithful, meaning that the geometric distance between vectors should correlate with the semantic similarity between the corresponding texts. If document A is more relevant to a query than document B, then the embedding of A should be closer to the embedding of the query than the embedding of B.

Second, embeddings should generalize across domains. A model trained primarily on web text should still produce reasonable representations for legal documents, medical papers, or code, even if its performance in these domains is somewhat lower than in its training distribution.

Third, embeddings should be computationally efficient to produce and compare. In a production retrieval system, we need to embed millions of documents and perform thousands of similarity queries per second. This requires that embedding inference is fast and that vector comparison operations are cheap.

Fourth, modern embedding models are typically normalized to unit length before storage and comparison. When vectors are on the unit sphere, the cosine similarity between two vectors equals their dot product, which makes comparison computationally simpler and numerically more stable.

## Measuring Semantic Similarity

Once we have embeddings, the most common way to measure similarity is cosine similarity. For two vectors u and v, cosine similarity is defined as the dot product of their normalized versions. Since we typically normalize embeddings to unit length, cosine similarity reduces to simple dot product, which is extremely fast to compute.

Another option is Euclidean distance. For normalized vectors, Euclidean distance and cosine similarity are monotonically related, so they produce the same ranking of results. The choice between them is mainly a matter of implementation convenience.

Inner product similarity is also used when vectors are not normalized. This is relevant in some advanced quantization scenarios where the original vector norms carry information that should be preserved.

Correlation-based metrics like Pearson and Spearman correlation are sometimes used in evaluation benchmarks but are less common in production systems due to their computational cost.

## Applications of Text Embeddings

Text embeddings have become fundamental building blocks in modern natural language processing systems. Some of the most important applications include semantic search, question answering, document clustering, and retrieval-augmented generation.

In semantic search, embeddings enable finding relevant documents even when they do not share keywords with the query. A search for "heart disease treatment" will return documents about "cardiac therapy" and "cardiovascular medication" because these texts have similar embeddings even though they use different words.

In question answering systems, embeddings are used to retrieve relevant passages from a knowledge base before passing them to a generative model that formulates the final answer. This retrieval step is critical for grounding the model's responses in factual content.

Document clustering uses embeddings to group similar documents together without requiring labeled training data. By clustering documents in embedding space, we can automatically organize large collections of text into thematic groups.

## Embedding Evaluation Benchmarks

The quality of embedding models is typically measured on standardized benchmarks. MTEB (Massive Text Embedding Benchmark) is the most comprehensive, covering 56 datasets across 8 task types including retrieval, clustering, classification, and reranking.

The BEIR benchmark focuses specifically on retrieval tasks across diverse domains including Wikipedia, news articles, scientific papers, biomedical literature, and legal documents. BEIR is particularly valuable because it tests generalization to domains that may differ significantly from the training distribution.

For retrieval specifically, the primary metrics are Recall@k, which measures what fraction of queries have their relevant document in the top-k results, and Mean Reciprocal Rank (MRR), which rewards systems that place relevant documents higher in the ranking.

NDCG (Normalized Discounted Cumulative Gain) is a graded relevance metric that gives more credit for finding highly relevant documents early in the ranking. It is particularly useful when there are multiple relevant documents with varying degrees of relevance.

## Popular Embedding Models

Several families of embedding models have become widely used in the research and industry communities.

The BAAI BGE series, developed by the Beijing Academy of Artificial Intelligence, offers models at different size points (small, base, large) that achieve excellent results on MTEB. The small variant with 384 dimensions and 130 MB is particularly popular for CPU deployments due to its excellent performance-to-cost ratio.

OpenAI's text-embedding models are popular in applications that are already using the OpenAI API. The text-embedding-3-small and text-embedding-3-large models offer strong performance but require API calls and incur per-token costs.

The E5 family from Microsoft Research and the instructor models from HKUNLP offer instruction-tuned embeddings that can be specialized for specific tasks by prepending a task description to the input.

Nomic AI's nomic-embed-text model is notable for being fully open-source with disclosed training data and a 8192 token context window, making it suitable for embedding long documents.

## Dimensionality and Its Tradeoffs

The dimensionality of embeddings has important practical implications. Higher-dimensional embeddings generally capture more information and produce better retrieval quality, but they also require more memory for storage and more computation for comparison.

For a corpus of one million documents with 768-dimensional float32 embeddings, storage requires roughly 3 gigabytes just for the vectors. With 384 dimensions, this drops to 1.5 gigabytes. When the corpus grows to tens or hundreds of millions of documents, memory becomes a critical bottleneck.

This is one of the core motivations for embedding compression research. Techniques like quantization can dramatically reduce the memory footprint of embeddings while preserving most of their retrieval quality. A 4-bit quantization of 384-dimensional embeddings uses only 192 bytes per vector instead of 1536 bytes, achieving an 8x compression ratio.

The relationship between dimensionality and retrieval quality is not straightforward. Increasing dimensions from 384 to 768 typically provides meaningful quality improvements, but going from 768 to 1536 yields diminishing returns. For many practical applications, 384-dimensional embeddings strike an excellent balance between quality and efficiency.

## Challenges in Embedding-Based Retrieval

Despite their impressive capabilities, embedding-based retrieval systems face several challenges that active research is working to address.

The semantic gap problem arises when a user query and a relevant document use very different vocabulary and styles. For example, a technical query might retrieve a different document than a colloquial query asking the same question. Instruction-tuned and query-aware embedding models help address this but do not fully solve the problem.

Hallucination in retrieval occurs when the embedding model places unrelated documents close together due to superficial lexical or stylistic similarities. For example, documents that are both very formal in tone might be placed close together even if they discuss entirely different topics.

Long document handling is challenging because transformer models have a limited context window, typically 512 tokens. Long documents must be split into chunks before embedding, which means the model may miss connections between distant parts of the document. Various strategies exist for aggregating chunk-level embeddings into document-level representations.

Multilingual and cross-lingual retrieval adds another layer of complexity. While some models like mE5 and LaBSE support multiple languages, cross-lingual retrieval quality is typically lower than monolingual retrieval.

Out-of-distribution generalization is perhaps the most persistent challenge. Embedding models trained on general web text may perform poorly on specialized domains like patent documents, clinical notes, or programming code without domain-specific fine-tuning.
