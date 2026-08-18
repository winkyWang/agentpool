## Why

Pool-backed `skill://.../references/...` resolution rebuilds every catalog entry
with a virtual path, even when `SkillEntry` already carries the authoritative
local `UPath`. The loader then routes the local reference through the remote MCP
provider aggregate, so a visible local Skill body loads but its one-hop
references always report not found. This breaks progressive disclosure and
role-scoped playbooks.

## What Changes

- Preserve a local catalog entry's real `skill_path` when the URI resolver
  constructs the resolved Skill.
- Continue using a virtual URI path for remote entries that have no local path.
- Add unit and pool integration coverage for local reference loading,
  node-visibility rejection, and unchanged remote-provider resolution.

## Capabilities

### Modified Capabilities

- `skill-manager-cap`: local reference resources remain readable through the
  same authoritative node visibility policy as Skill metadata and bodies.

## Impact

- `agentpool.skills.uri_resolver.SkillURIResolver`
- Pool-backed `load_skill("skill://.../references/...")`
- Skill resolver and runtime integration tests
