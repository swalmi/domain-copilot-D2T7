# Domain Copilot - handoff state (verified via bash/grep + py_compile + live E2E)
## Done (this session)
- system_logger.py: emit_system_log(phase, event, payload, correlation_id) + configure/get_path/set_correlation_id
  - FIXED import bug: `from collections.abc import Any` -> `from typing import Any` (broke app boot)
- configure_system_logger(root_dir / "system_logs.txt") wired at startup in src/api/main.py:47
- emit seams live (all call emit_system_log, all compile + import):
  - src/application/use_cases/ingest_document.py  (ingestion)
  - src/application/retrieval/hybrid_search.py     (retrieval)
  - src/application/use_cases/ask_question.py      (generation)
  - FIXED missing imports in ingest_document.py: emit_system_log, `time`
  - FIXED ask_question.py NameError `response_text` (now accumulates streamed tokens)
- SSE contract ALIGNED (backend+frontend, JSON-only):
  - ask.py: token -> `data: {"token": "..."}`, done -> `data: {"done": true, "citations": [...], "refused": bool, "correlation_id": "..."}`, terminator -> `data: [DONE]`; per-request correlation id via set_correlation_id
  - AskQAStream.tsx: parses `parsed.token`/`parsed.done`, breaks on `[DONE]`, maps citations (section/source/page/text_snippet), sends `policy_id` (was policy_number)
- worker health: GET /health/worker (celery control.ping via asyncio.to_thread; Celery 5.x returns list of {worker:{'ok':'pong'}}) -> 200 `{"status":"ok","workers":[...]}` or 503
- UI indicator: WorkerHealthIndicator pill in Navbar.tsx (polls /health/worker every 15s)
- .gitignore: added system_logs.txt + workflow.log (generated sinks)

## Verified live E2E (venv backend + docker infra, llama3.2:1b chat model)
- infra: db/redis/ollama healthy; celery worker container up
- ingest .txt (PDF path OOMs this 3.7GB host in unstructured hi_res) -> {"status":"success","chunks_count":1,"inserted_count":1}
- /ask SSE: HTTP 200 text/event-stream; tokens streamed as JSON; `[DONE]` seen; REFUSED False; CITATION_COUNT 1 (source/snippet/section page); correlation_id echoed
- system_logs.txt rows: ingestion/document_chunked, retrieval/query_embedded, retrieval/fusion_complete, generation/completed (token_count_estimate, citation_count, chunk ids, refused) — all under one correlation_id
- worker health: {"status":"ok","workers":["celery@6b29ab64cdf9"]}

## Environment notes
- HOST RAM is 3.7GB: llama3.2:3b FAILS to load in ollama ("timed out waiting for llama-server"), uvicorn was OOM-killed during hi_res PDF parse. Fallback that works: chat model OLLAMA_CHAT_MODEL=llama3.2:1b (pulled), .txt intake, `--no-reload` uvicorn.
- Backend left running as PID 57128 on :8000 (llama3.2:1b). dev.sh default still 3b if that env is unset on a bigger box.

## Ingestion pipeline visualization (Jenkins-style green checks)
- Backend: `POST /documents/stream` (documents.py) runs the SAME IngestDocumentUseCase but streams SSE per stage:
  `data: {"step": parsing|chunking|titling|embedding|storing|finalizing, "status": running|progress|completed|failed, "detail": "..."}`
  then `data: {"done": true, "result": {...}}` and `data: [DONE]`.
- Use case gained `on_progress` callback (ingest_document.py) + `asyncio.to_thread` around `load_and_chunk`/`link_tables_to_titles` so parsing never blocks the event loop mid-stream; also emits a new `ingestion/document_completed` system_log record (inserted/skipped/duration).
- Frontend DocumentIngestion.tsx: horizontal-free vertical pipeline card with stages labelled by description
  (Parsing: Reading the document / Chunking: Splitting into sections / Section Linking / Embedding / Storing: Saving to the database / Finalizing),
  green CheckCircle when passed, pulsing RefreshCw while running, red XCircle on failure, pending grey circle, live detail line per stage; offline fallback simulates stages.
- Verified live: 6-stage stream on renters_policy_v1.txt in ~8s, done.result `{"status":"success","inserted_count":1}`, system_logs `document_chunked` + `document_completed` under cid 02060349.

