# Security Policy & Threat-to-Control Matrix

## Overview
Domain Copilot implements defense-in-depth security controls targeting both **OWASP Web Top 10** and **OWASP LLM Top 10** vulnerabilities across API endpoints, data ingestion pipelines, agent prompt templates, and execution tracing.

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
| **Prompt Injection (OWASP LLM01)** | Instruction-defense delimiters (`<<<BEGIN DOCUMENT CONTEXT>>>`) framing retrieved reference material across all prompts. | [`prompts/`](file:///home/swalmi/domain-copilot/prompts/) | Integration test [`test_security_llm.py`](file:///home/swalmi/domain-copilot/tests/integration/test_security_llm.py) running 3 injection attack cases. |
| **Insecure Output Handling (OWASP LLM02)** | Strict Pydantic contract parsing of LLM outputs before downstream processing; zero raw shell/SQL executions. | [`src/application/agents/base_agent.py`](file:///home/swalmi/domain-copilot/src/application/agents/base_agent.py) | Integration test [`test_security_llm.py`](file:///home/swalmi/domain-copilot/tests/integration/test_security_llm.py). |
| **Unbounded Consumption (OWASP LLM04)** | Hard token output caps (`max_tokens=2048`) on LLM providers, payload max-lengths, and workflow circuit breakers. | [`src/infrastructure/llm/`](file:///home/swalmi/domain-copilot/src/infrastructure/llm/), [`src/api/routes/claims.py`](file:///home/swalmi/domain-copilot/src/api/routes/claims.py) | Unit tests [`test_ollama_provider.py`](file:///home/swalmi/domain-copilot/tests/unit/infrastructure/test_ollama_provider.py). |
| **Sensitive Info Disclosure (OWASP LLM06)** | Regex-based PII scrubber removing SSNs, email addresses, and phone numbers prior to trace log storage. | [`src/infrastructure/observability/trace_logger.py`](file:///home/swalmi/domain-copilot/src/infrastructure/observability/trace_logger.py) | Integration test [`test_security_llm.py`](file:///home/swalmi/domain-copilot/tests/integration/test_security_llm.py). |
| **Supply Chain Vulnerabilities (OWASP LLM05)** | Exact version pinning in `requirements.txt` and vulnerability scanning via `pip-audit`. | [`requirements.txt`](file:///home/swalmi/domain-copilot/requirements.txt), [`.github/workflows/ci.yml`](file:///home/swalmi/domain-copilot/.github/workflows/ci.yml) | Automated CI job running `pip-audit`. |
| **No Secrets in Repo History** | Gitleaks secret scanner in CI pipeline + manual full-history scan before submission. | [`.github/workflows/ci.yml`](file:///home/swalmi/domain-copilot/.github/workflows/ci.yml) | CI Gitleaks action step + local `gitleaks detect` full history scan. |

---

## Conclusion
Domain Copilot maintains zero secrets across git commit history and enforces complete threat mitigations across web and LLM attack vectors.
