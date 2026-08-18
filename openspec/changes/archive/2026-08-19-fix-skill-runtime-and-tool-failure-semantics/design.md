## Context

See `proposal.md`. Skill metadata/body selection currently lives partly in `SkillManagerCap`, partly in `SkillsTools`, and partly in hidden package-scope helpers. A pool-wide capability is injected into every native agent, so node identity is unavailable when metadata and tools are assembled. Tool execution already passes through PydanticAI, whose tool-return parts have a native `outcome` field, but AgentPool discards it and downstream adapters reconstruct failure from metadata or payload dictionaries.

## Goals / Non-Goals

**Goals:**

- One resolved node visibility policy used by every Skill access path.
- Per-run activation accounting shared by matcher and explicit load.
- Structured traces suitable for executable Skill-selection evaluations.
- One canonical tool result and event outcome propagated without payload inspection.

**Non-Goals:**

- Building a semantic Skill matcher; callers may inject one and explicit `load_skill` remains the standard activation path.
- Adding welding-specific routing or Skill content.
- Treating every domain-level rejection as infrastructure failure; tool owners declare that distinction.

## Decisions

### 1. Resolve visibility by Skill name, then build node-specific capability views

`SkillsConfig` gains a node-to-Skill allow-list. After discovery, the pool validates every configured name and resolves the authoritative visible-name set for each node. Package include scopes are normalized into the same resolved policy rather than consulted independently by tools. A catalog capability owns all discovered Skills for URI resolution, while each native agent receives a node-specific view filtered before metadata, tools, commands, or body injection are assembled.

This is preferable to a single scope label because one Skill can be shared by several nodes and one node can see several unrelated Skill sets. Passing node identity into every resource method was rejected because it would leak orchestration concerns into the generic resource protocols.

### 2. Store activation state on the per-run context

The per-run context owns a set of activated Skill names and structured trace records. Both matcher injection and `load_skill` call one activation function. The function computes the distinct union before mutation and raises `SkillActivationLimitError` with structured fields when the configured maximum would be exceeded. It never slices a result list. Reference-only reads do not activate a Skill body.

Agent or capability instances do not own activation state because they outlive runs and would leak between concurrent sessions.

### 3. Metadata-only is the only default

Without a matcher or always-active declaration, the dynamic instruction callable emits an exposure trace and returns no body. Explicit loading returns the body as the tool result and records activation. The old “no matcher means inject all” branch is deleted rather than retained behind a mode.

### 4. Emit a first-class Skill trace event and retain it in run state

A `SkillTraceEvent` records visible and activated names plus `metadata`, `matcher`, `always_active`, or `explicit` source. The event is appended to run state for deterministic tests and published to the EventBus when present. Protocol frontends may ignore this diagnostic event; evaluation code does not need to parse prompts.

### 5. Use `ToolResult.is_error` as the owner signal and PydanticAI `outcome` as the native bridge

AgentPool's canonical `ToolResult` gains `is_error`. The duplicate resource-protocol result type is replaced by the canonical type. The native interceptor turns `is_error=true` and ordinary exceptions into PydanticAI `ToolFailed`, which yields `ToolReturnPart(outcome="failed")`. `EventMapper` maps `outcome` to a first-class `ToolCallCompleteEvent.is_error` field and preserves ordinary metadata separately.

Using a reserved key inside arbitrary metadata was rejected because metadata is optional application data and can be overwritten. Returning `{"error": ...}` was rejected because it conflates payload schema with execution status.

### 6. Protocol adapters consume only typed outcome

- ACP server maps `ToolCallCompleteEvent.is_error` to `failed`/`completed`.
- ACP-agent input maps both terminal ACP statuses to `ToolCallCompleteEvent`, setting `is_error` from status.
- OpenCode maps `is_error` directly and never inspects result dictionaries.
- The MCP server bridge maps canonical `ToolResult.is_error` to FastMCP's native flag.
- The MCP client maps a native MCP error result into canonical `ToolResult(is_error=True)`, allowing the same native interceptor path to own failure conversion.

## Risks / Trade-offs

- [Breaking prompt behavior for consumers that relied on eager bodies] → remove eager behavior atomically, document explicit activation, and run an impact scan across repository manifests/tests.
- [Pool catalog accidentally leaks hidden Skills through resource registry] → do not register the unfiltered catalog as a node-visible provider; register node views at agent/session scope and test every access path.
- [Skill activation error aborts a model request] → expose a structured, actionable diagnostic instead of silently choosing the wrong Skills; matcher authors must keep selections within the configured budget.
- [Existing tools return error-shaped dictionaries] → migrate AgentPool-owned tools that represent execution failure to the canonical result, while tests prove ordinary domain dictionaries remain successful.
- [Control-flow exceptions are misclassified] → preserve the explicit retry/defer/approval/cancel/skip exception list and add regression tests.

## Migration Plan

1. Add configuration, node views, activation state, and trace tests before changing the default injection branch.
2. Delete eager injection and hidden per-path scope decisions after the unified visibility tests pass.
3. Add canonical failure fields and native mapping, then migrate ACP/OpenCode/MCP adapters and owned error-returning tools.
4. Run focused unit/integration suites, strict OpenSpec validation, lint/type checks, and repository-wide searches for eager Skill assumptions or payload-shape failure inference.
5. Archive the completed OpenSpec change, syncing its delta specs.

Rollback is a source revert of the single commit. No eager compatibility mode or protocol guessing branch will be retained.
