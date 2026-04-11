# Information Retrieval Metrics: Recall, MRR, NDCG, and Beyond

## Foundation: The Retrieval Task

Information retrieval is the task of finding relevant items in a collection given a query. The items might be documents, passages, images, or any other indexed content. The query might be a keyword search, a semantic query expressed in natural language, or a vector query embedding.

Evaluating retrieval systems requires ground truth relevance judgments: for a set of queries, which items in the collection are relevant? These judgments are typically binary (relevant or not relevant) for simple benchmarks, or graded (highly relevant, somewhat relevant, not relevant) for more nuanced evaluation.

Given a retrieval system, a set of queries, and relevance judgments, we can compute metrics that quantify how well the system is performing. Good metrics should correlate with user satisfaction, be interpretable, and be robust to variations in corpus and query characteristics.

## Precision and Recall

Precision and recall are the fundamental metrics of classification and retrieval. In the retrieval context, precision measures what fraction of retrieved items are relevant, and recall measures what fraction of all relevant items were retrieved.

Precision at k (P@k) is the fraction of the top-k retrieved items that are relevant. For k=10, it is the number of relevant items among the top 10 results divided by 10. P@k is a precision-at-fixed-depth metric that measures the density of relevant items in the top portion of the ranking.

Recall at k (R@k, also written Recall@k) is the fraction of all relevant items that appear in the top-k retrieved items. If a query has 5 relevant items in the corpus and 4 of them appear in the top 10 results, Recall@10 is 4/5 = 0.80.

For retrieval tasks where each query has only one relevant item (as in pseudo ground truth with topk=1), Recall@k simplifies to the fraction of queries where the relevant item appears in the top k results. This is sometimes called hit rate at k.

The tradeoff between precision and recall is fundamental: a system can achieve high recall by returning many results (including many irrelevant ones), and high precision by returning few results (only when very confident). Metrics at a fixed depth k provide a single operating point on this tradeoff.

## Mean Reciprocal Rank (MRR)

Mean Reciprocal Rank is a metric that rewards systems for placing relevant items high in the ranking. For a query where the first relevant item appears at rank r, the reciprocal rank is 1/r. MRR is the average reciprocal rank over all queries.

A system that always places the relevant item at rank 1 achieves MRR=1.0. A system where the relevant item is always at rank 2 achieves MRR=0.5. If the relevant item never appears in the results, the reciprocal rank for that query is 0.

MRR is particularly suitable for navigational queries where the user wants a single definitive answer. If the first relevant result answers the question completely, the user does not need to look further. MRR rewards finding that first relevant result quickly.

MRR has a practical limitation: it only considers the position of the first relevant item and ignores subsequent relevant items. For queries with multiple relevant items, Mean Average Precision (MAP) or NDCG are more appropriate.

Computing MRR requires a maximum rank cutoff. Typically, only the top 100 or top 1000 results are considered, and queries where no relevant item appears within the cutoff are assigned a reciprocal rank of 0. The sensitivity of MRR to the cutoff depends on the distribution of relevant item positions.

## Normalized Discounted Cumulative Gain (NDCG)

NDCG is a graded relevance metric that accounts for both the relevance of retrieved items and their positions in the ranking. It is the standard metric for evaluation in most competitive information retrieval benchmarks.

The Discounted Cumulative Gain (DCG) at depth k is computed as the sum over the top k positions of the relevance score divided by a position-based discount. The discount is log2(position + 1), which decreases as position increases, reflecting the observation that users are less likely to examine later results.

The Ideal DCG (IDCG) is the DCG that would be achieved by a perfect ranking where items are sorted by decreasing relevance. Normalizing DCG by IDCG gives a score between 0 and 1, where 1 indicates a perfect ranking.

For binary relevance (relevant or not), DCG simplifies to counting how many relevant items appear in the top-k positions, with each one discounted by its rank. NDCG with binary relevance is equivalent to a position-weighted recall.

For graded relevance, NDCG can distinguish between systems that retrieve highly relevant items versus marginally relevant items. A system that places a highly relevant item at rank 1 scores higher NDCG than one that places a marginally relevant item at rank 1.

NDCG@10 is the most commonly reported metric in BEIR and other retrieval benchmarks. It captures performance over the top 10 results, which corresponds to the typical first page of results in a web search or the context window of a RAG system.

## Average Precision and MAP

Average Precision (AP) summarizes the precision-recall curve for a single query. It is computed as the average of precision values at each rank position where a relevant item is found.

For a query with 3 relevant items found at ranks 1, 3, and 7 (with a corpus of 10 items), the AP is (1/1 + 2/3 + 3/7) / 3 = (1.0 + 0.667 + 0.429) / 3 = 0.699. The numerator 1, 2, 3 represents the count of relevant items found up to that rank.

Mean Average Precision (MAP) averages AP over all queries. MAP is sensitive to recall: if a relevant item is missed entirely, its contribution to AP is zero, which reduces MAP significantly.

MAP is commonly used in benchmarks where the complete set of relevant items is known and recall over the full corpus is important. For RAG evaluation with pseudo ground truth where each query has only one relevant item, MAP reduces to MRR.

