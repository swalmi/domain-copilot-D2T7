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
- **`claims_handler`**: Standard user capable of uploading documents, streaming Q&A, and submitting/canceling claims.
- **`adjuster`**: Senior user possessing elevated privileges to view and act upon the manual approval queue (`/approvals`).

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
  "email": "adjuster@domaincopilot.com",
  "password": "SecurePassword123!"
}
```
- **Response `200 OK`**:
```json
{
  "status": "success",
  "user": {
    "id": "11111111-1111-1111-1111-111111111111",
    "email": "adjuster@domaincopilot.com",
    "role": "adjuster"
  }
}
```

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
- **Auth**: Required (`claims_handler` or `adjuster`)
- **Content-Type**: `multipart/form-data`
- **Validation**: File extension whitelist (`.pdf`, `.docx`, `.txt`), magic-byte signature check (`%PDF-`, `PK\x03\x04`), and 10MB file size limit.
- **Form Parameters**:
  - `file`: UploadFile (binary)
  - `policy_id`: string (default `"POL-1001"`)
  - `policy_type`: string (default `"home"`)
  - `version`: string (default `"v1"`)
  - `effective_date`: date (`YYYY-MM-DD`)
- **Response `200 OK`**:
```json
{
  "status": "success",
  "inserted_count": 14,
  "policy_id": "POL-1001"
}
```

#### `GET /documents`
List all uploaded policy documents with processing status.
- **Auth**: Required
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

---

### 4. Policy Q&A & Streaming (`/ask`)

#### `POST /ask`
Stream token-by-token Q&A responses using Server-Sent Events (SSE).
- **Auth**: Required
- **Response Content-Type**: `text/event-stream`
- **Request Body**:
```json
{
  "query": "What is the deductible for windstorm damage under Section I?",
  "policy_number": "POL-1001"
}
```
- **SSE Data Stream Format**:
```http
data: {"token": "The "}

data: {"token": "deductible "}

data: {"token": "is "}

data: {"token": "$500.00."}

data: [DONE]
```

---

### 5. Claim Adjudication Workflow (`/claims`)

#### `POST /claims`
Submit a new insurance claim for asynchronous multi-agent adjudication via Celery.
- **Auth**: Required
- **Request Body**:
```json
{
  "policy_number": "POL-1001",
  "date_of_loss": "2026-08-01",
  "incident_description": "Water pipe leak caused damage to wooden flooring in living room.",
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

#### `GET /claims/{id}`
Retrieve adjudication status, calculated payout, and recommendation for a claim.
- **Auth**: Required
- **Response `200 OK`**:
```json
{
  "id": "c1a2b3c4-d5e6-7f8a-9b0c-1d2e3f4a5b6c",
  "policy_number": "POL-1001",
  "status": "approved",
  "claim_amount_requested": "4500.00",
  "calculated_payout": "4000.00",
  "deductible_applied": "500.00",
  "recommendation": "Approve payout of $4,000.00 after $500.00 deductible.",
  "created_at": "2026-08-31T00:10:00Z"
}
```

#### `POST /claims/{id}/cancel`
Cancel an active claim and revoke its executing Celery background task.
- **Auth**: Required
- **Response `200 OK`**:
```json
{
  "status": "cancelled",
  "claim_id": "c1a2b3c4-d5e6-7f8a-9b0c-1d2e3f4a5b6c"
}
```

---

### 6. Adjuster Manual Approval Gate (`/approvals`)

#### `GET /approvals`
Retrieve list of pending claim adjudication recommendations requiring manual review.
- **Auth**: Required (`role="adjuster"` required, returns `403 Forbidden` for handlers)
- **Response `200 OK`**:
```json
[
  {
    "claim_id": "c1a2b3c4-d5e6-7f8a-9b0c-1d2e3f4a5b6c",
    "policy_number": "POL-1001",
    "status": "pending_approval",
    "claim_amount_requested": "15000.00",
    "recommended_payout": "14000.00",
    "recommendation_reasoning": "High-value claim requiring manual adjuster authorization."
  }
]
```

#### `POST /approvals/{id}/approve`
Approve recommended payout amount.
- **Auth**: Required (`role="adjuster"`)
- **Response `200 OK`**:
```json
{
  "status": "approved",
  "claim_id": "c1a2b3c4-d5e6-7f8a-9b0c-1d2e3f4a5b6c"
}
```

#### `POST /approvals/{id}/reject`
Reject claim payout request.
- **Auth**: Required (`role="adjuster"`)
- **Response `200 OK`**:
```json
{
  "status": "rejected",
  "claim_id": "c1a2b3c4-d5e6-7f8a-9b0c-1d2e3f4a5b6c"
}
```

#### `POST /approvals/{id}/edit-and-approve`
Modify payout amount and approve claim.
- **Auth**: Required (`role="adjuster"`)
- **Request Body**:
```json
{
  "override_payout": "12000.00",
  "adjuster_notes": "Adjusted payout based on depreciation policy Schedule B."
}
```
- **Response `200 OK`**:
```json
{
  "status": "approved",
  "claim_id": "c1a2b3c4-d5e6-7f8a-9b0c-1d2e3f4a5b6c",
  "final_payout": "12000.00"
}
```

---

### 7. Observability & Tracing (`/runs`)

#### `GET /runs/{correlation_id}`
Retrieve sequential execution trace events for auditing agent decisions with scrubbed PII.
- **Auth**: Required
- **Response `200 OK`**:
```json
[
  {
    "id": "e4d3c2b1-a099-8877-6655-4433221100fe",
    "correlation_id": "f81d4fae-7dec-11d0-a765-00a0c91e6bf6",
    "step_name": "CoverageMatcher",
    "event_type": "input",
    "payload": {
      "kwargs_keys": ["policy_number", "incident_description"]
    },
    "timestamp": "2026-08-31T00:10:01Z"
  },
  {
    "id": "f5e4d3c2-b1a0-9988-7766-554433221100",
    "correlation_id": "f81d4fae-7dec-11d0-a765-00a0c91e6bf6",
    "step_name": "AdjudicationDrafter",
    "event_type": "decision",
    "payload": {
      "payout": "4000.00",
      "user_email": "[REDACTED_EMAIL]"
    },
    "timestamp": "2026-08-31T00:10:04Z"
  }
]
```

---

## Error Handling Standards

All API errors return standardized JSON responses adhering to RFC 7807:

| Status Code | Description | Example Cause |
| :--- | :--- | :--- |
| `400 Bad Request` | Payload or file validation failure | Invalid file extension or corrupted magic bytes |
| `401 Unauthorized` | Missing or invalid authentication token | Absent or expired `access_token` cookie |
| `403 Forbidden` | Insufficient role permissions | Non-adjuster accessing `/approvals` |
| `404 Not Found` | Requested resource does not exist | Invalid `claim_id` or `correlation_id` |
| `429 Too Many Requests` | Rate limit threshold exceeded | Exceeding 5 logins / minute |
| `500 Internal Error` | Unexpected backend server error | Database or unhandled exception |

#### Error Response Format
```json
{
  "detail": "Invalid file content signature: File content does not match PDF magic bytes."
}
```
