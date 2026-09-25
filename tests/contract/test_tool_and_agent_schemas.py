"""Contract tests for agent, tool and prompt schemas (FR-4).

These tests pin the agreements the orchestrator relies on — which agent may call
which tool, what each agent returns, and which placeholders each prompt demands —
so a change to any of them fails fast in CI instead of at runtime. No database,
no LLM, no network.
"""

import inspect
import json
import string
import uuid
from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest
from pydantic import BaseModel

from src.application.agents.adjudication_drafter import AdjudicationDrafter
from src.application.agents.base_agent import BaseAgent
from src.application.agents.coverage_matcher import CoverageMatcher
from src.application.agents.exclusion_analyst import ExclusionAnalyst
from src.application.contracts import (
    AdjudicationDraft,
    CoverageMatchResult,
    ExclusionAnalysisResult,
)
from src.application.retrieval.prompt_loader import load_prompt
from src.application.tools import __all__ as TOOL_EXPORTS
from src.application.tools.submit_for_approval import submit_for_approval
from src.domain.entities.claim import Claim
from src.domain.entities.policy import CitedChunk
from src.domain.interfaces.claim_repository import ClaimRepository
from src.domain.interfaces.llm_provider import LLMProvider

AGENTS: list[type[BaseAgent]] = [CoverageMatcher, ExclusionAnalyst, AdjudicationDrafter]
CONTRACTS: list[type[BaseModel]] = [
    CoverageMatchResult,
    ExclusionAnalysisResult,
    AdjudicationDraft,
]
WRITE_TOOL = "submit_for_approval"

#: Prompt template each agent loads, with the placeholders it must supply.
AGENT_PROMPTS: dict[type[BaseAgent], tuple[str, set[str]]] = {
    CoverageMatcher: (
        "coverage_matcher",
        {"policy_number", "date_of_loss", "incident_description", "retrieved_sections"},
    ),
    ExclusionAnalyst: (
        "exclusion_analyst",
        {"incident_description", "claim_amount_requested", "retrieved_exclusions"},
    ),
    AdjudicationDrafter: (
        "adjudication_drafter",
        {
            "claim_amount_requested",
            "incident_description",
            "coverage_confidence",
            "deductible_applied",
            "calculated_payout",
            "policy_limit",
            "policy_number",
        },
    ),
}

RUN_CONTRACTS: dict[type[BaseAgent], type[BaseModel]] = {
    CoverageMatcher: CoverageMatchResult,
    ExclusionAnalyst: ExclusionAnalysisResult,
    AdjudicationDrafter: AdjudicationDraft,
}


def make_chunk() -> CitedChunk:
    """Build a valid CitedChunk for contract round-trips."""
    return CitedChunk(
        chunk_id=uuid.uuid4(),
        text="Coverage section text for dwelling property loss.",
        source_document="ho3_policy.pdf",
        section="SECTION I - COVERAGES",
        page=1,
        policy_id="POL-HO3",
        version="1.0",
        effective_date=date(2026, 1, 1),
        chunk_type="narrative",
        policy_type="home",
    )


def make_claim() -> Claim:
    """Build a valid Claim entity for tool contract tests."""
    return Claim(
        id=uuid.uuid4(),
        policy_number="POL-HO3",
        date_of_loss=date(2026, 1, 15),
        incident_description="Water damage to kitchen ceiling.",
        claim_amount_requested=Decimal("12000.00"),
        status="report_ready",
    )


class StubRepository(ClaimRepository):
    """In-memory ClaimRepository that records every persisted claim."""

    def __init__(self, claim: Claim) -> None:
        self.claim = claim
        self.saved: list[Claim] = []

    async def save(self, claim: Claim) -> None:
        self.claim = claim
        self.saved.append(claim)

    async def get_by_id(self, claim_id: uuid.UUID) -> Claim | None:
        return self.claim if self.claim.id == claim_id else None

    async def list_pending_approvals(self) -> list[Claim]:
        return [self.claim] if self.claim.status == "pending_approval" else []

    async def list_all(self) -> list[Claim]:
        return [self.claim]

    async def list_by_user(self, user_id: uuid.UUID) -> list[Claim]:
        return [self.claim]

    async def delete(self, claim_id: uuid.UUID) -> bool:
        return False


def test_every_registered_tool_is_covered_by_an_agent_allow_list() -> None:
    """Each exported tool is reachable through some agent's explicit allow-list."""
    registry = set(TOOL_EXPORTS)
    used_by = {tool for agent in AGENTS for tool in agent.ALLOWED_TOOLS}

    assert registry, "tool registry must not be empty"
    assert used_by <= registry, f"unknown tools referenced: {used_by - registry}"
    assert registry - used_by == set(), f"tools no agent may call: {registry - used_by}"


def test_write_tool_is_restricted_to_the_drafter() -> None:
    """Only the drafter holds the side-effecting tool; readers never get it."""
    holders = [a for a in AGENTS if WRITE_TOOL in a.ALLOWED_TOOLS]
    assert holders == [AdjudicationDrafter]

    assert WRITE_TOOL not in CoverageMatcher.ALLOWED_TOOLS
    assert WRITE_TOOL not in ExclusionAnalyst.ALLOWED_TOOLS


