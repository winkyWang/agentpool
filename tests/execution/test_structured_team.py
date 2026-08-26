"""Structured Dynamic Team execution tests."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any

from wolfharness.agents.events import ArtifactCompletionEvent, StreamCompleteEvent
from wolfharness.execution import (
    StructuredTeamExecutionService,
    TeamExecutionPlan,
    TeamMemberDispatch,
    mission_from_deps,
)
from wolfharness.execution.mission import MissionExecutionContext
from wolfharness.orchestrator.event_bus import EventBus


class _Sessions:
    async def get_or_create_session_agent(self, session_id: str, agent_name: str) -> object:
        return object()


class _SessionPool:
    def __init__(self, *, expected_members: int, typed_completion: bool = True) -> None:
        self.event_bus = EventBus()
        self.sessions = _Sessions()
        self.closed_sessions: list[str] = []
        self._session_index = 0
        self._started = 0
        self._expected_members = expected_members
        self._all_started = asyncio.Event()
        self._typed_completion = typed_completion
        self._background_tasks: set[asyncio.Task[None]] = set()

    async def create_child_session(self, **_kwargs: Any) -> SimpleNamespace:
        self._session_index += 1
        return SimpleNamespace(session_id=f"member-session-{self._session_index}")

    async def send_message(self, session_id: str, _message: str, *, deps: Any) -> str:
        mission = mission_from_deps(deps)
        assert mission is not None
        self._started += 1
        if self._started == self._expected_members:
            self._all_started.set()

        async def finish() -> None:
            await self._all_started.wait()
            await asyncio.sleep(0.05)
            if self._typed_completion:
                event: object = ArtifactCompletionEvent(
                    mission_id=mission.mission_id,
                    session_id=session_id,
                    artifact_uri=f"scratchpad:///welding/{session_id}/fragment.json",
                    artifact_type="EvidenceFragment",
                )
            else:
                event = StreamCompleteEvent(message=None)
            await self.event_bus.publish(session_id, event)

        task = asyncio.create_task(finish())
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)
        return f"message-{session_id}"

    async def close_session(self, session_id: str) -> None:
        self.closed_sessions.append(session_id)
        await self.event_bus.close_session(session_id)


def _mission() -> MissionExecutionContext:
    return MissionExecutionContext.create(
        root_session_id="root-session",
        timeout_seconds=5,
        max_model_requests=20,
    )


def _plan(member_count: int) -> TeamExecutionPlan:
    return TeamExecutionPlan(
        name="evidence-team",
        parent_session_id="coordinator-session",
        lead_member_name="coordinator",
        max_parallel_members=member_count,
        dispatches=tuple(
            TeamMemberDispatch(
                dispatch_id=f"dispatch-{index}",
                member_name=f"explorer-{index}",
                agent_name="evidence-explorer",
                input_artifact_uri=f"scratchpad:///assignments/{index}.json",
                expected_artifact_type="EvidenceFragment",
                instruction="Evaluate the immutable assignment.",
            )
            for index in range(member_count)
        ),
    )


async def test_structured_team_runs_members_concurrently_and_cleans_sessions(tmp_path) -> None:
    pool = _SessionPool(expected_members=3)
    service = StructuredTeamExecutionService(
        session_pool=pool,  # type: ignore[arg-type]
        team_state_base_dir=tmp_path,
    )

    report = await service.execute(plan=_plan(3), mission=_mission())

    assert report.peak_parallel_members == 3
    assert report.elapsed_seconds < 0.5
    assert report.team_state_cleaned is True
    assert report.model_requests == 0
    assert report.input_tokens == 0
    assert report.output_tokens == 0
    assert report.tool_failures == 0
    assert all(completion.outcome == "completed" for completion in report.completions)
    assert len(pool.closed_sessions) == 3
    assert not (tmp_path / "teams" / report.team_id).exists()


async def test_structured_team_rejects_final_text_without_typed_completion(tmp_path) -> None:
    pool = _SessionPool(expected_members=1, typed_completion=False)
    service = StructuredTeamExecutionService(
        session_pool=pool,  # type: ignore[arg-type]
        team_state_base_dir=tmp_path,
    )

    report = await service.execute(plan=_plan(1), mission=_mission())

    completion = report.completions[0]
    assert completion.outcome == "technical_failure"
    assert completion.artifact_uri is None
    assert "without a typed Artifact completion" in (completion.error or "")
    assert pool.closed_sessions == ["member-session-1"]
