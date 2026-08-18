## 1. Skill Runtime Contract

- [x] 1.1 Add typed node-to-Skill visibility configuration and resolve/validate one visibility policy after discovery
- [x] 1.2 Build node-specific `SkillManagerCap` views and apply visibility to metadata, resources, commands, owned tools, matcher candidates, and agent injection
- [x] 1.3 Make no-matcher behavior metadata-only and enforce one per-run activation limit across matcher, always-active, and explicit load paths
- [x] 1.4 Add structured Skill exposure/activation trace records and EventBus publication
- [x] 1.5 Add unit and integration tests for metadata-only behavior, non-truncating limits, many-to-many isolation, explicit activation, and trace output

## 2. Tool Failure Contract

- [x] 2.1 Add `is_error` to the canonical `ToolResult`, remove the duplicate result model, and migrate AgentPool-owned failed-result call sites
- [x] 2.2 Convert declared failures and ordinary exceptions to native failed outcomes while preserving framework control-flow exceptions
- [x] 2.3 Add first-class failure to tool completion events and propagate ACP-agent, ACP server, OpenCode, MCP client, and MCP server mappings without payload guessing
- [x] 2.4 Add unit and integration tests for exception, declared-failure, business-negative, domain `error` key, and bidirectional protocol propagation cases

## 3. Validation and Delivery

- [x] 3.1 Run focused Skill and tool/protocol test suites, lint, type checks, and strict OpenSpec validation
- [x] 3.2 Scan repository consumers for eager Skill assumptions and error-key inference, document impact, and update the change tasks as complete
- [x] 3.3 Archive and sync the completed OpenSpec change, then commit only AgentPool submodule files
