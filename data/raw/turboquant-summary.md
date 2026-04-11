# TurboQuant: Near-Lossless Embedding Compression for Vector Search

## Overview

TurboQuant is a method for quantizing embedding vectors that achieves near-lossless compression while providing strong theoretical guarantees on inner product estimation error. The paper introduces two variants: TurboQuantMSE, which minimizes mean squared error, and TurboQuantProd, which additionally minimizes bias in inner product estimation.

The core insight of TurboQuant is that combining three components — a random orthogonal rotation, an optimal scalar codebook derived from the unit-sphere coordinate distribution, and bit-packed storage — achieves near-optimal compression quality for the class of scalar quantization methods applied to normalized embeddings.

The method is designed for the specific setting of maximum inner product search (MIPS) on normalized embeddings, which is the dominant paradigm in modern dense retrieval systems. In this setting, embeddings are stored on the unit sphere (normalized to unit L2 norm), and similarity is measured by inner product (dot product).

## Motivation: Why Existing Methods Fall Short

Existing methods for embedding compression have various limitations that TurboQuant addresses.

Product quantization (PQ) as used in FAISS can achieve high compression ratios but decomposes vectors into independent subspaces, losing information about cross-subspace structure. The resulting codebooks are data-dependent and require training on a sample of the corpus, which adds complexity and means the codebooks may not generalize well to new data.

Scalar uniform quantization is simple and data-independent but wastes quantization bins on rarely-occupied extremes of the value range. For normalized embeddings with high dimensionality, the coordinate distribution is sharply concentrated near zero, making uniform bins inefficient.

Binary quantization (1-bit per dimension) is extremely compact but introduces substantial retrieval quality loss, especially for high-precision retrieval tasks. It lacks the flexibility to trade off compression ratio against quality.

Previous non-uniform quantization methods for embeddings either require data-dependent codebooks or do not provide theoretical guarantees on inner product error.

## The Unit-Sphere Coordinate Distribution

A key insight underlying TurboQuant is the characterization of the distribution of a single coordinate of a uniformly distributed point on the d-dimensional unit sphere S^(d-1).

For a vector x uniformly distributed on S^(d-1), each individual coordinate x_i follows a distribution with density proportional to (1 - t^2)^((d-3)/2) for t in [-1, 1]. This is the arcsine distribution for d=2, approaches Gaussian as d increases, and for practical embedding dimensions (d=384 or d=768) is an extremely sharp, symmetric distribution concentrated near zero.

The normalizing constant is C_d = Gamma(d/2) / (sqrt(pi) * Gamma((d-1)/2)), which ensures the density integrates to 1 over [-1, 1]. This distribution is equivalent to the scaled Beta distribution: if X ~ Beta((d-1)/2, (d-1)/2) on [0,1], then Y = 2X - 1 follows the unit-sphere coordinate distribution on [-1, 1].

This distribution is entirely determined by the embedding dimension d and is independent of the specific data. This data-independence is a crucial property: the optimal quantization codebook can be computed once from the theoretical distribution and applied to any corpus embedded with the same model.

## Random Rotation for Uniform Energy Distribution

TurboQuant applies a random orthogonal rotation R to each embedding vector x before quantization. The rotation is the same for all vectors and is determined by a random seed stored as part of the quantization state.

The purpose of the rotation is to ensure that the rotated embedding y = R @ x has approximately equal energy across all dimensions. Raw embeddings from neural models often have highly non-uniform energy distribution — some dimensions may carry much more information than others. A fixed quantization scheme applied to such vectors will perform very differently across dimensions.

After a random rotation, by symmetry, each dimension of y has the same expected variance. Moreover, if x is approximately uniformly distributed on the unit sphere, each coordinate of y = R @ x exactly follows the unit-sphere coordinate distribution described above. This justifies applying the same codebook to all dimensions.

The rotation is computed using QR decomposition of a random Gaussian matrix. For a random Gaussian matrix G with entries drawn iid from N(0,1), the orthogonal factor Q from the QR decomposition is uniformly distributed over the group of orthogonal matrices (Haar measure). Alternatively, a Hadamard matrix multiplied by a random diagonal sign matrix provides a structured approximation that can be applied in O(d log d) time.

