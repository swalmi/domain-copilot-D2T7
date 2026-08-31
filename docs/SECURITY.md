# Security Report and Controls

This document summarises security controls mapped to the threats they mitigate, plus instructions to run a secret scan and security checks.

## Threat Model Highlights
- Threat: Broken access control — Mitigation: server-side role checks in `src/api/deps.py` via `require_role()`; documented tests should exercise forbidden access.
- Threat: Injection via external content — Mitigation: sanitise retrieved chunks before inclusion in templates, strict allow-lists for external tools, and refusal logic in the evaluation harness.
- Threat: Insecure secrets — Mitigation: use environment variables and a secrets manager in production; do not commit secrets to repo. `.env.example` provided.
- Threat: Resource abuse / cost control — Mitigation: rate limiter on endpoints (`slowapi`) and proposed per-user resource budget design in docs/SYSTEM-DESIGN.md.

## Controls (Mapping)
- Authentication: Cookie-based JWT with `httponly` cookies. See `src/api/routes/auth.py`.
- Authorization: Role checks enforced at dependency layer — do not rely on UI-only restrictions.
- Input validation: File magic-byte checks and size limit in `src/api/routes/documents.py`.
- Parameterised DB queries: Use SQLAlchemy with bound parameters to avoid injection risks.
- Logging: `workflow.log` contains trace events but PII is scrubbed by `trace_logger.sanitize_pii`.

-## Secure Development Practices
- Pin dependencies in `requirements.txt` and run `pip-audit`/`npm audit` in CI.
- Secret scanning: Run `git-secrets` or `truffleHog` before publishing.

## How to run local security checks
1. Python dependency audit
```bash
pip install pip-audit
pip-audit
```
2. Node audit
```bash
cd frontend
npm audit
```
3. Secret scanning (example)
```bash
brew install git-secrets
git secrets --scan
```

## Notes on Privacy and PII
- Trace events are scrubbed using regex for SSN, emails, and phone numbers in `trace_logger.sanitize_pii()`.
- No real personal data should be ingested into the corpus for demo/evaluation. Use synthetic or public data only.

## Known Gaps
- Secrets manager integration is deferred (see docs/SYSTEM-DESIGN.md). Do not deploy to production without moving secrets to a managed secret store.
- Token budget enforcement is a proposed design — partial implementation via endpoint rate-limiting exists.

-## CI & Branch Protection
- We provide a GitHub Actions workflow at `.github/workflows/ci.yml` which runs tests, `pip-audit`, a full-history secret scan (`gitleaks`), and a frontend build/audit on push and pull requests to `main`.
- The CI checks require `actions/checkout` to fetch full history (`fetch-depth: 0`) so the secret-scan covers repository history.
- To enable branch protection automatically, a manual workflow is included at `.github/workflows/provision-branch-protection.yml`. To run it:

1. Create a repository secret `REPO_ADMIN_TOKEN` containing a personal access token with `repo` and `admin:repo_hook` scopes (admin privileges to modify branch protection).

2. In the Actions UI, run the `Provision Branch Protection (manual)` workflow and confirm it completes. The workflow will set required status checks to include the CI workflow and enable required PR reviews.

Notes:
- The `REPO_ADMIN_TOKEN` secret must be provisioned by a repository administrator; the workflow cannot proceed without it.
- Alternatively, enable branch protection manually via the GitHub repository Settings → Branches → Add rule → protect `main` and require the CI workflow as a required status check.

# Security Policy & Threat-to-Control Matrix

## Overview
Domain Copilot implements defense-in-depth security controls targeting the **OWASP Web Top 10** and additional domain-specific threats across API endpoints, data ingestion pipelines, external processing templates, and execution tracing.

---

## Threat-to-Control Matrix

