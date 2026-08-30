# ADR-003: Document Chunking Strategy

## Status
Accepted

## Context
Insurance policy and claim documents encode strict legal meaning across structural boundaries (such as coverage grants, limits of liability, and exclusions). Selecting an appropriate document chunking strategy is critical for RAG accuracy: mixing content across structural boundaries risks legally contradictory information being merged into single retrieval units, while fragmenting tables destroys structured numerical data.

## Decision
We adopt **Unstructured's "By Title" chunking strategy** (`chunking_strategy="by_title"`) for document ingestion over fixed-size, recursive character, semantic, or sentence-window chunking.

Key implementation parameters applied in `load_and_chunk`:
- `chunking_strategy="by_title"`
- `strategy="hi_res"`
- `max_characters=1200`
- `new_after_n_chars=1000`
- `combine_text_under_n_chars=200`
- `multipage_sections=True`
- `overlap=100`
- `overlap_all=False`

### Structural Integrity & Boundary Protection
Insurance policies encode legal force in titled sections (e.g., *Coverage Endorsements*, *Exclusions*, *Limits of Liability*). Establishing chunk boundaries at each new `Title` element ensures that a chunk never spans across distinct legal sections.

### Handling Oversized Sections & Structured Tables
- **Automatic Character Bounding**: Large sections exceeding `max_characters=1200` are automatically split by Unstructured's internal character handling, eliminating the need for a separate manual recursive-character splitting pass.
- **Independent Table Chunks**: `Table` elements are preserved as standalone chunks separate from surrounding narrative text. This guarantees structured numerical data (such as deductible schedules and liability limits) remains cleanly retrievable without narrative contamination.

## Alternatives Considered
- **Semantic Chunking**: Specifically rejected. Coverage grants and their immediately following exclusions frequently share topical similarity (referencing the exact same subject matter, e.g., water damage or property loss) while asserting legally opposite outcomes. Semantic-similarity-based grouping risks incorrectly merging or separating these sections—a direct risk factor for D2's "silent omission" failure mode.
- **Fixed-Size & Recursive Character Chunking**: Rejected because arbitrary character/token cutoffs split sentences and sections mid-clause, stripping legal context from clauses and corrupting table structures.
- **Sentence-Window Chunking**: Rejected due to high retrieval redundancy and inability to preserve structured table layouts.

## References & Citations
- *RAG-from-First-Principles*, Ch. 2, "Using the unstructured tool for document structure-based chunking."
