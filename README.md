# Domain Copilot

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Agentic RAG platform for **insurance claims adjudication** (variant **D2** + twist **T7 — async long-running jobs**).

> **Variant derivation (if not stated in invitation):** Domain = (last two digits of National ID) mod 7 → **D2** (Insurance — claims adjudication). Twist = (sum of all digits) mod 8 → **T7** (async long-running jobs: Celery queue, live progress, cancel/pause/resume). Replace this note with the exact derivation from your invitation/National ID before submission.

## Videos (unlisted)

| Clip | Length | Link |
|---|---|---|
| Product demo | 5–8 min | _TODO: unlisted URL_ |
| Teaching sample | ~10 min | _TODO: unlisted URL_ |

## Prerequisites

- Docker + Docker Compose
- Python 3.12 (venv is created by `./scripts/dev.sh`)
- Node.js 20+ (frontend)
- Free local models via Ollama (no paid API key required). Optional: `OPENROUTER_API_KEY` for hosted fallback.

```bash
sudo apt install tesseract-ocr poppler-utils   # Debian/Ubuntu PDF/OCR helpers
```

## Quick start (15 minutes, Docker only for infra)

```bash
cp .env.example .env          # set JWT_SECRET to a random string
docker compose up -d db redis ollama
./scripts/dev.sh              # creates .venv, migrates, starts API :8000
./scripts/dev-worker.sh       # terminal 2 — Celery workers for claims
cd frontend && npm install && npm run dev   # terminal 3 — UI :3000
```

Open http://localhost:3000 (UI) or http://localhost:8000/docs (OpenAPI).

**All-in-one Docker (optional, slower first build):**

```bash
docker compose up --build --profile worker
# UI: http://localhost:3000
```

### Seed corpus & demo accounts

```bash
python scripts/seed_corpus.py     # ingests data/metadata.json (30 docs)
python scripts/seed_users.py      # creates demo corp + client accounts
```

Seeded accounts:

| Role | Email | Password |
|---|---|---|
| corp | `e2ecorp@example.com` | `password123` |
| client | `claimdemo@example.com` | `password123` |

### Environment variables (see `.env.example`)

| Variable | Purpose | Notes |
|---|---|---|
| `DATABASE_URL` | Postgres DSN | Dev scripts rewrite `@db:` → `@localhost:` |
| `REDIS_URL` | Celery broker + pause registry | Rewrite `//redis:` → `//localhost:` |
| `OLLAMA_BASE_URL` | Local LLM + embeddings | Default `http://ollama:11434` |
| `OLLAMA_CHAT_MODEL` / `OLLAMA_EMBEDDING_MODEL` / `OLLAMA_MODELS` | Model selection | e.g. `llama3.2:1b`, `nomic-embed-text` |
| `OPENROUTER_API_KEY` | Optional hosted fallback | Leave empty for fully local |
| `JWT_SECRET` | HMAC key for session cookies | **Never commit a real secret** |
| `TOKEN_USAGE_PATH` | Optional override for usage sink | Defaults to repo-root `token_usage.json` |

**Free API keys:** Ollama requires none. For OpenRouter, create a free account at openrouter.ai and paste the key into `.env` if you want the fallback path.

**Local model with no key:** leave `OPENROUTER_API_KEY` empty; the provider router uses Ollama only.

### 5-Minute Demo Path

