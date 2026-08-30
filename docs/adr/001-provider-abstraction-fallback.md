# ADR-001: Provider abstraction hierarchy and fallback chain strategy

## Status
Accepted

## Context
The project brief requires at least two LLM provider implementations combining hosted and local options, configurable provider selection, a documented fallback chain, and a design resilient to free-tier exhaustion or rate limiting.

## Decision
We adopt **Ollama** (local, free, always-available) as the **PRIMARY** provider for both chat completion and embedding generation.

We adopt **OpenRouter** (hosted, offering free-tier models) as the **FALLBACK** provider for chat completion and tool calling. The supported OpenRouter free-tier model options include:
- NVIDIA: `nvidia/nemotron-3-30b-a3b:free`
- OpenAI: `openai/gpt-4o-mini:free`
- Liquid: `liquid/lfm-2.5-2.6b:free`

**Embedding Invariance**: Vector embeddings always route to `OllamaProvider` (using `nomic-embed-text`) regardless of which chat provider is active. Mixing embedding models mid-corpus would silently corrupt vector-space consistency and break semantic retrieval.

When primary chat or tool-calling operations fail, `ProviderRouter` logs the failure with `agent="LLMRouter"`, `tool_name=None`, and `step_type="fallback_triggered"`, then transparently retries the exact same operation via `OpenRouterProvider`.

## Alternatives considered
- **OpenRouter Primary / Ollama Fallback**: A common pattern, but rejected because it risks burning limited hosted free-tier credits and hitting rate limits during routine development and test execution.
- **Ollama Only (No Fallback)**: Rejected because it does not satisfy the requirement for $\ge 2$ provider implementations and loses access to stronger hosted models for complex reasoning tasks.

## Consequences
- **Local Autonomy**: Local development operates indefinitely without incurring hosted API costs or facing quota exhaustion.
- **Quality Trade-off**: Local model quality (`llama3.2:3b`) is lower than larger hosted models for complex reasoning; this trade-off will be documented honestly in `EVALUATION.md`.
