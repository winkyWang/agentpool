"""Tests for opt-in conversation persistence projection."""

from __future__ import annotations

from pydantic_ai import BinaryContent, ModelRequest, ToolReturnPart, UserPromptPart
from pydantic_ai.models.test import TestModel
import pytest

from agentpool import Agent
from agentpool.messaging import ChatMessage
from agentpool.messaging.persistence import project_multimodal_references
from agentpool_config.session import MemoryConfig


pytestmark = pytest.mark.unit


def test_project_multimodal_references_removes_binary_bytes() -> None:
    binary = BinaryContent(
        data=b"secret-image-bytes",
        media_type="image/png",
        identifier="attachment:123",
    )
    message = ChatMessage(
        content=["查看附件", binary],
        role="assistant",
        messages=[
            ModelRequest(
                parts=[
                    UserPromptPart(content=["查看附件", binary]),
                    ToolReturnPart(
                        tool_name="view_attachment",
                        tool_call_id="call-1",
                        content=[binary],
                    ),
                ]
            )
        ],
    )

    projected = project_multimodal_references(message)

    assert projected is not message
    serialized = repr(projected)
    assert "secret-image-bytes" not in serialized
    assert "attachment:123" in serialized
    assert "image/png" in serialized
    assert binary in message.content


def test_memory_config_accepts_persistence_processors() -> None:
    config = MemoryConfig(
        persistence_processors=["agentpool.messaging.persistence:project_multimodal_references"]
    )

    assert config.persistence_processors == [
        "agentpool.messaging.persistence:project_multimodal_references"
    ]


async def test_agent_applies_configured_persistence_projection() -> None:
    binary = BinaryContent(
        data=b"secret-pdf-bytes",
        media_type="application/pdf",
        identifier="attachment:456",
    )
    agent = Agent(
        name="projection-test",
        model=TestModel(),
        session=MemoryConfig(
            persistence_processors=["agentpool.messaging.persistence:project_multimodal_references"]
        ),
    )

    projected = await agent.project_message_for_persistence(
        ChatMessage(content=[binary], role="assistant")
    )

    assert "secret-pdf-bytes" not in repr(projected)
    assert "attachment:456" in repr(projected)
