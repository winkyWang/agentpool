"""Typed Artifact completion is committed only by a successful tool return."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from pydantic_ai.models.test import TestModel
import pytest

from wolfharness import Agent
from wolfharness.agents.context import AgentContext, AgentRunContext
from wolfharness.agents.events import ArtifactCompletionEvent, ToolCallCompleteEvent
from wolfharness.agents.native_agent.turn import NativeTurn
from wolfharness.execution import MissionExecutionContext, with_mission_context


def _mission() -> MissionExecutionContext:
    return MissionExecutionContext.create(
        root_session_id="root-session",
        timeout_seconds=60,
        max_model_requests=5,
    )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_complete_artifact_stages_one_event_until_tool_success() -> None:
    """A domain tool cannot publish completion before its own return is known."""
    event_bus = MagicMock()
    event_bus.publish = AsyncMock()
    mission = _mission()
    run_ctx = AgentRunContext(
        session_id="member-session",
        event_bus=event_bus,
        deps=with_mission_context({}, mission),
    )
    ctx = AgentContext(node=MagicMock(), run_ctx=run_ctx)

    await ctx.complete_artifact(
        artifact_uri="scratchpad:///artifact.yaml",
        artifact_type="EvidenceFragment",
    )

    completion = run_ctx.pending_artifact_completion
    assert completion is not None
    assert completion.mission_id == mission.mission_id
    assert completion.session_id == "member-session"
    event_bus.publish.assert_not_awaited()
    with pytest.raises(RuntimeError, match="exactly one"):
        await ctx.complete_artifact(
            artifact_uri="scratchpad:///other.yaml",
            artifact_type="EvidenceFragment",
        )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_successful_artifact_tool_commits_event_and_ends_without_extra_request() -> None:
    """Typed completion is a generic terminal protocol, not a listener race."""
    event_bus = MagicMock()
    event_bus.publish = AsyncMock()
    mission = _mission()
    run_ctx = AgentRunContext(
        session_id="member-session",
        event_bus=event_bus,
        deps=with_mission_context({}, mission),
    )

    def persist_artifact() -> str:
        """Simulate a domain persistence tool that has staged exact completion."""
        run_ctx.pending_artifact_completion = ArtifactCompletionEvent(
            mission_id=mission.mission_id,
            session_id=run_ctx.session_id,
            artifact_uri="scratchpad:///artifact.yaml",
            artifact_type="EvidenceFragment",
        )
        return "persisted"

    agent = Agent(
        name="artifact-member",
        model=TestModel(call_tools=["persist_artifact"], custom_output_text="unused"),
        tools=[persist_artifact],
    )
    async with agent:
        turn = NativeTurn(
            agent=agent,
            prompts=["Persist the Artifact"],
            run_ctx=run_ctx,
            message_history=[],
        )
        events = [event async for event in turn.execute()]

    assert any(isinstance(event, ToolCallCompleteEvent) for event in events)
    assert run_ctx.terminal_tool_name == "persist_artifact"
    assert run_ctx.pending_artifact_completion is None
    assert mission.usage_snapshot().model_requests == 1
    event_bus.publish.assert_awaited_once()
    published_session_id, published_event = event_bus.publish.await_args.args
    assert published_session_id == "member-session"
    assert isinstance(published_event, ArtifactCompletionEvent)
    assert published_event.artifact_uri == "scratchpad:///artifact.yaml"
