"""Test: resume with active run - RunHandle cancellation is awaited.

Verifies that when ``close_session()`` is called on a session with an
active run, its driver task is cancelled and settled before cleanup proceeds.

This mirrors the ``resume_session()`` flow (T20) which calls
``SessionController.close_session()`` before recreating the session.
"""

from __future__ import annotations

import asyncio
from unittest.mock import Mock

import pytest

from wolfharness.lifecycle import RunState
from wolfharness.orchestrator.run import RunHandle
from wolfharness.orchestrator.session_controller import SessionController, SessionState


@pytest.mark.integration
@pytest.mark.asyncio
async def test_resume_with_active_run() -> None:
    """close_session cancels an active RunHandle and awaits its driver.

    Simulates a run that blocks until cancellation.
    ``close_session`` should:
    1. Cancel the Run driver.
    2. Wait for the driver's ``finally`` cleanup and ``complete_event``.
    3. Proceed to remove the Session from ``_sessions``.
    """
    mock_pool = Mock()
    controller = SessionController(pool=mock_pool)

    session_id = "test-resume-active-run"
    run_id = "run-never-completes"

    session = SessionState(
        session_id=session_id,
        agent_name="test_agent",
    )
    session.current_run_id = run_id
    controller._sessions[session_id] = session

    run_handle = RunHandle(
        run_id=run_id,
        session_id=session_id,
        agent_type="native",
    )
    started = asyncio.Event()

    async def drive() -> None:
        run_handle.run_ctx.current_task = asyncio.current_task()
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            run_handle.complete_event.set()

    driver_task = asyncio.create_task(drive())
    await started.wait()

    # Simulate a running run: status is running, complete_event NOT set.
    run_handle._run_state = RunState.RUNNING
    controller._runs[run_id] = run_handle

    # close_session should complete only after the driver has settled.
    await asyncio.wait_for(controller.close_session(session_id), timeout=30.0)

    # RunHandle was cancelled.
    assert run_handle.run_ctx.cancelled is True
    assert driver_task.cancelled()
    assert run_handle.complete_event.is_set()

    # Session was cleaned up.
    assert session_id not in controller._sessions
    assert run_id not in controller._runs
