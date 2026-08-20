# Forward-port generic welding runtime requirements onto WolfHarness 4.0

The archived AgentPool 2.9.5 welding branch has been audited against current
WolfHarness rather than merged across the package and capability refactors.

- Dynamic Context Pruning now derives pressure from the active model variant's
  declared context window, and `prune` has a scoped corrective retry allowance.
- Skill disclosure supports one node visibility policy across metadata, tools,
  commands, loading, and references. Distinct per-run activations enforce
  `max_skills` atomically and emit structured trace events.
- `ToolResult.is_error` and `ToolCallCompleteEvent.is_error` provide one typed
  failure contract across native execution, ACP, OpenCode, and MCP. Protocols
  no longer infer failure from payload keys or presentation metadata.
- Delegated agent waits use a configurable event-inactivity interval instead of
  a fixed total-duration timeout.
- OpenCode project watching filters invariant runtime paths, including `logs/**`,
  before watch logging and callback dispatch.

The change contains no welding-domain prompts or business rules and preserves
the current WolfHarness capability architecture.
