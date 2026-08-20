# tool-failure-semantics Specification

## Purpose
Provides one typed tool-outcome contract so agents and protocol frontends distinguish execution
failure from successful business-negative results without interpreting arbitrary payload content.

## Requirements

### Requirement: Canonical tool result declares failure
The canonical tool result SHALL expose a boolean failure field that defaults to false and remains
separate from content, structured content, and presentation metadata.

#### Scenario: Tool returns an ordinary result
- **WHEN** a tool returns content without declaring failure
- **THEN** the result SHALL be treated as a successful tool execution

#### Scenario: Tool owner declares failure
- **WHEN** a tool returns a canonical result with failure set to true
- **THEN** native execution SHALL expose a failed tool outcome to the model and event stream

### Requirement: Exceptions and business-negative results remain distinct
Ordinary tool exceptions SHALL become failed tool outcomes, while a valid domain result such as
"not found" or "not qualified" SHALL remain successful unless the tool owner declares failure.

#### Scenario: Tool raises an ordinary exception
- **WHEN** a tool raises an execution exception that is not a framework control-flow signal
- **THEN** the terminal tool event SHALL be marked failed

#### Scenario: Tool reports a valid negative domain decision
- **WHEN** a tool returns a structured negative business decision without declaring failure
- **THEN** the terminal tool event SHALL remain successful

### Requirement: Protocols consume typed failure only
Native events and ACP, OpenCode, and MCP adapters SHALL propagate the typed failure outcome and SHALL
NOT infer failure from dictionary keys, text, or optional presentation metadata.

#### Scenario: Failed outcome crosses a protocol adapter
- **WHEN** a typed failed tool outcome is converted for ACP, OpenCode, or MCP
- **THEN** the protocol-native terminal status SHALL be failed

#### Scenario: Successful payload contains an error-shaped key
- **WHEN** a successful tool result contains a domain field named `error`
- **THEN** protocol conversion SHALL preserve a successful terminal status