The inverse of the rotation is simply its transpose (since R is orthogonal), so reconstruction applies R.T to the dequantized vector.

## Lloyd-Max Codebook for the Optimal Scalar Quantizer

TurboQuant uses the Lloyd-Max algorithm to find the optimal scalar codebook for the unit-sphere coordinate distribution. The codebook consists of 2^b reconstruction levels c_1, ..., c_{2^b} that minimize the expected MSE for b-bit quantization.

The Lloyd-Max algorithm alternates between two steps until convergence. In the partition step, the decision boundaries are placed at the midpoints between adjacent reconstruction levels. In the reconstruction step, each reconstruction level is set to the conditional mean of the distribution within the corresponding interval.

Starting from an initial estimate of the reconstruction levels (e.g., the 2^b equal-probability quantiles of the distribution), the algorithm converges in a few dozen iterations. The computational cost is dominated by numerical integration to compute conditional means, which can be done efficiently with quadrature.

The resulting codebook is precomputed once for each (dimension, bits) combination and cached. For dimension 384 with 4-bit quantization, the codebook has 16 entries, requires less than 100 bytes to store, and is shared across all vectors in the corpus.

The Lloyd-Max codebook outperforms uniform quantization, particularly for low bit widths. For 2-bit quantization, the unit-sphere coordinate distribution is so concentrated near zero that a 4-entry uniform codebook with bins spanning [-1, 1] wastes most of its resolution on the tails. The Lloyd-Max codebook places 3 out of 4 entries near zero, drastically reducing MSE.

## TurboQuantMSE Algorithm

The complete TurboQuantMSE algorithm proceeds as follows for each embedding vector x.

Normalization: Store the original L2 norm ||x|| as a float16 value. Normalize x to unit length: x_hat = x / ||x||. (If x is already normalized, the norm is 1.0 and this step has no effect.)

Rotation: Apply the random rotation: y = R @ x_hat. Now y is on the unit sphere and each coordinate approximately follows the theoretical unit-sphere distribution.

Quantization: For each coordinate y_i, find the nearest codebook entry c_{k(i)} using argmin over the codebook. Store the index k(i) using b bits.

Bit packing: Pack all indices using numpy.packbits or equivalent. For b=4 and d=384, this produces 192 bytes of packed indices. For b=2 and d=384, it produces 96 bytes.

Storage: The quantized vector is stored as {packed_indices, norm}. The rotation matrix R and codebook are stored once as shared state.

Reconstruction: Unpack the indices, look up codebook entries to get y_hat, apply the inverse rotation x_hat = R.T @ y_hat, and rescale by the stored norm.

## TurboQuantProd: Bias Correction via QJL

TurboQuantMSE achieves excellent MSE but introduces a systematic bias in inner product estimation. Specifically, E[<q, x_hat>] does not exactly equal <q, x> because the quantization error correlates with the codebook in a biased way for finite b.

TurboQuantProd addresses this bias by adding a secondary quantization of the residual using the Johnson-Lindenstrauss Quantized Estimator (QJL). The residual after TurboQuantMSE quantization is r = y - y_hat, where y = R @ x and y_hat is the MSE reconstruction. The inner product error due to this residual is q.T @ R.T @ r = (R @ q).T @ r.

QJL approximates the inner product with the residual using a random Gaussian projection matrix S in R^(d x d) and 1-bit sign quantization. The sign vector s = sign(S @ r) is stored as a packed bit array (d/8 bytes total). The inner product estimate is reconstructed as (pi/2)/d * gamma * (R @ q).T @ S.T @ s, where gamma = ||r|| is stored as float16.

The total storage for TurboQuantProd with b bits per dimension is: MSE part with (b-1) bits (indices) + QJL part with 1 bit (signs) + gamma (float16). The bits for MSE and QJL sum to b bits total per dimension, maintaining the same overall bit rate.

The key advantage is that QJL provides an unbiased estimator of the inner product with the residual, so TurboQuantProd has smaller expected inner product error than TurboQuantMSE for the same total bit rate.

## Theoretical Guarantees

TurboQuant provides theoretical upper bounds on the expected inner product error between a query q and a quantized document x.

