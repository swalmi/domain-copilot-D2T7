# Domain Copilot API Specification

The Domain Copilot API provides endpoints for policy document ingestion, real-time RAG Q&A streaming, automated claim adjudication workflows, manual adjuster approval gates, and step-by-step execution auditing.

---

## Interactive Documentation
When running the FastAPI service locally, interactive API documentation is available at:
- **Swagger UI**: [`http://localhost:8000/docs`](http://localhost:8000/docs)
- **ReDoc**: [`http://localhost:8000/redoc`](http://localhost:8000/redoc)
- **OpenAPI Schema**: [`http://localhost:8000/openapi.json`](http://localhost:8000/openapi.json)

---

## Authentication & Authorization
All non-health endpoints require user authentication via an `httpOnly` JWT session cookie (`access_token`).

### User Roles
- **`client`**: Policyholder — submits/cancels/pauses their own claims, streams Q&A, reviews AI reports. Clients **cannot** approve claims, open `/approvals`, or upload/delete policies (UI hides those controls; API returns 403).
- **`corp`**: Adjuster/admin — ingests documents, reviews `/approvals`, approve/reject/edit-and-approve, delete rules, `/usage`, `/runs`.

Role checks are enforced server-side via `require_role()` (`src/api/deps.py`); hiding UI buttons is not authorisation.

---

## Endpoint Reference

### 1. Health & System Status

#### `GET /health`
Liveness probe indicating the web application server is online.
- **Auth**: None
- **Response `200 OK`**:
```json
{
  "status": "ok",
  "app_name": "Domain Copilot API",
  "version": "1.0.0"
}
```

#### `GET /health/worker`
Liveness probe confirming at least one Celery worker is registered.
- **Auth**: None
- **Response `200 OK`**:
```json
{
  "status": "ok",
  "message": "at least one worker is alive",
  "workers": ["celery@worker1", "celery@worker2"]
}
```

#### `GET /ready`
Readiness probe verifying database (PostgreSQL/SQLite) and Redis connection health.
- **Auth**: None
- **Response `200 OK`**:
```json
{
  "status": "ready",
  "database": "connected",
  "redis": "connected"
}
```

---

### 2. Authentication (`/auth`)

#### `POST /auth/login`
Authenticate user credentials and set an `httpOnly` JWT session cookie.
- **Rate Limit**: 5 requests / minute
- **Auth**: None
- **Request Body**:
```json
{
  "email": "e2ecorp@example.com",
  "password": "password123"
}
```
- **Response `200 OK`**:
```json
{
  "status": "success",
  "user": {
    "id": "11111111-1111-1111-1111-111111111111",
    "email": "e2ecorp@example.com",
    "role": "corp"
  }
}
```

#### `POST /auth/signup`
Register a new account (`role` must be `client` or `corp`) and set the session cookie.
- **Auth**: None
- **Response `201 Created`**: same user envelope as login

#### `GET /auth/me`
Current session profile from the `access_token` cookie.
- **Auth**: Required
- **Response `200 OK`**: `{"id": "...", "email": "...", "role": "corp"}`

#### `GET /auth/clients-count`
Aggregate count of `client` accounts (seeded for homepage stats).
- **Auth**: Required (`role="corp"`)

#### `POST /auth/logout`
Terminate active user session by clearing the JWT cookie.
- **Auth**: Required
- **Response `200 OK`**:
```json
{
  "status": "logged_out"
}
```

---

### 3. Policy Document Management (`/documents`)

#### `POST /documents`
Upload and synchronously ingest policy document files into the vector database.
- **Auth**: Required (`role="corp"`)
- **Content-Type**: `multipart/form-data`
- **Validation**: File extension whitelist (`.pdf`, `.docx`, `.txt`), magic-byte signature check (`%PDF-`, `PK\x03\x04`), and 10MB file size limit.
- **Form Parameters**:
  - `file`: UploadFile (binary)
  - `policy_id`: string (default `"ISO-PP-00-01"`)
  - `policy_type`: string (default `"auto"`)
  - `version`: string (default `"v1"`)
  - `effective_date`: date (`YYYY-MM-DD`)
- **Response `200 OK`**:
```json
{
  "status": "success",
  "inserted_count": 14,
  "policy_id": "ISO-PP-00-01"
}
```

#### `POST /documents/stream`
Same as `POST /documents` but streams ingestion pipeline stage events over SSE for live UI progress.
- **Auth**: Required (`role="corp"`)
- **Content-Type**: `text/event-stream`

#### `GET /documents`
List all uploaded policy documents with processing status.
- **Auth**: None (public read; used by Ask + Dashboard for both roles)
- **Response `200 OK`**:
```json
[
  {
    "id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
    "filename": "homeowners_policy_v1.pdf",
    "status": "ingested",
    "created_at": "2026-08-31T00:00:00Z"
  }
]
```

#### `DELETE /documents/{document_id}`
Remove a document and its chunks from the corpus.
- **Auth**: Required (`role="corp"`)
- **Response `200 OK`**

---

### 4. Policy Q&A & Streaming (`/ask`)

#### `POST /ask`
Stream token-by-token Q&A responses using Server-Sent Events (SSE).
- **Auth**: Required (authenticated session)
- **Response Content-Type**: `text/event-stream`
- **Request Body**:
```json
{
  "query": "What is the deductible for windstorm damage under Section I?",
  "policy_id": "ISO-PP-00-01"
}
```
- **SSE Data Stream Format**:
```http
data: {"token": "The "}

data: {"token": "deductible "}

data: {"token": "is "}

data: {"token": "$500.00."}

data: {"done": true, "citations": [...], "refused": false, "correlation_id": "..."}

data: [DONE]
```
- **Cancellation (FR-6):** aborting the HTTP request (UI **Stop** / `AbortController`) causes the server to detect disconnect, emit `generation/stream_cancelled` to `system_logs.txt`, and stop pulling further LLM tokens. The client may also receive:
```http
data: {"cancelled": true, "correlation_id": "..."}

data: [DONE]
```

---

### 5. Claim Adjudication Workflow (`/claims`)

#### `POST /claims`
Submit a new insurance claim for asynchronous multi-agent adjudication via Celery.
- **Auth**: Required (`role="client"`)
- **Request Body**:
```json
{
  "policy_number": "ISO-PP-00-01",
  "date_of_loss": "2026-08-15",
  "incident_description": "Electrical surge damaged kitchen appliances during storm.",
  "claim_amount_requested": "4500.00"
}
```
- **Response `202 Accepted`**:
```json
{
  "status": "queued",
  "claim_id": "c1a2b3c4-d5e6-7f8a-9b0c-1d2e3f4a5b6c",
  "correlation_id": "f81d4fae-7dec-11d0-a765-00a0c91e6bf6"
}
```

#### `GET /claims` / `GET /claims/{id}`
List claims (client sees own; corp sees all) and retrieve adjudication status, pipeline stage, calculated payout, and recommendation.
- **Auth**: Required (ownership enforced for `client`)
- **Response `200 OK`** (abridged):
```json
{
  "id": "c1a2b3c4-d5e6-7f8a-9b0c-1d2e3f4a5b6c",
  "policy_number": "ISO-PP-00-01",
  "status": "report_ready",
  "pipeline_stage": "done",
  "claim_amount_requested": "4500.00",
  "calculated_payout": "4000.00",
  "deductible_applied": "500.00",
  "final_payout": "4000.00",
  "recommendation": "Approve payout of $4,000.00 after $500.00 deductible.",
  "correlation_id": "f81d4fae-7dec-11d0-a765-00a0c91e6bf6"
}
```

#### `POST /claims/{id}/cancel`
Cancel an active claim and revoke its executing Celery background task.
- **Auth**: Required (`client` owner or `corp`)
- **Response `200 OK`**: `{"status": "cancelled", "claim_id": "..."}`

#### `POST /claims/{id}/pause` · `POST /claims/{id}/resume`
Redis-backed pause/resume of an in-flight adjudication (T7-style control).
- **Auth**: Required (`role="corp"`)

#### `DELETE /claims/{id}`
- **Auth**: Required (`client` owner, or `corp` for any claim)
- **Corp delete lock:** returns **`409 Conflict`** while status ∈ `submitted | processing | report_ready | pending_approval` with detail `Cannot delete an undecided claim. Approve or deny it first before deleting.`
- **Allowed statuses for corp delete:** `approved | rejected | refused | cancelled | failed`
- **Response `200 OK`** after successful delete

> There is **no** client `POST /claims/{id}/submit-for-approval`. After the pipeline finishes, status is `report_ready`; corp picks it up from `/approvals` (or the claim already appears in the corp queue via `list_pending_approvals`).

---

### 6. Adjuster Manual Approval Gate (`/approvals`) — role `corp`

#### `GET /approvals`
List claims available for human review (pending and decided).
- **Auth**: Required (`role="corp"`; `client` → `403`)
- **Response `200 OK`**:
```json
[
  {
    "claim_id": "c1a2b3c4-d5e6-7f8a-9b0c-1d2e3f4a5b6c",
    "policy_number": "ISO-PP-00-01",
    "status": "pending_approval",
    "claim_amount_requested": "4500.00",
    "recommended_payout": "4000.00",
    "final_payout": "4000.00",
    "recommendation_reasoning": "Approve after deductible.",
    "ai_justification": "...",
    "citations": []
  }
]
```

#### `POST /approvals/{claim_id}/approve`
Approve the claim; optional body may adjust payout/justification/notes at decision time.
- **Auth**: Required (`role="corp"`)
- **Request Body (optional)**:
```json
{
  "adjusted_payout": "3750.00",
  "justification": "Depreciation applied per Schedule B.",
  "notes": "Reviewed citations."
}
```
- **Response `200 OK`**: `{"status": "approved", "claim_id": "...", "final_payout": "3750.00"}`

#### `POST /approvals/{claim_id}/reject`
Reject the claim payout request (same optional decision payload).
- **Auth**: Required (`role="corp"`)
- **Response `200 OK`**: `{"status": "rejected", "claim_id": "..."}`

#### `POST /approvals/{claim_id}/edit-and-approve`
Modify payout and approve in one call.
- **Auth**: Required (`role="corp"`)
- **Request Body**:
```json
{
  "adjusted_payout": "3750.00",
  "adjuster_notes": "Adjusted after depreciation."
}
```
- **Response `200 OK`**: `{"status": "approved", "claim_id": "...", "final_payout": "3750.00"}`

All three decisions are audited via `system_logs.txt` (`approval_*` events) and update `final_payout` / `admin_justification` on the claim.

---

### 7. Observability & Tracing (`/runs`, `/usage`)

#### `GET /runs/{correlation_id}`
Ordered execution trace events for a correlation id (PII scrubbed).
- **Auth**: Required (`role="corp"`)
- **Response `200 OK`**: array of `{id, correlation_id, step_name, event_type, payload, timestamp}`

#### `GET /usage` (FR-9 — token & cost accounting)
Per-call LLM usage persisted to `token_usage.json`, filterable by correlation id.
- **Auth**: Required (`role="corp"`)
- **Query**: `?correlation_id=<uuid>&limit=100` (both optional)
- **Response `200 OK`**:
```json
{
  "summary": {
    "total_calls": 30,
    "total_prompt_tokens": 1200,
    "total_completion_tokens": 400,
    "total_tokens": 1600,
    "total_cost_usd": 0.0,
    "by_provider": {"ollama": {"calls": 30, "total_tokens": 1600, "cost_usd": 0.0}},
    "by_correlation_id": {"f81d4fae-...": {"calls": 4, "total_tokens": 220}}
  },
  "entries": [
    {
      "logged_at": "2026-09-24T15:25:06.911+00:00",
      "provider": "ollama",
      "model": "llama3.2:1b",
      "operation": "stream",
      "prompt_tokens": 800,
      "completion_tokens": 120,
      "total_tokens": 920,
      "cost_usd": 0.0,
      "correlation_id": "f81d4fae-...",
      "metadata": {}
    }
  ],
  "filtered_by_correlation_id": null
}
```

#### `GET /usage/summary`
Aggregate totals only (no entry list). **Auth**: `role="corp"`.

---

## Error Handling Standards

All API errors return standardized JSON responses adhering to RFC 7807:

| Status Code | Description | Example Cause |
| :--- | :--- | :--- |
| `400 Bad Request` | Payload or file validation failure | Invalid file extension or corrupted magic bytes |
| `401 Unauthorized` | Missing or invalid authentication token | Absent or expired `access_token` cookie |
| `403 Forbidden` | Insufficient role permissions | `client` accessing `/approvals` or `/usage` |
| `404 Not Found` | Requested resource does not exist | Invalid `claim_id` or `correlation_id` |
| `409 Conflict` | State-machine violation | Corp `DELETE` on undecided claim (`pending_approval`, etc.) |
| `429 Too Many Requests` | Rate limit threshold exceeded | Exceeding 5 logins / minute |
| `500 Internal Error` | Unexpected backend server error | Database or unhandled exception |

#### Error Response Format
```json
{
  "detail": "Invalid file content signature: File content does not match PDF magic bytes."
}
```
