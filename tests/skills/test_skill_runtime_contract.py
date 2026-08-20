"""Skill progressive-disclosure, activation-limit, and visibility contract tests."""

from __future__ import annotations

from pathlib import Path, PurePosixPath
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

from pydantic_ai.models.test import TestModel
from pydantic_ai.tools import RunContext
from pydantic_ai.usage import RunUsage
import pytest
from upathtools import UPath

from wolfharness import AgentPool
from wolfharness.agents.context import AgentContext, AgentRunContext
from wolfharness.capabilities.skill_manager_cap import SkillManagerCap
from wolfharness.skills.exceptions import SkillActivationLimitError
from wolfharness.skills.skill import Skill


pytestmark = pytest.mark.unit


def _skill(name: str) -> Skill:
    return Skill(
        name=name,
        description=f"{name} description",
        skill_path=PurePosixPath(f"skill://local/{name}"),
        instructions=f"{name} body",
    )


def _run_context(agent_ctx: AgentContext) -> RunContext[Any]:
    return RunContext(deps=agent_ctx, model=TestModel(), usage=RunUsage(), messages=[])


@pytest.mark.anyio
async def test_metadata_only_request_records_exposure_without_body() -> None:
    """Description mode records exposure without activating a Skill body."""
    cap = SkillManagerCap(local_skills={"alpha": _skill("alpha")})
    event_bus = SimpleNamespace(publish=AsyncMock())
    run_ctx = AgentRunContext(
        session_id="session-1",
        run_id="run-1",
        event_bus=event_bus,  # type: ignore[arg-type]
    )
    agent_ctx = AgentContext(  # type: ignore[arg-type]
        node=SimpleNamespace(name="root"),
        run_ctx=run_ctx,
    )

    instructions = cap.get_instructions()
    assert isinstance(instructions, list)
    assert 'name="alpha"' in instructions[0]
    assert await instructions[1](_run_context(agent_ctx)) is None
    assert run_ctx.activated_skills == set()
    assert len(run_ctx.skill_trace_records) == 1
    trace = run_ctx.skill_trace_records[0]
    assert trace.visible_skills == ("alpha",)
    assert trace.activated_skills == ()
    assert trace.source == "metadata"
    event_bus.publish.assert_awaited_once()


@pytest.mark.anyio
async def test_matcher_limit_raises_without_truncating() -> None:
    """Matcher selection fails atomically when its distinct union exceeds the limit."""
    cap = SkillManagerCap(
        local_skills={name: _skill(name) for name in ("alpha", "beta")},
        matcher_fn=lambda _messages: ["alpha", "beta"],
        inject_mode="matcher",
        max_skills=1,
    )
    run_ctx = AgentRunContext(session_id="session-1", run_id="run-1")
    agent_ctx = AgentContext(  # type: ignore[arg-type]
        node=SimpleNamespace(name="root"),
        run_ctx=run_ctx,
    )
    instructions = cap.get_instructions()
    assert isinstance(instructions, list)

    with pytest.raises(SkillActivationLimitError) as exc_info:
        await instructions[1](_run_context(agent_ctx))

    assert exc_info.value.limit == 1
    assert exc_info.value.requested_skills == frozenset({"alpha", "beta"})
    assert run_ctx.activated_skills == set()


@pytest.mark.anyio
async def test_scoped_view_filters_metadata_resources_and_matcher_candidates() -> None:
    """One scoped view controls metadata, matching, resources, and reads."""
    received_candidates: list[str] = []

    def matcher(_messages: list[Any], candidates: list[str]) -> list[str]:
        received_candidates.extend(candidates)
        return candidates

    catalog = SkillManagerCap(
        local_skills={name: _skill(name) for name in ("alpha", "beta")},
        matcher_fn=matcher,
        inject_mode="matcher",
    )
    view = catalog.scoped({"alpha"})
    instructions = view.get_instructions()
    assert isinstance(instructions, list)
    assert 'name="alpha"' in instructions[0]
    assert 'name="beta"' not in instructions[0]

    ctx = SimpleNamespace(messages=[], deps=None)
    content = await instructions[1](ctx)  # type: ignore[arg-type]
    assert content is not None
    assert "alpha body" in content
    assert "beta body" not in content
    assert received_candidates == ["alpha"]
    assert [entry.name for entry in await view.list_skills()] == ["alpha"]
    assert await view.read_skill("beta") is None
    assert await view.get_command("beta") is None


@pytest.mark.integration
@pytest.mark.anyio
async def test_pool_node_visibility_applies_to_load_and_references(tmp_path: Path) -> None:
    """Pool policy hides Skill bodies and references from excluded nodes."""
    for name in ("shared", "review"):
        skill_dir = tmp_path / name
        skill_dir.mkdir()
        (skill_dir / "references").mkdir()
        (skill_dir / "SKILL.md").write_text(
            f"---\nname: {name}\ndescription: {name} skill\n---\n\n{name} instructions",
            encoding="utf-8",
        )
        (skill_dir / "references" / "guide.md").write_text(
            f"{name} reference",
            encoding="utf-8",
        )

    config_path = tmp_path / "wolfharness.yaml"
    config_path.write_text(
        "\n".join(
            [
                "skills:",
                "  include_default: false",
                "  paths:",
                f"    - {tmp_path.as_posix()}",
                "  node_visibility:",
                "    root: [shared, review]",
                "    reviewer: [shared]",
                "agents:",
                "  root:",
                "    type: native",
                "    model: test",
                "  reviewer:",
                "    type: native",
                "    model: test",
            ]
        ),
        encoding="utf-8",
    )

    async with AgentPool(UPath(config_path)) as pool:
        assert pool.visible_skill_names_for_node("root") == {"shared", "review"}
        assert pool.visible_skill_names_for_node("reviewer") == {"shared"}

        reviewer_cap = pool.skill_capability_for_node("reviewer")
        assert reviewer_cap is not None
        assert [entry.name for entry in await reviewer_cap.list_skills()] == ["shared"]

        run_ctx = AgentRunContext(session_id="review-session", run_id="review-run")
        reviewer_ctx = AgentContext(  # type: ignore[arg-type]
            node=SimpleNamespace(name="reviewer"),
            pool=pool,
            run_ctx=run_ctx,
        )
        pydantic_ctx = _run_context(reviewer_ctx)
        loaded = await reviewer_cap._load_skill_impl(pydantic_ctx, "shared")
        assert "shared instructions" in loaded
        assert run_ctx.activated_skills == {"shared"}
        assert run_ctx.skill_trace_records[-1].source == "explicit"

        reference = await reviewer_cap._load_skill_impl(
            pydantic_ctx,
            "skill://shared/references/guide.md",
        )
        assert "shared reference" in reference
        assert run_ctx.activated_skills == {"shared"}

        hidden = await reviewer_cap._load_skill_impl(pydantic_ctx, "review")
        assert "not found" in hidden
        assert "review instructions" not in hidden
        hidden_reference = await reviewer_cap._load_skill_impl(
            pydantic_ctx,
            "skill://review/references/guide.md",
        )
        assert "not found" in hidden_reference
        assert "review reference" not in hidden_reference
