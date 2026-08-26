"""Mission progress to Agent Client Protocol conversion tests."""

from __future__ import annotations

from acp.schema import ToolCallProgress, ToolCallStart
from wolfharness.agents.events import MissionProgressEvent
from wolfharness_server.acp_server.event_converter import ACPEventConverter


async def test_mission_progress_opens_updates_and_completes_one_acp_item() -> None:
    converter = ACPEventConverter()
    started = MissionProgressEvent(
        mission_id="mission-1",
        source_session_id="member-1",
        phase="round_planned",
        current=0,
        total=3,
    )
    completed = MissionProgressEvent(
        mission_id="mission-1",
        source_session_id="coordinator",
        phase="result_ready",
        current=3,
        total=3,
        artifact_uri="scratchpad:///welding/result.json",
    )

    first_updates = [update async for update in converter.convert(started)]
    final_updates = [update async for update in converter.convert(completed)]

    assert [type(update) for update in first_updates] == [ToolCallStart, ToolCallProgress]
    assert first_updates[1].status == "in_progress"
    assert len(final_updates) == 1
    assert isinstance(final_updates[0], ToolCallProgress)
    assert final_updates[0].status == "completed"
    assert final_updates[0].raw_output["artifact_uri"].endswith("result.json")
