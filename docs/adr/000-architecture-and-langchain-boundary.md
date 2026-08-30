# ADR-000: Clean Architecture style and LangChain boundary

## Status
Accepted

## Context
The system architecture requires choosing between Clean, Hexagonal, Onion, or Vertical Slice architectural styles. We need LangChain for LLM providers, document loaders, and vector store integration, but `src/domain/` and `src/application/` must stay framework-free to preserve high testability and domain independence.

## Decision
We adopt Robert C. Martin's Clean Architecture (Entities/Use Cases/Interface Adapters/Frameworks & Drivers) over Onion or Hexagonal — functionally nearly identical, but Clean Architecture's explicit Use Cases layer maps precisely onto our multi-agent orchestration workflow.

LangChain is confined entirely to `src/infrastructure/`: provider adapters, document loaders, and vector store integration. `src/domain/` and `src/application/` interact with LangChain-backed code only through our own abstract interfaces declared in `src/domain/interfaces/`, never importing `langchain` directly.

Only plain Pydantic models cross layer boundaries, per Martin's rule that "isolated, simple data structures are passed across the boundaries" — never framework-native types like LangChain's `AIMessage` or SQLAlchemy row objects.

## Alternatives considered
- **Onion Architecture**: Nearly identical; rejected only for terminology clarity (Clean Architecture's explicit Use Cases layer better matches our orchestration-heavy design).
- **Vertical Slice**: Rejected — feature-oriented slices would couple business logic to specific infrastructure per feature, undermining the provider-swap guarantee.
- **LangChain used throughout including orchestration**: Rejected — would violate the Dependency Rule and make orchestration harder to explain and defend.

## Consequences
Swapping any provider requires one new adapter file + config, never touching `src/domain/` or `src/application/`.

*Slight overhead*: Every infrastructure integration needs an interface + adapter pair, resulting in more files than a direct-call approach.
