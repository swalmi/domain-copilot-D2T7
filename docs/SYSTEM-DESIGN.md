# System Design Document

Project: Domain Copilot
Date: 2026-08-31

## Overview
This document has two parts: Part A describes the target unconstrained architecture; Part B describes the implemented MVP, a gap table, and design rationale for major decisions.

---

## Part A — Target Architecture (Unconstrained)

- Gateway: API Gateway with managed rate limiting, WAF, TLS, and IP allowlist.
- Secrets manager: Centralised secrets store (HashiCorp Vault / AWS Secrets Manager) for provider API keys, DB credentials.
- Broker: Managed Redis (ElastiCache / Memorystore) for Celery broker, pub/sub, and cache.
- Autoscaling: Container orchestration (EKS/GKE) with HPA for API and workers.
- Caching: Redis for short-lived query caching and pause registry.
- Managed Vector DB: Hosted vector DB (Pinecone/Weaviate/Redis Vector) for large-scale similarity search.
- Observability stack: OpenTelemetry traces + Jaeger, Prometheus metrics, Loki/ELK logs, correlation IDs propagated.
- CI/CD: GitHub Actions for build/test, image publish, and deployment pipelines with branch protection.
- DR/Backup: Scheduled DB snapshots, vector DB export, and object storage backups.
- Cost model: Estimate operational costs and options for lower-cost local deployments.

## Part B — Implemented MVP (what's in this repo)

- API: FastAPI web server (HTTP) with route handlers (ingest, ask, claims, runs, approvals).
- Auth: Cookie-based JWT sessions with role enforcement (`corp`/`client`).
- Ingestion: Extract → Chunk → Embed → Index pipeline implemented in `src/application/use_cases/ingest_document.py` using `PgVectorStore` and an embedding adapter.
- Vector store: `PgVectorStore` backed by `pgvector` (open-source) for MVP deployments.
- Orchestration: Linear orchestrator `RunAdjudicationWorkflowUseCase` executing multiple processing steps with retry/backoff and traces; Celery worker for async jobs.
- Observability: `trace_logger` in-memory store with JSON lines written to `workflow.log`; `/runs/{correlation_id}` API endpoint.
- Pause/Resume: Redis-backed pause registry using `redis.asyncio` with pub/sub to coordinate API & Celery workers.
- Frontend: Vite + React UI with key screens (ingest, ask, claims, trace explorer).

### Gap Table (Target vs Implemented)
| Component | Target | Implemented? | Why deferred / notes | Interim mitigation | Effort to close |
|---|---|---:|---|---|---:|
| Managed rate limiting | API Gateway with global quotas | Partially | App-level rate limiting used (`slowapi`) — not managed | Accept in-process limiter; document gap | ~4h + infra ($) |
| Secrets manager | Vault / AWS Secrets Manager | Deferred | Local `.env` configuration used for dev | Keep `.env.example`; require secret-scan before publish | ~3h + infra ($) |
| Managed vector DB | Pinecone/Weaviate | Deferred | Using `pgvector` for MVP — lower scale | Pgvector is simple to run locally and portable adapters exist | ~6h + $X/month |
| Observability stack | OpenTelemetry + Jaeger + Prometheus + Loki | Partially | Local JSON logs + in-memory traces implemented | Logging + `workflow.log` provides demo-grade observability | ~8h + infra ($) |
| Multi-region availability | Yes | Deferred | Time/resource constraints | Single-region deployment documented and health checks included | ~2-3 days + ops |

## Design Decisions and Alternatives

### 1. Vector Store
- Decision: Use `pgvector` (Postgres + pgvector) for MVP.
- Alternatives: Pinecone, Weaviate, Redis Vector.
- Rationale: Simplicity, free open-source deployment, transactional guarantees with relational DB. Managed solutions deferred due to cost and time.

### 2. Orchestration Pattern
- Decision: Pipeline orchestrator with a supervising use-case and per-step timeouts/retries.
- Alternatives: Stateful workflow engine (Temporal), serverless step functions.
- Rationale: Pipeline is simple to inspect and integrates with approval gate; Temporal adds operational complexity and steep learning curve.

### 3. Provider Abstraction
- Decision: Provider selection is implemented via a pluggable adapter to allow replacing external processing services.
- Rationale: Allows local deployments and hosted-service fallbacks without code changes.
### 4. Pause/Resume
- Decision: Redis key + pub/sub for cluster-safe pause/resume.
- Alternatives: Database-driven locks, distributed job controller.
- Rationale: Redis is already used as Celery broker; pub/sub provides low-latency coordination.

## Operational Runbooks (short)
- Start services: `docker compose up --build` (includes DB, Redis, API, frontend, celery worker in compose if configured).
- Health checks: `GET /health` returns DB and Redis status.

## How to close gaps (effort estimates)
- Add Vault: 3–4 hours to wire secrets + CI integration.
- Deploy managed vector DB: 6–8 hours (incl. migration adapter and testing).
- Full observability stack: 8–12 hours to wire OpenTelemetry + Jaeger + Prometheus + dashboards.

---
Maintainer: Project Author
