import pytest

from src.application.retrieval.prompt_loader import load_prompt


def test_load_prompt_ask_qa_v1() -> None:
    """Verify that load_prompt correctly loads and formats the ask_qa/v1.md prompt template."""
    prompt_template = load_prompt("ask_qa", "v1")
    assert "{context}" in prompt_template
    assert "{query}" in prompt_template

    formatted_prompt = prompt_template.format(
        context="Policy section 4.2 covers water damage.",
        query="Is water damage covered?",
    )

    assert "Policy section 4.2 covers water damage." in formatted_prompt
    assert "Is water damage covered?" in formatted_prompt
    assert "{context}" not in formatted_prompt
    assert "{query}" not in formatted_prompt


def test_load_prompt_nonexistent() -> None:
    """Verify that load_prompt raises FileNotFoundError when the requested prompt template does not exist."""
    with pytest.raises(FileNotFoundError):
        load_prompt("nonexistent_prompt", "v99")
