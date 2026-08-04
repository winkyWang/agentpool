## Why

Dynamic Context Pruning (DCP) currently computes context pressure against a
fixed `max_context_tokens` value. When an agent changes to a model with a
different declared context window, pruning can run far too early or after the
provider limit has already been exceeded. The DCP `prune` tool also inherits the
agent-wide retry count, so one invalid model-selected target can terminate an
otherwise valid business workflow.

## What Changes

- Resolve the DCP context budget from the active native agent model
  configuration on every model request.
- Retain `max_context_tokens` as the explicit budget for programmatic agents
  whose model configuration does not declare `context_length`.
- Use the resolved budget consistently for watermarks, nudges, and telemetry.
- Give only the DCP `prune` tool two corrective retries; other DCP and business
  tools continue to use their existing retry configuration.

## Capabilities

### New Capabilities

- `model-aware-dcp-budget`: DCP pressure follows the active model's declared
  context window and remains correct after model switching.

### Modified Capabilities

- DCP tool exposure assigns a tool-specific retry limit to `prune`.

## Impact

- `src/agentpool/agents/native_agent/agent.py`
- `src/agentpool/capabilities/dcp/capability.py`
- DCP unit and integration tests
- No protocol or external tool contract changes