## Policy deletion (remove from knowledge base)
- `DELETE /documents/{document_id}` (documents.py, corp auth) loads the doc, deletes via `SqlalchemyDocumentRepository.delete_document` (ORM cascade removes every chunk row + the document's content_hash fingerprint; DB FK ondelete=CASCADE as backstop), then emits `ingestion/document_deleted` system_log (policy_id, chunks_removed).
- Domain interface + repository gained `delete_document(uuid) -> bool` (False when absent → route 404).
- Frontend Corpus Index: per-row Delete button (Trash2) with window.confirm, spinner while deleting, row removed on success, inline success/error message.
- Verified live: deleted POL-3003 (doc 20c982cc) → 0 chunk rows left, audited in system_logs, and re-uploading the identical file re-ingested as a NEW document (proves fingerprint gone).
- NOTE: never combine a `ps|grep`/kill of uvicorn with a launch of uvicorn in one bash invocation — the grep regex matches the launch string and self-kills the shell; do kill and launch as separate tool calls.

## Ask page returning "no info" — fixed (two root causes)
1. OOM death mid-stream: global OOM killed uvicorn (dmesg) right after the query-embed when llama3.2:1b cold-loaded on the 3.7GB host.
   - OllamaProvider now caps generation: `num_ctx=1024`, `num_predict=512` (defaults; factory passes no overrides), bounding llama KV memory + stream speed.
   - AskQuestionUseCase bounds RAG context via `_bounded_context` (MAX_CONTEXT_CHARS=6000).
   - docker-compose ollama env: `OLLAMA_KEEP_ALIVE=-1`, `OLLAMA_MAX_LOADED_MODELS=2`, and `docker/ollama-boot.sh` warmups llama3.2:1b + nomic-embed-text into memory at boot so per-ask cold-load spikes never occur.
   - Pinned config: `src/infrastructure/config.py` default `ollama_chat_model` changed 3b → `llama3.2:1b` and `.env` now sets `OLLAMA_CHAT_MODEL=llama3.2:1b`, `OLLAMA_EMBEDDING_MODEL=nomic-embed-text`, `OLLAMA_MODELS=llama3.2:1b,nomic-embed-text`. (3b caused OOM.)
2. Policy filter bug: AskQAStream dropdown filled from `/documents` sent the document UUID as `policy_id`, but the backend filters chunks by BUSINESS policy_id (`POL-1001`), so every filtered ask matched 0 chunks → refused. Dropdown now uses the `policy_id` from the API (fallback doc id), label `POL-xxxx — <filename>`, sends `policy_id ?? null`.
   - Frontend also surfaces honest stream errors now (red banner) instead of the old fake `simulateMockResponse` fallback; flags a truncated/no-`[DONE]` stream.
- Verified: unfiltered and `POL-1001` filtered asks stream tokens + 5 citations + `[DONE]` (4-34s), no OOM. Both models resident in ollama (`/api/ps`).
- Caveat: only `POL-1001` chunks exist in the DB right now (26); the renters re-ingest chunk did not persist (investigate if needed). Host memory is at the edge (334MB free with both models resident + docker + chrome) — do not load extra models or run 3b.

## "Bad gateway" / backend auto-restart (memory resilience)
- Global OOM killed uvicorn again (dmesg 23:58:34, uvicorn RSS 922MB). Root: 3.7GB host + resident ollama models + chrome.
- `scripts/dev-resilient.sh` (NEW): env rewrites (db/redis/ollama→localhost), `OLLAMA_CHAT_MODEL=llama3.2:1b`, `MALLOC_ARENA_MAX=2` + `PYTHONMALLOC=malloc` (uvicorn RSS now ~363MB vs ~922MB), and runs uvicorn in an auto-restart loop (NO --reload) so a 502 self-heals in ~15s. Start: `setsid nohup ./scripts/dev-resilient.sh >> /tmp/opencode/backend.log 2>&1 &`. Verified: killed uvicorn -9 → health recovered in ~15s.
- uvicorn has NO `--no-reload` flag on this version; reload is simply off by default (omit it).
- `POST /ask` generator now catches exceptions → yields `data: {"done": true, "error": ..., "correlation_id": ...}` + `[DONE]` instead of dying mid-connection; AskQAStream surfaces `parsed.error`.
- Verified live ask: 60 tokens, 5 citations, `[DONE]`, no error (~67s on this box). Backend :8000 (resilient launcher), frontend :3000 (vite), ollama 200.

## Single-system log view (`./scripts/system-logs`)
- Every ingestion stage transition (parsing/chunking/titling/embedding/storing/finalizing + per-chunk progress) now ALSO emits to `system_logs.txt` (was SSE-only) via `emit()` in `ingest_document.py` → `emit_system_log("ingestion", f"{step}_{status}", ...)`, correlation-id scoped.
- Ask/retrieval/generation: `query_received`, `query_embedded`, `fusion_complete`, `prompt_assembled`, `started`, `completed`/`refused` (both `execute` and `execute_stream`), token/citation counts.
- Adjudication: agent step events in `run_adjudication.py` (workflow_started, coverage_matcher_completed, coverage_matcher_failed_degraded, refused_no_match, exclusion_analyst_completed, adjudication_completed); claim lifecycle in `claims.py` (submit/pause/resume/cancel); approval decisions in `approvals.py` (approve/reject/edit_and_approved w/ reviewer).
- `scripts/system-logs` = tail -F `system_logs.txt` piped through `scripts/format_system_logs.py` (colorized phases). Entry `-f` = no history. README documents it.
- Caveat: Celery events only reach the repo-root sink when the worker runs via `dev-worker.sh` from repo root; the Docker worker container has no volume so it writes inside its own /app. `ruff check src/ tests/` now clean repo-wide.