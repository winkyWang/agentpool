## MODIFIED Requirements

### Requirement: SkillManagerCap SHALL support optional matcher_fn for dynamic skill injection

When `matcher_fn` is provided, `SkillManagerCap` SHALL call it for each model request and inject full instructions for matched, visible Skills only. When `matcher_fn` is absent, no Skill body SHALL be injected implicitly; only metadata SHALL be exposed until a Skill is explicitly loaded. Skills declared always-active count as explicit configuration and SHALL be activated subject to the same visibility and activation limit.

#### Scenario: Dynamic skill injection with matcher
- **WHEN** a matcher selects one visible Skill
- **THEN** only that Skill's full instructions SHALL be injected
- **AND** all other visible Skills SHALL remain metadata-only

#### Scenario: Metadata-only behavior without matcher
- **WHEN** no matcher is configured
- **AND** no Skill is declared always-active
- **THEN** no Skill body SHALL be injected into the model request
- **AND** visible Skill names and descriptions SHALL remain discoverable

#### Scenario: Always-active Skill follows the same contract
- **WHEN** a visible Skill is declared always-active
- **THEN** its full instructions SHALL be activated
- **AND** it SHALL count toward the activation limit

## ADDED Requirements

### Requirement: Skill activation limit SHALL be enforced uniformly

The configured maximum SHALL limit distinct Skill bodies activated in one run across matcher, always-active, and explicit load paths. Re-activating the same Skill SHALL be idempotent. Exceeding the maximum SHALL fail with a structured diagnostic naming the limit, already-active Skills, and requested Skills; the runtime SHALL NOT silently truncate or select an arbitrary subset.

#### Scenario: Matcher exceeds the limit
- **WHEN** a matcher requests more distinct visible Skills than the configured maximum
- **THEN** activation SHALL fail with a structured limit diagnostic
- **AND** no arbitrary subset SHALL be injected

#### Scenario: Explicit load exceeds the remaining limit
- **WHEN** explicit loads have already activated the configured maximum
- **AND** another distinct Skill body is requested
- **THEN** the load SHALL fail with the same structured limit diagnostic

#### Scenario: Repeated activation is idempotent
- **WHEN** an already-active Skill is selected or loaded again
- **THEN** it SHALL NOT consume another activation slot

### Requirement: Node Skill visibility SHALL be many-to-many and authoritative

Configuration SHALL allow each node to name every Skill visible to that node, and the same Skill MAY be visible to multiple nodes. The resolved visibility policy SHALL apply consistently to Skill metadata, list results, explicit loads, matcher candidates and injection, commands, Skill-owned tools, and Skill resources. A node with an explicit visibility policy SHALL NOT access a Skill outside its allow-list.

#### Scenario: Shared Skill is visible to multiple nodes
- **WHEN** the same Skill is listed for two nodes
- **THEN** both nodes SHALL discover and activate it independently

#### Scenario: Hidden Skill is absent from every access path
- **WHEN** a Skill is not visible to a node
- **THEN** that node SHALL NOT see it in metadata or list results
- **AND** explicit load, matcher injection, command execution, Skill tools, and resource reads SHALL NOT expose it

#### Scenario: Unknown configured Skill fails configuration
- **WHEN** a node visibility allow-list names a Skill that discovery did not resolve
- **THEN** pool initialization SHALL fail with a diagnostic naming the node and unknown Skill

### Requirement: Skill exposure and activation SHALL be traceable

Every model request SHALL record a structured Skill trace containing the node, run/session identity, visible Skill names, activated Skill names, and activation source. Explicit loads SHALL produce activation records even when no matcher is configured. Trace data SHALL be available without parsing prompts or tool result text.

#### Scenario: Metadata-only request produces exposure trace
- **WHEN** a model request exposes Skill metadata and activates no body
- **THEN** a structured trace SHALL list visible Skills and an empty activation set

#### Scenario: Explicit load produces activation trace
- **WHEN** a node explicitly loads a visible Skill body
- **THEN** a structured trace SHALL identify that Skill and the explicit-load source
