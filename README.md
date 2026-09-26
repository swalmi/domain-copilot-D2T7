# insureAI

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.12-blue.svg)](pyproject.toml)

**Ask a question about an insurance policy and get an answer with citations — or
file a claim and watch three LLM agents argue about it while a human keeps the
final say.**

insureAI is an agentic RAG system for insurance claims adjudication. It ingests
real policy documents, answers questions grounded in them (refusing when the
corpus cannot support an answer), and runs a submitted claim through a
three-agent pipeline whose output **cannot** move money without a human approval.

It runs entirely on your machine with **no API key at all**.

```
┌─ Policyholder ────────┐        ┌─ Claims handler ───────┐
│  "Is hail covered?"   │        │  approve / reject      │
│  file a claim         │        │  adjust the payout     │
└───────────┬───────────┘        └───────────┬────────────┘
            │  HTTP + SSE                    │
            ▼                                ▼
   ┌──────────────────────────────────────────────────┐
   │  FastAPI  ·  hybrid retrieval (dense + keyword)  │
   │  pgvector 1,958 chunks  ·  RRF fusion             │
   ├──────────────────────────────────────────────────┤
   │  Celery: CoverageMatcher → ExclusionAnalyst →    │
   │          AdjudicationDrafter → HUMAN APPROVAL     │
   └──────────────────────────────────────────────────┘
            │                                │
            ▼                                ▼
     Ollama (local)                  PostgreSQL 16
   llama3.2:1b + nomic-embed         + pgvector
```

📐 **[Architecture & diagrams](docs/ARCHITECTURE.md)** ·
🔒 **[Security report](docs/SECURITY.md)** ·
📊 **[Evaluation report](docs/EVALUATION.md)** ·
🎓 **[Teaching pack](teaching/)**

---

## Table of contents

