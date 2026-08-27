"""Model protocol for agents that can finish only through typed Artifacts."""

from __future__ import annotations

from typing import Any

from pydantic_ai.capabilities import AbstractCapability
from pydantic_ai.settings import ModelSettings


class ArtifactCompletionCapability(AbstractCapability[Any]):
    """Require every model response to select an Artifact-workflow tool.

    Structured workers must inspect immutable inputs and persist a typed output;
    free-text completion has no protocol meaning. Requiring a tool call uses the
    OpenAI-compatible protocol understood by proxy and self-hosted providers;
    the configured names remain the capability's declared worker contract and
    are validated against the worker's exposed tool surface by its manifest.
    """

    def __init__(self, tool_names: list[str]) -> None:
        """Bind the exact tools that constitute one Artifact worker protocol."""
        if not tool_names:
            raise ValueError("artifact completion requires at least one tool name")
        if len(tool_names) != len(set(tool_names)):
            raise ValueError("artifact completion tool names must be unique")
        if any(not name.strip() for name in tool_names):
            raise ValueError("artifact completion tool names must not be blank")
        self._tool_names = tuple(tool_names)

    def get_model_settings(self) -> ModelSettings:
        """Force one exposed protocol tool on every model response."""
        return ModelSettings(tool_choice="required")


__all__ = ["ArtifactCompletionCapability"]
