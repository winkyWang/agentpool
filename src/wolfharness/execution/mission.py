"""Shared execution budget for a delegated Session tree."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
import time
from typing import Any
from uuid import uuid4


MISSION_CONTEXT_KEY = "wolfharness_mission_context"
"""Dependency key used to propagate one mission through child Sessions."""


class MissionBudgetExceededError(RuntimeError):
    """Raised before a model request when the shared mission budget is exhausted."""


@dataclass(frozen=True, slots=True)
class MissionToolFailure:
    """One failed tool call observed at the typed runtime boundary."""

    session_id: str
    agent_name: str
    tool_name: str
    error: str


@dataclass(frozen=True, slots=True)
class MissionUsageSnapshot:
    """Immutable aggregate of model usage across a mission Session tree."""

    model_requests: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    tool_failures: int = 0
    tool_failure_details: tuple[MissionToolFailure, ...] = ()


@dataclass(slots=True)
class MissionExecutionContext:
    """One deadline, cancellation signal, and usage budget for a delegated mission."""

    mission_id: str
    root_session_id: str
    progress_session_id: str
    absolute_deadline: datetime
    max_model_requests: int
    _deadline_monotonic: float = field(repr=False)
    _cancelled: asyncio.Event = field(default_factory=asyncio.Event, repr=False)
    _usage_lock: asyncio.Lock = field(default_factory=asyncio.Lock, repr=False)
    _model_requests: int = 0
    _input_tokens: int = 0
    _output_tokens: int = 0
    _tool_failures: int = 0
    _tool_failure_details: list[MissionToolFailure] = field(
        default_factory=list,
        repr=False,
    )

    @classmethod
    def create(
        cls,
        *,
        root_session_id: str,
        timeout_seconds: float,
        max_model_requests: int,
        progress_session_id: str | None = None,
    ) -> MissionExecutionContext:
        """Create the execution context at mission launch time."""
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be greater than zero")
        if max_model_requests < 1:
            raise ValueError("max_model_requests must be at least one")
        return cls(
            mission_id=f"mission_{uuid4().hex[:16]}",
            root_session_id=root_session_id,
            progress_session_id=progress_session_id or root_session_id,
            absolute_deadline=datetime.now(tz=UTC) + timedelta(seconds=timeout_seconds),
            max_model_requests=max_model_requests,
            _deadline_monotonic=time.monotonic() + timeout_seconds,
        )

    @property
    def cancelled(self) -> bool:
        """Whether cancellation has been requested for the whole mission."""
        return self._cancelled.is_set()

    def cancel(self) -> None:
        """Request cooperative cancellation for every Session in the mission."""
        self._cancelled.set()

    def remaining_seconds(self) -> float:
        """Return the remaining monotonic execution time."""
        return max(0.0, self._deadline_monotonic - time.monotonic())

    async def reserve_model_request(self) -> None:
        """Atomically reserve one model request before network execution."""
        async with self._usage_lock:
            if self.cancelled:
                raise MissionBudgetExceededError(f"Mission {self.mission_id} was cancelled")
            if self.remaining_seconds() <= 0:
                raise MissionBudgetExceededError(f"Mission {self.mission_id} deadline expired")
            if self._model_requests >= self.max_model_requests:
                raise MissionBudgetExceededError(
                    f"Mission {self.mission_id} exhausted its "
                    f"{self.max_model_requests} model-request budget"
                )
            self._model_requests += 1

    async def record_tokens(self, *, input_tokens: int, output_tokens: int) -> None:
        """Add token usage emitted by one completed model request."""
        async with self._usage_lock:
            self._input_tokens += max(0, input_tokens)
            self._output_tokens += max(0, output_tokens)

    async def record_tool_failure(
        self,
        *,
        session_id: str,
        agent_name: str,
        tool_name: str,
        error: str,
    ) -> None:
        """Record a failed tool invocation within the mission."""
        async with self._usage_lock:
            self._tool_failures += 1
            self._tool_failure_details.append(
                MissionToolFailure(
                    session_id=session_id,
                    agent_name=agent_name,
                    tool_name=tool_name,
                    error=error,
                ),
            )

    def usage_snapshot(self) -> MissionUsageSnapshot:
        """Return a consistent event-loop-local usage snapshot."""
        return MissionUsageSnapshot(
            model_requests=self._model_requests,
            input_tokens=self._input_tokens,
            output_tokens=self._output_tokens,
            tool_failures=self._tool_failures,
            tool_failure_details=tuple(self._tool_failure_details),
        )


def mission_from_deps(deps: Any) -> MissionExecutionContext | None:
    """Read the mission through runtime and delegated dependency layers."""
    mapping = inherited_run_deps(deps)
    if mapping is None:
        return None
    mission = mapping.get(MISSION_CONTEXT_KEY)
    return mission if isinstance(mission, MissionExecutionContext) else None


def inherited_run_deps(deps: Any) -> Mapping[str, Any] | None:
    """Resolve caller-supplied Run data without discarding runtime services."""
    current = deps
    visited: set[int] = set()
    while current is not None and id(current) not in visited:
        visited.add(id(current))
        if isinstance(current, Mapping):
            return current
        inherited = getattr(current, "inherited_run_deps", None)
        if inherited is not None:
            current = inherited
            continue
        current = getattr(current, "data", None)
    return None


def with_mission_context(
    deps: Mapping[str, Any] | None,
    mission: MissionExecutionContext,
) -> dict[str, Any]:
    """Return child dependencies carrying the exact shared mission object."""
    return {**(dict(deps) if deps is not None else {}), MISSION_CONTEXT_KEY: mission}
