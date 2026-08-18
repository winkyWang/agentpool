"""Per-run Skill activation accounting and structured tracing."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from agentpool.skills.exceptions import SkillActivationLimitError


if TYPE_CHECKING:
    from collections.abc import Collection

    from agentpool.agents.context import AgentContext


SkillActivationSource = Literal["metadata", "matcher", "always_active", "explicit"]


@dataclass(frozen=True, slots=True, kw_only=True)
class SkillTraceRecord:
    """Structured record of Skill exposure or activation in one run."""

    node_name: str
    run_id: str
    session_id: str
    visible_skills: tuple[str, ...]
    activated_skills: tuple[str, ...]
    source: SkillActivationSource


async def record_skill_trace(
    agent_ctx: AgentContext | None,
    *,
    visible_skills: Collection[str],
    activated_skills: Collection[str],
    source: SkillActivationSource,
) -> SkillTraceRecord | None:
    """Record Skill exposure/activation and publish it when an EventBus exists."""
    if agent_ctx is None or agent_ctx.run_ctx is None:
        return None

    run_ctx = agent_ctx.run_ctx
    node_name = getattr(agent_ctx.node, "name", type(agent_ctx.node).__name__)
    record = SkillTraceRecord(
        node_name=str(node_name),
        run_id=run_ctx.run_id,
        session_id=run_ctx.session_id,
        visible_skills=tuple(sorted(set(visible_skills))),
        activated_skills=tuple(sorted(set(activated_skills))),
        source=source,
    )
    run_ctx.skill_trace_records.append(record)

    if run_ctx.event_bus is not None:
        from agentpool.agents.events import CustomEvent

        await run_ctx.event_bus.publish(
            run_ctx.session_id,
            CustomEvent(
                event_data=record,
                event_type="skill_trace",
                source=record.node_name,
            ),
        )
    return record


async def activate_skills(
    agent_ctx: AgentContext | None,
    *,
    requested_skills: Collection[str],
    visible_skills: Collection[str],
    max_skills: int,
    source: SkillActivationSource,
) -> frozenset[str]:
    """Activate distinct Skill bodies without silently truncating requests."""
    requested = set(requested_skills)
    if agent_ctx is not None and agent_ctx.run_ctx is not None:
        active = agent_ctx.run_ctx.activated_skills
    else:
        active = set()

    if len(active | requested) > max_skills:
        raise SkillActivationLimitError(
            limit=max_skills,
            active_skills=set(active),
            requested_skills=requested,
        )

    active.update(requested)
    await record_skill_trace(
        agent_ctx,
        visible_skills=visible_skills,
        activated_skills=requested,
        source=source,
    )
    return frozenset(active)
