from __future__ import annotations

from pydantic_ai import ToolReturn
import pytest

from agentpool.mcp_server.tool_bridge import _convert_to_tool_result
from agentpool.tools.base import ToolResult


pytestmark = pytest.mark.unit


def test_bridge_preserves_pydantic_tool_return_content() -> None:
    """`ToolReturn` content remains visible after MCP bridge conversion."""
    converted = _convert_to_tool_result(
        ToolReturn(
            return_value="<file>\n00001| graph TD\n00002| A --> B\n</file>",
            metadata={"file_path": "scratchpad://report.md", "read_lines": 2},
        )
    )

    assert converted.content
    assert converted.content[0].text.startswith("<file>\n00001| graph TD")
    assert converted.structured_content == {
        "file_path": "scratchpad://report.md",
        "read_lines": 2,
    }
    assert converted.meta == {"file_path": "scratchpad://report.md", "read_lines": 2}


def test_bridge_preserves_agentpool_failure_semantics() -> None:
    """MCP exposes AgentPool's declared execution failure as ``isError``."""
    converted = _convert_to_tool_result(ToolResult(content="boom", is_error=True))

    assert converted.is_error is True
    assert converted.content[0].text == "boom"
