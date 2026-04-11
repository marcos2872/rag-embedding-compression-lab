# Redis: In-Memory Data Structures and Caching Patterns

## Overview of Redis

Redis (Remote Dictionary Server) is an open-source, in-memory data structure store that can be used as a database, cache, message broker, and streaming engine. Originally developed by Salvatore Sanfilippo in 2009, Redis has become one of the most widely deployed databases in the world due to its exceptional performance, simplicity, and versatility.

Redis stores all data in memory by default, which enables sub-millisecond read and write latency for most operations. It supports persistence through snapshots (RDB) and append-only files (AOF), allowing data to survive process restarts without sacrificing its in-memory performance characteristics.

Redis is single-threaded for command processing, which eliminates the need for locks and makes its performance highly predictable. Modern versions use multiple threads for I/O and background operations, but the command processing thread remains single-threaded. This design achieves very high throughput (over 1 million operations per second on commodity hardware) with consistent low latency.

## Core Data Structures

Redis provides a rich set of data structures, each optimized for specific use cases.

Strings are the simplest and most versatile data type. A Redis string can hold text, binary data, integers, or floating-point numbers, up to 512 MB. String commands include SET, GET, APPEND, STRLEN, INCR, DECR, and many more. Atomic increment operations make strings ideal for counters, rate limiters, and distributed locks.

Lists are ordered sequences of strings, implemented as doubly-linked lists. They support efficient push and pop operations at both ends, making them ideal for queues, stacks, and activity feeds. LPUSH, RPUSH, LPOP, RPOP, LRANGE, and LINDEX are the primary list commands. Lists can contain up to 2^32 - 1 elements.

Hashes are maps between string fields and string values, similar to Python dictionaries. They are ideal for storing object attributes. HSET, HGET, HMSET, HMGET, HGETALL, and HDEL are the primary hash commands. Hashes are memory-efficient for small objects because Redis uses a compact encoding for hashes with fewer than 128 fields.

Sets are unordered collections of unique strings. Set operations include SADD, SREM, SMEMBERS, SCARD, SINTER, SUNION, and SDIFF. The intersection, union, and difference operations make sets powerful for implementing relationships and faceted search.

Sorted sets (ZSets) combine a set of unique strings with floating-point scores. Elements are stored sorted by score, enabling efficient range queries. ZADD, ZREM, ZRANGE, ZRANGEBYSCORE, ZSCORE, and ZRANK are primary sorted set commands. Sorted sets are ideal for leaderboards, rate limiters, and time-series data.

Bitmaps are not a separate data type but string operations on bit positions within a string value. SETBIT, GETBIT, BITCOUNT, and BITOP enable efficient storage and manipulation of bit arrays, ideal for user activity tracking and feature flags at scale.

HyperLogLog is a probabilistic data structure for counting unique elements with a fixed memory footprint of approximately 12 KB per HyperLogLog, regardless of the number of unique elements counted. PFADD and PFCOUNT are the primary commands. The count is an approximation with less than 1% standard error.

Streams are an append-only log data structure for message streaming use cases. They support consumer groups, allowing multiple consumers to process messages from the same stream with delivery guarantees. Streams are Redis's most complex data structure and are suitable for event sourcing, activity feeds, and inter-service messaging.

## Caching Patterns

Redis is most commonly deployed as a cache in front of a slower data store. Several caching patterns have emerged as best practices.

Cache-aside (lazy loading) is the most common pattern. The application first checks the cache; on a miss, it reads from the database, writes the result to the cache with an expiration time (TTL), and returns the result. Subsequent reads within the TTL are served from the cache. This pattern tolerates cache failures gracefully because the application can always fall back to the database.

Write-through caching writes to both the cache and the database simultaneously on every write. This ensures the cache is always consistent with the database at the cost of higher write latency. Cache failures can be tolerated by writing directly to the database.

Write-behind (write-back) caching writes to the cache first and asynchronously flushes changes to the database. This reduces write latency but risks data loss if the cache fails before the flush completes. It is suitable for write-heavy workloads where some data loss is acceptable.

Cache warming pre-populates the cache with frequently accessed data before traffic begins, avoiding cache misses and thundering herd problems during startup.

TTL (Time-To-Live) management is critical for cache consistency. Setting appropriate TTLs requires understanding the staleness tolerance of each type of cached data. Configuration data might have TTLs of hours or days, while user session data might have TTLs of minutes.

## Persistence Options

Redis provides two persistence mechanisms that can be used independently or together.

RDB (Redis Database) creates point-in-time snapshots of the dataset to disk. The SAVE command blocks until the snapshot is complete. The BGSAVE command creates the snapshot in a background child process without blocking the server. RDB files are compact and restore quickly, making them suitable for backups and disaster recovery.

AOF (Append Only File) logs every write command executed by the server. On restart, Redis replays the AOF to reconstruct the dataset. AOF can be configured to fsync (flush to disk) on every write, every second, or never, providing a configurable durability tradeoff. AOF provides better durability guarantees than RDB at the cost of larger file sizes and slower startup.

In production, many deployments use both RDB and AOF together: AOF for durability and RDB for faster restarts and backups.

