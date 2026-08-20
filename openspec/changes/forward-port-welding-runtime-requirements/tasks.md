## 1. Baseline and supersession audit

- [x] 1.1 Record which archived AgentPool commits are superseded by WolfHarness 4.0 capabilities
- [x] 1.2 Add failing focused tests for every retained generic runtime requirement

## 2. Model-aware DCP

- [x] 2.1 Expose the active native model context window through the current agent abstraction
- [x] 2.2 Use one request-local effective DCP configuration and scope retries to prune
- [x] 2.3 Pass DCP unit, integration, and model-variant tests

## 3. Skill runtime policy

- [x] 3.1 Add authoritative node visibility configuration and resolution
- [x] 3.2 Add per-run activation accounting, structured traces, and atomic max-skill enforcement
- [x] 3.3 Preserve local Skill paths through reference resolution without fallback lookup
- [x] 3.4 Pass Skill metadata, matcher, explicit-load, visibility, reference, command, and tool tests

## 4. Typed tool outcomes

- [x] 4.1 Add canonical tool-result and terminal-event failure fields
- [x] 4.2 Map native declared failures and ordinary exceptions to typed failed outcomes
- [x] 4.3 Update ACP, OpenCode, and MCP adapters to consume typed failure only
- [x] 4.4 Pass native and protocol tool-outcome regression tests

## 5. Delegated runtime and watcher stability

- [x] 5.1 Add configurable delegated-event inactivity waits and configuration tests
- [x] 5.2 Filter invariant and configured paths before OpenCode watcher logging and dispatch
- [x] 5.3 Pass SessionPool, OpenCode configuration, and file-watcher tests

## 6. Framework validation and publication

- [x] 6.1 Add the unreleased changelog entry and update affected documentation
- [x] 6.2 Run strict OpenSpec validation, Ruff, mypy, and the focused/full WolfHarness test suites
- [ ] 6.3 Archive the completed OpenSpec change and commit the framework implementation
- [ ] 6.4 Push the WolfHarness feature branch to the personal fork

## 7. Parent repository migration

- [ ] 7.1 Migrate affected parent packages from AgentPool 2.9.5 names to WolfHarness 4.x contracts
- [ ] 7.2 Run welding-agent and affected cross-package integration tests
- [ ] 7.3 Update `.gitmodules`, synchronize the submodule URL, and commit the new submodule pointer
- [ ] 7.4 Push the parent `feature/tasiawang/welding_agent` branch without merging its upstream base
