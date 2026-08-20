## Why

The welding integration currently depends on several runtime guarantees that exist only on its
AgentPool 2.9.5 branch, while WolfHarness 4.0 has replaced the package layout and several related
subsystems. The guarantees must be forward-ported onto the current WolfHarness architecture so the
integration can upgrade without restoring deleted AgentPool paths, compatibility namespaces, or
welding-specific behavior in the framework.

## What Changes

- Resolve Dynamic Context Pruning pressure from the active model variant's declared context window,
  while retaining the explicit DCP budget for programmatic agents without model metadata and
  limiting corrective retries to the model-selected prune tool.
- Make Skill activation metadata-only by default, enforce one configured activation limit across
  matcher, always-active, and explicit loads, and preserve local Skill resource identity when
  resolving one-hop references.
- Add a typed failure flag to the canonical tool result/event path and propagate it through native,
  ACP, OpenCode, and MCP adapters without inspecting result payload shapes.
- Replace the fixed delegated-run event wait with a configurable inactivity timeout that can be
  disabled by deployments which rely on explicit cancellation.
- Filter invariant runtime output paths before OpenCode's project watcher logs or broadcasts them.
- Reuse WolfHarness 4.0's existing QuestionCapability, runtime-context resolver, SessionPool,
  SkillManagerCap, extension registry, and renamed package layout; do not restore superseded
  AgentPool implementations.

## Capabilities

### New Capabilities

- `model-aware-dcp-budget`: DCP uses the active model's declared context window consistently for
  pressure, nudges, pruning, and telemetry.
- `tool-failure-semantics`: Tool owners declare infrastructure failure through one typed outcome
  that protocol adapters propagate without payload guessing.
- `delegated-run-inactivity`: Delegated runs use a deployment-configurable event inactivity deadline
  instead of a fixed framework timeout.
- `opencode-runtime-watch-filtering`: The OpenCode project watcher excludes invariant runtime output
  before logging and event dispatch.

### Modified Capabilities

- `skill-manager-cap`: Skill disclosure, activation accounting, node visibility, and local reference
  resolution use one authoritative runtime policy.

## Impact

- WolfHarness native agent, DCP, SkillManagerCap, resource protocols, tool result/event conversion,
  SessionPool messaging, OpenCode watcher, ACP/OpenCode/MCP adapters, configuration, and tests.
- Welding integration configuration and imports will be migrated separately in the parent
  repository to consume the WolfHarness 4.x package names and contracts.
- No welding domain rules, workflow state, or project-specific tool implementation will be added to
  WolfHarness.
