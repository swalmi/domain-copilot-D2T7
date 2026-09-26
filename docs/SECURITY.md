# Security Report

Scope: the `insureAI` codebase at commit `c5d4ce2` (PR #160). Every claim below
cites `file:line`. Where a control is **absent**, that is recorded as a finding,
not omitted — this report is meant to be auditable, not flattering.

Legend: **PRESENT** · **PARTIAL** · **ABSENT** (control does not exist) ·
**DOC DRIFT** (documentation and code disagree).

---

## Summary

| # | Control | Status | One-line verdict |
|---|---|---|---|
| 1.1 | Password hashing | **PARTIAL** | bcrypt cost 12 ✔, but a 73–128 char password returns HTTP 500 |
| 1.2 | Session token | **PARTIAL** | HS256 pinned ✔, no revocation, and a **hardcoded default secret** |
| 1.3 | Session cookie | **PARTIAL** | `httponly` + `samesite=lax` ✔, **`secure` flag missing** |
| 1.4 | Role model | **PARTIAL** | Two roles, free-form DB string, no CHECK constraint |
| 2.1 | Route-level RBAC | **PARTIAL** | 20/23 routes correct |
| 2.2 | `POST /ask` authentication | **ABSENT** | Documented as authenticated; **requires no auth at all** |
| 2.3 | Claim ownership check | **ABSENT** | Null-owner claims readable/cancellable/deletable by any client |
| 3.1 | Prompt delimiters | **PRESENT** | All four prompts delimit and instruct |
| 3.2 | Retrieved-text sanitisation / tool allow-list | **PARTIAL** | No sanitisation at all, but the closed tool set holds — though the check fails open |
| 3.3 | Refusal / confidence gate | **PRESENT** | Cosine-distance gate, `MAX_COSINE_DISTANCE=0.35` |
| 3.4 | Output validation | **PARTIAL** | Pydantic contracts ✔; no grounding check |
| 3.5 | Injection tests | **PARTIAL** | Tests never reach the LLM; eval not in CI |
| 4.1 | Input bounds | **PARTIAL** | `AskRequest.query` and `adjuster_notes` unbounded |
| 4.2 | Upload validation | **PRESENT** | Extension **and** magic-byte check, 10 MB cap |
| 4.3 | Path traversal | **PRESENT** | Temp files only, cleaned up in `finally` |
| 5.1 | Committed live secrets | **ABSENT** | No real credential in the repo (good) |
| 5.2 | Hardcoded fallback secrets | **PARTIAL** | `JWT_SECRET` and DB password have source defaults |
| 5.3 | CORS | **PRESENT** | Wildcard explicitly rejected at config; unit-tested |
| 5.4 | Security headers | **PARTIAL** | `nosniff`/`DENY`/HSTS ✔; no CSP, no `no-store` |
| 6.1 | Rate limiting | **PARTIAL** | Middleware never registered ⇒ *no* limit applies, not even the 5/min on login |
| 6.2 | LLM timeouts | **ABSENT** | No timeout on either provider client |
| 6.3 | Retry/backoff | **PARTIAL** | One no-backoff fallback; 180 s × 2 worst case per agent |
| 7.1 | CI gates | **PARTIAL** | Tests and gitleaks run; audits are advisory-only |
| 7.2 | Branch protection | **ABSENT** | Manual workflow; required-check name does not match job names |
| 8.1 | Seeded demo accounts | **PARTIAL** | Now aligned to `client`/`corp`; passwords are plaintext in git |
| 9.1 | PII scrubbing | **PARTIAL** | 3 regexes, and **not** applied to the highest-volume sinks |

**Highest-impact findings**, in the order I would fix them:

1. `POST /ask` is unauthenticated (§2.2) — anonymous LLM spend, embedding calls and
   corpus access, with no effective rate limit (§6.1).
2. Null-owner claim bypass (§2.3) — horizontal privilege escalation on PII: any
   authenticated `client` can read, cancel and delete the claim.
3. Hardcoded `JWT_SECRET` default (§1.2) — `/auth/signup` is open, so a forgotten
   `JWT_SECRET` means anyone can mint their own `corp` token.
4. Missing cookie `secure` flag (§1.3) — the session token is sent over plaintext
   HTTP, and `docker/nginx.conf:23` rewrites the cookie without adding it either.
5. Login rate limiting is inert *and* mis-keyed (§6.1) — not only is the advertised
   5/min not enforced, the key function sees only the proxy IP, so if it were
   enforced it would lock out every user after 5 attempts globally.

---

## 1. Authentication and session

### 1.1 Password hashing — **PARTIAL**

bcrypt via the raw `bcrypt` library, cost 12, per-hash random salt, constant-time
`checkpw` — `src/api/routes/auth.py:38-47`. This is the correct primitive.

Two defects:

- **72-byte cliff → HTTP 500.** `SignupRequest.password` allows 8–128 characters
  (`auth.py:27`), but `bcrypt==5.0.0` raises `ValueError` above 72 **bytes**. A
  73–128 character password passes validation and then crashes inside
  `hash_password`, and the only exception handler registered on the app is for
  `RateLimitExceeded` (`src/api/main.py:49-50`), so the `ValueError` surfaces as an
  unhandled 500. `LoginRequest.password` (`auth.py:35`) has no maximum
  at all, so the same crash is reachable pre-authentication.
  *Fix:* cap both at 72 bytes, or pre-hash with SHA-256 before bcrypt.
- **`passlib` is declared but never imported.** `passlib==1.7.4` is pinned in
  `requirements.txt:22` and `requirements.base.txt:18` and installed into the venv,
  but `grep -rn passlib src/ tests/ scripts/` returns nothing — the code calls the
  raw `bcrypt` library directly (`auth.py:5,38-47`). The dependency implies a
  stronger KDF wrapper than is in use and widens the supply-chain surface for no
  benefit. *Fix:* remove it from all three files.

### 1.2 Session token — **PARTIAL**

`PyJWT`, HS256, 24 h lifetime, in an `access_token` cookie
(`auth.py:50-58`, `:99-105`). The decoder pins `algorithms=[settings.jwt_algorithm]`
(`src/api/deps.py:165-169`), which correctly closes the algorithm-confusion class.

Gaps:

- **No revocation.** `logout` only clears the browser cookie
  (`auth.py:173-178`). A captured token is replayable for its full 24 h. No `jti`,
  no denylist, no token version.
- **No database revalidation.** `get_current_user` (`deps.py:154-185`) decodes the
  token and returns a `UserPayload` **without querying `users`**. A demoted or
  deleted user keeps access until expiry.
- **Hardcoded default secret.** `jwt_secret` defaults to the literal
  `"domain-copilot-jwt-secret-key-must-be-at-least-32-bytes"`
  (`src/infrastructure/config.py:35`) and the stated length requirement is never
  validated. `/auth/signup` is open (`auth.py:69`), so an outsider can mint an
  arbitrary `corp` token **if the operator forgets to set `JWT_SECRET`**.
  *Fix:* fail startup if the secret is unset or is the default.
- `Settings.model_config` uses `extra="ignore"` (`config.py:11-13`), so a typo
  like `JWT_SECERT=` is silently dropped and the hardcoded default is used — a
  security-critical misconfiguration with no error and no log line.
- No `aud`/`iss` validation. `VALID_ROLES` (`auth.py:20`) is dead code; the real
  enforcement is `Literal["client","corp"]` on the request model (`auth.py:28`).

### 1.3 Session cookie — **PARTIAL**

```python
response.set_cookie(key="access_token", value=token,
                    httponly=True, samesite="lax", max_age=86400)
```
— `auth.py:99-105` and `:136-142`

- `httponly=True` **PRESENT** — blocks XSS token theft.
- `samesite="lax"` **PRESENT** — baseline CSRF mitigation.
- **`secure=` ABSENT.** Confirmed by grep across `src/` and `frontend/src/`. The
  cookie is therefore sent over plaintext HTTP. HSTS is set
  (`src/api/main.py:67`) but is a no-op without TLS termination.
- No CSRF tokens anywhere (grep `csrf` → nothing). Residual risk is genuinely low
  because `SameSite=Lax` plus JSON-only bodies force a preflight, but this is
  defence-by-configuration.
- No `Authorization`-header path: `get_current_user` reads the cookie only
  (`deps.py:155`), so there is no service-to-service auth.

### 1.4 Roles — **PARTIAL**

Exactly two roles, `client` and `corp`; `corp` is a single all-powerful bucket
with no admin/adjuster split. `require_role` matches by exact string
(`deps.py:194`). `UserPayload.role` is an unconstrained `str` (`deps.py:38`) and
the DB column is a bare `String` with **no CHECK constraint and no enum**
(`src/infrastructure/db/migrations/versions/a1b2c3d4e5f6_*.py:28`).

**Fixed in PR #161:** `scripts/seed_users.py` seeded roles `claims_handler` and
`adjuster`, which are outside the accepted set, so the demo accounts could
authenticate but were refused by every protected route. The seeder now creates
`corp` + `client` and reconciles the role of an existing row on re-run.

---

## 2. Authorization

### 2.1 Route matrix — **PARTIAL**

| Endpoint | Required | Code | Matches docs? |
|---|---|---|---|
| `GET /health`, `/health/worker`, `/ready` | none | `routes/health.py` | ✔ |
| `POST /auth/login`, `/auth/signup` | none | `auth.py:113,61` | ✔ |
| `GET /auth/me` | session | `auth.py:150-153` | ✔ |
| `GET /auth/clients-count` | `corp` | `auth.py:162-165` | ✔ |
| `POST /auth/logout` | none | `auth.py:173` | ✘ **DOC DRIFT** (docs say required) |
| `POST /documents`, `/documents/stream` | `corp` | `documents.py:70` | ✔ |
| `GET /documents` | none | `documents.py:159` | ✔ (correctly labelled public) |
| `DELETE /documents/{id}` | `corp` | `documents.py:197` | ✔ |
| **`POST /ask`** | **none** | `ask.py:30-35` | ✘ **DOC DRIFT + VULNERABILITY** |
| `POST /claims` | `client` | `claims.py:122` | ✔ |
| `GET /claims` | scoped | `claims.py:227` | ✔ |
| `GET /claims/{id}` | owner or `corp` | `claims.py:263` | ✔ with caveat §2.3 |
| `POST /claims/{id}/cancel` | owner or `corp` | `claims.py:280` | ✔ with caveat §2.3 |
| `POST /claims/{id}/pause`, `/resume` | `corp` | `claims.py:241,252` | ✔ |
| `DELETE /claims/{id}` | owner or `corp` | `claims.py:326` | ✔ with caveat §2.3 |
| `GET /approvals`, `POST /approvals/{id}/*` | `corp` | `approvals.py` | ✔ |
| `GET /runs/{correlation_id}` | `corp` | `routes/runs.py` | ✔ |
| `GET /usage`, `/usage/summary` | `corp` | `usage.py:15-40` | ✔ |

### 2.2 `POST /ask` is unauthenticated — **ABSENT**

```python
@router.post("")
async def ask_question(payload: AskRequest, request: Request,
                       use_case: AskQuestionUseCase = Depends(get_ask_question_use_case)):
```
— `src/api/routes/ask.py:30-35`

No `get_current_user`, no `require_role`. But `docs/API.md:16` states *"All
non-health endpoints require user authentication"* and `docs/API.md:172` labels
this endpoint *"Auth: Required (authenticated session)"*. Both are false.

**Impact.** Any anonymous caller can drive the full RAG pipeline: hybrid retrieval
over the entire corpus, an LLM generation, an embedding call, `trace_events`
writes and a `retrieval_log.json` append. That is an unauthenticated cost-
amplification vector and a corpus-disclosure path. Combined with §6.1 (no
effective rate limit) and §9 (no spend cap), it is the most abusable surface in
the system.

*Fix:* add `Depends(get_current_user)` to the route and reconcile `docs/API.md`.

### 2.3 Null-owner claim bypass — **ABSENT (IDOR)**

```python
def _assert_claim_access(claim: Claim, current_user: UserPayload) -> None:
    if current_user.role == "corp":
        return
    if claim.user_id is None:
        return  # Legacy claim without ownership — allow authenticated read.
    if str(claim.user_id) != current_user.id:
        raise HTTPException(403, ...)
```
— `src/api/routes/claims.py:105-115`

`claims.user_id` is nullable, and the comment says "read" — but the same helper
gates **cancel** (`:280`) and **delete** (`:326`). Any row with
`user_id IS NULL` (legacy import, manual write, partial insert, or a Celery
payload built outside `submit_claim`) is readable, cancellable **and deletable** by
any authenticated `client`. That is horizontal privilege escalation over claims
containing PII.

*Fix:* `raise HTTPException(403)` unless `corp`; backfill or reject null owners.

### 2.4 Unsegmented corpus — **ABSENT by design, undocumented**

There is no document-ownership column; the corpus is global. Any authenticated
`client` can read any `policy_id` through `/ask`, including commercial policies
never intended for them. For a multi-book insurer this is a data-segregation gap.
`docs/API.md:19-22` describes `client` as "Policyholder" with no statement that
corpus access is unsegmented.

---

## 3. Prompt injection

### 3.1 Delimiters and instruction — **PRESENT**

`docs/adr/002-prompt-injection-defense.md:9-21` mandates content boundaries, an
explicit "this is data, not instructions" instruction, and a strict refusal. All
four prompts implement it:

| Prompt | Boundary | Instruction | Refusal |
|---|---|---|---|
| `prompts/ask_qa/v1.md:1-13` | `<<<BEGIN DOCUMENT CONTEXT>>>`, `<context>`, `<query>` | ✔ | ✔ |
| `prompts/coverage_matcher/v1.md:3-19` | `<coverage_documents>` | ✔ | ✔ |
| `prompts/exclusion_analyst/v1.md:3-18` | `<exclusion_documents>` | ✔ | ✔ |
| `prompts/adjudication_drafter/v1.md:3-33` | `<adjudication_context>` | ✔ | ✔ |

### 3.2 Retrieved-text sanitisation — **ABSENT**

There is **no** escaping, instruction-stripping, delimiter-break detection, or
homoglyph normalisation of retrieved or user text before interpolation.
`src/application/use_cases/ask_question.py` interpolates chunk text directly;
`MAX_CONTEXT_CHARS = 6000` (`ask_question.py:25`) truncates by length only. A 6 KB
budget lets a single uploaded document occupy the context window and evict the
system framing. The agents share the pattern.

**The mitigation that actually holds** is structural, not textual: each agent
declares a closed tool allow-list, and `_call_tool` rejects anything outside it.
`coverage_matcher` → `["search_policies"]` (`coverage_matcher.py:18`),
`exclusion_analyst` → `["search_exclusions", "calculate_limits_and_deductibles"]`
(`exclusion_analyst.py:22-25`), `adjudication_drafter` → `["submit_for_approval"]`
(`adjudication_drafter.py:49`). A fully successful injection still cannot reach the
network or the filesystem, because the tool namespace is fixed by the framework
rather than chosen by the model. This is the single strongest existing control and
it is what §3.1's ADR understates.

**But the check fails open.** `base_agent.py:32` reads
`if self.ALLOWED_TOOLS and tool_name not in self.ALLOWED_TOOLS:` — the leading
truthiness test means an agent whose `ALLOWED_TOOLS` is empty (the inherited
default, `base_agent.py:16`) enforces **nothing**, and a subclass that forgets to
override the class variable silently loses the control. A deny-by-default
allow-list would invert this so that a forgotten declaration fails closed.
*Fix:* `if tool_name not in self.ALLOWED_TOOLS:` and give the base a sentinel that
always raises.

### 3.3 Confidence gate — **PRESENT**

`src/application/retrieval/hybrid_search.py` refuses when the best dense cosine
distance exceeds `max_cosine_distance = 0.35` (`config.py:39-42`). This replaced an
RRF floor of `0.01` that provably could never fire: RRF scores are rank-based and
every non-empty fusion scores at least `1/61 ≈ 0.0164`. The gate is a sound
anti-hallucination control — but it is a **relevance** gate and gives no
protection against indirect injection, which typically arrives *in* the top-ranked
chunk.

### 3.4 Output validation — **PARTIAL**

- **Structured contracts PRESENT.** `src/application/contracts/adjudication_draft.py:9-18`,
  `coverage_match_result.py:9-17`, `exclusion_analysis_result.py:8-15` reject
  model output that does not parse.
- **Refusal/meta-text filter PRESENT.** `agents/decision_text.py:10-44` detects
  apology boilerplate and requires ≥40 characters of substance.
- **Grounding check ABSENT.** Nothing verifies the answer is *supported* by the
  retrieved chunks — no faithfulness score, no citation-entailment check. A
  hallucinated coverage grant passes if it is well-formed JSON with plausible
  citations. This is the metric the evaluation harness measures
  (`faithfulness`, see `docs/EVALUATION.md`); it is reported, not enforced.

### 3.5 Injection tests — **PARTIAL, and weaker than they look**

`tests/integration/test_security_llm.py:16-37` exercises three injection strings,
but the mocked `searches` return **empty** results, so the confidence gate refuses
**before the LLM is called**, and the mock LLM is pre-programmed to emit a canned
refusal. The test asserts the harness refuses — **not** that the model resists a
malicious retrieved chunk. It would still pass if the entire injection-defence
layer were deleted.

The one real indirect-injection case lives in `evaluation/golden_set.json:128-148`
and is scored by `evaluation/score_refusal.py:11-20` — but `evaluation/` is not
wired into CI (§7.1), and its scoring is substring matching, trivially satisfiable.

---

## 4. Input validation and upload

### 4.1 Pydantic bounds — **PARTIAL**

| Model | Constraint | Location | Gap |
|---|---|---|---|
| `SignupRequest.password` | 8–128 | `auth.py:27` | 72-byte cliff → 500 |
| `LoginRequest.password` | **none** | `auth.py:35` | unbounded |
| `SignupRequest.email` | `EmailStr` | `auth.py:26` | ✔ |
| `CreateClaimRequest.policy_number` | 1–100 | `claims.py:53-63` | ✔ |
| `CreateClaimRequest.incident_description` | 10 000 | `claims.py:53-63` | large but bounded |
| `CreateClaimRequest.claim_amount_requested` | `>0`, `≤10M` | `claims.py:53-63` | ✔ |
| `CreateClaimRequest.idempotency_key` | 8–128 | `claims.py:53-63` | ✔ |
| **`AskRequest.query`** | **none** | `ask.py:21-27` | **ABSENT** — unbounded text on an unauthenticated LLM endpoint; the primary cost/DoS vector |
| `ApprovalRequest.justification` | 20 000 | `approvals.py:18-23` | ✔ |
| `ApprovalRequest.notes` | 5 000 | `approvals.py:18-23` | ✔ |
| **`adjuster_notes`** | **none** | `approvals.py:26-30` | **ABSENT** |

`policy_type` is a restricted `Literal` on the claim request (`claims.py:53-63`)
but a bare `str` on the upload form (`documents.py:67`), so arbitrary taxonomy
strings reach the vector store.

### 4.2 Upload validation — **PRESENT**, with a DoS caveat

Three real layers in `src/api/routes/documents.py:35-60`:

1. **Size** — `MAX_FILE_SIZE_BYTES = 10 MiB` (`:31`), rejected 400 at `:37-41`.
2. **Extension allow-list** — `{".pdf", ".docx", ".txt"}` (`:32`), checked
   case-insensitively at `:43-48`.
3. **Magic-byte signature** — `%PDF-` (`:51-55`), `PK\x03\x04` (`:56-60`). The
   declared content type is not trusted. This is the right call and it is often
   gotten wrong.

Caveats:

- **The size limit does not bound memory.** `documents.py:74` does
  `contents = await file.read()` — fully buffering the body **before**
  validation at `:75`. A 2 GB upload is buffered, then rejected. There is no
  ASGI-level body cap and no `limit_req` in `docker/nginx.conf`.
- **No filename sanitisation.** `file.filename` is used verbatim as
  `original_filename` (`:81`) and to derive the temp suffix (`:77`), with no
  `Path(...).name` normalisation or length cap. It is persisted and echoed by
  `GET /documents` (`:183`). No arbitrary-path write occurs, because a
  `NamedTemporaryFile` is used and unlinked in `finally` (`:78`, `:93-94`).
- **No zip-bomb protection.** `.docx` is accepted on the ZIP signature alone, with
  no uncompressed-size or entry-count cap. `.docm`/VBA is blocked incidentally,
  since it is not in the allow-list.
- **No rate limit on upload.** `require_role("corp")` only; repeated `hi_res`
  parsing is a CPU-saturation path.

### 4.3 Path traversal — **PRESENT (correctly absent)**

The ingested path is always a generated temp path (`documents.py:80,85`), never
client-supplied; `seed_corpus.py` reads from a fixed `data/` root. No traversal
vector.

---

## 5. Secrets and configuration

### 5.1 Committed live secrets — **ABSENT (good)**

`git ls-files` shows no `.env`; `.gitignore:151` excludes it and
`git check-ignore` confirms. `.env.example` holds placeholders only
(`your-secret-key-here`). `openrouter_api_key` defaults to `""`
(`config.py:31`). No cloud keys, no private keys, no `.npmrc`/`.pypirc` tokens. CI
runs `gitleaks protect --staged --redact` on every PR.

### 5.2 Hardcoded fallback secrets — **PARTIAL**

| Variable | Class | Tracked default |
|---|---|---|
| `JWT_SECRET` | secret | **hardcoded literal** (`config.py:35`) |
| `DATABASE_URL` | secret (embeds password) | `postgres:postgres` (`config.py:20-22`) |
| `POSTGRES_PASSWORD` | secret | `postgres` (Compose) |
| `OPENROUTER_API_KEY` | secret | `""` (`config.py:31`) |
| `OLLAMA_BASE_URL` / `REDIS_URL` | config, plaintext transport | `http://` / `redis://` |

The JWT default is the material one; see §1.2. No TLS option is surfaced for
Ollama or Redis.

### 5.3 CORS — **PRESENT, correctly**

`src/api/main.py:52-58` sets `allow_origins=settings.allow_origins` with
`allow_credentials=True`. The wildcard is **rejected at the settings layer** by a
`field_validator` for both the comma-string and list forms (`config.py:45-62`),
and that rejection is unit-tested (`tests/unit/api/test_deps.py`). This is the
right way to do it: it means credentials are never paired with a wildcard origin,
which would otherwise be a spec violation.

Gap: `allow_origins` accepts any string with no scheme/host/port validation, and
dev localhost origins are the shipped default.

### 5.4 Security headers — **PARTIAL**

`src/api/main.py:61-68` sets `X-Content-Type-Options: nosniff` (`:65`),
`X-Frame-Options: DENY` (`:66`), `Strict-Transport-Security: max-age=31536000;
includeSubDomains` (`:67`).

**ABSENT:** `Content-Security-Policy`, `Referrer-Policy`, `Permissions-Policy`,
and `Cache-Control: no-store` on authenticated responses. HSTS is emitted even
when serving plaintext HTTP in dev.

---

## 6. Rate limiting, DoS and external-service resilience

### 6.1 Rate limiting — **PARTIAL; the default does not apply**

```python
limiter = Limiter(key_func=get_remote_address, default_limits=["60/minute"])
```
— `src/api/limiter.py:1-4`, registered at `src/api/main.py:49-50`

`SlowAPIMiddleware` is **never added** (grep across `src/` returns nothing). In
SlowAPI the `default_limits` are applied by the middleware's dispatch hook, not by
the exception handler — so the advertised `60/minute` default **does not exist**
for any endpoint lacking an explicit decorator. Only two routes are decorated,
both correctly declaring `request: Request`:

- `POST /auth/login` — `@limiter.limit("5/minute")` (`auth.py:114`)
- `POST /auth/signup` — `@limiter.limit("5/minute")` (`auth.py:62`)

**Unlimited today:** `POST /ask` (LLM + embeddings, and anonymous), `POST
/documents` and `/documents/stream` (`hi_res` parsing), `GET /documents`,
`GET /usage`, `GET /approvals`, and all `POST /claims/{id}/*` transitions.

Three scaling defects, the second of which is a live self-inflicted DoS on the
shipped Docker deployment:

1. The `Limiter` has no `storage_uri`, so it uses the in-process `memory://`
   backend — per-process, reset on restart, and **not** shared across workers.
2. `get_remote_address` reads `request.client.host`. `docker/nginx.conf:12-13`
   *does* correctly set `X-Real-IP` and `X-Forwarded-For`, but `Dockerfile.app:48`
   starts uvicorn as
   `uvicorn src.api.main:app --host 0.0.0.0 --port 8000` — **without
   `--proxy-headers`**. Starlette therefore ignores those headers, and every
   proxied request presents the `frontend` container's IP as the peer. **All
   users consequently share one 5/minute login bucket**, so the sixth login
   attempt from anyone locks out everyone.
3. `SlowAPIMiddleware` is not registered at all, so the 5/minute route decorators
   — which rely on the middleware's dispatch hook — do not fire either. The
   `5/minute` limits above are currently documentation, not behaviour.

*Fix:* register `SlowAPIMiddleware`, add `--proxy-headers --forwarded-allow-ips=*`
to the uvicorn command, add a Redis `storage_uri`, and decorate `/ask`.

### 6.2 LLM timeouts — **ABSENT**

`src/infrastructure/llm/ollama_provider.py:32-37` and
`openrouter_provider.py:31-36` build `ChatOllama` / `ChatOpenAI` with
`max_tokens`/`num_ctx` but **no `timeout` and no `max_retries`**, and there is no
`asyncio.wait_for` around `ainvoke` and no circuit breaker. A hung upstream blocks
the request thread indefinitely.

### 6.3 Retry and backoff — **PARTIAL**

- `src/infrastructure/llm/provider_router.py:25-42` — a **single** immediate
  Ollama → OpenRouter fallback: no retry, no backoff, no jitter. A cold OpenRouter
  is re-hit on every request.
- `src/application/use_cases/run_adjudication.py:48-55` — per-agent
  `asyncio.wait_for(timeout=180)` with **one** retry after a 1-second sleep, so
  worst case is ~361 s per agent. nginx `proxy_read_timeout` is 300 s
  (`docker/nginx.conf:24`), so a client-side timeout can fire while the server
  keeps working.
- No Celery `task_time_limit`/`soft_time_limit` in
  `src/infrastructure/tasks/celery_app.py`; a wedged LLM call holds a worker slot
  indefinitely.

### 6.4 Body-size and resource DoS — **ABSENT**

No ASGI body-size middleware; no `limit_req` in nginx; no concurrency cap; no
queue-depth limit; no circuit breaker on `/ask`; no spend cap or quota. The
unbounded `AskRequest.query` on an anonymous endpoint (§2.2, §4.1) is the cheapest
possible cost-exhaustion path.

---

## 7. CI, supply chain and branch protection

### 7.1 Workflows — **PARTIAL**

`.github/workflows/ci.yml`:

- **Backend** (`:15-52`): `pip install -e .` + `requirements.txt`,
  `pytest tests/unit tests/contract --cov=src --cov-fail-under=70`, then
  `pip-audit` **and** `gitleaks protect --staged --redact`.
- **Frontend** (`:54`+): `npm ci` → `npm run lint` (oxlint) → `npm run build`
  (`tsc -b && vite build`) → `npm audit --audit-level=high`.

`ci-pipeline.yml` adds ruff, an integration job on a real Postgres, and duplicates
the audits.

Gaps:

- **Audits are advisory-only by design** (`|| echo "advisory only"` /
  `|| true`). A known-CVE dependency or a leaked secret does **not** fail the
  build. There is no blocking vulnerability gate.
- CI installs from `requirements.txt` (ranges), not `requirements.lock` (exact
  pins), so it resolves fresh versions every run. `scripts/setup_env.sh:8,28-29`
  prefers the lockfile; CI does not. The CI path is the weaker one.
- **The two CI workflows overlap without coordination.** `ci.yml` (`CI — tests &
  security`) and `ci-pipeline.yml` (`CI Pipeline`) both run on every push *and*
  every pull request, both install from `requirements.txt`, and both run
  `pip-audit` and `gitleaks`. Four checks therefore cover roughly two jobs' worth
  of work, doubling CI minutes and quadrupling the number of required contexts a
  branch-protection rule has to name. Consolidate to one workflow.
- **No frontend tests exist.** `frontend/package.json` defines only `dev`, `build`
  (`tsc -b && vite build`), `lint` (`oxlint`) and `preview` — there is no `test`
  script, and no test runner in `devDependencies`. `CONTRIBUTING.md:39` instructs
  contributors to run `npm test`, which fails with "missing script: test".
  Type-checking via `tsc -b` is the only frontend gate.
- **`evaluation/` is not in CI** (§3.5), so the prompt-injection regression suite
  is manual only.
- Actions are pinned to mutable tags (`@v4`, `@v5`), not SHAs. No `dependabot` or
  `renovate` config. No pre-commit hooks.

### 7.2 Branch protection — **ABSENT / unverifiable**

`.github/workflows/provision-branch-protection.yml` is `workflow_dispatch`-only
(`:3-4`) and requires a `REPO_ADMIN_TOKEN` (`:14-17`). Its
`required_status_checks.contexts` is set to `["CI — tests & security"]` (`:30`),
which is the **workflow** name (`ci.yml:1`), not a **job** name. The four actual
check runs are `Backend — Python tests & audits` (`ci.yml:11`), `Frontend — build &
audit` (`ci.yml:55`), `Lint, Fast Tests & Security Scan` (`ci-pipeline.yml:11`) and
`Integration Tests (Docker Compose)` (`ci-pipeline.yml:55`). A required context must match a job name, so this either matches
nothing (PRs block forever) or does not protect. There is no in-repo evidence the
workflow has ever run.

*Treat branch protection as absent until verified via the GitHub API.* It also
omits CODEOWNERS approval, conversation resolution, signed commits and an
explicit `allow_force_pushes: false`.

### 7.3 Repository hygiene

Three accidental empty files are committed at the repo root: `=3.11,`, `=3.7,`,
`=3.9.0,` — the residue of a mistyped shell redirect such as
`pip install "pandas>=3.11," > =3.11,`. Inert, but they are the fingerprint of a
packaging command writing into the working tree, and they should be deleted.

---

## 8. Seed data

### 8.1 Seeded users — **PARTIAL (fixed in PR #161)**

`scripts/seed_users.py` previously seeded `claims_handler` and `adjuster` roles,
which are outside the accepted `client`/`corp` set, while `README.md` and
`docs/API.md` documented a *third*, entirely disjoint pair
(`e2ecorp@example.com`). Net effect: **no working `corp` account could be
provisioned on a fresh clone**, and a reader following the API docs would
authenticate against an account that could not exist.

Now: the seeder creates `e2ecorp@example.com` (`corp`) and
`claimdemo@example.com` (`client`), matching the README and the API docs, and
reconciles the role of an already-seeded row on re-run. Verified by authenticating
and receiving `200` from `/approvals`, `/usage/summary`, `/documents` and
`/auth/clients-count`.

Both passwords are plaintext in git. They are local-only demo credentials and
must never be reused.

### 8.2 Seeded corpus — **PRESENT**

`scripts/seed_corpus.py:43-50` ingests `data/metadata.json`: **30 documents**
(19 PDF, 10 TXT, 1 DOCX) → 1,958 chunks, idempotent by content hash
(`document_loader.py:12-14`).

- The 10 synthetic `POL-500x` TXT files are clean, purpose-built retrieval
  fixtures — a deterministic baseline.
- The 20 real-world PDFs/DOCX are **third-party copyrighted material** (state
  model laws, NAIC forms, insurer publications) committed to the repository.
  That is a redistribution/licensing question rather than a security bug, but it
  should be settled before the repository is made public.
- `data/metadata.json` is the de-facto manifest; `seed-data/manifest.json` exists
  but is empty (`.gitkeep` only), which is misleading.

---

## 9. Logging, observability and PII

### 9.1 Log sinks — **PRESENT**, ungoverned

| Sink | Configured | PII scrubbed |
|---|---|---|
| `workflow.log` | `src/api/main.py:34-43` | ✘ |
| `system_logs.txt` (JSONL) | `main.py:45-47` | partial (§9.2) |
| `retrieval_log.json` | `observability/retrieval_logger.py:1-10` | ✘ |
| `claim_logs.json` | `observability/claim_logger.py:1-13` | ✘ |
| `chunk_log.json` + `chunks/<uuid>.json` | `chunk_log.py:1-13`, `document_chunk_store.py:15-23,34-52` | ✘ |
| `token_usage.json` | `token_usage.py:1-5` | n/a (low PII) |

`workflow.log` and `system_logs.txt` are written **into the repository working
directory** (`main.py:34-35,47`). There is **no rotation, no size cap, and no
retention or deletion policy**; `logging.FileHandler` grows unbounded, and
multi-worker deployments write the same file concurrently from independent
processes.

### 9.2 PII scrubbing — **PARTIAL, and applied inversely**

`src/infrastructure/observability/trace_logger.py:24-40` defines `sanitize_pii`,
used by `emit_trace_event` (`trace_logger.py:58`) and `emit_system_log`
(`system_logger.py:28-33`). It redacts **SSN, email and
phone only**.

Not redacted: **full names** (the most common PII class in insurance),
**policy numbers**, **claimant addresses**, **date of loss**, the free-text
`incident_description`, and all document body text.

The "phone" pattern matches a bare digit run with optional separators, which is a
**superset of SSNs** and of any 9–11 digit substring of a longer number — so it
redacts innocuous numerics while implying broad telephone coverage.

**The structural defect:** `retrieval_log.json` and `claim_logs.json` are written
**without calling `sanitize_pii` at all** (`retrieval_logger.py:89-163`,
`claim_logger.py:46`). The two highest-volume, highest-sensitivity sinks are
entirely unredacted, while the two lowest-volume ones are the only scrubbed ones.

### 9.3 Retrieved content logging — **ABSENT (highest-sensitivity finding)**

`retrieval_logger.py:89-163` writes, per retrieval call: the raw user `query`,
prompt previews, and the **full text of every retrieved chunk** plus complete
agent tool responses. `claim_logger.py:46` writes the full claim record
including `incident_description`. `src/infrastructure/observability/document_chunk_store.py:34-52` writes one
`chunks/<document_id>.json` per document with full chunk text.

So the **entire unredacted policy corpus and the entire unredacted claims corpus
are durably persisted to plaintext JSON in the working directory, indefinitely,
with no rotation and no deletion path.** Deleting a policy document
(`documents.py:192-234`, which does cascade to `delete_document_chunks` at
`:233`) does **not** remove what was already logged from it. There is no
erasure path — a GDPR "right to be forgotten" cannot be satisfied.

### 9.4 Trace events — **PARTIAL**

`trace_events` exists (`migrations/versions/a1b2c3d4e5f6_*.py:33-42`) with
`payload` as unbounded `JSON` and no retention job, and nothing reads it back for
authorization or for `/runs` (served from the in-memory store). It is written and
never queried.

### 9.5 Cost accounting — **PRESENT but structurally unable to report cost**

`src/infrastructure/observability/token_usage.py:1-5,24-28,37-53`, exposed at
`GET /usage` and `/usage/summary` (both `corp`-gated, `usage.py:15-40`).

- **Token counts are estimates**, ~4 characters per token (`token_usage.py:44-46`,
  `(len(text) + 3) // 4`). No `tiktoken`, no provider-reported usage.
- **Prices are hardcoded to `$0.00`** for both providers (`:24-28`, applied at `:49-53`), so `usd` is
  structurally always zero. There is no price table, no env override, and no
  OpenRouter credit reconciliation. **The USD figure in the demo is not a real
  cost.**
- No `user_id` on the records, so with `/ask` anonymous (§2.2) spend cannot be
  attributed, rate-limited or billed.
- No budget, quota or alert.

---

## Prioritised remediation

Ordered by exploitability × impact, cheapest first.

| # | Fix | Effort | Closes |
|---|---|---|---|
| 1 | Add `SlowAPIMiddleware` + Redis `storage_uri`; add `--proxy-headers` to the uvicorn CMD; decorate `/ask` | S | §6.1 |
| 2 | `Depends(get_current_user)` on `POST /ask`; bound `AskRequest.query` | S | §2.2, §4.1, §6.4 |
| 3 | 403 on null-owner claims; backfill owners | S | §2.3 |
| 4 | Fail startup if `JWT_SECRET` is unset or default; `extra="forbid"` | S | §1.2, §5.3 |
| 5 | Cap password length at 72 bytes on signup **and** login; drop `passlib` | S | §1.1 |
| 6 | `set_cookie(..., secure=True)` behind TLS; add `Cache-Control: no-store` | S | §1.3, §5.4 |
| 7 | Apply `sanitize_pii` in `retrieval_logger` and `claim_logger`; add log rotation and a retention policy | M | §9.1–9.3 |
| 8 | Add `timeout`/`max_retries` to both providers; Celery `time_limit` | S | §6.2, §6.3 |
| 9 | Wire `evaluation/` into CI; make `pip-audit` blocking | M | §3.5, §7.1 |
| 10 | Verify/fix branch protection; add SHA-pinned actions + dependabot | M | §7.2 |
| 11 | Stream uploads instead of buffering; add nginx `client_max_body_size` | M | §4.2, §6.4 |
| 12 | Re-validate role from the DB in `get_current_user`; add a CHECK constraint | M | §1.2, §1.4 |
| 13 | Sanitise `file.filename`; add zip-bomb caps | M | §4.2 |
| 14 | Make the tool allow-list deny-by-default (`if tool_name not in ALLOWED_TOOLS`) | S | §3.2 |
| 15 | Add a grounding/entailment check on generated answers | L | §3.4 |
| 16 | Delete `=3.11,`, `=3.7,`, `=3.9.0,`; add a `test` script or fix `CONTRIBUTING.md:39` | S | §7.3 |

**Not planned, stated for completeness:** the corpus is unsegmented across clients
(§2.4) and `token_usage` cannot report real money (§9.5). Both are product
decisions, not bugs.
