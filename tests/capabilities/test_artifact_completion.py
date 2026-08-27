from __future__ import annotations

import pytest

from wolfharness.capabilities.artifact_completion import (
    ArtifactCompletionCapability,
)


def test_artifact_completion_requires_an_exposed_protocol_tool() -> None:
    capability = ArtifactCompletionCapability(
        tool_names=["read_assignment", "record_artifact"],
        model_settings={
            "extra_body": {"thinking": {"type": "disabled"}},
        },
    )

    settings = capability.get_model_settings()
    assert settings["tool_choice"] == "required"
    assert settings["extra_body"] == {"thinking": {"type": "disabled"}}


@pytest.mark.parametrize(
    "tool_names",
    [[], ["record", "record"], ["read", ""]],
)
def test_artifact_completion_rejects_ambiguous_protocol(
    tool_names: list[str],
) -> None:
    with pytest.raises(ValueError, match="artifact completion"):
        ArtifactCompletionCapability(tool_names=tool_names)


def test_artifact_completion_rejects_tool_choice_override() -> None:
    with pytest.raises(ValueError, match="owns tool_choice"):
        ArtifactCompletionCapability(
            tool_names=["record"],
            model_settings={"tool_choice": "auto"},
        )
