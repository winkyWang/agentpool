"""Programmatic Dynamic Team fan-out/fan-in with typed Artifact completion."""

from __future__ import annotations

import asyncio
import contextlib
from dataclasses import dataclass, field
import datetime
import tempfile
import time
from typing import TYPE_CHECKING, Literal
from uuid import uuid4

from wolfharness.agents.events import (
    ArtifactCompletionEvent,
    MissionProgressEvent,
    RunErrorEvent,
    RunFailedEvent,
    StreamCompleteEvent,
    ToolCallCompleteEvent,
)
from wolfharness.capabilities.file_team_state import FileTeamState
from wolfharness.execution.mission import MissionExecutionContext, with_mission_context


if TYPE_CHECKING:
    from pathlib import Path

    from wolfharness.orchestrator.event_bus import EventEnvelope
    from wolfharness.orchestrator.session_pool import SessionPool


@dataclass(frozen=True, slots=True, kw_only=True)
class TeamMemberDispatch:
    """One immutable Artifact assignment for one eligible Agent."""

    dispatch_id: str
    member_name: str
    agent_name: str
    input_artifact_uri: str
    expected_artifact_type: str
    instruction: str


@dataclass(frozen=True, slots=True, kw_only=True)
class TeamExecutionPlan:
    """Runtime-owned parallel execution plan."""

    name: str
    parent_session_id: str
    lead_member_name: str
    max_parallel_members: int
    dispatches: tuple[TeamMemberDispatch, ...]


@dataclass(frozen=True, slots=True, kw_only=True)
class TeamMemberCompletion:
    """Typed member completion or technical failure."""

    dispatch_id: str
    member_name: str
    session_id: str | None
    outcome: Literal["completed", "technical_failure"]
    artifact_uri: str | None = None
    artifact_type: str | None = None
    error: str | None = None
    elapsed_seconds: float = 0.0


@dataclass(frozen=True, slots=True, kw_only=True)
class TeamExecutionReport:
    """Runtime facts for one structured Team execution."""

    team_id: str
    completions: tuple[TeamMemberCompletion, ...]
    peak_parallel_members: int
    elapsed_seconds: float
    team_state_cleaned: bool
    model_requests: int
    input_tokens: int
    output_tokens: int
    tool_failures: int


class StructuredTeamExecutionError(RuntimeError):
    """Technical failure while executing a structured Team member."""


@dataclass(slots=True)
class _ParallelismTracker:
    active: int = 0
    peak: int = 0
    lock: asyncio.Lock = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self.lock = asyncio.Lock()

    async def enter(self) -> None:
        async with self.lock:
            self.active += 1
            self.peak = max(self.peak, self.active)

    async def exit(self) -> None:
        async with self.lock:
            self.active -= 1


