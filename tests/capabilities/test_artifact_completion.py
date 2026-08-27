from __future__ import annotations

import pytest

from wolfharness.capabilities.artifact_completion import (
    ArtifactCompletionCapability,
)


def test_artifact_completion_forces_exact_protocol_tools() -> None:
    capability = ArtifactCompletionCapability(
        tool_names=["read_assignment", "record_artifact"],
    )

    assert capability.get_model_settings()["tool_choice"] == [
        "read_assignment",
        "record_artifact",
    ]


@pytest.mark.parametrize(
    "tool_names",
    [[], ["record", "record"], ["read", ""]],
)
def test_artifact_completion_rejects_ambiguous_protocol(
    tool_names: list[str],
) -> None:
    with pytest.raises(ValueError, match="artifact completion"):
        ArtifactCompletionCapability(tool_names=tool_names)
