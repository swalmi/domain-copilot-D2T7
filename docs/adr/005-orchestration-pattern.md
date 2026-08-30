# ADR-005: Multi-Agent Orchestration Pattern — Hand-Rolled Pipeline

## Status
Accepted

## Context
The Domain Co-Pilot application automates complex insurance claim adjudication through a series of specialized agent evaluations:
1. **Coverage Matcher**: Matches claim incident details to specific policy coverage sections using hard version-date pre-filtering.
2. **Exclusion Analyst**: Evaluates applicable exclusions and extracts deductible and policy limit numeric values from retrieved policy text.
3. **Adjudication Drafter**: Composes a structured, human-readable adjudication recommendation and submits the draft for human approval.

We needed to select an architectural orchestration pattern to coordinate execution, handle agent dependencies, enforce security controls, and manage failure recovery.

## Options Considered

### Option 1: Dynamic Supervisor Pattern
A central LLM supervisor dynamically selects which agent to invoke next at runtime based on conversation history and state.

* **Pros**: Flexible routing for highly non-deterministic workflows.
* **Cons**: Introduces non-deterministic routing loops, increases latency and token cost, and creates risks of infinite agent loops or invalid state transitions.

### Option 2: Heavyweight Graph Framework (e.g. LangGraph / AutoGen)
Using a multi-agent framework like LangGraph to construct state graphs, conditional edges, and persistence loops.

* **Pros**: Built-in state graph visualizer and node routing abstractions.
* **Cons**: Adds a second complex LLM framework layer on top of our existing provider abstractions, increases vendor lock-in, complicates debugging, and masks underlying execution flow.

### Option 3: Hand-Rolled Plain Async Python Pipeline (Selected)
A deterministic, linear async Python pipeline (`RunAdjudicationWorkflowUseCase`) invoking agents sequentially: Coverage Matcher $\rightarrow$ Exclusion Analyst $\rightarrow$ Adjudication Drafter.

* **Pros**: 100% transparent execution flow, zero third-party framework overhead, explicit typing via Pydantic contracts, deterministic error handling, 30s timeouts, 1-time exponential backoff retries, and graceful degradation fallbacks.
* **Cons**: Requires explicit Python code for sequential execution steps.

## Decision
We chose **Option 3: Hand-Rolled Plain Async Python Pipeline**.

## Rationale
1. **Inherent Linearity**: Claim adjudication in domain insurance is naturally linear (`Receive Claim` $\rightarrow$ `Match Policy Version` $\rightarrow$ `Evaluate Coverage & Exclusions` $\rightarrow$ `Calculate Payout` $\rightarrow$ `Draft Recommendation`). Each step's output is a strict, typed prerequisite for the subsequent step (e.g. Exclusion Analyst cannot evaluate limits without a resolved `CoverageMatchResult`).
2. **Deterministic Security & Reliability**: Enterprise insurance applications prioritize stability, predictability, and auditability over open-ended autonomy. A hand-rolled pipeline guarantees that agents execute in exact order with zero dynamic loop risk.
3. **Clean Architecture Compliance**: Hand-rolled async Python keeps the Use Case layer free of external framework dependencies (obeying Robert C. Martin's Dependency Rule).
4. **Resilience Safeguards**: The pipeline incorporates explicit timeouts (30s), exponential backoff retries (2s wait), circuit breakers preventing infinite recursion, and graceful degradation to `AskQuestionUseCase` fallback drafts if an agent fails.

## Consequences
* The workflow sequence is explicitly defined in `RunAdjudicationWorkflowUseCase.execute()`.
* All inter-agent data passing relies on strict Pydantic contracts (`CoverageMatchResult`, `ExclusionAnalysisResult`, `AdjudicationDraft`).
* Tracing and observability are cleanly integrated via `@traced_step` decorator instrumentation without framework magic.
