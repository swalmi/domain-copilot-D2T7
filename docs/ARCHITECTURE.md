# Architecture

insureAI is an agentic RAG system for insurance claims adjudication. It answers
grounded questions against a corpus of real policy documents, and adjudicates a
submitted claim with three LLM agents whose output a human must approve before
money moves.

- **Diagram source is committed** in [`docs/diagrams/`](diagrams/) as Mermaid
  (`.mmd`) and embedded below so GitHub renders it.
  `tests/unit/test_architecture_docs.py` fails if the two copies drift.
- **Decision records** live in [`docs/adr/`](adr/) — see [ADRs](#adrs).
- **Trust boundaries and what the LLM sees** are in [Data flow](#data-flow-and-trust-boundaries).
  Read that section before changing anything prompt-related.

## Contents

- [C4 Level 1 — System context](#c4-level-1--system-context)
- [C4 Level 2 — Containers](#c4-level-2--containers)
- [C4 Level 3 — Components](#c4-level-3--components)
- [Sequence — agentic claim workflow](#sequence--the-agentic-claim-workflow)
- [Data flow and trust boundaries](#data-flow-and-trust-boundaries)
- [ER diagram](#er-diagram)
- [Layer dependencies](#layer-dependencies)
- [ADRs](#adrs)

---

## C4 Level 1 — System context

Two kinds of user, one system, two dependencies: the policy corpus and the LLM
provider. The system is deliberately *assistive* — it produces a recommendation,
and a human approves it.

```mermaid
%% C4 Level 1 — System Context
%% Canonical source. Rendered inline in docs/ARCHITECTURE.md; kept here so the
%% diagram can be linted/exported outside GitHub. tests/unit/test_architecture_docs.py
%% asserts the two copies stay identical.
graph LR
    claimant["Policyholder<br/><b>client</b>"]
    adjuster["Claims handler<br/><b>corp</b>"]

    subgraph system["insureAI — agentic RAG for insurance claims adjudication"]
        direction TB
        sysdesc["<b>insureAI</b><br/>Grounded question answering over a policy corpus<br/>and multi-agent claim adjudication<br/>with a human approval gate.<br/>Python 3.12 · FastAPI · Celery · pgvector"]
    end

    corpus[("Policy corpus<br/>30 third-party policy documents<br/>1,958 chunks")]
    llm["LLM provider<br/>Ollama (local, default)<br/>OpenRouter (optional fallback)"]

    claimant -->|"HTTPS/JSON + SSE<br/>submit claim, ask question,<br/>read own claims"| system
    adjuster -->|"HTTPS/JSON<br/>ingest policies, ask question,<br/>approve / reject / edit payout"| system

    system -->|"read + write<br/>documents, chunks, users,<br/>claims, trace_events"| corpus
    system -->|"prompt in: retrieved chunks + user text<br/>prompt out: generated text"| llm

    classDef person fill:#e8f0fe,stroke:#4285f4,color:#174ea6
    classDef sys fill:#e6f4ea,stroke:#34a853,color:#0b3d1c
    classDef store fill:#fef7e0,stroke:#fbbc04,color:#7a4b00
    classDef ext fill:#fce8e6,stroke:#ea4335,color:#a50e0e
    class claimant,adjuster person
    class sysdesc sys
    class corpus store
    class llm ext
```

**Read this as:** the only outbound trust dependency is the LLM provider. Policy
data and user data both reach it. There is no other network egress.

---

## C4 Level 2 — Containers

```mermaid
%% C4 Level 2 — Containers
%% Canonical source. Rendered inline in docs/ARCHITECTURE.md; kept here so the
%% diagram can be linted/exported outside GitHub. tests/unit/test_architecture_docs.py
%% asserts the two copies stay identical.
graph TB
    claimant["Policyholder<br/>(client)"]
    adjuster["Claims handler<br/>(corp)"]

    subgraph insureai["insureAI"]
        direction TB

        subgraph edge["Edge / presentation"]
            fe["<b>Frontend</b><br/>React 18 + Vite + Tailwind<br/>Served by nginx on :3000<br/>Talks to the API through the<br/>same-origin /api proxy"]
        end

        subgraph app["Application — Docker profile: app"]
            api["<b>REST API</b><br/>FastAPI on :8000<br/>Auth + RBAC on 22 of 23 routes<br/>SSE streaming, approval gate<br/>rate limiting NOT enforced"]
            ask["AskQuestionUseCase<br/>hybrid retrieval → RRF →<br/>refusal gate → grounded answer"]
        end

        subgraph worker["Async — Docker profile: worker"]
            celery["<b>Celery worker</b><br/>claim adjudication queue<br/>3 agents + per-agent<br/>timeout/retry"]
            orch["RunAdjudicationWorkflow<br/>CoverageMatcher → ExclusionAnalyst<br/>→ AdjudicationDrafter"]
        end

        subgraph data["State"]
            pg[("<b>PostgreSQL 16 + pgvector</b><br/>documents, chunks + 768-dim<br/>embeddings, users, claims,<br/>trace_events")]
            redis[("<b>Redis 7</b><br/>Celery broker/result backend<br/>+ pause/resume registry")]
        end

        obs["<b>Observability</b><br/>retrieval_log.json · system_logs.txt<br/>token_usage.json · trace_events"]
    end

    ollama["<b>Ollama</b><br/>llama3.2:1b + nomic-embed-text<br/>on :11434"]
    openrouter["OpenRouter<br/>optional hosted fallback"]

    claimant --> fe
    adjuster --> fe
    fe -->|"HTTP + text/event-stream"| api
    api --> ask
    api -->|"enqueue process_claim_adjudication"| celery
    celery --> orch
    orch -->|"LLM calls"| ollama
    api -->|"LLM calls"| ollama
    ask --> ollama
    orch -.->|"primary down"| openrouter
    api -.->|"primary down"| openrouter
    ask -.->|"primary down"| openrouter

    api --> pg
    celery --> pg
    ask -->|"hybrid search"| pg
    api <--> redis
    celery <--> redis
    api --> obs
    celery --> obs

    classDef person fill:#e8f0fe,stroke:#4285f4,color:#174ea6
    classDef container fill:#e6f4ea,stroke:#34a853,color:#0b3d1c
    classDef store fill:#fef7e0,stroke:#fbbc04,color:#7a4b00
    classDef ext fill:#fce8e6,stroke:#ea4335,color:#a50e0e
    class claimant,adjuster person
    class fe,api,ask,celery,orch,obs container
    class pg,redis store
    class ollama,openrouter ext
```

| Container | Port | Runs where | Notes |
|---|---|---|---|
| Frontend | `3000` (nginx → `80`) | `docker compose` | Vite dev server also uses `3000`; the proxy keeps cookies same-origin |
| REST API | `8000` | `docker compose`, or `./scripts/dev.sh` | Composition root — wires use cases and ports |
| Celery worker | — | `docker compose --profile worker`, or `./scripts/dev-worker.sh` | Claims only; nothing else is queued |
| PostgreSQL + pgvector | `5432` | `docker compose` | `pgvector/pgvector:pg16`; single database, no replicas |
| Redis | `6379` | `docker compose` | Celery broker **and** the pause/resume registry |
| Ollama | `11434` | `docker compose` | Default LLM + embedder; no API key required |

**Why claims are asynchronous.** Adjudication is three sequential LLM agents, each
with a 180 s timeout and one retry. That is minutes of work, which does not belong
in an HTTP request. The API returns `202` with a `correlation_id` immediately; the
client polls for `status` and `pipeline_stage`, and the worker owns the run.

---

## C4 Level 3 — Components

```mermaid
%% C4 Level 3 — Components: the API container, and the worker pipeline
%% Canonical source. Rendered inline in docs/ARCHITECTURE.md; kept here so the
%% diagram can be linted/exported outside GitHub. tests/unit/test_architecture_docs.py
%% asserts the two copies stay identical.
graph TB
    subgraph apiBox["<b>API container</b> — src/api"]
        direction TB
        subgraph security["Security middleware"]
            mw["Security headers<br/>nosniff · DENY · HSTS"]
            cors["CORS<br/>wildcard rejected at config"]
            rl["Limiter<br/>login/signup 5/min"]
        end
        subgraph routes["Route modules — src/api/routes"]
            authR["auth<br/>signup · login · logout · me"]
            docR["documents<br/>upload · list · delete · stream"]
            askR["ask<br/>SSE stream + cancel"]
            claimR["claims<br/>submit · pause · resume<br/>cancel · delete"]
            apprR["approvals<br/>approve · reject<br/>edit-and-approve"]
            runR["runs / usage<br/>trace · token cost"]
        end
        deps["deps.py<br/>get_current_user (JWT cookie)<br/>require_role('client'|'corp')<br/>_assert_claim_access (ownership)"]
    end

    subgraph ucBox["<b>Use cases</b> — src/application/use_cases"]
        direction TB
        ingUC["IngestDocumentUseCase<br/>extract → chunk → embed → upsert"]
        askUC["AskQuestionUseCase<br/>hybrid_search → confidence gate<br/>→ expand_to_parent_sections → prompt"]
        adjUC["RunAdjudicationWorkflow<br/>3 agents, timeouts, degradation"]
    end

    subgraph retBox["<b>Retrieval</b> — src/application"]
        direction TB
        hyb["HybridSearch<br/>dense + keyword → RRF(k=60)<br/>cosine-distance gate"]
        expander["ContextExpander<br/>group by (policy_id, version, section)"]
        resolver["PolicyResolver<br/>customer number → corpus id<br/>unambiguous or unfiltered"]
    end

    subgraph agentBox["<b>Agents</b> — src/application/agents"]
        direction TB
        base["BaseAgent<br/>closed tool set:<br/>search_policies · search_exclusions<br/>calculate_limits_and_deductibles<br/>submit_for_approval"]
        cm["CoverageMatcher"]
        ea["ExclusionAnalyst"]
        ad["AdjudicationDrafter"]
    end

    subgraph infraBox["<b>Infrastructure</b> — src/infrastructure"]
        direction TB
        vs[("PgVectorStore<br/>HNSW cosine · FTS keyword<br/>list_policy_ids")]
        prompts["prompts/*/v1.md<br/>versioned, loaded at runtime"]
        prov["ProviderRouter<br/>Ollama → OpenRouter fallback"]
        logger["Observability<br/>retrieval_logger · trace_logger<br/>token_usage · sanitize_pii"]
    end

    askR --> askUC
    docR --> ingUC
    claimR --> adjUC
    apprR --> claimR
    runR --> logger
    routes --> deps
    mw -.-> routes
    cors -.-> routes
    rl -.-> routes

    askUC --> hyb
    hyb --> expander
    expander --> vs
    hyb --> vs
    adjUC --> resolver
    adjUC --> base
    base --> cm
    base --> ea
    base --> ad
    cm --> hyb
    ea --> hyb
    hyb --> prompts
    askUC --> prompts
    prompts --> prov
    cm --> prov
    ea --> prov
    ad --> prov
    adjUC --> logger
    askUC --> logger
    ingUC --> logger

    classDef sec fill:#fce8e6,stroke:#ea4335,color:#a50e0e
    classDef comp fill:#e6f4ea,stroke:#34a853,color:#0b3d1c
    classDef uc fill:#e8f0fe,stroke:#4285f4,color:#174ea6
    classDef store fill:#fef7e0,stroke:#fbbc04,color:#7a4b00
    class security sec
    class routes,base,cm,ea,ad,hyb,expander,resolver,prompts,prov,logger comp
    class ucBox comp
    class uc uc
    class vs store
```

### The retrieval path, in order

1. `PolicyResolver` maps the customer's policy number to a corpus `policy_id`
   (`HO3-2024-884512 → SHELTER-HO3`). If it cannot resolve unambiguously it
   returns `unresolved` and retrieval runs **unfiltered** — it never guesses.
2. `HybridSearch` runs dense (pgvector HNSW, 40 candidates) and keyword
   (PostgreSQL FTS, 40 candidates) and fuses with RRF, `k=60`.
3. The **refusal gate** refuses when the best dense cosine distance exceeds
   `MAX_COSINE_DISTANCE` (default `0.35`). This replaced an RRF-score floor that
   could never fire, because every non-empty fusion scores at least `1/61`.
4. `ContextExpander` grows each hit to its full section, grouped by
   `(policy_id, version, section)`.
5. The prompt is assembled from a versioned file under `prompts/*/v1.md` — never a
   string literal in application code.

---

> **Read the API box honestly.** `SlowAPI` is imported and a `Limiter` is constructed
> with a `60/minute` default, but `SlowAPIMiddleware` is never registered, so no
> default limit applies to any route. The two routes carrying explicit
> `@limiter.limit` decorators do not fire either. `POST /ask` additionally carries
> **no authentication at all**, despite `docs/API.md` stating that every non-health
> endpoint requires a session. Both are findings, not oversights in the diagram —
> see `docs/SECURITY.md` §2.2 and §6.1.

## Sequence — the agentic claim workflow

The approval gate is the point of the sequence: the drafter *submits* a claim for
approval, and only a `corp` user can move it to `approved`.

```mermaid
%% Sequence — the full agentic claim workflow, with the approval gate and streaming
%% Canonical source. Rendered inline in docs/ARCHITECTURE.md; kept here so the
%% diagram can be linted/exported outside GitHub. tests/unit/test_architecture_docs.py
%% asserts the two copies stay identical.
sequenceDiagram
    autonumber
    actor C as Policyholder (client)
    actor A as Claims handler (corp)
    participant FE as Frontend
    participant API as FastAPI
    participant R as Redis
    participant W as Celery worker
    participant AG as Agents
    participant P as PgVectorStore
    participant L as LLM provider

    rect rgb(232, 240, 254)
    Note over C,API: 1 — Submit (idempotent, async)
    C->>FE: POST /claims {policy_number, date_of_loss,<br/>incident_description, claim_amount_requested, idempotency_key}
    FE->>API: POST /claims (session cookie)
    API->>API: require_role("client")
    API->>P: INSERT claims (status=pending, correlation_id)
    API->>R: enqueue process_claim_adjudication
    API-->>FE: 202 {claim_id, task_id, correlation_id}
    FE-->>C: "submitted — live progress begins"
    end

    rect rgb(255, 247, 224)
    Note over FE,W: 2 — Live progress (SSE poll, not a push stream)
    loop until terminal state
        FE->>API: GET /claims/{id}
        API-->>FE: {status, pipeline_stage}
    end
    opt operator pauses the run
        A->>API: POST /claims/{id}/pause
        API->>R: set pause key
        W->>R: check pause key before each stage
    end
    end

    rect rgb(230, 244, 234)
    Note over W,L: 3 — Adjudication, three agents, each with timeout + 1 retry
    W->>P: load claim + stage=reading_policy
    W->>AG: CoverageMatcher.execute(incident_description)
    AG->>AG: resolve policy number → corpus id<br/>(exact → distinctive segment → unfiltered)
    AG->>P: search_policies(policy_id, query)
    P->>L: embed query
    L-->>P: 768-dim vector
    P->>P: dense HNSW (40) + keyword FTS (40) → RRF(k=60) → top-6
    P-->>AG: ranked chunks with sections
    AG->>L: prompt: <coverage_documents> + question
    L-->>AG: CoverageMatchResult (JSON contract)
    Note right of AG: confidence == no_match → claim.status=refused,<br/>short-circuit. Agent raises → graceful degradation:<br/>fall back to AskQuestionUseCase and deny.

    W->>AG: ExclusionAnalyst.execute(claim + coverage)
    AG->>P: search_exclusions(...) + calculate_limits_and_deductibles(...)
    AG->>L: prompt: <exclusion_documents> + amounts
    L-->>AG: ExclusionAnalysisResult (JSON contract)

    W->>AG: AdjudicationDrafter.execute(everything so far)
    AG->>L: prompt: <adjudication_context> + both results
    L-->>AG: AdjudicationDraft (JSON contract)
    AG->>P: submit_for_approval(draft) → status=pending_approval
    end

    rect rgb(252, 232, 230)
    Note over A,P: 4 — Human approval gate — the LLM cannot approve a claim
    A->>API: GET /approvals
    API-->>A: claims awaiting decision
    A->>API: POST /approvals/{id}/edit-and-approve<br/>{adjusted_payout, justification, notes}
    API->>API: require_role("corp") + status must be pending_approval
    API->>P: status=approved, adjusted_payout, admin_justification
    P-->>C: client re-reads claim → approved + final_payout
    end

    rect rgb(248, 249, 250)
    Note over API,L: 5 — Ask path (grounded Q&A, streamed)
    C->>FE: POST /ask {query}
    FE->>API: POST /ask
    API->>L: embed + generate (streamed tokens)
    L-->>API: text/event-stream: token, metadata, citations
    API-->>FE: SSE frames
    Note right of API: client disconnect cancels the generator;<br/>generation/stream_cancelled is emitted
    end

    rect rgb(242, 242, 242)
    Note over API: 6 — Every retrieval writes one correlated record
    API->>P: retrieval_log.json: dense, keyword, RRF, expansion,<br/>agent steps, final decision
    API->>P: trace_events + token_usage.json
    end
```

### Failure paths worth knowing

| Failure | Behaviour | User sees |
|---|---|---|
| `CoverageMatcher` returns `no_match` | Short-circuit; no further agents | `status=refused` + reason |
| `CoverageMatcher` raises | Graceful degradation: fall back to `AskQuestionUseCase`, deny | `status=report_ready`, `recommendation=deny`, low confidence |
| An agent exceeds 180 s | One retry after 1 s, then give up on that agent | Degraded result, logged |
| The claim's policy number is unknown | Retrieve **unfiltered**, let the LLM decide | Normal adjudication |
| Worker dies mid-run | `claim.error_message` set, status `failed` | `GET /claims/{id}` shows the error |

---

## Data flow and trust boundaries

Five boundaries. The fourth is the one that matters: **the LLM provider is the
only place data leaves the host**, and it receives retrieved text verbatim.

```mermaid
%% Data flow — trust boundaries and exactly what crosses to the LLM provider
%% Canonical source. Rendered inline in docs/ARCHITECTURE.md; kept here so the
%% diagram can be linted/exported outside GitHub. tests/unit/test_architecture_docs.py
%% asserts the two copies stay identical.
flowchart TB
    subgraph TB1["<b>TB-1 · Untrusted client</b> — anything here is attacker-controlled"]
        U["Browser / curl<br/>no trust whatsoever"]
        Q["user question or<br/>claim incident_description"]
        F["uploaded file<br/>.pdf / .docx / .txt, ≤10 MB"]
        U --> Q
        U --> F
    end

    subgraph TB2["<b>TB-2 · Trust boundary: API edge</b> — auth, RBAC, validation<br/>NOTE: POST /ask is unauthenticated; rate limiter middleware is not registered"]
        API["FastAPI<br/>JWT cookie · require_role (not on /ask)<br/>Pydantic bounds (query unbounded)<br/>SlowAPI configured, NOT mounted<br/>ext+magic-byte upload check"]
        SAN["sanitize_pii<br/>SSN · email · phone only<br/>NOT applied to retrieval_log/claim_logs"]
    end

    subgraph TB3["<b>TB-3 · Trusted application core</b> — no raw user text reaches here unvalidated"]
        UC["Use cases"]
        POL["PolicyResolver<br/>never guesses a policy id"]
        GATE["Confidence gate<br/>refuse when top cosine distance > 0.35"]
        EXP["ContextExpander<br/>(policy_id, version, section)"]
        AG["Agents — closed tool set<br/>no network/filesystem tool exists"]
    end

    subgraph TB4["<b>TB-4 · Trust boundary: LLM provider — the only place our data leaves the host"]
        LLM["Ollama (default, localhost)<br/>or OpenRouter (optional, remote)"]
    end

    subgraph TB5["<b>TB-5 · Storage</b>"]
        PG[("Postgres + pgvector<br/>1,958 chunks · claims · users")]
        LOG[("repo-root JSON sinks<br/>retrieval_log · claim_logs<br/>chunk_log · token_usage")]
    end

    Q --> API
    F --> API
    API --> SAN
    SAN --> UC
    UC --> POL
    POL --> GATE
    GATE --> EXP
    EXP --> AG
    UC --> LOG
    AG --> LOG

    EXP ==>|"PROMPT IN — what the provider actually sees:<br/>① system framing (prompts/*/v1.md)<br/>② the user's question, verbatim, unescaped<br/>③ retrieved chunk text, verbatim, unescaped<br/>④ for claims: amounts, dates, policy number"| LLM
    LLM ==>|"PROMPT OUT — trusted only after validation:<br/>token stream for /ask;<br/>JSON for agents, rejected unless it parses<br/>into the Pydantic contract"| API

    AG --> PG
    GATE --> PG
    API --> PG

    classDef untrusted fill:#fce8e6,stroke:#ea4335,color:#a50e0e,stroke-width:2px
    classDef trusted fill:#e6f4ea,stroke:#34a853,color:#0b3d1c
    classDef store fill:#fef7e0,stroke:#fbbc04,color:#7a4b00
    classDef llmprov fill:#e8f0fe,stroke:#4285f4,color:#174ea6,stroke-width:3px
    class U,Q,F untrusted
    class API,SAN,UC,POL,GATE,EXP,AG trusted
    class PG,LOG store
    class LLM llmprov
```

### What the LLM provider receives

For `POST /ask`, the prompt is the concatenation of:

1. the system framing from `prompts/ask_qa/v1.md`;
2. the user's `query`, **verbatim and unescaped**;
3. up to `MAX_CONTEXT_CHARS` (6,000) characters of retrieved chunk text,
   **verbatim and unescaped**;
4. a delimiting instruction that the context is untrusted data, not instructions.

For a claim, the three agents additionally receive the claim amount, date of loss
and policy number. Nothing else — no credentials, no other users' claims, no
document bytes beyond retrieved chunks.

The delimiting instruction is **prompt-level only**. There is no sanitisation of
retrieved text, and an uploaded document is the realistic injection vector. The
mitigation that actually holds is structural: the agent tool set is closed in
`BaseAgent`, so a successful injection still cannot reach the network or the
filesystem. Note the check **fails open** — `base_agent.py:32` skips enforcement
whenever `ALLOWED_TOOLS` is empty, so a subclass that forgets the class variable loses
the control silently. `docs/SECURITY.md` §3.2 has the full analysis and residual risk.

---

## ER diagram

Five tables. Fields and comments are read from `src/infrastructure/db/models.py`.

```mermaid
%% ER diagram — the five tables, read straight from src/infrastructure/db/models.py
%% Canonical source. Rendered inline in docs/ARCHITECTURE.md; kept here so the
%% diagram can be linted/exported outside GitHub. tests/unit/test_architecture_docs.py
%% asserts the two copies stay identical.
erDiagram
    documents ||--o{ chunks : "contains (document_id)"
    users ||--o{ claims : "files (user_id, nullable)"

    documents {
        uuid id PK
        string filename "original name, echoed back by GET /documents"
        string content_hash UK "sha256 — idempotent re-ingest"
        string status "processing | ready | failed"
        datetime created_at
    }

    chunks {
        uuid id PK
        uuid document_id FK
        string policy_id "SHELTER-HO3, NAIC-MDL-280, ..."
        string policy_type "home | auto | commercial | regulatory"
        string version "e.g. 2007-01"
        date effective_date
        string section "derived heading, else 'page N' — groups expansion"
        string chunk_type "narrative | table"
        int page "1-based PDF page"
        text text "the only thing sent to the LLM as context"
        string content_hash
        float8 embedding "vector(768), nomic-embed-text"
    }

    users {
        uuid id PK
        string email UK
        string hashed_password "bcrypt cost 12"
        string role "client | corp — free-form String, no CHECK"
    }

    claims {
        uuid id PK
        string policy_number "customer form no., indexed"
        date date_of_loss
        text incident_description "untrusted free text, up to 10k chars"
        decimal claim_amount_requested "greater than 0, at most 10,000,000"
        string status "pending|processing|refused|report_ready|pending_approval|approved|rejected|cancelled"
        string pipeline_stage "reading_policy | building_report | done"
        uuid user_id FK "nullable — see SECURITY.md 2.3"
        uuid correlation_id "joins trace_events, logs, usage"
        string celery_task_id
        decimal calculated_payout
        decimal deductible_applied
        decimal policy_limit
        text recommendation
        text reasoning_text
        json citations "list of CitedChunk"
        decimal adjusted_payout "set only by the corp approval gate"
        text adjuster_notes
        text admin_justification
        text error_message
        datetime created_at
        datetime updated_at
    }

    trace_events {
        uuid id PK
        uuid correlation_id "indexed — the join key for /runs/{correlation_id}"
        string step_name
        string event_type
        json payload "sanitize_pii applied (SSN/email/phone only)"
        datetime timestamp
    }
```

Notes that a diagram cannot show:

- `claims.citations` and `claims.reasoning_text` are `NULL` until the pipeline
  finishes; a `report_ready` claim always has both.
- `trace_events` is written but never read back for authorization. It is an audit
  trail, not an access-control source.
- There is **no** approvals table. The approval decision is denormalised onto
  `claims` (`status`, `adjusted_payout`, `admin_justification`).

---

## Layer dependencies

```mermaid
%% Layer dependency — the Clean Architecture rule, and where it is actually violated
%% Canonical source. Rendered inline in docs/ARCHITECTURE.md; kept here so the
%% diagram can be linted/exported outside GitHub. tests/unit/test_architecture_docs.py
%% asserts the two copies stay identical.
graph LR
    subgraph inward["Dependencies point inward. Nothing on the left may import from the right."]
        direction LR
        UI["<b>Presentation</b><br/>frontend/src<br/>React components, SSE client"]
        API["<b>Interface</b><br/>src/api<br/>routes, deps, schemas, limiter"]
        APP["<b>Application</b><br/>src/application<br/>use cases, agents, retrieval"]
        DOM["<b>Domain</b><br/>src/domain<br/>entities, contracts, ports"]
        INFRA["<b>Infrastructure</b><br/>src/infrastructure<br/>pgvector, llm, observability"]
    end

    UI -->|"HTTP only"| API
    API --> APP
    APP --> DOM
    APP -->|"via ports only"| INFRA
    INFRA -.->|"implements the ports<br/>declared in domain"| DOM

    subgraph ports["Ports (src/domain/interfaces) — the only seam between application and infrastructure"]
        VS["VectorStore"]
        REPO["ClaimRepository · DocumentRepository · UserRepository"]
        LLM["LLMProvider"]
    end
    DOM --- ports
    INFRA -.-> ports

    note1["<b>Rule</b>: src/domain must not import an I/O framework —<br/>no fastapi, sqlalchemy, celery, langchain or pgvector.<br/>pydantic IS allowed there: the entities are validated value objects.<br/>Checked automatically by tests/unit/test_architecture.py."]
    note2["<b>Known, allow-listed exceptions (4 files)</b> — application reaches for infrastructure:<br/>ask_question · hybrid_search · run_adjudication (observability loggers)<br/>ingest_document (loader, embedder cache, table linker, chunk store)<br/>These are recorded in the test's allow-list, not hidden. See docs/SECURITY.md 3.4."]
    DOM -.-> note1
    APP -.-> note2

    classDef layer fill:#e6f4ea,stroke:#34a853,color:#0b3d1c
    classDef seam fill:#e8f0fe,stroke:#4285f4,color:#174ea6
    classDef note fill:#fef7e0,stroke:#fbbc04,color:#7a4b00
    class UI,API,APP,DOM,INFRA layer
    class VS,REPO,LLM seam
    class note1,note2 note
```

`src/api` importing use cases and ports is **not** a violation — the API is the
composition root, and wiring dependencies is its job.

The rule and the four allow-listed exceptions are both asserted by
`tests/unit/test_architecture.py`, so neither can grow unnoticed.

---

## ADRs

Six decision records, in [`docs/adr/`](adr/). Each states context, decision, and
consequences — including the consequences that turned out badly.

| ADR | Decision | Why it still holds |
|---|---|---|
| [000](adr/000-architecture-and-langchain-boundary.md) | Clean Architecture with LangChain confined to infrastructure | Keeps the domain testable without a network or a model |
| [001](adr/001-provider-abstraction-fallback.md) | `LLMProvider` port, Ollama primary, OpenRouter fallback | The system runs with no API key at all |
| [002](adr/002-prompt-injection-defense.md) | Delimit context, instruct the model to treat it as data, refuse when unsupported | Still the only *runtime* defence; the closed tool set is what actually holds |
| [003](adr/003-chunking-strategy.md) | Section-aware chunking with policy metadata | Sections are what make parent expansion and citations meaningful |
| [004](adr/004-vector-store-choice.md) | pgvector in Postgres, no dedicated vector DB | One backup, one transaction, one place to look |
| [005](adr/005-orchestration-pattern.md) | Supervised linear pipeline, not a free-form agent graph | Auditable and replayable; the approval gate needs a known order |

Two of these have been revised by experience, and the ADRs say so:

- **002** assumed instruction-level defences were sufficient. They are not the
  real control; see `docs/SECURITY.md` §3.
- **003** assumed a `Title` ancestor would always be present in extracted
  documents. The installed `langchain_unstructured` emits
  `category="CompositeElement"` with `parent_id=None`, so 1,956 of 1,958 chunks
  had an empty `section` and expansion silently did nothing. Sections are now
  derived from the chunk text (`src/infrastructure/ingestion/section_titles.py`),
  with `scripts/backfill_chunk_sections.py` to repair existing rows.
