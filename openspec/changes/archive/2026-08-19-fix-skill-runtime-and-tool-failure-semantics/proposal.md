## Why

AgentPool currently advertises progressive Skill disclosure but injects every Skill body when no matcher is configured, ignores `max_skills`, and applies package scope only to selected load/list paths. Tool failures have a similar split-brain contract: successful and failed results share the same untyped payload, while protocol adapters infer failure from dictionaries or metadata.

## What Changes

- **BREAKING**: make Skill discovery metadata-only by default; full instructions enter a run only through an explicit load, matcher selection, or declared always-active Skill.
- **BREAKING**: enforce `max_skills` across matcher, always-active, and explicit activation paths and raise a structured diagnostic instead of truncating or eagerly injecting Skills.
- Add node-to-Skill many-to-many visibility and apply one policy to metadata, list, load, matcher injection, commands, and Skill-owned tools.
- Emit structured Skill exposure and activation trace records for runtime evaluation.
- Add `is_error` to the canonical AgentPool `ToolResult` and propagate failure through native execution, `ToolCallCompleteEvent`, ACP, OpenCode, and MCP.
- Mark ordinary tool exceptions as failed while keeping declared business-negative results successful.
- Remove protocol-side payload-shape and `error`-key guessing.

## Capabilities

### New Capabilities
- `tool-failure-semantics`: Defines the canonical tool outcome contract and its protocol propagation.

### Modified Capabilities
- `skill-manager-cap`: Changes Skill disclosure, activation limits, node visibility, and observability requirements.

## Impact

- Skill configuration and runtime: `agentpool_config.skills`, `AgentPool`, `SkillManagerCap`, `SkillsTools`, Skill URI/resource exposure, and native agent capability assembly.
- Tool execution and events: canonical `ToolResult`, native interceptor, `EventMapper`, ACP-agent conversion, ACP server conversion, OpenCode event processing, and MCP client/server bridges.
- Existing configurations that depended on implicit eager Skill bodies must use explicit activation, matching, or `always_active`.
- Existing tools that intend to report execution failure must return `ToolResult(is_error=True)` or raise; ordinary values such as “not found” domain results remain successful unless the tool owner declares failure.
