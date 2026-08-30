# Project-Wide Rules

1. **Comment Policy**: Never write comments that restate what the code obviously does (e.g., `# increment i`, `# call the function`). Only write comments to explain **WHY** a non-obvious decision was made (e.g., why a specific library parameter was chosen).
2. **Layer Cleanliness**: Never import `langchain`, `fastapi`, `sqlalchemy`, `celery`, or any LLM/DB/web-framework SDK inside `src/domain/` or `src/application/`. These layers may only import from Python's standard library, `pydantic`, and other files within `domain/` or `application/`.
3. **Externalized Prompts**: All prompts sent to LLMs must live in `prompts/` as `.md` files, never as inline string literals in Python code.
4. **Docstrings**: Every function and class must have a docstring explaining its purpose in one sentence. Docstrings are expected; inline comments explaining obvious code are not.
5. **Commit Message Format**: Follow Conventional Commits format for any commit message drafted: `type(scope): summary`.
6. **LLM Provider Hierarchy**: Ollama is the **PRIMARY** LLM provider for this project (local, free, always available). OpenRouter is the **FALLBACK** provider, used only if Ollama fails or is unavailable. Do not default to treating OpenRouter as primary.
