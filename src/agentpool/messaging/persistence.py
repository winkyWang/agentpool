"""Projection helpers for safe long-term conversation persistence."""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING, Any

from pydantic_ai import (
    AudioUrl,
    BaseToolReturnPart,
    BinaryContent,
    BinaryImage,
    DocumentUrl,
    FilePart,
    ImageUrl,
    ModelRequest,
    ModelResponse,
    TextPart,
    UploadedFile,
    UserPromptPart,
    VideoUrl,
)


if TYPE_CHECKING:
    from pydantic_ai.messages import ModelMessage, ModelRequestPart, ModelResponsePart

    from agentpool.messaging.messages import ChatMessage


def _binary_reference(content: BinaryContent | BinaryImage) -> str:
    return f"[attachment ref={content.identifier} media_type={content.media_type}]"


def _project_content(content: Any) -> Any:
    projected: Any
    match content:
        case BinaryContent() | BinaryImage():
            projected = _binary_reference(content)
        case ImageUrl(media_type=media_type):
            projected = f"[image media_type={media_type or 'unknown'}]"
        case AudioUrl(media_type=media_type):
            projected = f"[audio media_type={media_type or 'unknown'}]"
        case VideoUrl(media_type=media_type):
            projected = f"[video media_type={media_type or 'unknown'}]"
        case DocumentUrl(media_type=media_type):
            projected = f"[document media_type={media_type or 'unknown'}]"
        case UploadedFile(file_id=file_id):
            projected = f"[uploaded-file ref={file_id}]"
        case list() as items:
            projected = [_project_content(item) for item in items]
        case tuple() as items:
            projected = tuple(_project_content(item) for item in items)
        case dict() as mapping:
            projected = {key: _project_content(value) for key, value in mapping.items()}
        case _:
            projected = content
    return projected


def project_multimodal_references(message: ChatMessage[Any]) -> ChatMessage[Any]:
    """Replace persisted multimodal payloads with safe textual references."""
    projected_messages: list[ModelMessage] = []
    for model_message in message.messages:
        if isinstance(model_message, ModelRequest):
            request_parts: list[ModelRequestPart] = []
            for request_part in model_message.parts:
                if isinstance(request_part, (UserPromptPart, BaseToolReturnPart)):
                    request_parts.append(
                        replace(
                            request_part,
                            content=_project_content(request_part.content),
                        )
                    )
                else:
                    request_parts.append(request_part)
            projected_messages.append(replace(model_message, parts=request_parts))
        elif isinstance(model_message, ModelResponse):
            response_parts: list[ModelResponsePart] = []
            for response_part in model_message.parts:
                if isinstance(response_part, FilePart):
                    response_parts.append(
                        TextPart(content=_binary_reference(response_part.content))
                    )
                else:
                    response_parts.append(response_part)
            projected_messages.append(replace(model_message, parts=response_parts))
        else:
            projected_messages.append(model_message)
    return replace(
        message,
        content=_project_content(message.content),
        messages=projected_messages,
    )
