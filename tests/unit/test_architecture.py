"""Architecture guard: the dependency rule, enforced instead of merely documented.

`docs/diagrams/07-layer-dependencies.mmd` claims this rule is checked
automatically. These tests make that claim true, and they pin the known
exceptions so they cannot quietly grow.

Rule: ``src/domain`` may not import an I/O framework. ``pydantic`` is
deliberately allowed — the domain entities are validated value objects, and
pydantic performs no I/O.
"""

import ast
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[2] / "src"

#: Frameworks that perform I/O or bind us to a runtime. None may enter the domain.
FORBIDDEN_IN_DOMAIN = {
    "alembic",
    "celery",
    "fastapi",
    "httpx",
    "langchain",
    "langchain_core",
    "langchain_ollama",
    "langchain_openai",
    "pgvector",
    "requests",
    "slowapi",
    "sqlalchemy",
    "starlette",
    "unstructured",
}

#: Allowed in the domain: pure validation, no I/O.
ALLOWED_IN_DOMAIN = {"pydantic", "decimal", "datetime", "enum", "uuid", "typing"}

#: Application files that legitimately reach into infrastructure today, with the
#: reason. Adding a new one should be a deliberate decision, not an accident.
#:
#: Three use observability loggers; ingest_document genuinely orchestrates the
#: extraction pipeline. Tracked in docs/SECURITY.md 3.4.
KNOWN_APPLICATION_INFRASTRUCTURE_IMPORTS = {
    "src/application/retrieval/hybrid_search.py": "observability loggers",
    "src/application/use_cases/ask_question.py": "observability loggers",
    "src/application/use_cases/run_adjudication.py": "observability + pause registry",
    "src/application/use_cases/ingest_document.py": "loader, embedder cache, table linker, chunk store",
}


def _top_level_imports(path: Path) -> set[str]:
    """Return the root package of every absolute import in ``path``."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            roots.add(node.module.split(".")[0])
    return roots


def _python_files(root: Path) -> list[Path]:
    return sorted(root.rglob("*.py"))


@pytest.mark.parametrize(
    "path", _python_files(SRC / "domain"), ids=lambda p: p.name
)
def test_domain_imports_no_io_framework(path: Path) -> None:
    offenders = _top_level_imports(path) & FORBIDDEN_IN_DOMAIN
    assert not offenders, (
        f"{path.relative_to(SRC)} imports {sorted(offenders)}; the domain layer "
        "must stay free of I/O frameworks. Move the I/O behind a port in "
        "src/domain/interfaces and inject it."
    )


@pytest.mark.parametrize(
    "path", _python_files(SRC / "domain"), ids=lambda p: p.name
)
def test_domain_imports_only_stdlib_and_pure_libraries(path: Path) -> None:
    """Catch a new third-party dependency in the domain even if it is not banned."""
    import sys

    permitted = (
        set(sys.stdlib_module_names)
        | ALLOWED_IN_DOMAIN
        | FORBIDDEN_IN_DOMAIN  # already rejected by the test above; listed for clarity
        | {"src", "__future__"}  # first-party and deferred-annotation machinery
    )
    unexpected = _top_level_imports(path) - permitted
    assert not unexpected, (
        f"{path.relative_to(SRC)} imports {sorted(unexpected)}, which is neither "
        "the standard library, a first-party module, nor an allow-listed pure "
        "library. Add it to ALLOWED_IN_DOMAIN only if it performs no I/O."
    )


def test_application_infrastructure_imports_stay_allow_listed() -> None:
    """The application layer may only reach infrastructure where it already does."""
    actual: dict[str, list[str]] = {}
    for path in _python_files(SRC / "application"):
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        infra: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                if node.module.startswith("src.infrastructure"):
                    infra.add(node.module)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith("src.infrastructure"):
                        infra.add(alias.name)
        if infra:
            actual[str(path.relative_to(SRC.parent))] = sorted(infra)

    assert set(actual) == set(KNOWN_APPLICATION_INFRASTRUCTURE_IMPORTS), (
        "The set of application modules importing src.infrastructure changed.\n"
        f"  expected: {sorted(KNOWN_APPLICATION_INFRASTRUCTURE_IMPORTS)}\n"
        f"  actual:   {sorted(actual)}\n"
        "If a new one is intentional, add it to "
        "KNOWN_APPLICATION_INFRASTRUCTURE_IMPORTS with a reason in a comment, and "
        "record it in docs/SECURITY.md 3.4. If it is not, inject a port instead."
    )