1. Start services (quick start above). `curl localhost:8000/health` → `{"status":"ok"}`.
2. Open http://localhost:3000 → sign up / log in as **corp** (`e2ecorp@example.com`).
3. **Documents** → confirm seeded policies (or upload a small `.txt` with `policy_id=ISO-PP-00-01`). Watch the staged ingestion panel.
4. **Ask** → select `ISO-PP-00-01` → ask *“What is the deductible for windstorm or hail damage?”* → verify citation cards. Press **Stop** mid-stream → `generation/stream_cancelled` in `system_logs.txt` (FR-6).
5. **Ask** → ask *“What does the corpus say about lunar module insurance?”* → expect exact refusal (no fabricated citation).
6. Log in as **client** → **Claims** → submit a claim with `policy_number=ISO-PP-00-01`, `date_of_loss=2026-08-15`, amount `4500` → live pipeline stages → `report_ready`.
7. Client → **Claims** → after pipeline, status `report_ready` (clients cannot approve). Corp → **Approvals** → edit payout (e.g. `3750`) + justification → **Approve**. Client reloads → `approved`, `final_payout=3750`.
8. Corp `DELETE` while still `pending_approval`/`report_ready` → **HTTP 409** (delete lock). After approve → delete succeeds.
9. **Trace / cost:** copy `correlation_id` → `GET /runs/{id}` and `GET /usage?correlation_id={id}` (token/cost accounting, FR-9).

### How to run tests & evaluation harness

```bash
source .venv/bin/activate
ruff check src/ tests/
python -m pytest tests/unit tests/contract -q          # fast, LLM mocked
python -m pytest tests/integration/test_claims_routes.py tests/integration/test_approval_gate.py -q
cd frontend && npx tsc --noEmit
python evaluation/run_eval_scripts.py --golden evaluation/golden_set.json --topk 10
```

Golden set: **25** questions (`18` normal + `7` adversarial: 3 injection, 2 OOC, 1 ambiguous, 1 conflicting). See `docs/EVALUATION.md`.

### Observe the whole system live

```bash
./scripts/system-logs        # last 5 events + live follow (Ctrl+C)
./scripts/system-logs -f     # follow from now
```

Sinks at repo root (gitignored): `system_logs.txt`, `workflow.log`, `chunk_log.json`, `claim_logs.json`, `retrieval_log.json`, `token_usage.json`, `chunks/`.

### Troubleshooting

- Cookies not set → use the Vite proxy on :3000 (not opening components in isolation). See `frontend/vite.config.ts`.
- Workers unhealthy → ensure Redis is up and `REDIS_URL` uses `localhost` on the host (`./scripts/dev-worker.sh` rewrites it).
- Ollama slow/OOM → keep `llama3.2:1b` + `nomic-embed-text`; avoid concurrent large PDF `hi_res` ingests on a 4 GB host.
- Stale bytecode after edits → `find src tests -name __pycache__ -prune -exec rm -rf {} +` and restart workers.

### Where to look in the code

| Concern | Path |
|---|---|
| Ingestion | `src/application/use_cases/ingest_document.py` |
| Hybrid retrieval + RRF | `src/application/use_cases/ask_question.py` |
| Multi-agent adjudication | `src/application/use_cases/run_adjudication.py`, `src/application/agents/*` |
| Approval gate | `src/api/routes/approvals.py`, `src/api/routes/claims.py` |
| Token/cost (FR-9) | `src/infrastructure/observability/token_usage.py`, `src/api/routes/usage.py` |
| Ask cancel (FR-6) | `src/api/routes/ask.py`, `frontend/src/components/AskQAStream.tsx` |
| Tracing | `src/infrastructure/observability/trace_logger.py` → `/runs/{correlation_id}` |
| Frontend | `frontend/src/components/*` |

### Teaching pack

- Slides: `teaching/slides/rag-beyond-the-demo.md` (20 slides, 90 min)
- Lab: `teaching/lab-sheet.md` (Tasks A–E + stretch + answer key)
- Outcomes: `teaching/learning-outcomes.md`
- Mistakes: `teaching/common-mistakes.md`

### Agentic workflow & AI usage

- `docs/AGENTIC-WORKFLOW.md` — what was configured and why
- `docs/AI-USAGE-LOG.md` — delegated vs hand-written, where the model misled us

### Setup (reproducible)

```bash
./scripts/setup_env.sh
source .venv/bin/activate
python scripts/inspect_unstructured.py /path/to/document.pdf
```

`requirements.lock` pins the environment.

---

Contact / Maintainer: Project Author · License: [MIT](LICENSE)
