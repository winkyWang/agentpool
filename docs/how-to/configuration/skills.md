---
title: Skills Configuration
description: Configure Skill discovery, node visibility, and activation
order: 10
icon: material/lightning-bolt
---

Skills provide specialized instructions and supporting resources. AgentPool exposes
visible Skill metadata by default and loads a Skill body only when the Skill is
explicitly requested, selected by a configured matcher, or marked always-active.

## Configuration

```yaml
skills:
  paths:
    - ~/.config/agentpool/skills
    - ./skills
  include_default: true
  instruction:
    # One per-run budget shared by automatic and explicit activation.
    max_skills: 20
  node_visibility:
    planner:
      - planning
      - code-review
    implementer:
      - coding
      - code-review
```

`instruction.max_skills` is the single activation limit. It counts distinct Skill
bodies across matcher, always-active, and `load_skill` activation during one run.
AgentPool raises a structured activation error when a request would exceed the
limit; it never silently truncates the requested Skills.

When `node_visibility` is present, each key is an exact node allow-list. A Skill may
be visible to multiple nodes. Nodes omitted from the mapping see no Skills. The same
visibility rule applies to prompt metadata, Skill listing, URI/bare-name loading,
matcher candidates, and native capability injection.

When `node_visibility` is omitted, AgentPool derives visibility from Skill package
scope where available; otherwise all discovered Skills are visible.

## Runtime contract

Visible agents receive metadata rather than complete bodies:

```xml
<available-skills>
  <skill name="code-review" description="Review code changes" />
</available-skills>
```

The body is activated through one of these routes:

- `load_skill("code-review")` or a `skill://` URI;
- a configured semantic matcher selecting the Skill;
- an explicit always-active declaration.

Reference files loaded through a Skill URI are progressive-disclosure resources and
do not activate another Skill body. Each exposure or activation is recorded as a
structured per-run trace with node, run, session, visible Skills, activated Skills,
and activation source.

## Agent tools

The Skill toolset controls which Skill tools are callable; it does not define a
second activation budget.

```yaml
agents:
  assistant:
    model: openai:gpt-4o-mini
    tools:
      - type: skills
        tools:
          load_skill: true
          get_skill_reference: true
```

## See also

- [Skill URI usage](./skill-uri-usage.md)
- [RFC-0008: Dynamic Skills Injection](../../rfcs/implemented/RFC-0008-dynamic-skills-injection.md)