For TurboQuantMSE with b bits and embedding dimension d, the expected squared inner product error is bounded by O(1/(d * 4^b)). This matches the information-theoretic lower bound for scalar quantization up to constant factors, establishing near-optimality.

The bound improves quadratically with the number of bits: each additional bit reduces inner product error by approximately 4x. The dimension d appears in the denominator because with more dimensions, the errors from individual coordinates cancel more effectively (central limit theorem effect).

For TurboQuantProd, the additional QJL step reduces the bias in the inner product estimator. The expected inner product error is bounded by O(1/(d * 4^b)) with a smaller constant than TurboQuantMSE.

These guarantees hold under the assumption that embeddings are approximately uniformly distributed on the unit sphere, which is approximately satisfied for normalized embeddings from modern models with random rotation applied.

## Practical Compression Ratios

With correct bit packing, TurboQuant achieves the following practical compression ratios for a 384-dimensional embedding.

Float32 baseline: 384 * 4 = 1536 bytes per vector.
Float16: 384 * 2 = 768 bytes per vector (2x compression).
TurboQuantMSE 8-bit: ceil(384 * 8 / 8) = 384 bytes per vector (4x compression).
TurboQuantMSE 4-bit: ceil(384 * 4 / 8) = 192 bytes per vector (8x compression).
TurboQuantMSE 2-bit: ceil(384 * 2 / 8) = 96 bytes per vector (16x compression).
TurboQuantProd 4-bit: 192 bytes (3-bit MSE) + 48 bytes (1-bit QJL) + 2 bytes (gamma) = 242 bytes (~6.4x compression).

For a corpus of 1 million documents, TurboQuantMSE 4-bit requires 192 MB versus 1.5 GB for float32, making it feasible to keep the entire embedding corpus in memory on a single server with 256 GB RAM even for corpora of tens of millions of documents.

## Comparison with Other Methods

Experiments in the paper compare TurboQuant against several baselines on standard retrieval benchmarks.

Uniform scalar quantization with the same number of bits consistently underperforms TurboQuant due to suboptimal bin placement. The gap is largest for 2-bit quantization, where TurboQuant's Lloyd-Max codebook allocates most bins near zero while uniform wastes bins on the tails.

FAISS IndexIVFPQ achieves comparable compression ratios but requires data-dependent codebook training and does not provide inner product error guarantees. TurboQuant's data-independent codebook is advantageous in dynamic settings where new documents are added continuously.

Binary quantization (1-bit per dimension, achieved by taking the sign of each coordinate after rotation) is a special case of TurboQuant with b=1. It achieves 16x compression but with substantial recall degradation. TurboQuantProd with b=1 (pure QJL) provides an unbiased estimator that outperforms naive binary quantization.

The paper finds that TurboQuantMSE with 4 bits achieves greater than 95% of float32 retrieval quality (Recall@10) on BEIR benchmarks while using only 1/8 of the memory. TurboQuantProd with 4 bits achieves similar recall with lower inner product bias.

## Implementation Considerations

Several implementation details are important for achieving the theoretical compression ratios and quality guarantees.

The rotation matrix R must be computed and stored as float32. For dimension 384, the rotation matrix is 384 * 384 * 4 = 589,824 bytes (approximately 576 KB). This overhead is shared across all vectors. Alternatively, R can be regenerated from a stored random seed, saving disk space at the cost of recomputation.

The codebook must be precomputed with sufficient precision. Lloyd-Max convergence should be checked by verifying that the codebook MSE has stabilized (change less than 1e-8 between iterations). The final codebook should be stored as float32.

Bit packing should be implemented carefully to avoid off-by-one errors in the bit counts. The packed byte array has length ceil(d * b / 8). Unpacking must correctly handle the last byte, which may be padded with zeros if d * b is not a multiple of 8.

Batch processing is important for efficiency. Quantizing and dequantizing one vector at a time is much slower than processing all N vectors simultaneously using vectorized numpy operations. The rotation can be applied as a single matrix multiplication R @ X.T (where X is the N x d embedding matrix), producing a d x N result matrix.

The random seed for the rotation and the QJL matrix should be stored as part of the quantization state so that the same transformation can be applied to query vectors during retrieval.