@pytest.mark.asyncio
@pytest.mark.parametrize("agent_cls", AGENTS, ids=lambda c: c.__name__)
async def test_agent_rejects_tools_outside_its_allow_list(
    agent_cls: type[BaseAgent],
) -> None:
    """An agent asked to run a tool it does not own fails closed, not open."""
    provider = AsyncMock(spec=LLMProvider)
    provider.call_tool.return_value = {"name": "x", "args": {}}

    foreign = (
        WRITE_TOOL
        if WRITE_TOOL not in agent_cls.ALLOWED_TOOLS
        else "search_policies"
    )
    agent = agent_cls(llm_provider=provider)

    with pytest.raises(PermissionError) as exc:
        await agent._call_tool({"function": {"name": foreign}}, prompt="do it")

    assert foreign in str(exc.value)
    provider.call_tool.assert_not_called()


@pytest.mark.parametrize("agent_cls", AGENTS, ids=lambda c: c.__name__)
def test_agent_run_returns_a_typed_contract(agent_cls: type[BaseAgent]) -> None:
    """Every agent declares a Pydantic return contract, not a bare dict."""
    run = agent_cls.run
    hints = inspect.get_annotations(run, eval_str=True)
    assert hints.get("return") is RUN_CONTRACTS[agent_cls]

    signature = inspect.signature(run)
    for name, param in signature.parameters.items():
        if name == "self":
            continue
        assert param.annotation is not inspect.Parameter.empty, (
            f"{agent_cls.__name__}.run({name}) must declare a type"
        )


@pytest.mark.parametrize("contract", CONTRACTS, ids=lambda c: c.__name__)
def test_contract_publishes_a_json_schema(contract: type[BaseModel]) -> None:
    """Contracts are machine-checkable: JSON-schema with required fields."""
    schema = contract.model_json_schema()

    assert schema["title"] == contract.__name__
    assert schema.get("properties"), "contract must declare fields"
    assert schema.get("required"), "contract must mark mandatory fields"
    json.dumps(schema)  # must be serialisable for API/tool payloads


def test_contracts_round_trip_through_json() -> None:
    """Contract instances survive a JSON round-trip without losing their types."""
    chunk = make_chunk()
    draft = AdjudicationDraft(
        recommendation="partial",
        calculated_payout=Decimal("9500.00"),
        reasoning_text="Deductible applied, limit not reached.",
        citations=[chunk],
        confidence="high",
        deductible_applied=Decimal("2500.00"),
        policy_limit=Decimal("50000.00"),
    )

    restored = AdjudicationDraft.model_validate_json(draft.model_dump_json())
    assert restored.recommendation == "partial"
    assert restored.calculated_payout == Decimal("9500.00")
    assert restored.citations[0].chunk_id == chunk.chunk_id

    match = CoverageMatchResult(
        policy_id="POL-HO3",
        version_effective_date=date(2026, 1, 1),
        applicable_coverage_sections=[chunk],
        confidence="matched",
    )
    assert (
        CoverageMatchResult.model_validate_json(match.model_dump_json()) == match
    )

    analysis = ExclusionAnalysisResult(
        exclusions_found=[],
        deductible_applied=Decimal("2500.00"),
        policy_limit=Decimal("50000.00"),
        calculated_payout=Decimal("9500.00"),
        anomaly_flags=[],
    )
    assert (
        ExclusionAnalysisResult.model_validate_json(analysis.model_dump_json())
        == analysis
    )


@pytest.mark.parametrize("agent_cls", AGENTS, ids=lambda c: c.__name__)
def test_prompt_template_placeholders_match_the_agent_call_site(
    agent_cls: type[BaseAgent],
) -> None:
    """The prompt an agent loads formats cleanly with exactly the keys it passes."""
    prompt_name, expected_placeholders = AGENT_PROMPTS[agent_cls]
    template = load_prompt(prompt_name, "v1")

    placeholders = {
        field_name
        for _, field_name, _, _ in string.Formatter().parse(template)
        if field_name
    }
    assert placeholders == expected_placeholders, (
        f"{prompt_name}/v1.md placeholders changed: "
        f"template={sorted(placeholders)} agent supplies={sorted(expected_placeholders)}"
    )

    filled = template.format(**{k: f"<{k}>" for k in placeholders})
    assert "<" in filled  # every placeholder was substituted


@pytest.mark.asyncio
async def test_write_tool_only_reaches_pending_approval() -> None:
    """The side-effecting tool moves a claim to pending_approval and no further."""
    claim = make_claim()
    repo = StubRepository(claim)

    await submit_for_approval(draft=AdjudicationDraft(
        recommendation="approve",
        calculated_payout=Decimal("9500.00"),
        reasoning_text="Within limits.",
        citations=[make_chunk()],
        confidence="high",
    ), claim_id=claim.id, claim_repo=repo)

    assert repo.claim.status == "pending_approval"
    assert "approved" not in {c.status for c in repo.saved}
    assert "rejected" not in {c.status for c in repo.saved}
