"""Typed execution of one isolated child Agent over one immutable Artifact."""

from __future__ import annotations

import asyncio
import contextlib
from dataclasses import dataclass, field
import time
from typing import TYPE_CHECKING, Any, Literal

import logfire

from wolfharness.agents.events import (
    ArtifactCompletionEvent,
    MissionProgressEvent,
    RunErrorEvent,
    RunFailedEvent,
    StreamCompleteEvent,
    ToolCallCompleteEvent,
)
from wolfharness.execution.mission import with_mission_context


_PROGRESS_HEARTBEAT_SECONDS = 30.0
_MAX_TOOL_ERROR_TEXT_CHARACTERS = 2_000
STRUCTURED_INPUT_ARTIFACT_URI_METADATA_KEY = "structured_input_artifact_uri"
STRUCTURED_EXPECTED_ARTIFACT_TYPE_METADATA_KEY = "structured_expected_artifact_type"


if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from wolfharness.execution.mission import MissionExecutionContext
    from wolfharness.orchestrator.event_bus import EventEnvelope
    from wolfharness.orchestrator.session_pool import SessionPool


@dataclass(frozen=True, slots=True, kw_only=True)
class TypedArtifactExecutionRequest:
    """One isolated child execution whose only valid completion is an Artifact."""

    execution_id: str
    parent_session_id: str
    agent_name: str
    input_artifact_uri: str
    expected_artifact_type: str
    instruction: str
    progress_phase: str = "artifact_agent_running"
    child_session_metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True, kw_only=True)
class TypedArtifactExecutionResult:
    """Typed completion or technical failure for one isolated Agent run."""

    execution_id: str
    session_id: str | None
    outcome: Literal["completed", "technical_failure"]
    artifact_uri: str | None = None
    artifact_type: str | None = None
    error: str | None = None
    elapsed_seconds: float = 0.0


class TypedArtifactExecutionError(RuntimeError):
    """Technical failure while waiting for a child Artifact completion."""


