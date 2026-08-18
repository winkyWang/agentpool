"""Skill progressive-disclosure, activation-limit, and visibility contract tests."""

from __future__ import annotations

from pathlib import PurePosixPath
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock

from pydantic_ai.models.test import TestModel
from pydantic_ai.tools import RunContext
from pydantic_ai.usage import RunUsage
import pytest
from upathtools import UPath

from agentpool import AgentPool
from agentpool.agents.context import AgentContext, AgentRunContext
from agentpool.capabilities.extension_registry import Scope, ScopeLevel
from agentpool.capabilities.skill_manager_cap import SkillManagerCap
from agentpool.skills.exceptions import SkillActivationLimitError
from agentpool.skills.skill import Skill
from agentpool_toolsets.builtin.skills import load_skill


if TYPE_CHECKING:
    from pathlib import Path


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
    cap = SkillManagerCap(local_skills={"alpha": _skill("alpha")})
    event_bus = SimpleNamespace(publish=AsyncMock())
    run_ctx = AgentRunContext(
        session_id="session-1",
        run_id="run-1",
        event_bus=event_bus,  # type: ignore[arg-type]
    )
    node = SimpleNamespace(name="root")
    agent_ctx = AgentContext(node=node, run_ctx=run_ctx)  # type: ignore[arg-type]

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
    published_session, published_event = event_bus.publish.await_args.args
    assert published_session == "session-1"
    assert published_event.event_type == "skill_trace"
    assert published_event.event_data is trace


@pytest.mark.anyio
async def test_matcher_limit_raises_without_truncating() -> None:
    skills = {name: _skill(name) for name in ("alpha", "beta")}
    cap = SkillManagerCap(
        local_skills=skills,
        matcher_fn=lambda _messages: ["alpha", "beta"],
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
    received_candidates: list[str] = []

    def matcher(_messages: list[Any], candidates: list[str]) -> list[str]:
        received_candidates.extend(candidates)
        return candidates

    catalog = SkillManagerCap(
        local_skills={name: _skill(name) for name in ("alpha", "beta")},
        matcher_fn=matcher,
    )
    view = catalog.scoped({"alpha"})
    instructions = view.get_instructions()
    assert isinstance(instructions, list)
    assert 'name="alpha"' in instructions[0]
    assert 'name="beta"' not in instructions[0]

    ctx = SimpleNamespace(messages=[], deps=None)
    content = await instructions[1](ctx)  # type: ignore[arg-type]
    assert content is not None and "alpha body" in content
    assert "beta body" not in content
    assert received_candidates == ["alpha"]
    assert [entry.name for entry in await view.list_skills()] == ["alpha"]
    assert await view.read_skill("beta") is None
    assert await view.get_command("beta") is None


@pytest.mark.integration
@pytest.mark.anyio
async def test_pool_node_visibility_applies_to_load_and_resource_registry(tmp_path: Path) -> None:
    for name in ("shared", "review"):
        skill_dir = tmp_path / name
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(
            f"---\nname: {name}\ndescription: {name} skill\n---\n\n{name} instructions",
            encoding="utf-8",
        )

    config_path = tmp_path / "agentpool.yaml"
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
        assert pool.visible_skill_names_for_node("root") == frozenset({"shared", "review"})
        assert pool.visible_skill_names_for_node("reviewer") == frozenset({"shared"})

        reviewer_resources = pool.extension_registry.get_skill_resources(
            Scope(level=ScopeLevel.AGENT, agent_name="reviewer")
        )
        assert len(reviewer_resources) == 1
        assert [entry.name for entry in await reviewer_resources[0].list_skills()] == ["shared"]
        assert pool.skill_capability_for_node("reviewer") is reviewer_resources[0]

        root_resources = pool.extension_registry.get_skill_resources(
            Scope(level=ScopeLevel.AGENT, agent_name="root")
        )
        assert len(root_resources) == 1
        assert {entry.name for entry in await root_resources[0].list_skills()} == {
            "shared",
            "review",
        }

        run_ctx = AgentRunContext(session_id="review-session", run_id="review-run")
        reviewer_ctx = AgentContext(  # type: ignore[arg-type]
            node=SimpleNamespace(name="reviewer"),
            pool=pool,
            run_ctx=run_ctx,
        )
        loaded = await load_skill(reviewer_ctx, "shared")
        assert "shared instructions" in loaded
        assert run_ctx.activated_skills == {"shared"}
        assert run_ctx.skill_trace_records[-1].source == "explicit"

        hidden = await load_skill(reviewer_ctx, "review")
        assert "not found" in hidden
        assert "review instructions" not in hidden


@pytest.mark.integration
@pytest.mark.anyio
async def test_unknown_visibility_skill_fails_pool_initialization(tmp_path: Path) -> None:
    config_path = tmp_path / "agentpool.yaml"
    config_path.write_text(
        "\n".join(
            [
                "skills:",
                "  include_default: false",
                "  paths: []",
                "  node_visibility:",
                "    root: [missing-skill]",
                "agents:",
                "  root:",
                "    type: native",
                "    model: test",
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(RuntimeError) as exc_info:
        async with AgentPool(UPath(config_path)):
            pass
    assert isinstance(exc_info.value.__cause__, ValueError)
    assert "missing-skill" in str(exc_info.value.__cause__)
