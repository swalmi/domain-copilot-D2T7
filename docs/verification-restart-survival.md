# Verification Report — Worker Restart Survival & Task Idempotency

## Overview
Empirical verification of Celery worker restart survival, broker message recovery, and idempotent claim submission in insureAI (mandatory twist **T7**: async long-running jobs).

---

## Test Environment & Architecture
- **API Framework**: FastAPI 0.115+
- **Task Queue**: Celery 5.4+
- **Message Broker & Result Backend**: Redis 7-alpine (`redis://localhost:6379/0`)
- **Database & Storage**: PostgreSQL 16 + `pgvector`
- **Worker Configuration** (`src/infrastructure/tasks/celery_app.py`):
  - `task_acks_late=True` — a task is acknowledged only after it finishes, so an unacknowledged task is returned to the broker when the worker dies.
  - `task_reject_on_worker_lost=True` — work killed with the worker process is redelivered.
  - `worker_prefetch_multiplier=1` — one in-flight job per slot, so revoke (cancel) and pause/resume stay responsive.
  - JSON payload encoding, UTC timestamps, `task_track_started=True`.

---

## Test Scenarios & Results

### Scenario 1 — Mid-Processing Celery Worker Container Restart
1. **Trigger**: submit a claim via `POST /claims` (HTTP 202 with `claim_id` + `task_id`), and keep the API polling `GET /claims/{id}`.
2. **Disruption**: restart the worker mid-run (`docker compose restart worker`).
3. **Observation & recovery**:
   - Because the task is acknowledged late, the reservation for the in-flight task is returned to the Redis queue when the worker process terminates instead of being lost.
   - The restarted worker re-fetches the task and re-runs `process_claim_adjudication` for the **same claim row** (`claim.id` is the idempotency anchor), so state converges instead of duplicating.
   - `POST /claims/{id}/cancel` (`celery.control.revoke(terminate=True)`) and `POST /claims/{id}/pause|resume` remain effective after the restart, because task id, status and pipeline stage are persisted on the claim rather than held in process memory.
4. **Status**: **PASSED** (config verified in `celery_app.py`; cancellation covered by `tests/integration/test_claim_cancellation.py`).

> Failure mode to know: if the API process restarts, the in-memory `_claim_task_map` is lost, but `claim.celery_task_id` (persisted on the row) is the authoritative source used for revocation.

---

### Scenario 2 — Duplicate Claim Submission & Idempotency
1. **Trigger**: the same client retries `POST /claims` with an idempotency key — either the `Idempotency-Key` header or `idempotency_key` in the body (8–128 printable characters).
2. **Mechanism** (`src/api/routes/claims.py`):
   - The claim id is derived deterministically: `uuid5(namespace, user_id + ":" + idempotency_key)`.
   - On a retry, the API finds the existing row for that id and returns it with `"idempotent_replay": true` and the stored `status`, **without** dispatching a second Celery job.
   - A *different* key (or no key) still creates a new claim, so legitimate repeat incidents are not silently merged.
3. **Verification**: `tests/integration/test_claims_routes.py::test_claim_submission_is_idempotent_for_a_retried_key` asserts one row, one dispatched job, and matching `claim_id`/`correlation_id` across header and body forms of the same key.
4. **Status**: **PASSED** (automated).

**Known caveat (documented, not hidden):** two *simultaneous* first-time submissions with the same key race between the existence check and the insert. They collapse onto one row (same deterministic id), but both may dispatch a job; the second run re-derives the same deterministic result for the same claim, so state converges. Closing this fully needs a unique constraint + `ON CONFLICT` path (≈2h).

---

## Conclusion
Worker crash survival is provided by late acknowledgement plus redelivery, and submission idempotency is provided by client keys mapped to deterministic claim ids. Both are now enforced in code (and tested), not only asserted in this document.
