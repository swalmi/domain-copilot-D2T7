# Domain Copilot

Quick start: assume Docker is installed. From repo root:

```bash
# optional: create Python venv, install deps, then
docker compose up --build
```

Local dev (fast):

1. Start backend (with venv active):
```bash
uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000
```
2. Start frontend:
```bash
cd frontend
npm install
npm run dev
# open http://localhost:3001/
```

Environment variables (see `.env.example`):
- `DATABASE_URL` — Postgres connection (postgresql+asyncpg://...)
- `REDIS_URL` — Redis connection (redis://localhost:6379/0)
- `JWT_SECRET` — HMAC key for JWT


5-Minute Demo Path
1. Start services (as above).
2. Open frontend and `Sign Up` as `corp@example.test` role `corp`.
3. In Documents → Upload a small `.txt` or `.pdf` policy file (use `POL-1001`). Watch the Ingestion Progress panel.
4. Open Ask; pick the uploaded policy in the dropdown; ask a policy-specific question.
5. Sign up as `client` and submit a claim in Claims tab. Observe task queued and use Pause/Resume to control execution.
6. Open `workflow.log` to inspect exaggerated trace events.

How to run tests & evaluation harness
```bash
python -m pytest
python evaluation/run_eval_scripts.py  # runs retrieval/eval harness
```

Troubleshooting
- If cookies are not set, ensure frontend is served via the Vite proxy (or set proper CORS and domain for cookies). See `src/api/routes/auth.py` and `frontend/vite.config.ts`.
- If using local Ollama, ensure the service is running on `OLLAMA_BASE_URL`.

Where to look in the code
- Ingestion: `src/application/use_cases/ingest_document.py`
- Tracing: `src/infrastructure/observability/trace_logger.py` and `workflow.log` (repo root)
- Pause/Resume: `src/infrastructure/observability/pause_registry.py` and `/claims/{id}/pause`
- Frontend: `frontend/src/components/*` (DocumentIngestion, AskQAStream, ClaimAdjudication)

Contact / Maintainer: Project Author

Setup (reproducible)
--------------------

1. Create the environment and install exact pinned packages:

```bash
./scripts/setup_env.sh
```

2. Activate the venv and run the inspector:

```bash
source .venv/bin/activate
python scripts/inspect_unstructured.py /path/to/document.pdf
```

Notes:
- `requirements.lock` pins the environment precisely to avoid dependency conflicts across machines.
