# ADR-004: Vector store choice (pgvector single-DB with HNSW)

## Status
Accepted

## Context
The domain copilot system requires both relational storage for policy metadata, document tracking, and ingestion state, as well as high-performance vector storage for similarity search over document chunk embeddings. At our target deployment scale (~30 policy documents), system design efficiency, operational simplicity, and minimal container deployment overhead are critical.

## Decision
We select **PostgreSQL + pgvector extension** as a unified single-database solution over operating a dedicated standalone vector database (such as Pinecone, Qdrant, or Weaviate).

### Key Rationale
1. **Single Database Operations**: Satisfies the system architecture requirement for combined relational and vector storage within a single running engine (`pgvector/pgvector:pg16`). This halves Docker Compose service complexity, backup procedures, and migration management compared to running two distinct database services.
2. **Corpus Scale Alignment**: PostgreSQL with `pgvector` easily handles our 30-document corpus scale with sub-millisecond retrieval latency while keeping memory overhead minimal.
3. **HNSW Indexing**: We adopt **HNSW** (Hierarchical Navigable Small World) indexing using cosine distance (`vector_cosine_ops`) over exact/brute-force nearest-neighbor search. HNSW trades a negligible loss in recall for sub-linear query time ($O(\log N)$), representing the standard production choice as documented in *RAG at Scale* (Chapter 3, table on vector DB suitability) and *RAG-from-First-Principles* (ANN algorithm analysis).

## Alternatives Considered
- **Dedicated Vector Database (e.g., Qdrant / Pinecone / Weaviate)**: Offers optimized instant-indexing and ultra-high QPS capabilities for large-scale multi-tenant production deployments (per *RAG at Scale*, Table 3-1). However, introducing a separate vector database service at our current scale adds unnecessary infrastructure complexity without tangible performance gains. This option is deferred to `SYSTEM-DESIGN.md` (Part A) as a target-architecture evolution item.
- **Exact / Flat Nearest-Neighbor Search (No Index)**: Guarantees 100% recall but exhibits $O(N)$ query time complexity, which degrades as chunk count scales.

## Consequences
- **Deployment Efficiency**: A single PostgreSQL container manages relational schemas, full-text GIN search indexes, and HNSW vector similarity indexes.
- **Unified Migrations**: Schema updates and index definitions for both relational data and vector fields are managed atomically via Alembic migrations.
- **Operational Simplicity**: Developers run a lightweight local stack without managing multi-service database credentials or sync pipelines.
