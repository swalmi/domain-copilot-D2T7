# Agentic Coding Workflow

This repository is developed with AI as a **governed participant**, not an autonomous author. Configuration lives in-repo so reviewers can inspect exactly how direction is encoded.

## What is configured

| Asset | Location | Purpose |
|---|---|---|
| Project instruction file | `.agents/AGENTS.md` | Encodes Clean Architecture dependency rules, provider hierarchy (Ollama primary / OpenRouter fallback), docstring & prompt-externalisation standards, Conventional Commits. |
| Editor/MCP configuration | `opencode.json` | Ships the `shadcn` MCP server for consistent UI component generation. |
| Versioned prompt assets | `prompts/**/v1.md` | All LLM prompts are files under `prompts/` loaded via `prompt_loader` — never inline string literals in application code. |
| CI quality gates | `.github/workflows/ci.yml` | Pytest, ruff-equivalent install path, `pip-audit`, gitleaks secret scan, frontend build, npm audit — runs on every PR. |
| PR / issue templates | `.github/PULL_REQUEST_TEMPLATE.md`, `.github/ISSUE_TEMPLATE` | Forces structured PR descriptions (what / why / how tested) and linked issues. |
| Branch protection provisioning | `.github/workflows/provision-branch-protection.yml` | Automates required reviews / status checks on `main`. |
| CODEOWNERS | `CODEOWNERS` | Single-owner review path for a solo instructor repo. |
| MCP server | `opencode.json` → `shadcn` | Reusable component scaffolding without hand-rolled design drift. |

## Why these choices

1. **Architecture rules as first-class instructions** — the most common AI failure mode in layered codebases is adding framework imports into `src/domain/`. `AGENTS.md` is re-read before any domain/application edit so the dependency rule survives context switches.
2. **Prompts as versioned artifacts** — evaluation and A/B comparison require diffable prompts; files enable git history and golden-set regression testing.
3. **Hooks/gates in CI rather than chat** — humans forget; CI does not. Secret scan + dependency audit + tests are non-optional on PR.
4. **Scoped MCP (shadcn only)** — broad filesystem MCP access increases blast radius; this config only exposes the component registry needed for frontend work.

## What the agentic approach changed

- **Faster scaffolding** of CRUD routes, migrations, and React screens when boundaries were pre-declared.
- **Fewer architectural reverts** once `AGENTS.md` existed; earlier sessions occasionally violated Clean Architecture before the rule file was added.
- **Test doubles** for abstract interfaces were frequently missed by the model — caught by unit tests that instantiate concrete implementations of repository interfaces.

## Where agentic guidance failed

| Failure | Detection | Mitigation |
|---|---|---|
| Model invented endpoint paths / OpenAPI paths that did not match FastAPI mount prefixes | Live curl against `/openapi.json` | Always verify routes from the running app, not from memory. |
| Stale `.pyc` files after edits caused phantom `TypeError` on abstract methods | Direct import outside pytest | Clear `__pycache__` and restart workers after source edits. |
| Model proposed `pkill -f` patterns that self-matched the launching shell | Tool timeout / shell death | Kill by explicit PID lists; never combine `ps\|grep\|pkill` with a launch in one command. |
| Hallucinated completion of FR items (e.g. claiming token accounting before it existed) | Requirement checklist + code search | Maintain an explicit gap list; never accept “implemented” without a file/endpoint. |
| Integration tests appear to hang (slow `langchain_ollama` import) | Redirect pytest to log files with generous timeouts | Document import latency; prefer targeted suites for iteration. |

## How to verify the configuration yourself

```bash
# Architecture rules for the agent
cat .agents/AGENTS.md

# Prompt assets are files, not literals
ls prompts/*/

# CI gates
cat .github/workflows/ci.yml

# MCP servers
cat opencode.json
```
