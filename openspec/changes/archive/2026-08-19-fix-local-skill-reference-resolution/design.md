## Context

`SkillManagerCap.list_skills()` already identifies local entries with a real
`skill_path`. `SkillURIResolver._build_skill_from_entry()` discards that field
and always creates a `PurePosixPath(entry.uri)`. The reference loader correctly
uses filesystem I/O for `UPath` and provider I/O for virtual paths, so the loss
of identity in the resolver is the single fault.

## Goals / Non-Goals

**Goals:**

- Retain the authoritative local/remote resource identity through URI
  resolution.
- Keep node visibility checks unchanged and effective for reference reads.
- Prove remote providers still use their provider-owned virtual identity.

**Non-Goals:**

- Add fallback lookup or probe both filesystem and provider paths.
- Change Skill URI syntax, activation accounting, or reference-only activation.

## Decision

When a `SkillEntry` has `skill_path`, construct the resolved `Skill` with that
path. When it is absent, construct it with `PurePosixPath(entry.uri)` as before.
The entry owner therefore decides resource identity once. The downstream
reference loader follows the existing typed path distinction without guessing,
fallback, or duplicated lookup.

## Risks / Trade-offs

- A provider could incorrectly claim a local path. That path is already part of
  the typed `SkillEntry` contract; provider correctness is preferable to a
  second inference layer.
- Node visibility must be checked before either local or remote read. Existing
  load flow already performs this check and the integration test locks it down.

## Validation

- Unit resolver test for local `UPath` retention and remote virtual paths.
- Real `AgentPool` integration test for visible one-hop local reference load and
  hidden-node rejection.
- Focused Skill resolver/runtime tests, Ruff, mypy, and strict OpenSpec
  validation.
