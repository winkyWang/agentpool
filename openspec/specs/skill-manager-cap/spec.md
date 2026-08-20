## Purpose

Define the canonical Skill management capability that aggregates local and remote Skills,
commands, toolsets, lifecycle behavior, and progressive instruction disclosure.

## Requirements

### Requirement: SkillManagerCap SHALL extend CombinedToolsetCapability

`SkillManagerCap` SHALL inherit from `CombinedToolsetCapability` to reuse `get_toolset()` (merge children), `on_change()` (merge streams), and `__aenter__`/`__aexit__` (lifecycle). It SHALL additionally implement `SkillResource`, `CommandResource`, and `ChangeObservable`.

#### Scenario: SkillManagerCap inherits tool merging
- **WHEN** `get_toolset()` is called on `SkillManagerCap`
- **THEN** it SHALL merge toolsets from all child capabilities (MCP servers declared by skills)
- **AND** tools from local skill Python functions SHALL be included

#### Scenario: SkillManagerCap inherits lifecycle management
- **WHEN** `SkillManagerCap.__aenter__()` is called
- **THEN** all child capabilities SHALL be entered
- **AND** when `__aexit__()` is called, all children SHALL be exited in reverse order

### Requirement: SkillManagerCap SHALL hold local skills as Skill objects directly

`SkillManagerCap` SHALL hold local skills as `dict[str, Skill]` (keyed by skill name), NOT wrapped in individual capability instances. This eliminates one layer of indirection.

#### Scenario: Local skill stored directly
- **WHEN** `SkillManagerCap(local_skills=[skill1, skill2])` is constructed
- **THEN** `self._local_skills` SHALL be `{"skill1": skill1, "skill2": skill2}`
- **AND** no `SkillCapability` instances SHALL be created

### Requirement: SkillManagerCap SHALL aggregate SkillResource from local and remote sources

`list_skills()` SHALL return skills from both local filesystem (`self._local_skills`) and remote MCP servers (child `McpServerCap` instances implementing `SkillResource`). `read_skill(uri)` SHALL route by URI: `skill://local/` to local skills, `skill://<mcp-server>/` to the corresponding `McpServerCap`.

#### Scenario: List skills from both local and remote
- **WHEN** `list_skills()` is called
- **AND** `SkillManagerCap` has 3 local skills and 2 child `McpServerCap` instances with skills
- **THEN** all 5 skills (3 local + 2 remote) SHALL be returned in a single list

#### Scenario: Read local skill
- **WHEN** `read_skill("skill://ponytail/SKILL.md")` is called
- **AND** "ponytail" is in `self._local_skills`
- **THEN** the skill content SHALL be read from the local filesystem

#### Scenario: Read remote skill from MCP
- **WHEN** `read_skill("skill://github-mcp/code-review")` is called
- **AND** "github-mcp" is a child `McpServerCap`
- **THEN** `McpServerCap.read_skill("skill://github-mcp/code-review")` SHALL be called

### Requirement: SkillManagerCap SHALL aggregate CommandResource

`list_commands()` SHALL return commands from local skills (each skill becomes a `CommandEntry` with `name=skill.name`, `description=skill.description`) and from child `McpServerCap` instances implementing `CommandResource`. `get_command(name, args)` SHALL route by name: local skills first, then remote.

#### Scenario: List commands from both local and remote
- **WHEN** `list_commands()` is called
- **AND** `SkillManagerCap` has 3 local skills and 1 child `McpServerCap` with 2 MCP prompts
- **THEN** 5 `CommandEntry` objects SHALL be returned (3 local + 2 remote)

#### Scenario: Local command takes precedence over remote
- **WHEN** `get_command("ponytail", [])` is called
- **AND** "ponytail" exists both as a local skill and as an MCP prompt
- **THEN** the local skill's content SHALL be returned
- **AND** the MCP prompt SHALL NOT be called

### Requirement: SkillManagerCap SHALL provide metadata-only instructions by default

`get_instructions()` SHALL return an `<available-skills>` XML block containing skill names and descriptions (~100 tokens per skill), NOT full skill instructions. This implements progressive disclosure: metadata at compilation, full instructions on demand.

#### Scenario: Metadata-only instructions
- **WHEN** `get_instructions()` is called
- **THEN** an XML block SHALL be returned with format `<available-skills><skill name="..." description="..."/>...</available-skills>`
- **AND** each skill SHALL contribute approximately 100 tokens or fewer

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

### Requirement: SkillManagerCap SHALL support per-skill always_active flag

Skills with `always_active: true` in their config SHALL bypass the `matcher_fn` and always have their full instructions injected, regardless of the matcher's selection.

#### Scenario: Always-active skill bypasses matcher
- **WHEN** `matcher_fn` selects only skill "A"
- **AND** skill "B" has `always_active: true`
- **THEN** both skill "A" and skill "B" instructions SHALL be injected

### Requirement: SkillManagerCap SHALL query child McpServerCap instances for remote skills

`SkillManagerCap` SHALL query child `McpServerCap` instances (via `self._children`) for `SkillResource` and `CommandResource` methods. This is an internal interface — child `McpServerCap` instances are NOT registered in `ExtensionRegistry` individually. The registry only sees `SkillManagerCap` as the single `SkillResource` + `CommandResource`.

#### Scenario: ExtensionRegistry sees only SkillManagerCap
- **WHEN** `ExtensionRegistry.get_skill_resources(scope)` is called
- **AND** the scope has a `SkillManagerCap` with 3 child `McpServerCap` instances
- **THEN** only `SkillManagerCap` SHALL be returned
- **AND** the 3 `McpServerCap` instances SHALL NOT be returned individually

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
