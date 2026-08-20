## Context

See `proposal.md`. The retained welding branch is based on AgentPool 2.9.5, whereas the target is
WolfHarness 4.0. WolfHarness already provides the renamed package layout, ExtensionRegistry,
SkillManagerCap, QuestionCapability, typed runtime-context resolution, and current SessionPool. The
old branch contains generic fixes on top of the pre-rename architecture; several other commits are
superseded or cancel one another and must not be replayed wholesale.

## Goals / Non-Goals

**Goals:**

- Re-express still-missing runtime guarantees in current WolfHarness abstractions.
- Keep each behavior owned by one authoritative component and covered by unit/integration tests.
- Make the resulting fork suitable for an upstream pull request without welding-domain coupling.

**Non-Goals:**

- Restore `agentpool`, `agentpool_config`, `agentpool_server`, or `agentpool_toolsets` namespaces.
- Reintroduce the old question tools, legacy async subagent polling, or old Skill toolset.
- Add welding prompts, business rules, workflow state, or configuration defaults to WolfHarness.
- Merge the archived 2.9.5 branch into current `main`.

## Decisions

### 1. Forward-port behaviors, not commits

The archived commits are evidence of required behavior, not a patch series to replay. Each behavior
will be compared with current WolfHarness first. Existing 4.0 implementations remain unchanged when
they already satisfy the requirement; only demonstrated gaps receive code and regression tests.
Cherry-picking the old series was rejected because the package rename and capability refactors make
conflict resolution indistinguishable from recreating deleted architecture.

### 2. The active native model supplies the DCP window

The native agent will expose its resolved positive model context length. DCP will derive one
request-local immutable effective configuration before processing messages and use it throughout
that request. Its stored configuration remains the source only when model metadata is absent.
Combining both values with `min()` was rejected because it recreates two competing limits.

### 3. SkillManagerCap remains the single Skill authority

Current SkillManagerCap and ExtensionRegistry remain in place. Per-run activation state and traces
will live on the current run context rather than on the long-lived capability. Node visibility will
be resolved once from configuration and applied before every Skill projection. Local `SkillEntry`
paths will pass through URI resolution unchanged; remote virtual paths remain provider-owned. No
filesystem/provider fallback will be added.

### 4. Typed tool failure follows the current native event path

The canonical tool result gains a boolean failure signal. The native wrapper maps declared failure
and ordinary exceptions to Pydantic AI's failed tool outcome, and the event mapper publishes a typed
terminal failure field. ACP, OpenCode, and MCP consume only that field. Payload-key and metadata
guessing will be removed rather than retained as compatibility logic.

### 5. Delegated waits use a configurable inactivity interval

SessionPool configuration owns a positive seconds-or-null value. Each event arrival starts the next
wait, so the setting limits silence rather than wall-clock execution. Null delegates termination to
explicit cancellation. A separate global run timeout was rejected because it would terminate
productive long-running specialists.

### 6. Watch filtering occurs at the watch source

Invariant exclusions and configured patterns are assembled before the OpenCode watcher starts. A
path predicate is passed into the watcher so ignored runtime output is removed before both internal
logging and callbacks. Filtering only at frontend broadcast was rejected because it leaves the
self-generated watcher/log loop intact.

### 7. Parent-repository migration is a consumer change

After the framework branch passes its own checks, the parent iroot-llm branch will replace package
names and adapt manifests/tools to WolfHarness 4.0. This migration will not be implemented as alias
packages inside WolfHarness. Other parent packages must either migrate in the same commit series or
remain pinned to a separately addressable legacy dependency; the submodule pointer will not be
advanced while the parent repository is internally inconsistent.

## Risks / Trade-offs

- [Old behavior is already superseded semantically] → compare tests and current contracts before
  implementing; omit redundant patches and record the replacement in the migration summary.
- [Typed failure changes protocol output] → add native plus ACP/OpenCode/MCP regression tests and
  preserve successful business-negative results.
- [Node visibility accidentally hides required tools] → test metadata, list, load, reference,
  command, and tool projections for visible and hidden nodes.
- [Parent migration has broad import impact] → update consumers by package, run repository-wide
  import scans, and advance the submodule pointer only after affected tests pass.

## Migration Plan

1. Preserve the current 2.9.5 head on the personal fork's dated archive branch.
2. Implement and validate this OpenSpec change on a branch based on current upstream `main`.
3. Push the WolfHarness feature branch to the personal fork.
4. Migrate parent-repository consumers to canonical WolfHarness package and configuration names.
5. Run WolfHarness focused/full checks and parent welding plus affected integration tests.
6. Update `.gitmodules` to the canonical/fork strategy chosen for reproducible clones, commit the
   new submodule pointer, and push the parent feature branch.

Rollback keeps the parent repository pinned to archived commit `2209837` and does not rewrite either
branch history.
