"""Test: WebSocket disconnect cancels and settles the active RunHandle.

Verifies that when ``close_all_sessions_for_connection()`` is called
(e.g. on WebSocket disconnect) for a session with an active run, the
RunHandle driver is cancelled and settled before session identity is removed.

This is the end-to-end disconnect path (T25 + T26):
1. ``on_disconnect`` callback fires on WebSocket close.
2. ``ACPSessionManager.close_all_sessions_for_connection()`` is called.
3. ``SessionController.close_session()`` is called for each session.
4. ``_close_session_run_turn()`` cancels and awaits the RunHandle driver.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, Mock

import pytest

from wolfharness.lifecycle import RunState
from wolfharness.orchestrator.run import RunHandle
from wolfharness.orchestrator.session_controller import SessionController, SessionState
from wolfharness_server.acp_server.session_manager import ACPSessionManager


@pytest.mark.integration
@pytest.mark.asyncio
async def test_websocket_disconnect_during_run() -> None:
    """close_all_sessions_for_connection settles the owned Run driver.

    Simulates a WebSocket disconnect while a cancellable run is active. The
    disconnect path should:
    1. Call ``SessionController.close_session()`` (via the controller).
    2. ``_close_session_run_turn()`` acquires ``turn_lock``.
    3. Cancels and awaits the driver task.
    4. Observes driver cleanup through ``complete_event``.
    5. Only then removes the session from ``_sessions`` and ``_acp_sessions``.
    """
    mock_pool = Mock()
    controller = SessionController(pool=mock_pool)

    session_id = "test-ws-disconnect-active-run"
    run_id = "run-hung-on-disconnect"
    connection_id = "conn-uuid-hex-1234"

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
    run_handle._run_state = RunState.RUNNING

    driver_started = asyncio.Event()
    driver_finalized = asyncio.Event()

    async def _drive_until_cancelled() -> None:
        driver_started.set()
        try:
            await asyncio.Event().wait()
        finally:
            driver_finalized.set()
            run_handle.complete_event.set()

    driver_task = asyncio.create_task(_drive_until_cancelled())
    run_handle.bind_driver_task(driver_task)
    await driver_started.wait()
    controller._runs[run_id] = run_handle

    mock_acp_session = Mock()
    mock_acp_session.close = AsyncMock()

    session_manager = ACPSessionManager(pool=mock_pool)
    mock_pool.session_pool = Mock()
    mock_pool.session_pool.sessions = controller

    async def _close_via_controller(sid: str) -> None:
        await controller.close_session(sid)

    mock_pool.session_pool.close_session = _close_via_controller
    session_manager._acp_sessions[session_id] = mock_acp_session
    session_manager._connection_sessions[connection_id] = {session_id}

    await asyncio.wait_for(
        session_manager.close_all_sessions_for_connection(connection_id),
        timeout=30.0,
    )

    assert run_handle.run_ctx.cancelled is True
    assert driver_task.cancelled()
    assert driver_finalized.is_set()
    assert run_handle.complete_event.is_set()
    assert session_id not in controller._sessions
    assert session_id not in session_manager._acp_sessions
    assert connection_id not in session_manager._connection_sessions
    mock_acp_session.close.assert_awaited_once()
