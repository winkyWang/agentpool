# Archived commit supersession audit

| Archived commit | Decision on WolfHarness 4.0 | Evidence / replacement |
| --- | --- | --- |
| `327a2c717` ACP notification batching | Omitted | Current ACP turn and event converter pipeline owns notification ordering; no welding requirement demonstrated a remaining gap. |
| `48b0762e6` OpenCode empty tool input | Superseded | Current OpenCode event processor and its start/progress regression tests already normalize empty input. |
| `4f6afc9c0` question tools | Superseded | `QuestionCapability` is the current elicitation implementation. |
| `90dc04d20` async subagent results | Omitted | The later archived commit reverted cancellation behavior; current `SessionPool` and background-task capabilities are authoritative. |
| `aa928f16e` session status | Superseded | Current `SessionPool`, `RunHandle`, and protocol event bridges own session lifecycle. |
| `5246ca490` native runtime context | Superseded | `resolve_agent_context_from_deps` and current `SubagentCapability` already resolve runtime context. |
| `8635f4de1` model-aware DCP budget | Forward-ported | Current NativeAgent exposes the resolved model window and DCP builds a request-local effective configuration. |
| `87e45a0b7` delegated runtime stability | Forward-ported | Current SessionPool owns configurable inactivity waits; current FileWatcher owns source filtering. |
| `d8ee2f950` Skill runtime and tool failures | Forward-ported selectively | Extended current `SkillManagerCap`, `ExtensionRegistry`, native interception, and protocol adapters; deleted AgentPool toolsets were not restored. |
| `2209837da` local Skill reference path | Forward-ported | `SkillEntry.skill_path` remains authoritative through URI resolution. |

The archived branch and current upstream share Git ancestry. The package rename
and subsystem refactors explain direct-merge conflicts; no history rewrite or
unrelated repository caused the divergence.

## Validation record

- `openspec validate forward-port-welding-runtime-requirements --strict`: passed.
- `ruff check .`: passed.
- `mypy src`: passed for 685 source files.
- Focused DCP, Skill, typed-tool-outcome, SessionPool, OpenCode, MCP, ACP, and
  file-watcher suites: passed.
- Full WolfHarness suite: 6,844 passed, 158 skipped, 3 expected failures, 70
  failed, and 4 setup errors. The failures reproduce in unchanged upstream
  areas and are caused by Windows-incompatible test assumptions or missing
  external executables/fixtures (for example `/test/dir`, shell-builtin
  `echo`, symlink privileges, and ACP VCR subprocess setup).
- `mkdocs build --strict`: reached a complete content build, then failed on 21
  pre-existing navigation/link warnings in current upstream documentation.

No framework behavior was changed merely to mask platform-specific baseline
test failures. The retained welding runtime requirements are covered by focused
regression tests that pass on this checkout.
