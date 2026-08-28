"""Tests for _execute_turn() RunErrorEvent handling.

Since RunErrorEvent IS a terminal event, _execute_turn() breaks on it
just like StreamCompleteEvent. No trailing StreamCompleteEvent follows.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from wolfharness.agents.context import AgentRunContext
from wolfharness.agents.events.events import (
    RunErrorEvent,
    StreamCompleteEvent,
    ToolCallCompleteEvent,
)
from wolfharness.execution import MissionExecutionContext, with_mission_context
from wolfharness.messaging.messagenode import ChatMessage


def _make_mock_session() -> MagicMock:
    """Create a mock SessionState with a working _comm_channel."""
    session = MagicMock()
    comm = MagicMock()
    comm.publish = AsyncMock()
    comm.publishes_to_event_bus = True
    session._comm_channel = comm
    return session


@pytest.mark.unit
@pytest.mark.asyncio
async def test_execute_turn_breaks_on_run_error_event() -> None:
    """Break on RunErrorEvent — no trailing StreamCompleteEvent is yielded.

    When turn.execute() yields [RunErrorEvent, StreamCompleteEvent],
    _execute_turn() breaks on RunErrorEvent and does NOT yield the trailing
    StreamCompleteEvent.
    """
    from wolfharness.orchestrator.run import RunHandle

    error_event = RunErrorEvent(
        message="Something went wrong",
        agent_name="test",
        run_id="test-run",
    )
    complete_event = StreamCompleteEvent(
        message=ChatMessage(content="done", role="assistant"),
        cancelled=True,
    )

    async def mock_execute():
        yield error_event
        yield complete_event

    mock_turn = MagicMock()
    mock_turn.execute = mock_execute
    mock_turn._final_message = None

    mock_agent = MagicMock()
    mock_agent.create_turn = MagicMock(return_value=mock_turn)
    mock_agent.conversation = MagicMock()

    handle = RunHandle(
        run_id="test-run",
        session_id="test-session",
        agent_type="native",
        agent=mock_agent,
        event_bus=None,
        session=None,
        run_ctx=MagicMock(),
    )

    events = [
        event
        async for event in handle._execute_turn(mock_agent, None, _make_mock_session(), ["test"])
    ]

    # Only RunErrorEvent should be yielded — _execute_turn breaks on it.
    error_events = [e for e in events if isinstance(e, RunErrorEvent)]
    assert len(error_events) == 1, f"Expected 1 RunErrorEvent, got {len(error_events)}"

    # StreamCompleteEvent should NOT be yielded — _execute_turn broke before reaching it.
    complete_events = [e for e in events if isinstance(e, StreamCompleteEvent)]
    assert len(complete_events) == 0, (
        f"Expected 0 StreamCompleteEvent (broke on RunErrorEvent), got {len(complete_events)}"
    )

    assert handle._current_turn_failed is True


@pytest.mark.unit
@pytest.mark.asyncio
async def test_execute_turn_breaks_on_stream_complete() -> None:
    """Break on StreamCompleteEvent normally when no RunErrorEvent.

    When turn.execute() yields StreamCompleteEvent (no RunErrorEvent),
    _execute_turn() breaks normally.
    """
    from wolfharness.orchestrator.run import RunHandle

    complete_event = StreamCompleteEvent(
        message=ChatMessage(content="done", role="assistant"),
        cancelled=False,
    )

    async def mock_execute():
        yield complete_event

    mock_turn = MagicMock()
    mock_turn.execute = mock_execute
    mock_turn._final_message = ChatMessage(content="done", role="assistant")

    mock_agent = MagicMock()
    mock_agent.create_turn = MagicMock(return_value=mock_turn)
    mock_agent.conversation = MagicMock()
    mock_agent.conversation.add_chat_messages = MagicMock()

    handle = RunHandle(
        run_id="test-run",
        session_id="test-session",
        agent_type="native",
        agent=mock_agent,
        event_bus=None,
        session=None,
        run_ctx=MagicMock(),
    )

    events = [
        event
        async for event in handle._execute_turn(mock_agent, None, _make_mock_session(), ["test"])
    ]

    complete_events = [e for e in events if isinstance(e, StreamCompleteEvent)]
    assert len(complete_events) == 1
    assert handle._current_turn_failed is False


@pytest.mark.unit
@pytest.mark.asyncio
async def test_execute_turn_counts_and_logs_error_event_once_without_ending_run() -> None:
    """A failed tool event is usage data, not a Run terminal event."""
    from wolfharness.orchestrator.run import RunHandle

    tool_error = ToolCallCompleteEvent(
        tool_name="record_review",
        tool_call_id="tool-call-1",
        tool_input={},
        tool_result="Invalid JSON: expected ',' or ']'",
        agent_name="reviewer",
        message_id="message-1",
        is_error=True,
        session_id="member-session",
    )
    complete_event = StreamCompleteEvent(
        message=ChatMessage(content="corrected", role="assistant"),
    )

    async def mock_execute():
        yield tool_error
        yield complete_event

    mock_turn = MagicMock()
    mock_turn.execute = mock_execute
    mock_turn._final_message = ChatMessage(content="corrected", role="assistant")

    mock_agent = MagicMock()
    mock_agent.create_turn = MagicMock(return_value=mock_turn)
    mock_agent.conversation = MagicMock()

    mission = MissionExecutionContext.create(
        root_session_id="root-session",
        timeout_seconds=30,
        max_model_requests=5,
    )
    handle = RunHandle(
        run_id="test-run",
        session_id="member-session",
        agent_type="native",
        agent=mock_agent,
        event_bus=None,
        session=None,
        run_ctx=AgentRunContext(
            session_id="member-session",
            deps=with_mission_context({}, mission),
        ),
    )

    with patch("wolfharness.orchestrator.run.logger.warning") as warning:
        events = [
            event
            async for event in handle._execute_turn(
                mock_agent,
                None,
                _make_mock_session(),
                ["test"],
            )
        ]

    assert events == [tool_error, complete_event]
    assert mission.usage_snapshot().tool_failures == 1
    assert handle._current_turn_failed is False
    warning.assert_called_once_with(
        "Agent tool call failed: session=%s agent=%s tool=%s result=%s",
        "member-session",
        "reviewer",
        "record_review",
        "Invalid JSON: expected ',' or ']'",
    )
