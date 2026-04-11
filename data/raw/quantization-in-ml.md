# Quantization Techniques for Neural Networks and Embeddings

## Introduction to Quantization

Quantization is the process of representing numerical values with fewer bits than their original representation. In the context of neural networks and machine learning, quantization typically refers to representing 32-bit floating-point (float32) weights, activations, or embeddings using lower-precision formats such as float16, int8, int4, or even binary representations.

The motivation for quantization is primarily memory efficiency and computational speed. Float32 values require 4 bytes each. Int8 values require only 1 byte, achieving a 4x reduction in memory. Int4 requires 0.5 bytes per value with careful bit-packing, achieving 8x compression. These reductions directly translate to lower memory costs for storing embeddings, faster data transfer times, and in some cases faster arithmetic operations.

Modern deep learning inference increasingly relies on quantization to deploy large models on resource-constrained hardware. A large language model that requires 40 gigabytes of memory in float32 might require only 10 gigabytes in int8 or 5 gigabytes in int4, making it deployable on consumer hardware with far less expensive memory.

## Types of Quantization

Several distinct quantization approaches have been developed, each with different tradeoffs between compression ratio, reconstruction accuracy, and computational complexity.

Uniform scalar quantization is the simplest approach. The range of values being quantized is divided into equally-sized bins. Each value is mapped to the nearest bin center and stored as an integer index. Reconstruction simply looks up the bin center. The error introduced is bounded by half the bin width and decreases as the number of bits increases.

Non-uniform scalar quantization uses variable-width bins to better match the distribution of values being quantized. Since most neural network weights and embeddings follow roughly Gaussian or bell-shaped distributions, having smaller bins near zero (where density is highest) and larger bins in the tails reduces average quantization error. Lloyd-Max quantization is the classic algorithm for finding the optimal bin boundaries for a given distribution.

Vector quantization replaces individual scalars with codebook entries that represent groups of values. A codebook of K entries is learned from data, and each group of d values is replaced by the index of the nearest codebook entry. Vector quantization can achieve very high compression ratios but requires expensive codebook search during quantization.

Product quantization (PQ) divides the full-dimensional vector into subvectors and applies vector quantization to each subvector independently using a separate codebook. This reduces the computational cost of codebook search while retaining much of the compression efficiency of full vector quantization. FAISS uses product quantization extensively in its IndexIVFPQ index type.

## Quantization Granularity

Quantization can be applied at different levels of granularity, each with different implications for accuracy and implementation complexity.

Per-tensor quantization uses a single scale and zero-point for the entire tensor. This is the simplest approach but may sacrifice accuracy because different channels or rows may have very different value distributions.

Per-channel quantization uses different scale and zero-point values for each channel or row. This better captures the distribution of each channel and typically achieves higher accuracy than per-tensor quantization, but requires storing one scale and zero-point per channel.

Per-group quantization is a compromise that uses shared scales and zero-points for groups of consecutive elements within a channel. This is widely used in large language model quantization, where group sizes of 32 or 128 are common.

## Symmetric vs Asymmetric Quantization

Symmetric quantization uses quantization bins that are symmetric around zero, with a zero-point of zero. This simplifies arithmetic because zero in the quantized domain corresponds to zero in the floating-point domain. It is the preferred choice for activations that are roughly symmetric and for weights.

Asymmetric quantization uses a zero-point that can be any value, allowing the quantization range to be shifted to better cover the actual distribution of values. This is especially useful for activations after ReLU, which are always non-negative and therefore benefit from a quantization range that starts at zero.

For embedding compression, symmetric quantization is typically preferred because embedding values after normalization to the unit sphere follow distributions centered at zero, making symmetric bins naturally efficient.

## Quantization of Embeddings Specifically

Quantizing embeddings presents some unique challenges compared to quantizing model weights. The most important difference is that embeddings must preserve inner product relationships, not just individual value accuracy. Two embeddings that are very similar after decompression but have slightly different directions than the originals will produce incorrect similarity scores.

When embeddings are normalized to the unit sphere (as is standard practice in modern retrieval systems), each coordinate follows a marginal distribution derived from the uniform distribution on the hypersphere. For a d-dimensional unit sphere, the marginal distribution of a single coordinate follows the density proportional to (1 - x^2)^((d-3)/2) for x in [-1, 1]. For large dimensions like d=384 or d=768, this distribution is very sharply peaked around zero, meaning most coordinates have values very close to zero with few large positive or negative values.

This concentrated distribution means that uniform quantization wastes bin resolution on the rarely-occupied extremes of the value range. Non-uniform quantization methods like Lloyd-Max can allocate more bins near zero, where the distribution is dense, and fewer bins in the tails. This produces substantially lower quantization error for the same number of bits.

## The Role of Random Rotation

A key insight from recent work on embedding quantization is that applying a random orthogonal rotation before quantization can significantly improve quality. The reason is that raw embedding vectors often have very non-uniform distributions across dimensions. Some dimensions may have much higher variance than others, meaning that a fixed quantization range performs very differently for different dimensions.

After a random rotation, the energy of the original vector is spread more uniformly across all dimensions. In expectation, each dimension of the rotated vector has the same variance as the others, which makes uniform quantization more effective and allows a shared quantization scheme to work well for all dimensions simultaneously.

