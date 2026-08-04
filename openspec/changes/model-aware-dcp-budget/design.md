## Context

DCP owns a configured context budget while the native agent owns the resolved
model configuration. The latter already carries the optional
`context_length` declared on a model variant, but DCP does not read it. This
creates two independent sources for the same runtime limit.

## Decisions

### Decision 1: The active model configuration is authoritative

The native agent exposes a read-only `model_context_window_tokens` property.
DCP reads it before every model request, so a model-mode change takes effect on
the next request without rebuilding the capability.

When no resolved model configuration exists, `max_context_tokens` remains the
explicit budget for programmatically constructed agents. It is not combined
with the model window and does not cap a declared model context.

### Decision 2: Reuse one effective DCP configuration per request

DCP creates an immutable Pydantic model copy whose `max_context_tokens` equals
the effective model window. Watermark calculation, prunable-list generation,
nudge text, and telemetry all consume that same request-local configuration.
The stored capability configuration is never mutated.

### Decision 3: Retry only prune

`Tool(..., max_retries=2)` is applied to `prune`. `distill` and `decompress`
continue inheriting the agent default. This avoids broad retries of business
tools and gives the model one additional correction opportunity for DCP's
model-selected numeric targets.

## Risks

- A programmatic agent without a resolved model configuration cannot be
  model-adaptive. Its explicit DCP budget remains required and is logged.
- Declared model metadata can be wrong. Configuration validation ensures only
  that the value is positive; deployment owners remain responsible for using
  provider-published limits.
