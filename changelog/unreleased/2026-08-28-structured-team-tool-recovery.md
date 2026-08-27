# Structured Team preserves model tool correction

- Structured Team execution now waits for typed Artifact completion or a real Run terminal
  event instead of treating an intermediate failed tool call as a terminal member failure.
- Mission tool-failure accounting now observes emitted `ToolCallCompleteEvent` instances in
  `RunHandle`, covering argument validation retries without double-counting handler failures.
- A member that exhausts its correction opportunity and ends without typed completion still
  produces a deterministic technical failure.
