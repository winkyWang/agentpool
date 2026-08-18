## MODIFIED Requirements

### Requirement: Node Skill visibility SHALL be many-to-many and authoritative

Configuration SHALL allow each node to name every Skill visible to that node,
and the same Skill MAY be visible to multiple nodes. The resolved visibility
policy SHALL apply consistently to Skill metadata, list results, explicit loads,
matcher candidates and injection, commands, Skill-owned tools, Skill bodies,
and one-hop reference resources. A node with an explicit visibility policy
SHALL NOT access a Skill or its references outside its allow-list. Local
references SHALL retain their filesystem identity through URI resolution;
remote references SHALL retain provider-owned virtual identity.

#### Scenario: Shared Skill is visible to multiple nodes

- **WHEN** the same Skill is listed for two nodes
- **THEN** both nodes SHALL discover and activate it independently

#### Scenario: Hidden Skill is absent from every access path

- **WHEN** a Skill is not visible to a node
- **THEN** that node SHALL NOT see it in metadata or list results
- **AND** explicit load, matcher injection, command execution, Skill tools, and
  resource reads SHALL NOT expose it

#### Scenario: Unknown configured Skill fails configuration

- **WHEN** a node visibility allow-list names a Skill that discovery did not
  resolve
- **THEN** pool initialization SHALL fail with a diagnostic naming the node and
  unknown Skill

#### Scenario: Visible local reference loads through its filesystem identity

- **WHEN** a visible local Skill is loaded by a `skill://.../references/...` URI
- **THEN** the resolver SHALL retain the entry's local path
- **AND** the reference SHALL be read from that Skill directory

#### Scenario: Hidden local reference remains inaccessible

- **WHEN** a node requests a reference owned by a Skill outside its allow-list
- **THEN** the reference content SHALL NOT be returned

#### Scenario: Remote reference retains provider ownership

- **WHEN** a remote Skill entry has no local path
- **THEN** URI resolution SHALL preserve its virtual provider identity
- **AND** reference loading SHALL remain provider-owned
