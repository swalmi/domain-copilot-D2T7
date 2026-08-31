# Business Requirements Document (BRD)

Project: Domain Copilot
Owner: Project Author
Date: 2026-08-31

## 1. Purpose & Scope
Purpose: Provide a concise BRD describing personas, objectives, measurable acceptance criteria, business rules, assumptions, risks, and a traceability matrix linking requirements to implemented components and evidence.

Scope: Ingest policy documents, answer queries with verifiable citations, and execute a multi-agent adjudication workflow with a human approval gate and observability.

Out-of-scope: OCR heavy-lift optimised production pipelines, multi-tenant billing, and fully managed vector DB hosting (these are documented as deferred with mitigations).

## 2. Personas
- Policy Administrator (Corp): uploads policies, manages versions, reviews ingestion status.
- Claims Handler (Client): submits claims, sees adjudication drafts, requests human review.
- Adjudicator (Reviewer): approves/rejects drafts via approval gate.
- Engineering Admin: deploys, monitors, and configures the system.

## 3. Objectives & Measurable Criteria
- O1: Ingest ≥2 input formats (.pdf, .docx, .txt) with idempotent processing. Acceptance: `POST /documents` returns `correlation_id` and records document `content_hash`; re-upload returns `already_ingested`.
- O2: Answer queries with citations. Acceptance: `POST /ask` returns a cited answer structure or explicit refusal when evidence is insufficient.
- O3: Multi-agent workflow. Acceptance: Claim adjudication runs (CoverageMatcher, ExclusionAnalyst, AdjudicationDrafter) with an approval gate step requiring manual approval before final side-effecting actions.
- O4: Observability. Acceptance: `workflow.log` contains detailed JSON trace lines and `/runs/{correlation_id}` returns event lists for an execution.
- O5: Role-based access. Acceptance: `corp` and `client` roles enforced server-side; unauthorized access returns 403.

## 4. Requirements (Unique IDs)

- BR-01: Ingestion pipeline stages (Extract → Clean → Chunk → Embed → Index). Acceptance: APIs and logs show stage transitions and per-document status. Evidence: `src/application/use_cases/ingest_document.py` logs and `workflow.log`.
- BR-02: Idempotent ingestion by content hash. Acceptance: re-upload returns `already_ingested`. Evidence: document repository and `ingest` response includes `existing_document_id`.
- BR-03: Policy selection by document ID in UI. Acceptance: Ask UI dropdown lists ingested documents by ID. Evidence: `frontend/src/components/AskQAStream.tsx`.
- BR-04: Multi-agent orchestrator with tracing. Acceptance: `/claims` returns task and trace available via `/runs/{correlation_id}`. Evidence: `src/application/use_cases/run_adjudication.py` and `src/infrastructure/observability/trace_logger.py`.
- BR-05: Pause/resume across cluster. Acceptance: Pause/resume endpoints pause workers (Redis-backed). Evidence: `src/infrastructure/observability/pause_registry.py` and `src/api/routes/claims.py`.
- BR-06: Authentication and role enforcement. Acceptance: cookie-based JWT session with role checks. Evidence: `src/api/routes/auth.py` and `src/api/deps.py`.

## 5. Business Rules
- Only `corp` users may ingest documents and view trace logs; only `client` users may submit claims.
- Documents are immutable once `status=success` for a given `content_hash`. Re-ingestion creates a new version only when `content_hash` differs.

## 6. Assumptions
- A Redis instance is available for Celery broker and pause registry.
- Local development may use a local runtime or a hosted provider for external processing; provider abstraction supports either.

## 7. Risks & Mitigations
-- R1: Resource-cost abuse — mitigation: per-user budgets and rate limits (configured in `src/api/limiter.py`, design note in docs/SYSTEM-DESIGN.md). Implementation: rate limiter applied to auth endpoints and external-facing operations.
-- R2: Injection via external content — mitigation: sanitisation, strict tool allow-lists, and refusal patterns in evaluation suite.

## 8. Traceability Matrix
| BR-ID | Implemented | Evidence (file / API) |
|---|---:|---|
| BR-01 | Implemented | `src/application/use_cases/ingest_document.py`, `POST /documents` |
| BR-02 | Implemented | `src/infrastructure/db/models.py` (content_hash unique), `ingest_document` response |
| BR-03 | Implemented | `frontend/src/components/AskQAStream.tsx` (documents fetch) |
| BR-04 | Implemented | `src/infrastructure/observability/trace_logger.py`, `/runs/{id}` API |
| BR-05 | Implemented | `src/infrastructure/observability/pause_registry.py` (Redis), `/claims/{id}/pause` |
| BR-06 | Implemented | `src/api/routes/auth.py`, `src/api/deps.py` |

## 9. Acceptance Test Plan (brief)
1. Start services (Postgres, Redis, API, Frontend, Celery worker).
2. Create a `corp` user; upload a PDF. Observe `correlation_id` and `/runs/{correlation_id}`; confirm `workflow.log` events.
3. Re-upload same file → expect `already_ingested`.
4. As `client`, submit claim; observe Celery worker processing and pause/resume behaviour.

---
Document maintained by: Project Author
