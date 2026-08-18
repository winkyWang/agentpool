# skill-manager-cap Specification

## Purpose

Define the unified capability that exposes Skill metadata, resources, commands,
owned tools, lifecycle, and progressive body activation.

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