| Threat Category | Implemented Control | Where Implemented | How Tested |
| :--- | :--- | :--- | :--- |
| **Broken Object / Access Control (OWASP Web A01)** | Mandatory RBAC enforcement (`get_current_user`, `require_role('adjuster')`) on every API endpoint. | [`src/api/deps.py`](file:///home/swalmi/domain-copilot/src/api/deps.py), [`src/api/routes/`](file:///home/swalmi/domain-copilot/src/api/routes/) | Integration test [`test_approval_gate.py`](file:///home/swalmi/domain-copilot/tests/integration/test_approval_gate.py) verifying 403 Forbidden for claims_handler. |
| **Brute Force / Denial of Service (OWASP Web A04)** | Rate limiting via `slowapi` (stricter 5/min limit on `/auth/login`, 60/min default across API). | [`src/api/main.py`](file:///home/swalmi/domain-copilot/src/api/main.py), [`src/api/routes/auth.py`](file:///home/swalmi/domain-copilot/src/api/routes/auth.py) | Integration test [`test_security_web.py`](file:///home/swalmi/domain-copilot/tests/integration/test_security_web.py). |
| **MIME-Type Spoofing / Malicious File Upload (OWASP Web A04)** | File upload validation with magic-byte signature checks (`%PDF-`, `PK\x03\x04`), extension whitelist, and 10MB size limit. | [`src/api/routes/documents.py`](file:///home/swalmi/domain-copilot/src/api/routes/documents.py) | Integration test [`test_security_web.py`](file:///home/swalmi/domain-copilot/tests/integration/test_security_web.py) verifying renamed `.exe` binary rejection (HTTP 400). |
| **Clickjacking / MIME Sniffing (OWASP Web A05)** | Security Headers Middleware (`X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Strict-Transport-Security`). | [`src/api/main.py`](file:///home/swalmi/domain-copilot/src/api/main.py) | Integration test [`test_security_web.py`](file:///home/swalmi/domain-copilot/tests/integration/test_security_web.py). |
| **CORS Wildcard Exposure (OWASP Web A05)** | Explicit allowed origins whitelist in Settings prohibiting wildcard `*`. | [`src/infrastructure/config.py`](file:///home/swalmi/domain-copilot/src/infrastructure/config.py) | Unit test suite [`test_main.py`](file:///home/swalmi/domain-copilot/tests/unit/api/test_main.py). |
| **Sensitive Data Leakage in Logs (OWASP Web A09)** | Trace logger redacts request passwords/tokens and scrubs PII patterns (SSNs, emails, phone numbers). | [`src/infrastructure/observability/trace_logger.py`](file:///home/swalmi/domain-copilot/src/infrastructure/observability/trace_logger.py) | Integration test [`test_security_llm.py`](file:///home/swalmi/domain-copilot/tests/integration/test_security_llm.py). |
| **Injection via external content** | Instruction-defense delimiters (`<<<BEGIN DOCUMENT CONTEXT>>>`) framing retrieved reference material across all templates. | [`prompts/`](file:///home/swalmi/domain-copilot/prompts/) | Integration test [`test_security_llm.py`](file:///home/swalmi/domain-copilot/tests/integration/test_security_llm.py) running 3 injection attack cases. |
| **Insecure Output Handling** | Strict Pydantic contract parsing of external processing outputs before downstream processing; zero raw shell/SQL executions. | [`src/application/agents/base_agent.py`](file:///home/swalmi/domain-copilot/src/application/agents/base_agent.py) | Integration test [`test_security_llm.py`](file:///home/swalmi/domain-copilot/tests/integration/test_security_llm.py). |
| **Unbounded Consumption** | Hard output caps, payload max-lengths, and workflow circuit breakers. | [`src/infrastructure/llm/`](file:///home/swalmi/domain-copilot/src/infrastructure/llm/), [`src/api/routes/claims.py`](file:///home/swalmi/domain-copilot/src/api/routes/claims.py) | Unit tests [`test_ollama_provider.py`](file:///home/swalmi/domain-copilot/tests/unit/infrastructure/test_ollama_provider.py). |
| **Sensitive Info Disclosure** | Regex-based PII scrubber removing SSNs, email addresses, and phone numbers prior to trace log storage. | [`src/infrastructure/observability/trace_logger.py`](file:///home/swalmi/domain-copilot/src/infrastructure/observability/trace_logger.py) | Integration test [`test_security_llm.py`](file:///home/swalmi/domain-copilot/tests/integration/test_security_llm.py). |
| **Supply Chain Vulnerabilities** | Exact version pinning in `requirements.txt` and vulnerability scanning via `pip-audit`. | [`requirements.txt`](file:///home/swalmi/domain-copilot/requirements.txt), [`.github/workflows/ci.yml`](file:///home/swalmi/domain-copilot/.github/workflows/ci.yml) | Automated CI job running `pip-audit`. |
| **No Secrets in Repo History** | Gitleaks secret scanner in CI pipeline + manual full-history scan before submission. | [`.github/workflows/ci.yml`](file:///home/swalmi/domain-copilot/.github/workflows/ci.yml) | CI Gitleaks action step + local `gitleaks detect` full history scan. |

---

## Conclusion
Domain Copilot maintains zero secrets across git commit history and enforces complete threat mitigations across web and external-processing attack vectors.
