from unittest.mock import AsyncMock

import pytest
from pydantic import BaseModel

from src.application.agents.base_agent import BaseAgent
from src.domain.interfaces.llm_provider import LLMProvider


class DummyContract(BaseModel):
    result: str


def test_base_agent_cannot_instantiate_without_run() -> None:
    """Verify BaseAgent cannot be instantiated without implementing abstract run method."""
    mock_provider = AsyncMock(spec=LLMProvider)

    class IncompleteAgent(BaseAgent):
        pass

    with pytest.raises(TypeError):
        IncompleteAgent(llm_provider=mock_provider, name="Incomplete")  # type: ignore[abstract]


@pytest.mark.asyncio
async def test_concrete_agent_execution_and_tool_allow_list() -> None:
    """Verify concrete agent executes run and enforces ALLOWED_TOOLS security control."""
    mock_provider = AsyncMock(spec=LLMProvider)
    mock_provider.call_tool = AsyncMock(return_value={"name": "allowed_tool", "args": {}})

    class ValidAgent(BaseAgent):
        ALLOWED_TOOLS = ["allowed_tool"]

        async def run(self, **kwargs) -> DummyContract:
            return DummyContract(result="success")

    agent = ValidAgent(llm_provider=mock_provider, name="TestAgent")

    # Run execution
    res = await agent.run()
    assert res.result == "success"

    # Authorized tool call
    allowed_schema = {"function": {"name": "allowed_tool"}}
    tool_res = await agent._call_tool(allowed_schema, prompt="Run tool")
    assert tool_res == {"name": "allowed_tool", "args": {}}

    # Unauthorized tool call -> PermissionError
    unauthorized_schema = {"function": {"name": "unauthorized_tool"}}
    with pytest.raises(PermissionError) as exc_info:
        await agent._call_tool(unauthorized_schema, prompt="Run forbidden tool")

    assert "unauthorized_tool" in str(exc_info.value)
    assert "TestAgent" in str(exc_info.value)
