"""Tests for collecting asynchronous subagent results without file polling."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from pydantic_ai import ModelRetry
import pytest

from agentpool_toolsets.builtin.subagent_tools import SubagentTools


@pytest.mark.asyncio
async def test_async_subagent_result_is_collected_with_wait_tool() -> None:
    """A completed task is returned by one blocking wait call."""
    ctx = MagicMock()
    ctx.complete_background_task = AsyncMock()
    tools = SubagentTools()

    with patch.object(
        SubagentTools,
        "_run_sync",
        new=AsyncMock(return_value="retrieval result"),
    ):
        started = await tools._start_async_task(
            ctx=ctx,
            session_pool=MagicMock(),
            node=MagicMock(),
            child_session_id="child-session",
            agent_or_team="retriever",
            prompt="retrieve evidence",
            description="Retrieve evidence",
            input_provider=None,
            is_team_node=False,
        )
        result = await tools.wait_for_task(ctx, started["metadata"]["taskId"])

    assert started["metadata"]["delivery"] == "wait_for_task"
    assert "outputFile" not in started["metadata"]
    assert "wait_for_task" in started["output"]
    assert "Do not poll" in started["output"]
    assert result["output"] == "retrieval result"
    assert result["metadata"]["sessionId"] == "child-session"
    ctx.complete_background_task.assert_awaited_once()
    assert not ctx.internal_fs.mock_calls


@pytest.mark.asyncio
async def test_async_subagent_failure_is_collected_with_wait_tool() -> None:
    """A failed task returns its actual error through the same result channel."""
    ctx = MagicMock()
    ctx.complete_background_task = AsyncMock()
    tools = SubagentTools()

    with patch.object(
        SubagentTools,
        "_run_sync",
        new=AsyncMock(side_effect=RuntimeError("retrieval unavailable")),
    ):
        started = await tools._start_async_task(
            ctx=ctx,
            session_pool=MagicMock(),
            node=MagicMock(),
            child_session_id="child-session",
            agent_or_team="retriever",
            prompt="retrieve evidence",
            description="Retrieve evidence",
            input_provider=None,
            is_team_node=False,
        )
        result = await tools.wait_for_task(ctx, started["metadata"]["taskId"])

    assert result["metadata"]["failed"] is True
    assert "RuntimeError: retrieval unavailable" in result["output"]
    ctx.complete_background_task.assert_awaited_once()
    assert not ctx.internal_fs.mock_calls


@pytest.mark.asyncio
async def test_async_task_ids_are_unique_and_each_result_is_collected_once() -> None:
    """Concurrent tasks with the same description remain independently addressable."""
    ctx = MagicMock()
    ctx.complete_background_task = AsyncMock()
    tools = SubagentTools()

    with patch.object(
        SubagentTools,
        "_run_sync",
        new=AsyncMock(side_effect=["first result", "second result"]),
    ):
        first = await tools._start_async_task(
            ctx=ctx,
            session_pool=MagicMock(),
            node=MagicMock(),
            child_session_id="child-1",
            agent_or_team="retriever",
            prompt="first",
            description="Same description",
            input_provider=None,
            is_team_node=False,
        )
        second = await tools._start_async_task(
            ctx=ctx,
            session_pool=MagicMock(),
            node=MagicMock(),
            child_session_id="child-2",
            agent_or_team="retriever",
            prompt="second",
            description="Same description",
            input_provider=None,
            is_team_node=False,
        )

        first_id = first["metadata"]["taskId"]
        second_id = second["metadata"]["taskId"]
        assert first_id != second_id
        first_result = await tools.wait_for_task(ctx, first_id)
        second_result = await tools.wait_for_task(ctx, second_id)

    assert first_result["output"] == "first result"
    assert second_result["output"] == "second result"

    with pytest.raises(ModelRetry, match="already collected"):
        await tools.wait_for_task(ctx, first_id)