Redis 7.0 introduced RDB-AOF (also called dual format) which combines the compactness of RDB with the durability of AOF.

## Replication and High Availability

Redis supports primary-replica replication where one primary node serves all writes and replicas asynchronously receive all writes from the primary. Replicas can serve read queries, distributing read load. Replication is eventually consistent by default.

Redis Sentinel provides automatic failover for Redis deployments. Sentinel processes monitor the primary and replicas, and when the primary fails, Sentinel automatically promotes a replica to primary and reconfigures other replicas to follow the new primary. Client libraries can connect to Sentinel to discover the current primary address.

Redis Cluster is the native sharding solution that distributes data across multiple Redis nodes using consistent hashing over 16384 hash slots. Each slot range is assigned to a primary node with one or more replicas. Redis Cluster provides automatic failover within each slot group and can scale horizontally by adding nodes and rebalancing slots.

## Redis as a Vector Database: Redis VSS

Redis Vector Similarity Search (VSS) adds vector search capabilities to Redis through the RediSearch module. It enables storing vectors alongside other data and querying for approximate nearest neighbors using the same Redis connection.

Redis VSS supports FLAT (exact search) and HNSW (approximate search) index types with cosine, L2, and inner product distance metrics. Vector fields can be combined with other RediSearch field types (text, numeric, tag) to enable hybrid search that combines semantic similarity with attribute filtering.

The integration of vector search with Redis's existing data structures enables powerful patterns. For example, user session data, recent activity, and vector embeddings can all be stored in the same Redis hash, and searched together.

For RAG applications, Redis VSS can serve as both the document store and the vector search engine, simplifying the infrastructure stack. Documents are stored as Redis hashes with text, metadata, and embedding vector fields. Queries retrieve the k nearest vectors and the associated text in a single query.

## Redis in Machine Learning Infrastructure

Beyond caching and vector search, Redis serves many roles in ML infrastructure.

Feature stores use Redis to serve pre-computed features to ML models at low latency. Training features are computed offline and stored in Redis; online inference reads features from Redis in real time. The sub-millisecond read latency of Redis is critical for models that require dozens of features per inference.

Model serving uses Redis to store model artifacts, share state between model servers, and coordinate distributed inference. The pub/sub messaging capabilities enable real-time notification when models are updated.

Experiment tracking and hyperparameter optimization use Redis as a shared state store for distributed optimization frameworks. Workers can read and write trial results atomically, enabling efficient parallel search over hyperparameter spaces.

Task queuing uses Redis lists or streams as reliable message queues for background workers. Libraries like Celery and RQ (Redis Queue) are built on this pattern, enabling asynchronous task execution at scale.

Session management stores user sessions as Redis hashes with TTL expiration, providing fast session lookup and automatic cleanup of expired sessions.

## Performance and Sizing

Redis performance depends on several factors: the data structure used, operation complexity, network round-trip time, and memory capacity.

Simple GET and SET operations with small values achieve over 1 million operations per second on a single Redis instance running on commodity hardware. Complex operations like SORT or ZUNIONSTORE on large datasets are proportionally slower due to their higher computational complexity.

Memory sizing requires estimating the size of all data that needs to be kept in memory, including Redis overhead. Redis uses approximately 100 bytes of overhead per key in addition to the actual value size. For a cache of 1 million string values averaging 100 bytes each, the total memory requirement is approximately 200 MB.

The maxmemory configuration limits Redis memory usage. When memory is full, the eviction policy determines which keys to remove. LRU (least recently used) and LFU (least frequently used) eviction policies are commonly used for caches to remove the least valuable data first.

Memory fragmentation is a common Redis performance issue. When keys of varying sizes are frequently added and deleted, the memory allocator may have fragmented free memory that cannot be reclaimed without compacting. The activedefrag configuration option enables automatic defragmentation in Redis 4.0 and later.

Network latency dominates Redis latency for small operations. Pipelining multiple commands into a single network round trip dramatically improves throughput by reducing the number of round trips. MULTI/EXEC transactions batch multiple commands atomically. Lua scripts execute arbitrary logic server-side, eliminating multiple round trips for complex operations.

## Monitoring and Observability

The INFO command returns a comprehensive overview of the Redis server state, including memory usage, connected clients, replication status, persistence statistics, and command statistics. This is the primary source of operational metrics for Redis.

The SLOWLOG command records commands that exceed a configurable execution time threshold. Analyzing slow commands helps identify performance bottlenecks caused by expensive operations on large data structures.

MONITOR streams all commands processed by the server in real time, which is useful for debugging but should be disabled in production due to its performance impact.

The LATENCY subsystem tracks latency spikes caused by disk I/O, memory operations, and other factors. The LATENCY HISTORY and LATENCY LATEST commands provide insight into latency patterns over time.

Commercial monitoring tools like RedisInsight, Datadog Redis integration, and Prometheus with the Redis exporter provide dashboards and alerting for Redis deployments. Key metrics to monitor include used_memory, connected_clients, keyspace hits and misses, evicted_keys, and rdb_last_save_time.
