# Architecture Documentation

This file contains C4 diagrams (levels 1-3), data-flow notes, ER diagram summary, layer-dependency mapping, and ADRs.

## C4 - Level 1 (System Context)
```mermaid
graph LR
  User[User (Browser)] -->|HTTP| WebApp[Frontend (Vite/React)]
  WebApp -->|REST| API[Domain Copilot API (FastAPI)]
  API -->|SQL| Postgres[(Postgres + pgvector)]
  API -->|Broker| Redis[(Redis - broker & pause registry)]
  API -->|Celery tasks| Celery[Celery Workers]
  Celery -->|LLM calls| LLM[LLM Provider (Ollama/OpenRouter)]
  API -->|External calls| ExternalService[External service]
  API -->|Logs/Traces| workflowLog[workflow.log]
```

## C4 - Level 2 (Container)
```mermaid
sequenceDiagram
  participant U as User
  participant FE as Frontend
  participant API as FastAPI
  participant DB as Postgres
  participant RB as Redis
  participant CW as Celery Worker
  participant ExternalService as External service

  U->>FE: Interact (ingest, ask, claim)
  FE->>API: POST /documents (file)
  API->>DB: persist document record (processing)
  API->>API: run ingestion pipeline (extract->chunk)
  API->>ExternalService: external processing requests
  API->>Postgres: upsert chunks (pgvector)
  API->>RB: publish trace events & pause keys
  FE->>API: POST /claims -> API enqueues Celery task
  CW->>API: fetch claim data, run orchestrator
  CW->>ExternalService: external processing calls
  CW->>RB: check pause key; wait via pub/sub if paused
  CW->>API: write final claim state
```

## Data-flow and Trust Boundaries
- Client browser ↔ API: authenticated cookie-based session. TLS required in production.
- API ↔ External service: requests and retrieved content are sent; sanitize retrieved content before inclusion.
- Storage: Document contents stored only as chunked text and fingerprints; originals may be stored in object storage per policy.

## ER Diagram (summary)
- `documents` (id, filename, content_hash, status, created_at)
- `chunks` (id, document_id, policy_id, text, content_hash, embedding)
- `users` (id, email, hashed_password, role)
- `trace_events` (id, correlation_id, step_name, event_type, payload, timestamp)

## Layer-Dependency Diagram
- UI (React) -> HTTP API (FastAPI) -> Application (use-cases) -> Domain (entities/contracts) -> Infrastructure (DB, VectorStore, External service, Redis)

## ADRs (Architectural Decision Records)

### ADR-001: Chunking Strategy & Retrieval
- Decision: Fixed-size semantic chunks with table/title linking and policy-aware metadata.
- Rationale: Policies contain sections and tables; chunking by logical section plus overlap yields better citation mapping.
- Consequence: Simpler retrieval by metadata filters (policy_id, version) and chunk-level citations.

### ADR-002: Orchestration Pattern
- Decision: Pipeline orchestrator (supervised linear pipeline) with per-step timeouts and retry/backoff.
- Rationale: Easier to audit and replay; approval gate fits naturally between steps.

### ADR-003: Vector Store
- Decision: `pgvector` (Postgres extension) for MVP.
- Rationale: Avoids vendor lock-in and is easy to run locally and in CI.

### ADR-004: Pause/Resume Implementation
- Decision: Redis-based key + pub/sub.
- Rationale: Works across processes; leveraging existing Redis broker avoids adding new infra.

---
Files with diagrams source committed. Maintainer: Project Author