class TypedArtifactExecutionService:
    """Own one child Session from creation through typed completion and cleanup."""

    def __init__(self, *, session_pool: SessionPool) -> None:
        self._session_pool = session_pool

    @logfire.instrument("execution.typed_artifact.execute")
    async def execute(
        self,
        *,
        request: TypedArtifactExecutionRequest,
        mission: MissionExecutionContext,
        on_session_started: Callable[[str], Awaitable[None]] | None = None,
    ) -> TypedArtifactExecutionResult:
        """Run one child Agent and close its Session before returning."""
        self._validate_request(request)
        started = time.monotonic()
        child_session_id: str | None = None
        event_queue: asyncio.Queue[EventEnvelope] | None = None
        try:
            self._assert_dispatchable(mission)
            child_session_id = await self._create_child_session(request)
            if on_session_started is not None:
                await on_session_started(child_session_id)
            event_queue = await self._session_pool.event_bus.subscribe(
                child_session_id,
                scope="session",
                replay=False,
            )
            await self._publish_progress(
                mission=mission,
                source_session_id=child_session_id,
                phase="artifact_agent_started",
            )
            message_id = await self._session_pool.send_message(
                child_session_id,
                self._message(request),
                deps=with_mission_context({}, mission),
            )
            self._require_started_run(message_id)
            completion = await self._wait_for_completion(
                queue=event_queue,
                mission=mission,
                session_id=child_session_id,
                expected_artifact_type=request.expected_artifact_type,
                progress_phase=request.progress_phase,
            )
            await self._publish_progress(
                mission=mission,
                source_session_id=child_session_id,
                phase="artifact_agent_completed",
                artifact_uri=completion.artifact_uri,
            )
            return TypedArtifactExecutionResult(
                execution_id=request.execution_id,
                session_id=child_session_id,
                outcome="completed",
                artifact_uri=completion.artifact_uri,
                artifact_type=completion.artifact_type,
                elapsed_seconds=time.monotonic() - started,
            )
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001 - converted to a typed runtime result.
            return TypedArtifactExecutionResult(
                execution_id=request.execution_id,
                session_id=child_session_id,
                outcome="technical_failure",
                error=f"{type(exc).__name__}: {exc}",
                elapsed_seconds=time.monotonic() - started,
            )
        finally:
            await self._cleanup(child_session_id, event_queue)

    async def _create_child_session(
        self,
        request: TypedArtifactExecutionRequest,
    ) -> str:
        runtime_metadata = {
            **request.child_session_metadata,
            "structured_execution_id": request.execution_id,
            STRUCTURED_INPUT_ARTIFACT_URI_METADATA_KEY: request.input_artifact_uri,
            STRUCTURED_EXPECTED_ARTIFACT_TYPE_METADATA_KEY: request.expected_artifact_type,
        }
        child = await self._session_pool.create_child_session(
            parent_session_id=request.parent_session_id,
            agent_name=request.agent_name,
            agent_type="native",
            lifecycle_policy="cascade",
            **runtime_metadata,
        )
        child_session_id = child.session_id
        await self._session_pool.sessions.get_or_create_session_agent(
            child_session_id,
            request.agent_name,
        )
        return child_session_id

    async def _cleanup(
        self,
        child_session_id: str | None,
        event_queue: asyncio.Queue[EventEnvelope] | None,
    ) -> None:
        if event_queue is not None and child_session_id is not None:
            with contextlib.suppress(Exception):
                await self._session_pool.event_bus.unsubscribe(
                    child_session_id,
                    event_queue,
                )
        if child_session_id is not None:
            await self._session_pool.close_session(child_session_id)

    @staticmethod
    def _message(request: TypedArtifactExecutionRequest) -> str:
        return (
            f"{request.instruction.strip()}\n\n"
            f"Use only this immutable input Artifact URI:\n"
            f"{request.input_artifact_uri}\n\n"
            f"Persist exactly one {request.expected_artifact_type} Artifact. "
            "The persistence tool publishes typed completion automatically."
        )

    @staticmethod
    def _require_started_run(message_id: str | None) -> None:
        if message_id is None:
            raise TypedArtifactExecutionError(
                "SessionPool did not start the child Agent Run",
            )

    @staticmethod
    def _validate_request(request: TypedArtifactExecutionRequest) -> None:
        required = {
            "execution_id": request.execution_id,
            "parent_session_id": request.parent_session_id,
            "agent_name": request.agent_name,
            "input_artifact_uri": request.input_artifact_uri,
            "expected_artifact_type": request.expected_artifact_type,
            "instruction": request.instruction,
            "progress_phase": request.progress_phase,
        }
        blank = [name for name, value in required.items() if not value.strip()]
        if blank:
            raise ValueError(
                "typed Artifact execution fields must not be blank: " + ", ".join(blank),
            )

    @staticmethod
    def _assert_dispatchable(mission: MissionExecutionContext) -> None:
        if mission.cancelled or mission.remaining_seconds() <= 0:
            raise TimeoutError("Mission deadline expired before child dispatch")

    async def _wait_for_completion(
        self,
        *,
        queue: asyncio.Queue[EventEnvelope],
        mission: MissionExecutionContext,
        session_id: str,
        expected_artifact_type: str,
        progress_phase: str,
    ) -> ArtifactCompletionEvent:
        tool_errors: list[str] = []
        while True:
            remaining = mission.remaining_seconds()
            if mission.cancelled or remaining <= 0:
                raise TimeoutError("Mission ended before child completion")
            try:
                async with asyncio.timeout(
                    min(remaining, _PROGRESS_HEARTBEAT_SECONDS),
                ):
                    envelope = await queue.get()
            except TimeoutError:
                await self._publish_progress(
                    mission=mission,
                    source_session_id=session_id,
                    phase=progress_phase,
                )
                continue
            event = envelope.event
            if isinstance(event, ToolCallCompleteEvent) and event.is_error:
                tool_errors.append(
                    f"{event.tool_name}: {self._tool_error_text(event.tool_result)}",
                )
                continue
            if isinstance(event, ArtifactCompletionEvent):
                if event.mission_id != mission.mission_id or event.session_id != session_id:
                    continue
                if event.artifact_type != expected_artifact_type:
                    raise TypedArtifactExecutionError(
                        f"Expected {expected_artifact_type}, got {event.artifact_type}",
                    )
                return event
            if isinstance(event, RunErrorEvent):
                raise TypedArtifactExecutionError(event.message)
            if isinstance(event, RunFailedEvent):
                raise TypedArtifactExecutionError(str(event.exception))
            if isinstance(event, StreamCompleteEvent):
                details = ""
                if tool_errors:
                    details = "; tool errors: " + " | ".join(tool_errors)
                raise TypedArtifactExecutionError(
                    "Child Agent ended without a typed Artifact completion" + details,
                )

    @staticmethod
    def _tool_error_text(tool_result: object) -> str:
        text = str(tool_result).strip()
        limit = _MAX_TOOL_ERROR_TEXT_CHARACTERS
        return text if len(text) <= limit else f"{text[:limit]}…"

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


__all__ = [
    "STRUCTURED_EXPECTED_ARTIFACT_TYPE_METADATA_KEY",
    "STRUCTURED_INPUT_ARTIFACT_URI_METADATA_KEY",
    "TypedArtifactExecutionError",
    "TypedArtifactExecutionRequest",
    "TypedArtifactExecutionResult",
    "TypedArtifactExecutionService",
]
