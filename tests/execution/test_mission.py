"""Mission execution context tests."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from wolfharness.execution import (
    MissionBudgetExceededError,
    MissionExecutionContext,
    mission_from_deps,
    with_mission_context,
)


def _mission(
    *, timeout_seconds: float = 10, max_model_requests: int = 2
) -> MissionExecutionContext:
    return MissionExecutionContext.create(
        root_session_id="root-session",
        timeout_seconds=timeout_seconds,
        max_model_requests=max_model_requests,
    )


async def test_mission_enforces_one_shared_model_request_budget() -> None:
    mission = _mission(max_model_requests=2)

    await asyncio.gather(mission.reserve_model_request(), mission.reserve_model_request())

    with pytest.raises(MissionBudgetExceededError, match="model-request budget"):
        await mission.reserve_model_request()
    assert mission.usage_snapshot().model_requests == 2


async def test_mission_aggregates_tokens_from_parallel_children() -> None:
    mission = _mission()

    await asyncio.gather(
        mission.record_tokens(input_tokens=100, output_tokens=20),
        mission.record_tokens(input_tokens=80, output_tokens=30),
    )

    usage = mission.usage_snapshot()
    assert usage.input_tokens == 180
    assert usage.output_tokens == 50


async def test_mission_cancellation_rejects_future_model_requests() -> None:
    mission = _mission()
    mission.cancel()

    with pytest.raises(MissionBudgetExceededError, match="cancelled"):
        await mission.reserve_model_request()


def test_mission_context_is_propagated_by_identity() -> None:
    mission = _mission()
    deps = with_mission_context({"domain": "welding"}, mission)

    assert mission_from_deps(deps) is mission
    assert deps["domain"] == "welding"


def test_mission_context_resolves_through_runtime_dependency_layers() -> None:
    mission = _mission()
    delegated = with_mission_context({"delegation_depth": 1}, mission)
    runtime_services = SimpleNamespace(inherited_run_deps=delegated)
    agent_context = SimpleNamespace(data=runtime_services)

    assert mission_from_deps(agent_context) is mission
