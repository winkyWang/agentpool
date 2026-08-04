## ADDED Requirements

### Requirement: DCP uses the active model context window

The system SHALL compute Dynamic Context Pruning pressure using the active
native model configuration's declared `context_length`. The system SHALL
re-evaluate this value for every model request so a model change takes effect
without recreating the DCP capability.

#### Scenario: Declared model window overrides configured programmatic budget

- **GIVEN** DCP was constructed with `max_context_tokens=128000`
- **AND** the active model declares `context_length=1000000`
- **WHEN** DCP processes a model request
- **THEN** watermark pressure SHALL be calculated against `1000000`
- **AND** nudge text and telemetry SHALL report the same effective limit

#### Scenario: Programmatic agent has no declared model window

- **GIVEN** the active agent has no resolved model configuration
- **WHEN** DCP processes a model request
- **THEN** DCP SHALL use its explicitly configured `max_context_tokens`

### Requirement: prune permits two corrective retries

The DCP `prune` tool SHALL declare `max_retries=2`. This tool-specific value
SHALL NOT change retry counts for `distill`, `decompress`, or business tools.

#### Scenario: DCP toolset is constructed

- **WHEN** DCP exposes its context-management tools
- **THEN** the `prune` tool SHALL have `max_retries=2`
- **AND** `distill` and `decompress` SHALL continue to inherit the agent retry
  configuration
