# Project Instructions & Rules

> [!IMPORTANT]
> Before generating any code touching `src/domain/` or `src/application/`, re-read this file.

## Architectural Principles & Clean Architecture
- **Clean Architecture**: This project follows Clean Architecture (Robert C. Martin's formulation: Entities → Use Cases → Interface Adapters → Frameworks & Drivers).
- **The Dependency Rule**: Source code dependencies point inward only. Concrete implementations (in `src/infrastructure/`) implement abstract interfaces declared in `src/domain/interfaces/`.
- **`src/domain/` (Entities Layer)**: Zero imports outside Python standard library and `pydantic`.
- **`src/application/` (Use Cases Layer)**: May import from `src/domain/` only.
- **`src/infrastructure/` and `src/api/` (Interface Adapters + Frameworks & Drivers)**: May import anything (`langchain`, `fastapi`, `sqlalchemy`, `celery`).

## LLM Provider Hierarchy
- Ollama is the **PRIMARY** LLM/embedding provider (local, free, always available).
- OpenRouter is the **FALLBACK** provider, used only if Ollama fails or is unavailable. Do not default to treating OpenRouter as primary.

## Coding & Documentation Standards
- **Comment Policy**: Never write comments that restate obvious code (e.g., `# increment i`, `# call the function`). Only write comments to explain **WHY** a non-obvious decision was made.
- **Docstrings**: Every function and class must have a docstring explaining its purpose in one sentence.
- **Externalized Prompts**: All prompts sent to LLMs must live in `prompts/` as `.md` files, never as inline string literals in Python code.
- **Commit Message Format**: Follow Conventional Commits format for any commit message drafted: `type(scope): summary`.