- [Videos](#videos)
- [Prerequisites](#prerequisites)
- [Quick start — Docker only, 15 minutes](#quick-start--docker-only-15-minutes)
- [5-Minute Demo Path](#5-minute-demo-path)
- [Running with no API key (fully local)](#running-with-no-api-key-fully-local)
- [Free API keys (optional)](#free-api-keys-optional)
- [Every environment variable](#every-environment-variable)
- [Demo accounts](#demo-accounts)
- [Running the tests](#running-the-tests)
- [Running the evaluation harness](#running-the-evaluation-harness)
- [Troubleshooting](#troubleshooting)
- [Where to look in the code](#where-to-look-in-the-code)

---

## Videos

| Clip | Length | Link |
|---|---|---|
| Product demo | 5–8 min | *not yet recorded* |
| Teaching sample | ~10 min | *not yet recorded* |

---

## Prerequisites

**You need Docker. That is the whole list for the main path.**

| Tool | Needed for | Install |
|---|---|---|
| **Docker** + Docker Compose v2 | everything | [docker.com/get-docker](https://docs.docker.com/get-docker/) |
| Python 3.12 | only for running tests / the eval harness on the host | [python.org](https://www.python.org/downloads/) |
| Node.js 20+ | only for frontend development with hot reload | [nodejs.org](https://nodejs.org/) |

Verify Docker is working:

```bash
docker --version && docker compose version
```

> **RAM: 4 GB is the floor for the stack; 8 GB is where everything is comfortable.**
> The default local model (`llama3.2:1b`) was chosen because `llama3.2:3b` OOM-kills the
> API on a 3.7 GB host. If ingestion dies during PDF layout analysis, that is usually the
> cause — see [Troubleshooting](#troubleshooting).
>
> Measured on a **3 GB** host (the committed evaluation run): the stack itself starts
> fine, but there is not enough headroom to also run the test suite or the eval harness.
> The 25-case harness took **17 min 31 s** (~42 s/case) while thrashing, and
> `pytest tests/integration` **hung indefinitely** partway through — a symptom that looks
> like a broken test but is pure memory pressure. Check `free -g` first if either stalls.
> Close a browser before running either.

---

## Quick start — Docker only, 15 minutes

No local Python, Node, or model downloads needed. Everything below runs in
containers.

### 1. Configure (1 min)

```bash
git clone https://github.com/swalmi/domain-copilot-D2T7.git
cd domain-copilot-D2T7
cp .env.example .env
```

Generate a real signing secret and put it in `.env` (replacing the placeholder).
This is the **only** step that needs anything beyond Docker — use whichever is
already on your machine:

```bash
python3 -c "import secrets;print('JWT_SECRET='+secrets.token_urlsafe(48))"
# or, with openssl:  openssl rand -base64 48
# or, with Docker only:
docker run --rm alpine sh -c 'head -c 48 /dev/urandom | base64 | sed "s/^/JWT_SECRET=/"' >> .env
```

Edit `.env` and paste it over `JWT_SECRET=your-secret-key-here`.

> ⚠️ `JWT_SECRET` has a **hardcoded fallback in the source**. If you skip this
> step the app still runs — with a key that is public in the repository, so
> anyone could forge an admin session. See [SECURITY.md §1.2](docs/SECURITY.md).

### 2. Start the full stack (10–12 min, mostly model download)

```bash
docker compose up -d --build
docker compose --profile worker up -d worker    # the Celery claim pipeline
```

The first command starts five services: `db` (Postgres + pgvector), `redis`,
`ollama`, `app` (API on **:8000**) and `frontend` (UI on **:3000**).

`worker` is behind the **`worker`** compose profile so it stays off during
lightweight development. The claim pipeline in step ⑤ needs it, so start it with the
second command — or run `docker compose --profile worker up -d --build` once instead
of both, to bring up all six.

The first run pulls `llama3.2:1b` and `nomic-embed-text` into the Ollama
container — roughly 1.4 GB. Watch it happen:

```bash
docker compose logs -f ollama-init
```

### 3. Load the corpus and demo accounts (2–3 min)

```bash
docker compose exec app python scripts/seed_corpus.py
docker compose exec app python scripts/seed_users.py
```

`seed_corpus.py` ingests **30 policy documents → 1,958 chunks**
(19 PDF, 10 TXT, 1 DOCX). First run takes a few minutes because `hi_res` layout
analysis is CPU-heavy. It is idempotent — re-running skips documents whose
content hash already exists.

### 4. Open it

| What | URL |
|---|---|
| **Web UI** | http://localhost:3000 |
| API docs (interactive) | http://localhost:8000/docs |
| Health check | http://localhost:8000/health |

Sign in with a [demo account](#demo-accounts) and follow the
[5-Minute Demo Path](#5-minute-demo-path).

```bash
curl -s localhost:8000/health   # {"status":"ok", ...}
```

---

## 5-Minute Demo Path

A numbered script that exercises every core capability. Have the UI open at
http://localhost:3000 and a terminal handy.

**① Health check** — the stack is up.

```bash
curl -s localhost:8000/health
```

**② Sign in as a claims handler (`corp`)** — `e2ecorp@example.com` /
`password123`. This role can ingest policies, approve claims and see cost data.

**③ Inspect the ingested corpus** — go to **Documents**. You should see 30
policies. Pick `SHELTER-HO3` (no hyphen before the 3) and note its chunk
count. This proves ingestion,
chunking and embedding all worked.

**④ Grounded answer with citations** — go to **Ask**, select `SHELTER-HO3`, and
ask:

> *What is the deductible, and what does the policy pay for loss of use?*

You get a streamed answer with **citation cards** naming the policy, section and
page. Each claim in the answer traces back to a specific chunk.

**⑤ Correct refusal** — clear the policy filter and ask:

> *What does the corpus say about lunar module insurance?*

The system **refuses**: the best dense match is further away than
`MAX_COSINE_DISTANCE` (0.35), so it will not invent an answer. No fabricated
citation appears. This is the anti-hallucination gate doing its job — the single
most important behaviour in the system.

**⑥ Cancel a stream** — start the question from ④ again and press **Stop**
mid-stream. `system_logs.txt` records `generation/stream_cancelled`. The
server-side generator is cancelled, not just the browser.

**⑦ File a claim and watch three agents work** — sign in as the **policyholder**
(`claimdemo@example.com` / `password123`), go to **Claims → New claim**, and use:

| Field | Value |
|---|---|
| Policy number | `HO3-2024-884512` |
| Date of loss | `2026-08-14` |
| Amount | `18500` |
| Description | `A kitchen fire caused by a faulty microwave oven damaged the cabinets, countertop and flooring. The fire started in the kitchen and smoke spread to the adjoining living room.` |

Note the policy number: it is a **customer form number**, not the corpus id. The
system resolves `HO3-2024-884512 → SHELTER-HO3` before searching. Submit it and
watch `pipeline_stage` advance live: `reading_policy` → `building_report` →
`report_ready`. Roughly 2–4 minutes on the 1b model.

**⑧ Read the report** — the claim shows a recommendation, a deductible, a policy
limit and **5 citations**, every one from `SHELTER-HO3`. This is the
`CoverageMatcher → ExclusionAnalyst → AdjudicationDrafter` output.

**⑨ The human approval gate** — sign back in as **`corp`**, open **Approvals**,
and approve the claim with an **adjusted payout** (e.g. `15000`) and a
justification. Now sign in as the **policyholder** and reload: status is
`approved` and the payout is *yours*, not the model's. The LLM can recommend; only
a human can decide.

**⑩ Trace and cost** — copy the `correlation_id` from the claim and run:

```bash
curl -s -b cookies.txt "localhost:8000/runs/$CORRELATION_ID" | jq    # every pipeline step
curl -s -b cookies.txt "localhost:8000/usage?correlation_id=$CORRELATION_ID" | jq
```

You get the full step-by-step trace and the token accounting for that one run.

**⑪ The twist: async + cancel + pause.** Submit a second claim, then use
**Cancel** (works before the pipeline finishes) or, as `corp`, **Pause** — the
Celery worker checks a Redis pause key between stages, so a long adjudication can
be held for human review and resumed.

---

## Running with no API key (fully local)

**This is the default and it needs nothing from us.** Ollama runs inside the
compose network:

```bash
docker compose up -d ollama          # already part of `up -d`
docker compose exec ollama ollama list   # llama3.2:1b, nomic-embed-text
```

Leave `OPENROUTER_API_KEY` empty. `ProviderRouter` uses Ollama and never calls
out. Your policy text never leaves your machine.

To use a different local model, set it in `.env` and restart:

```bash
OLLAMA_CHAT_MODEL=llama3.2:3b        # only if you have ≥8 GB RAM
OLLAMA_EMBEDDING_MODEL=nomic-embed-text
```

> ⚠️ Changing the **chat** model is safe. Changing the **embedding** model
> invalidates every stored vector — you must re-ingest the corpus, because
> 768-dim vectors from a different model are not comparable.

---

## Free API keys (optional)

Only needed if you want the hosted fallback. Everything works without it.

| Provider | How to get a free key | Free tier |
|---|---|---|
| **OpenRouter** | Sign up at [openrouter.ai/keys](https://openrouter.ai/keys) → Create API key | Some free models; credit card not required for the free tier |
| Google AI Studio | [aistudio.google.com/apikey](https://aistudio.google.com/app/apikey) | Gemini free tier |
| Groq | [console.groq.com/keys](https://console.groq.com/keys) | Free tier, fast |

Then:

```bash
# .env
OPENROUTER_API_KEY=sk-or-v1-...
OPENROUTER_MODEL_NAME=<any free model id from openrouter.ai/models>
```

`ProviderRouter` calls Ollama first and falls back to OpenRouter **only** if
Ollama raises. Note the consequence: with a key set, a failing local model sends
your retrieved policy text to a third party. For regulated data, leave it blank.

---

## Every environment variable

All configuration is read by `src/infrastructure/config.py` (Pydantic Settings)
plus a few path overrides read directly via `os.environ`. Copy
`.env.example` to `.env` and edit. Everything below has a working default except
`JWT_SECRET`.

### Core

| Variable | Default | Purpose |
|---|---|---|
| `JWT_SECRET` | ⚠️ hardcoded in source | HMAC key for session JWTs. **Set this.** Any value works but should be ≥32 random bytes. |
| `JWT_ALGORITHM` | `HS256` | JWT signing algorithm. Do not change without changing `JWT_SECRET` handling. |
| `ALLOW_ORIGINS` | `http://localhost:3000,http://localhost:8000` | Comma-separated CORS allow-list. `*` is **rejected at startup** by design — never pair a wildcard with credentialed cookies. |
| `APP_TITLE` | `insureAI` | Title in the OpenAPI docs. |

### Database and queue

| Variable | Default | Purpose |
|---|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://postgres:postgres@localhost:5432/domain_copilot` | Postgres DSN. A bare `postgresql://` is rewritten to the async driver automatically. **Dev scripts rewrite `@db:` → `@localhost:`** so the same `.env` works in and out of Docker. |
| `REDIS_URL` | `redis://localhost:6379/0` | Celery broker/result backend **and** the pause/resume registry. Same `@redis:` rewrite applies. |
| `POSTGRES_USER` | `postgres` | Compose only — bootstrap superuser. |
| `POSTGRES_PASSWORD` | `postgres` | Compose only — bootstrap password. **Change for anything shared.** |
| `POSTGRES_DB` | `domain_copilot` | Compose only — database name. |
| `POSTGRES_HOST` | `localhost` | Alembic migrations only. |
| `POSTGRES_PORT` | `5432` | Alembic migrations only. |

### LLM providers

| Variable | Default | Purpose |
|---|---|---|
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Local LLM + embedding server. |
| `OLLAMA_CHAT_MODEL` | `llama3.2:1b` | Generation model. `3b` needs ≥8 GB RAM. |
| `OLLAMA_EMBEDDING_MODEL` | `nomic-embed-text` | Embedding model. **Changing it requires re-ingestion.** |
| `OLLAMA_MODELS` | `llama3.2:1b,nomic-embed-text` | Compose only — comma-separated list the `ollama-init` container pulls on boot. |
| `OPENROUTER_API_KEY` | `""` (empty) | Hosted fallback key. Empty = fully local. **Secret.** |
| `OPENROUTER_MODEL_NAME` | `nvidia` | Fallback model id on OpenRouter. |
| `OPENROUTER_BASE_URL` | `https://openrouter.ai/api/v1` | OpenRouter API base. |

### Retrieval tuning

| Variable | Default | Purpose |
|---|---|---|
| `MAX_COSINE_DISTANCE` | `0.35` | Refusal gate. Refuse when the best dense match is further away than this. **Raise** = more answers, more hallucination risk. **Lower** = safer, more false refusals. |

### Ingestion

| Variable | Default | Purpose |
|---|---|---|
| `UNSTRUCTURED_PDF_STRATEGY` | `hi_res` | PDF layout strategy: `hi_res` (accurate, slow, memory-hungry) or `fast`. Set to `fast` on small machines. |
| `SEED_MANIFEST` | `data/metadata.json` | Corpus manifest used by `seed_corpus.py`. |

### Observability (all optional path overrides)

| Variable | Default | Purpose |
|---|---|---|
| `RETRIEVAL_LOG_PATH` | `retrieval_log.json` | Per-retrieval record: dense hits, keyword hits, RRF scores, expansion, agent steps, final decision. |
| `CLAIM_LOG_PATH` | `claim_logs.json` | Per-claim record. |
| `CHUNK_LOG_PATH` | `chunk_log.json` | Per-document chunking record. |
| `DOCUMENT_CHUNKS_DIR` | `chunks/` | Directory for per-document chunk JSON. |
| `TOKEN_USAGE_PATH` | `token_usage.json` | Token accounting behind `/usage`. |

> ⚠️ These JSON sinks contain **unredacted** policy and claim text. They are
> gitignored, but they are plaintext on disk. See
> [SECURITY.md §9](docs/SECURITY.md).

---

## Demo accounts

Created by `scripts/seed_users.py`. **Local demo credentials — never reuse them.**

| Role | Email | Password | Can do |
|---|---|---|---|
| `corp` | `e2ecorp@example.com` | `password123` | Everything: ingest, ask, approve/reject claims, view traces, view cost |
| `client` | `claimdemo@example.com` | `password123` | Ask questions, file claims, read and cancel **their own** claims |

There are exactly two roles, and `require_role` matches the string exactly — an
account with any other role authenticates successfully and is then refused by
every protected route. If you add a user by hand, use `client` or `corp`.

Prefer to sign up? `POST /auth/signup` accepts `client` and `corp` at
http://localhost:8000/docs.

---

## Running the tests

```bash
# Inside Docker — no local Python needed
docker compose exec app bash -lc "pip install -q pytest pytest-asyncio && pytest tests/unit tests/contract -q"
```

Or on the host, if you have Python 3.12:

```bash
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pytest tests/unit tests/contract -q          # fast: LLM is mocked, no network
pytest tests/integration -q                 # real DB + real retrieval
pytest -q                                   # everything
```

| Suite | Count | Time | Needs |
|---|---|---|---|
| `tests/unit` | 169 | ~25 s | nothing |
| `tests/contract` | 16 | ~3 s | nothing |
| `tests/integration` | 49 | ~8 min | running Postgres + Ollama |

Also worth running:

```bash
ruff check src/ tests/ scripts/     # lint
cd frontend && npm run build        # type-check + production build (tsc -b && vite build)
```

---

## Running the evaluation harness

Scores the system against a 25-question golden set covering normal questions,
out-of-corpus questions, ambiguity, conflicting sources and prompt injection.

```bash
docker compose exec app bash -lc \
  "pip install -q && PYTHONPATH=. python evaluation/run_harness.py"
```

Takes roughly 8–15 minutes on the 1b model and rewrites
`evaluation/baseline_results.json`. Read **[docs/EVALUATION.md](docs/EVALUATION.md)**
for the current numbers, the exact metric definitions, and an analysis of every
known failure.

> **Do not use `evaluation/run_eval_scripts.py`.** It is a superseded script that
> hardcodes `llama3.2:3b` — a model this project does not pull — and accepts
> command-line flags it does not actually parse. `run_harness.py` is the real
> harness.

---

## Troubleshooting

**`docker compose up` fails on the Ollama pull** — the model download needs
~1.4 GB and a few minutes. Re-run `docker compose logs -f ollama-init`; the
container retries. To pre-download on the host instead:
`ollama pull llama3.2:1b && ollama pull nomic-embed-text`.

**Port already in use** — something else owns 3000/8000/5432/6379/11434. Change
the left-hand side in `docker-compose.yml` (`"3001:80"`) or stop the other
process. Note that the Vite dev server also wants 3000.

**The API is up but every `/ask` refuses** — check the corpus is actually loaded:

```bash
docker compose exec db psql -U postgres -d domain_copilot -c "select count(*) from chunks;"
```

If that is `0`, run `seed_corpus.py`. If the count is right but everything
refuses, raise `MAX_COSINE_DISTANCE` in steps of `0.05` and watch
`retrieval_log.json` — each entry records the cosine distance that was compared
against the threshold.

**Claims sit at `pending` forever** — the Celery worker is not running:

```bash
docker compose ps worker        # must be Up
docker compose logs --tail=50 worker
```

**The worker OOM-kills during a claim** — you are on a small host. The default
`llama3.2:1b` is chosen for exactly this reason; do not switch to `3b` under
8 GB. Ingestion is the other memory hog: set
`UNSTRUCTURED_PDF_STRATEGY=fast` to trade layout accuracy for memory.

**Ingestion produces empty chunk text** — the installed `langchain_unstructured`
version changed its return shape. `document_loader.py` reads `page_content`
correctly for the pinned version; if you upgrade that library, re-check
`raw_chunks` before ingesting, because empty text **overwrites good data**. Take
a `pg_dump` first. Existing rows can be repaired for sections with
`scripts/backfill_chunk_sections.py` (it has `--dry-run`).

**Not logged in / cookies missing** — use the UI at http://localhost:3000 rather
than opening components in isolation. The Vite dev server proxies `/api`,
`/auth`, `/claims` to the backend so the session cookie is same-origin.

**Stale behaviour after editing source** — the worker does not hot-reload:

```bash
docker compose restart worker app
find src tests -name __pycache__ -prune -exec rm -rf {} +
```

**Reading the logs**

```bash
./scripts/system-logs          # last 5 events, then follow
./scripts/system-logs -f       # follow from now
docker compose logs -f app worker
```

Sinks, all gitignored: `system_logs.txt`, `workflow.log`, `retrieval_log.json`,
`claim_logs.json`, `chunk_log.json`, `token_usage.json`, `chunks/`.

---

## Where to look in the code

| Concern | Path |
|---|---|
| C4 + sequence + data-flow diagrams | [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md), source in `docs/diagrams/*.mmd` |
| Decision records | `docs/adr/000`–`005` |
| Ingestion (extract → chunk → embed) | `src/application/use_cases/ingest_document.py` |
| Section derivation (the expansion fix) | `src/infrastructure/ingestion/section_titles.py` |
| Hybrid retrieval, RRF, refusal gate | `src/application/retrieval/hybrid_search.py` |
| Grounded Q&A + confidence gate | `src/application/use_cases/ask_question.py` |
| Policy-number resolution | `src/application/retrieval/policy_resolver.py` |
| Multi-agent adjudication | `src/application/use_cases/run_adjudication.py`, `src/application/agents/*` |
| Agent tool set (closed) | `src/application/agents/base_agent.py` |
| Approval gate | `src/api/routes/approvals.py` |
| Auth, RBAC, ownership checks | `src/api/routes/auth.py`, `src/api/deps.py` |
| Streaming + cancel | `src/api/routes/ask.py` |
| Vector store (HNSW + FTS) | `src/infrastructure/vectorstore/pgvector_store.py` |
| Versioned prompts | `prompts/*/v1.md` |
| Retrieval logging | `src/infrastructure/observability/retrieval_logger.py` |
| Token/cost accounting | `src/infrastructure/observability/token_usage.py`, `src/api/routes/usage.py` |
| Frontend | `frontend/src/components/*` |

---

## Further reading

| Document | What it covers |
|---|---|
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | C4 L1–L3, full agentic sequence, trust boundaries, ER, layer rules, ADRs |
| [`docs/SECURITY.md`](docs/SECURITY.md) | Every control, **and every gap**, with file:line evidence |
| [`docs/EVALUATION.md`](docs/EVALUATION.md) | Golden set, metric definitions, current numbers, failure analysis |
| [`docs/API.md`](docs/API.md) | Endpoint reference with auth requirements |
| [`docs/BRD.md`](docs/BRD.md) | Requirements the build was traced against |
| [`docs/AGENTIC-WORKFLOW.md`](docs/AGENTIC-WORKFLOW.md) | How AI was used as a governed participant |
| [`docs/AI-USAGE-LOG.md`](docs/AI-USAGE-LOG.md) | What was delegated, and where the model misled us |
| [`teaching/`](teaching/) | 90-minute post-graduate session: slides, lab sheet, answer key, common mistakes |

---

## License

[MIT](LICENSE)
