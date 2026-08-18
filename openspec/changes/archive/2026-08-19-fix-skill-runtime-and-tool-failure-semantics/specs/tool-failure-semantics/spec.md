## Purpose

Provide one explicit, provider-independent tool outcome contract so execution failures reach every AgentPool protocol without interpreting business payload shapes.

## ADDED Requirements

### Requirement: Tool results SHALL declare execution failure explicitly

The canonical tool result SHALL include an `is_error` boolean that defaults to false. A tool SHALL set it to true only when execution failed. A successful domain result, including an empty result, rejected business condition, or payload containing an `error` field as domain data, SHALL remain successful unless the tool explicitly marks failure.

#### Scenario: Declared tool failure
- **WHEN** a tool returns a result with `is_error=true`
- **THEN** AgentPool SHALL record the tool call as failed
- **AND** the result content SHALL remain available to the model and clients

#### Scenario: Business-negative result remains successful
- **WHEN** a tool returns a normal result describing “not found”, “no matches”, or another business-negative outcome
- **AND** `is_error` is false
- **THEN** AgentPool SHALL record the tool call as completed successfully

#### Scenario: Domain payload contains an error key
- **WHEN** a successful tool payload contains a field named `error`
- **AND** `is_error` is false
- **THEN** no protocol adapter SHALL reinterpret that payload as execution failure

### Requirement: Ordinary exceptions SHALL become failed tool outcomes

An ordinary exception raised during tool execution SHALL be converted into a terminal failed tool outcome visible to the model. Framework control-flow exceptions for retry, deferral, approval, cancellation, and deliberate skip SHALL retain their native semantics and SHALL NOT be reclassified as ordinary failures.

#### Scenario: Tool raises ordinary exception
- **WHEN** tool execution raises an ordinary exception
- **THEN** the model SHALL receive a failed tool result containing the failure message
- **AND** downstream completion events SHALL identify the call as failed

#### Scenario: Control-flow exception is preserved
- **WHEN** tool execution raises a retry, deferral, approval, cancellation, or skip signal
- **THEN** AgentPool SHALL preserve that signal instead of converting it to a failed result

### Requirement: Tool failure SHALL propagate across protocols

The native event stream SHALL carry a first-class failure flag on tool completion. ACP, OpenCode, and MCP adapters SHALL derive their protocol status exclusively from that flag or the source protocol's native status. Protocol adapters SHALL NOT inspect result strings, JSON shapes, or keys to infer failure.

#### Scenario: Failed native tool reaches ACP
- **WHEN** a native tool completion is marked failed
- **THEN** ACP SHALL emit tool status `failed`

#### Scenario: Failed native tool reaches OpenCode
- **WHEN** a native tool completion is marked failed
- **THEN** OpenCode SHALL emit an error tool state using the tool result as the error message

#### Scenario: Failed AgentPool tool reaches MCP
- **WHEN** an AgentPool tool result has `is_error=true`
- **THEN** the MCP call result SHALL set the protocol-native error flag

#### Scenario: Failed ACP tool reaches AgentPool
- **WHEN** an ACP agent reports tool status `failed`
- **THEN** AgentPool SHALL emit a completed tool event with its first-class failure flag set
