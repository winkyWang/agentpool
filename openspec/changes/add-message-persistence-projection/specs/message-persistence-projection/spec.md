## ADDED Requirements

### Requirement: Configurable persistence projection

The framework SHALL allow a native agent session to declare ordered message persistence processors independently from model history processors.

#### Scenario: No processor configured

- **WHEN** a session does not configure persistence processors
- **THEN** messages are persisted with the existing content unchanged

#### Scenario: Processor configured

- **WHEN** a session configures a persistence processor
- **THEN** the processor output is stored while the current event and model input remain unchanged

### Requirement: Safe multimodal reference projection

The framework SHALL provide a processor that removes binary bytes and file URLs from persisted message content while preserving safe media and identifier references.

#### Scenario: Binary attachment has identifier

- **WHEN** a `BinaryContent` item has an identifier
- **THEN** persisted content contains the identifier and media type but no original bytes

#### Scenario: File URL has no safe identifier

- **WHEN** persisted content contains an image, audio, video, or document URL
- **THEN** persisted content contains only its media category and type, not the URL

