## 1. Runtime implementation

- [x] 1.1 Expose the active native-model context window.
- [x] 1.2 Resolve a request-local DCP configuration from that window.
- [x] 1.3 Use the effective budget for watermarks, nudges, and telemetry.
- [x] 1.4 Set `prune` tool `max_retries` to 2.

## 2. Verification

- [x] 2.1 Add a unit test for `prune`'s tool-specific retry count.
- [x] 2.2 Add an integration test proving the model context window overrides
      the configured programmatic budget.
- [x] 2.3 Run DCP tests, lint, and type checking.