class StructuredTeamExecutionService:
    """Execute immutable assignments concurrently using SessionPool and Team state."""

    def __init__(
        self,
        *,
        session_pool: SessionPool,
        team_state_base_dir: str | Path | None = None,
    ) -> None:
        self._session_pool = session_pool
        self._team_state = FileTeamState(str(team_state_base_dir or tempfile.gettempdir()))

    async def execute(
        self,
        *,
        plan: TeamExecutionPlan,
        mission: MissionExecutionContext,
    ) -> TeamExecutionReport:
        """Fan out members, wait for typed completions, and always clean resources."""
        self._validate_plan(plan)
        team_id = f"team_{uuid4().hex[:12]}"
        started = time.monotonic()
        semaphore = asyncio.Semaphore(plan.max_parallel_members)
        tracker = _ParallelismTracker()
        members = [
            {"name": dispatch.member_name, "agent": dispatch.agent_name}
            for dispatch in plan.dispatches
        ]
        self._team_state.init(
            team_id,
            plan.name,
            members,
            max_parallel_members=plan.max_parallel_members,
        )
        self._team_state.register_member(
            team_id,
            plan.lead_member_name,
            plan.parent_session_id,
            agent=plan.lead_member_name,
        )
        self._team_state.set_started_at(
            team_id,
            datetime.datetime.now(datetime.UTC).isoformat(),
        )

        cleaned = False
        try:
            completions = await asyncio.gather(
                *(
                    self._execute_member(
                        dispatch=dispatch,
                        plan=plan,
                        mission=mission,
                        team_id=team_id,
                        semaphore=semaphore,
                        tracker=tracker,
                    )
                    for dispatch in plan.dispatches
                ),
            )
        finally:
            self._team_state.mark_deleted(team_id)
            self._team_state.cleanup(team_id)
            cleaned = True

        usage = mission.usage_snapshot()
        return TeamExecutionReport(
            team_id=team_id,
            completions=tuple(completions),
            peak_parallel_members=tracker.peak,
            elapsed_seconds=time.monotonic() - started,
            team_state_cleaned=cleaned,
            model_requests=usage.model_requests,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            tool_failures=usage.tool_failures,
        )

    async def _execute_member(
        self,
        *,
        dispatch: TeamMemberDispatch,
        plan: TeamExecutionPlan,
        mission: MissionExecutionContext,
        team_id: str,
        semaphore: asyncio.Semaphore,
        tracker: _ParallelismTracker,
    ) -> TeamMemberCompletion:
        member_started = time.monotonic()
        child_session_id: str | None = None
        event_queue: asyncio.Queue[EventEnvelope] | None = None
        async with semaphore:
            await tracker.enter()
            try:
                self._assert_dispatchable(mission)
                child_session_id = await self._create_member_session(
                    dispatch=dispatch,
                    plan=plan,
                    team_id=team_id,
                )
                event_queue = await self._session_pool.event_bus.subscribe(
                    child_session_id,
                    scope="session",
                    replay=False,
                )
                await self._publish_progress(
                    mission=mission,
                    source_session_id=child_session_id,
                    phase="team_member_started",
                )
                message_id = await self._session_pool.send_message(
                    child_session_id,
                    self._member_message(dispatch),
                    deps=with_mission_context({}, mission),
                )
                self._assert_run_started(message_id)
                completion = await self._wait_for_completion(
                    queue=event_queue,
                    mission=mission,
                    session_id=child_session_id,
                    expected_artifact_type=dispatch.expected_artifact_type,
                )
                await self._publish_progress(
                    mission=mission,
                    source_session_id=child_session_id,
                    phase="team_member_completed",
                    artifact_uri=completion.artifact_uri,
                )
                return TeamMemberCompletion(
                    dispatch_id=dispatch.dispatch_id,
                    member_name=dispatch.member_name,
                    session_id=child_session_id,
                    outcome="completed",
                    artifact_uri=completion.artifact_uri,
                    artifact_type=completion.artifact_type,
                    elapsed_seconds=time.monotonic() - member_started,
                )
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001 - converted to typed runtime result.
                return TeamMemberCompletion(
                    dispatch_id=dispatch.dispatch_id,
                    member_name=dispatch.member_name,
                    session_id=child_session_id,
                    outcome="technical_failure",
                    error=f"{type(exc).__name__}: {exc}",
                    elapsed_seconds=time.monotonic() - member_started,
                )
            finally:
                await self._cleanup_member(child_session_id, event_queue)
                await tracker.exit()

    async def _create_member_session(
        self,
        *,
        dispatch: TeamMemberDispatch,
        plan: TeamExecutionPlan,
        team_id: str,
    ) -> str:
        child = await self._session_pool.create_child_session(
            parent_session_id=plan.parent_session_id,
            agent_name=dispatch.agent_name,
            agent_type="native",
            lifecycle_policy="cascade",
            team_id=team_id,
            team_name=plan.name,
            team_role="member",
            team_member_name=dispatch.member_name,
            structured_dispatch_id=dispatch.dispatch_id,
        )
        child_session_id = child.session_id
        await self._session_pool.sessions.get_or_create_session_agent(
            child_session_id,
            dispatch.agent_name,
        )
        self._team_state.register_member(
            team_id,
            dispatch.member_name,
            child_session_id,
            agent=dispatch.agent_name,
        )
        return child_session_id

    async def _cleanup_member(
        self,
        child_session_id: str | None,
        event_queue: asyncio.Queue[EventEnvelope] | None,
    ) -> None:
        if event_queue is not None and child_session_id is not None:
            with contextlib.suppress(Exception):
                await self._session_pool.event_bus.unsubscribe(child_session_id, event_queue)
        if child_session_id is not None:
            await self._session_pool.close_session(child_session_id)

    @staticmethod
    def _member_message(dispatch: TeamMemberDispatch) -> str:
        return (
            f"{dispatch.instruction.strip()}\n\n"
            f"Use only this immutable input Artifact URI:\n{dispatch.input_artifact_uri}\n\n"
            f"Persist exactly one {dispatch.expected_artifact_type} Artifact. "
            "The persistence tool publishes typed completion automatically."
        )

    @staticmethod
    def _assert_dispatchable(mission: MissionExecutionContext) -> None:
        if mission.cancelled or mission.remaining_seconds() <= 0:
            raise TimeoutError("Mission deadline expired before member dispatch")

    @staticmethod
    def _assert_run_started(message_id: str | None) -> None:
        if message_id is None:
            raise StructuredTeamExecutionError("SessionPool did not start the member Run")

    @staticmethod
    def _validate_plan(plan: TeamExecutionPlan) -> None:
        if plan.max_parallel_members < 1:
            raise ValueError("max_parallel_members must be at least one")
        if not plan.dispatches:
            raise ValueError("Structured Team requires at least one dispatch")
        dispatch_ids = [dispatch.dispatch_id for dispatch in plan.dispatches]
        if len(dispatch_ids) != len(set(dispatch_ids)):
            raise ValueError("dispatch_id values must be unique")
        member_names = [dispatch.member_name for dispatch in plan.dispatches]
        if len(member_names) != len(set(member_names)):
            raise ValueError("member_name values must be unique")
        if plan.lead_member_name in member_names:
            raise ValueError("lead_member_name must not duplicate a member_name")

    async def _wait_for_completion(
        self,
        *,
        queue: asyncio.Queue[EventEnvelope],
        mission: MissionExecutionContext,
        session_id: str,
        expected_artifact_type: str,
    ) -> ArtifactCompletionEvent:
        while True:
            remaining = mission.remaining_seconds()
            if mission.cancelled or remaining <= 0:
                raise TimeoutError("Mission ended before member completion")
            async with asyncio.timeout(remaining):
                envelope = await queue.get()
            event = envelope.event
            if isinstance(event, ArtifactCompletionEvent):
                if event.mission_id != mission.mission_id or event.session_id != session_id:
                    continue
                if event.artifact_type != expected_artifact_type:
                    raise StructuredTeamExecutionError(
                        f"Expected {expected_artifact_type}, got {event.artifact_type}"
                    )
                return event
            if isinstance(event, RunErrorEvent):
                raise StructuredTeamExecutionError(event.message)
            if isinstance(event, RunFailedEvent):
                raise StructuredTeamExecutionError(str(event.exception))
            if isinstance(event, ToolCallCompleteEvent) and event.is_error:
                raise StructuredTeamExecutionError(
                    f"Tool {event.tool_name!r} failed: {event.tool_result}"
                )
            if isinstance(event, StreamCompleteEvent):
                raise StructuredTeamExecutionError(
                    "Member ended without a typed Artifact completion"
                )

    async def _publish_progress(
        self,
        *,
        mission: MissionExecutionContext,
        source_session_id: str,
        phase: str,
        artifact_uri: str | None = None,
    ) -> None:
        await self._session_pool.event_bus.publish(
            mission.progress_session_id,
            MissionProgressEvent(
                mission_id=mission.mission_id,
                source_session_id=source_session_id,
                phase=phase,
                artifact_uri=artifact_uri,
            ),
        )