The rotation is invertible, so reconstruction simply applies the inverse (transpose) of the rotation matrix after dequantizing. The rotation matrix can be stored once and shared across all vectors, adding only a small constant overhead.

Hadamard matrices provide a structured alternative to random Gaussian rotation matrices. The Walsh-Hadamard transform can be applied in O(d log d) time rather than O(d^2) time for general matrix multiplication, making rotation practical even for very high-dimensional embeddings.

## Bit Packing and Storage Efficiency

A crucial implementation detail for low-bit quantization is proper bit packing. Without bit packing, a 4-bit quantized value stored in a uint8 variable wastes the upper 4 bits of that byte. Similarly, a 2-bit value stored in a uint8 wastes 6 bits. Without packing, 4-bit quantization uses 1 byte per value, providing only 4x compression versus float32, not the theoretical 8x.

With proper bit packing using numpy's packbits function or similar, two 4-bit values can be stored in a single byte, and four 2-bit values can be stored in a single byte. This achieves the theoretical compression ratios: 8x for 4-bit and 16x for 2-bit compared to float32.

For the TurboQuant algorithm and similar methods, bit packing is implemented by first converting each quantized index to its binary representation, then concatenating all bits and repacking into bytes. The reverse process unpacks the bytes into bits and reconstructs the original indices. This can be efficiently implemented using numpy's packbits and unpackbits functions.

## Lloyd-Max Optimal Quantization

The Lloyd-Max algorithm finds the optimal quantization boundaries and reconstruction values for a scalar quantizer under a given probability distribution. The optimality criterion is minimum mean squared error (MSE) between the original and reconstructed values.

The algorithm alternates between two steps. In the partition step, for a given set of reconstruction levels, the optimal decision boundaries are placed halfway between adjacent reconstruction levels. In the reconstruction step, for a given set of decision boundaries, the optimal reconstruction level for each bin is the conditional expectation of the distribution within that bin.

Starting from an initial set of reconstruction levels (typically based on equal-probability quantiles of the distribution), the algorithm iterates these two steps until convergence. The algorithm is guaranteed to converge to a local minimum of MSE, which in practice is usually very close to the global minimum.

For the unit-sphere coordinate distribution, the Lloyd-Max codebook depends only on the embedding dimension d and the number of bits b. It is independent of the specific data being quantized. This means the codebook can be precomputed once and reused for all embeddings with the same model (same dimension d).

## Quantization Error Analysis

The quality loss from quantization can be analyzed from multiple perspectives. Quantization increases the mean squared error between original and reconstructed vectors. This error can be decomposed into a bias component (systematic offset in the expected value of each coordinate) and a variance component (random noise added to each coordinate).

Uniform quantization with symmetric bins has zero bias at the level of individual coordinates, because the expected quantization error is zero for a symmetric distribution with symmetric bins. However, the inner product between a query and a quantized document embedding has error that grows with dimension.

The inner product error for uniform scalar quantization is approximately (quantization_step^2 * d) / 12, where d is the embedding dimension and quantization_step is the width of each bin. This error decreases proportionally to (2^b)^2 = 4^b as the number of bits b increases, which means each additional bit reduces the inner product error by a factor of 4.

TurboQuant's analysis shows that applying a random rotation before quantization reduces the inner product error by equalizing the energy across dimensions, which reduces the worst-case error. The paper proves that TurboQuantMSE achieves near-optimal inner product estimation error for the class of scalar quantization methods with shared codebooks.

## Post-Training Quantization vs Quantization-Aware Training

For embedding models, quantization is almost always applied post-training (PTQ) rather than during training (QAT). This is because the embedding model itself is not being retrained; we are only quantizing the output vectors for storage efficiency.

PTQ applies the quantization scheme to existing embeddings without any model retraining. It is fast and requires only a representative sample of embeddings to calibrate the quantization parameters. The calibration step determines the value range and, for non-uniform methods, the codebook.

QAT inserts simulated quantization operations into the forward pass during fine-tuning, allowing the model to adapt to the quantization error. QAT typically achieves better quality than PTQ for the same compression ratio, especially at very low bit widths, but requires additional training infrastructure and compute.

For embedding compression in RAG systems, PTQ is almost always sufficient and preferred because we are quantizing the embeddings after they are generated, not modifying the model that generates them.

## Evaluation Metrics for Quantization Quality

Several metrics are used to evaluate quantization quality for embeddings.

Mean Squared Error (MSE) measures the average squared L2 distance between original and reconstructed embeddings. It captures the geometric distortion introduced by quantization but does not directly measure retrieval quality.

Cosine similarity error measures how much the direction of embeddings changes after quantization and reconstruction. Since retrieval is based on cosine similarity, this metric is more directly relevant than MSE for retrieval applications.

Inner product error measures the average error in the dot product between query embeddings and document embeddings after quantization. This directly measures the retrieval quality impact because similarity scores in retrieval are computed as inner products.

Recall@k with ground truth from float32 retrieval measures how often the quantized system returns the same top-k results as the exact float32 system. This is the most directly relevant metric for RAG applications but requires running both float32 and quantized retrieval to compute.

Mean Reciprocal Rank (MRR) captures not just whether the relevant document appears in the top-k but where it ranks. A system that places the relevant document at rank 1 scores higher MRR than one that places it at rank k, even if both have perfect Recall@k.
