## MODIFIED Requirements

### Requirement: SkillManagerCap SHALL support optional matcher_fn for dynamic skill injection

Skill instruction disclosure SHALL be metadata-only by default. Matcher mode SHALL inject full
instructions only for matcher-selected and declared always-active Skills. Full eager injection of
all visible Skills SHALL occur only when the deployment explicitly selects all-injection mode; the
absence of a matcher SHALL NOT enable eager injection.

#### Scenario: Dynamic skill injection with matcher
- **WHEN** matcher mode is configured with a matcher
- **AND** a model request is prepared
- **THEN** the matcher SHALL select relevant visible Skills
- **AND** only selected and always-active Skill bodies SHALL be injected

#### Scenario: All skills injected without matcher (backward compat)
- **WHEN** matcher mode is configured without a matcher
- **THEN** the legacy eager-injection behavior SHALL NOT apply
- **AND** the request SHALL retain metadata-only disclosure
- **AND** no Skill body SHALL be injected implicitly

#### Scenario: All-injection is explicitly selected
- **WHEN** all-injection mode is explicitly configured
- **THEN** every visible Skill body SHALL be injected

## ADDED Requirements

### Requirement: Skill activation limit is authoritative
Matcher selection, always-active Skills, and explicit Skill loads SHALL share one per-run set of
activated Skill names and SHALL enforce the configured maximum against their distinct union.

#### Scenario: Activation remains within the limit
- **WHEN** a matcher or explicit load activates Skills whose distinct union is within the maximum
- **THEN** each Skill SHALL be activated once for the current run

#### Scenario: Activation would exceed the limit
- **WHEN** a matcher, always-active declaration, or explicit load would exceed the maximum
- **THEN** activation SHALL fail with a structured diagnostic naming the limit and requested Skills
- **AND** the manager SHALL NOT truncate the selection or partially mutate activation state

### Requirement: Node visibility governs every Skill access path
One resolved node-to-Skill visibility policy SHALL govern metadata, listing, matcher selection,
explicit loading, commands, reference reads, and Skill-owned tools.

#### Scenario: Skill is hidden from a node
- **WHEN** a node requests a Skill excluded by its visibility policy
- **THEN** the Skill SHALL be absent from metadata, listing, commands, loading, references, and tools

#### Scenario: Shared Skill is visible to multiple nodes
- **WHEN** the visibility policy assigns one Skill to multiple nodes
- **THEN** each assigned node SHALL access the same authoritative Skill without duplicating it

### Requirement: Local Skill reference identity is preserved
A listed local Skill's authoritative filesystem path SHALL be retained when resolving one-hop
references, while remote entries without a local path SHALL retain their provider-owned virtual
identity.

#### Scenario: Visible local Skill loads a reference
- **WHEN** a visible local Skill loads `skill://<name>/references/<file>`
- **THEN** the reference SHALL be read beneath that Skill's authoritative local directory
- **AND** the manager SHALL NOT probe remote providers as a fallback

#### Scenario: Remote Skill loads a reference
- **WHEN** a remote Skill entry has no local filesystem path
- **THEN** its reference SHALL be resolved by the owning provider

### Requirement: Skill activation is observable
Skill exposure and activation SHALL produce structured per-run trace records containing visible and
activated Skill names and the activation source.

#### Scenario: Skill is explicitly loaded
- **WHEN** a model explicitly loads a visible Skill
- **THEN** the run trace SHALL identify that Skill and `explicit` as the activation source

#### Scenario: Reference-only read occurs
- **WHEN** an already-visible Skill reference is read without loading the Skill body
- **THEN** the reference read SHALL NOT consume an additional Skill activation