## Metrics for RAG-Specific Evaluation

Beyond standard IR metrics, RAG systems require evaluation of generation quality in addition to retrieval quality. Several frameworks have been developed for this purpose.

RAGAS (Retrieval Augmented Generation Assessment) provides a set of metrics that evaluate different aspects of RAG system quality. Faithfulness measures whether the generated answer is supported by the retrieved context. Answer relevance measures whether the answer addresses the question. Context precision measures the fraction of retrieved context that is relevant. Context recall measures the fraction of relevant information that was retrieved.

TruEra and ARES are alternative frameworks that use language model judges to evaluate RAG quality. The judge model is prompted with the query, retrieved context, and generated answer, and asked to evaluate specific quality dimensions.

LLM-as-judge evaluation is becoming standard for open-ended generation quality assessment where automated string matching metrics like exact match and F1 are insufficient. The key concern with LLM judges is their potential biases and inconsistencies, which can be mitigated by averaging over multiple runs or using multiple independent judge models.

## Statistical Significance in Retrieval Evaluation

When comparing retrieval systems, it is important to assess whether observed differences in metrics reflect real differences in system quality or are due to sampling variation.

The paired t-test can be applied to compare per-query metric values from two systems. If the same set of queries is used, the per-query scores are paired and the test directly estimates whether the mean difference is significantly nonzero.

For non-parametric comparison, the Wilcoxon signed-rank test is preferred because retrieval metric distributions are often skewed and non-normal. The test ranks the absolute differences and accounts for the direction of each difference.

Bootstrap confidence intervals can be computed by resampling queries with replacement many times and computing the metric on each resample. The percentile interval (5th to 95th percentile of the bootstrap distribution) provides a non-parametric confidence interval.

The number of queries needed for statistical significance depends on the expected effect size. For typical differences between similar retrieval methods (1-3% Recall@10), a test set of 100-1000 queries is usually sufficient to detect statistically significant differences with high power.

## Offline vs Online Evaluation

Offline evaluation uses static test sets with pre-computed relevance judgments to evaluate retrieval quality. It is reproducible and cheap because it does not require user interactions. However, it may not perfectly predict online performance because test set queries may differ from real user queries.

Online evaluation uses live user interactions to measure retrieval quality. Click-through rates, dwell time, and explicit user ratings provide direct evidence of user satisfaction. The challenge is that these signals are noisy and influenced by factors other than retrieval quality (UI design, prior user exposure, query familiarity).

A/B testing is the standard method for online evaluation. Users are randomly assigned to the baseline system (control) or the new system (treatment), and engagement metrics are compared. Online A/B tests require sufficient traffic to detect meaningful differences, typically thousands to tens of thousands of query sessions.

For embedding compression in RAG systems, offline evaluation is the primary method: standardized retrieval benchmarks with known ground truth allow systematic comparison of different quantization methods.

## Evaluation of Embedding Compression Quality

For the specific problem of evaluating embedding quantization, the primary concern is how much retrieval quality degrades as compression increases.

The standard approach is to compare retrieval metrics between the float32 baseline and each compressed variant, using the same ground truth relevance labels and the same queries. The relative difference (compressed - baseline) / baseline gives the degradation as a fraction of baseline performance.

Upper-bounded recall is relevant when pseudo ground truth is used (top-1 float32). In this case, the float32 system achieves 100% Recall@1 by definition. The question is how much of this recall is preserved by compressed variants.

Memory-quality Pareto frontiers plot retrieval quality (Recall@k or NDCG) against memory usage (bytes per vector) for different compression methods and bit rates. Points on the Pareto frontier represent configurations where it is impossible to improve quality without increasing memory. The goal of embedding compression research is to push this frontier upward and to the left.

Compression ratios are computed as float32_bytes / compressed_bytes. For bit-packed quantization, float32_bytes = d * 4 and compressed_bytes = ceil(d * bits / 8). The ratio is (d * 4) / ceil(d * bits / 8) = 32 / bits for cases where d * bits is divisible by 8.

## Practical Considerations for Benchmark Design

Designing retrieval benchmarks for embedding compression evaluation requires careful attention to several factors.

Query diversity is important for representative evaluation. A benchmark dominated by simple factual queries will not capture the performance of more complex semantic queries. Including queries that require reasoning across multiple documents, queries with specialized vocabulary, and queries where relevant documents use very different terminology than the query helps ensure comprehensive evaluation.

Corpus size affects the difficulty of retrieval. Small corpora (a few hundred documents) are too easy because there are fewer candidate documents to confuse with relevant ones. Production corpora for RAG systems typically contain thousands to millions of documents. Benchmarks should use corpora large enough that retrieval is non-trivial.

Ground truth quality is critical. Pseudo ground truth from float32 retrieval is convenient but creates a ceiling effect where float32 by definition achieves perfect recall. Human annotation provides more reliable ground truth but is expensive and may miss some relevant documents.

Temporal consistency ensures that the benchmark can be reproduced across different times and environments. This requires fixing the embedding model version, corpus snapshot, and random seeds used in any stochastic processing steps.
