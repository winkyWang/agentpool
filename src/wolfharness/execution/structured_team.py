"""Programmatic Dynamic Team fan-out/fan-in with typed Artifact completion."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
import datetime
import tempfile
import time
from typing import TYPE_CHECKING, Literal
from uuid import uuid4

import logfire

from wolfharness.capabilities.file_team_state import FileTeamState
from wolfharness.execution.typed_artifact import (
    TypedArtifactExecutionRequest,
    TypedArtifactExecutionService,
)


if TYPE_CHECKING:
    from pathlib import Path

    from wolfharness.execution.mission import (
        MissionExecutionContext,
        MissionToolFailure,
    )
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
    progress_phase: str = "team_member_running"


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
    tool_failure_details: tuple[MissionToolFailure, ...]


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

    @logfire.instrument("execution.structured_team.execute")
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
            tool_failure_details=usage.tool_failure_details,
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
        async with semaphore:
            await tracker.enter()
            try:
                self._assert_dispatchable(mission)
                async def register_member(session_id: str) -> None:
                    self._team_state.register_member(
                        team_id,
                        dispatch.member_name,
                        session_id,
                        agent=dispatch.agent_name,
                    )

                result = await TypedArtifactExecutionService(
                    session_pool=self._session_pool,
                ).execute(
                    request=TypedArtifactExecutionRequest(
                        execution_id=dispatch.dispatch_id,
                        parent_session_id=plan.parent_session_id,
                        agent_name=dispatch.agent_name,
                        input_artifact_uri=dispatch.input_artifact_uri,
                        expected_artifact_type=dispatch.expected_artifact_type,
                        progress_phase=dispatch.progress_phase,
                        instruction=dispatch.instruction,
                        child_session_metadata={
                            "team_id": team_id,
                            "team_name": plan.name,
                            "team_role": "member",
                            "team_member_name": dispatch.member_name,
                            "structured_dispatch_id": dispatch.dispatch_id,
                        },
                    ),
                    mission=mission,
                    on_session_started=register_member,
                )
                return TeamMemberCompletion(
                    dispatch_id=dispatch.dispatch_id,
                    member_name=dispatch.member_name,
                    session_id=result.session_id,
                    outcome=result.outcome,
                    artifact_uri=result.artifact_uri,
                    artifact_type=result.artifact_type,
                    error=result.error,
                    elapsed_seconds=time.monotonic() - member_started,
                )
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001 - converted to typed runtime result.
                return TeamMemberCompletion(
                    dispatch_id=dispatch.dispatch_id,
                    member_name=dispatch.member_name,
                    session_id=None,
                    outcome="technical_failure",
                    error=f"{type(exc).__name__}: {exc}",
                    elapsed_seconds=time.monotonic() - member_started,
                )
            finally:
                await tracker.exit()

    @staticmethod
    def _assert_dispatchable(mission: MissionExecutionContext) -> None:
        if mission.cancelled or mission.remaining_seconds() <= 0:
            raise TimeoutError("Mission deadline expired before member dispatch")

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
        if any(not dispatch.progress_phase.strip() for dispatch in plan.dispatches):
            raise ValueError("progress_phase values must not be blank")
