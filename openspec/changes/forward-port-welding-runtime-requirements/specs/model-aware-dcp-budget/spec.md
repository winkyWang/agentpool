## Purpose

Keeps Dynamic Context Pruning pressure and corrective actions aligned with the context window of
the model that is actually serving the current native-agent request.

## ADDED Requirements

### Requirement: Active model context window is authoritative
Dynamic Context Pruning SHALL resolve its token budget from the active model variant's declared
positive context window before every model request.

#### Scenario: Model variant declares a context window
- **WHEN** a native agent request uses a model variant with a declared context window
- **THEN** Dynamic Context Pruning SHALL use that declared window as the request budget
- **AND** a model switch SHALL take effect on the next request without rebuilding the capability

### Requirement: Explicit budget remains authoritative without model metadata
Dynamic Context Pruning SHALL retain its explicitly configured maximum context tokens when the
active agent does not expose a declared model context window.

#### Scenario: Programmatic agent has no declared window
- **WHEN** Dynamic Context Pruning runs for an agent without declared model context metadata
- **THEN** it SHALL use the explicitly configured maximum context tokens
- **AND** it SHALL NOT infer or silently substitute a second budget

### Requirement: One effective budget governs each request
Watermarks, pressure percentages, pruning decisions, nudges, prunable-list generation, and telemetry
for one request SHALL all use the same resolved context budget.

#### Scenario: Request reaches a pruning watermark
- **WHEN** the resolved request budget produces an information, warning, or critical watermark
- **THEN** every pruning decision and diagnostic for that request SHALL report and use that budget

### Requirement: Corrective retry is scoped to prune
The model-selected prune operation SHALL receive two corrective retries for invalid targets, while
other Dynamic Context Pruning tools and ordinary business tools SHALL retain their own retry policy.

#### Scenario: Prune target is invalid
- **WHEN** the model supplies an invalid target to the prune operation
- **THEN** that operation SHALL permit up to two corrective retries
- **AND** no agent-wide retry increase SHALL be applied to unrelated tools
