# AI Usage Log

Honest ledger of what was delegated to AI, what was written/verified by hand, where the model misled us, and how each claim was checked. Timestamps are session dates (UTC context of the development box).

## Delegated (AI-authored, human-directed)

| Area | What the AI produced | Direction given by human |
|---|---|---|
| FastAPI routers (`claims`, `approvals`, `auth`, `ask`, `documents`, `usage`) | Initial route handlers, Pydantic schemas, RBAC dependencies | “Match existing `require_role` patterns; no business logic in routes.” |
| Repository layer (`SqlAlchemyClaimRepository`, `InMemoryClaimRepository`, document repo) | ORM mapping, abstract interface implementations | “Domain interfaces stay framework-free; fill every abstract method.” |
| Frontend components (`ClaimAdjudication`, `ApprovalsQueue`, `DocumentIngestion`, `AskQAStream`) | React TSX screens, polling, modals | “State-based SPA (no react-router); credentials include; proxy paths only.” |
| Migrations (`e5f6a7b8c9d0` review columns, users/trace tables) | Alembic revision skeletons | Applied and inspected schema via `docker exec psql` before trusting. |
| Observability sinks (`system_logger`, `claim_logger`, `retrieval_logger`, `token_usage`) | JSON/JSONL writers with locking | “Never raise into the hot path; gitignore sinks.” |
| Unit/contract tests for interfaces and providers | Dummy implementations, mock fixtures | Ran full suite; fixed abstract-method gaps the model left. |
| Documentation drafts (BRD, SYSTEM-DESIGN, SECURITY, EVALUATION) | First drafts | Human rewrote gap tables and acceptance numbers where the model invented metrics. |

## Written / heavily edited by hand

- HITL status machine (`submitted → processing → report_ready → pending_approval → approved/rejected`) and corp delete-lock rules — designed against product requirements, then implemented.
- E2E verification scripts (login cookies, claim lifecycle polling, 409 delete checks) — executed live against `localhost:8000`.
- `docs/AGENTIC-WORKFLOW.md` (this file’s companion) — failure modes taken from real session incidents, not generated from templates.
- Golden-set question authoring review — adversarial categories validated for realism against OWASP LLM Top 10.

## Where the AI misled us (and what we did)

| Incident | How we caught it | Fix |
|---|---|---|
| Claim stuck at `processing` after success (status never advanced) | Live poll of `GET /claims/{id}` | `claim_tasks.py` now sets `report_ready` / `pipeline_stage=done`. |
| `create_retrieval_log` crashed on UUID serialization / missing args | Worker traceback in logs | Optional args + `str(uuid)` + isoformat-safe filters. |
| Tests failed with “abstract methods `list_all`/`delete`…” after interface growth | pytest | Updated *all* dummy repos (unit + integration doubles). |
| Stale `.pyc` made a fixed class still look abstract | Direct `python -c` import after `find … -delete __pycache__` | Documented: clear bytecode and restart workers after edits. |
| Frontend defaulted to `POL-1001` while corpus only had `ISO-PP-00-01` | E2E claim returned `refused` / 0 search hits | Default policy corrected; date_of_loss must be ≥ effective_date. |
| Model claimed “token accounting done” before any sink existed | Grep for `token_usage` returned nothing | Built `token_usage.py` + `/usage` endpoint; added to this log. |
| `pkill -f celery` killed the launching shell (regex self-match) | Tool timeout | Kill by PID list in a separate command. |
| OpenAPI paths (`/api/...`) guessed wrong — actual mounts are unprefixed | `curl /openapi.json` | Always read live OpenAPI. |

## How we verify (standing practice)

1. **Static:** `ruff check src/ tests/` and `npx tsc --noEmit` after every edit batch.
2. **Unit/contract:** `pytest tests/unit tests/contract` (LLM mocked).
3. **Route-level integration:** targeted pytest files that do not require Docker DB/Ollama from host.
4. **Live E2E:** restart backend+workers, login both roles, run full claim HITL path, hit observability sinks (`claim_logs.json`, `retrieval_log.json`, `token_usage.json`, `system_logs.txt`).
5. **OpenAPI truth:** dump paths from the running app rather than trusting memory.

## Hours / scope note (for submission form)

See README “Variant & hours” section for declared variant derivation and honest hour total. This log does not claim flawless AI use — catching model errors *is* part of the demonstrated skill set for the instructor role.
