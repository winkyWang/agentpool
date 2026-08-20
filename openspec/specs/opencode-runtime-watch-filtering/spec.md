# opencode-runtime-watch-filtering Specification

## Purpose
Prevents OpenCode's project watcher from reacting to its own runtime output while preserving project
source notifications and deployment-provided ignore patterns.

## Requirements

### Requirement: Runtime exclusions are active at watcher startup
The project watcher SHALL combine invariant runtime exclusions with configured project exclusions
before monitoring begins, without depending on a later configuration endpoint request.

#### Scenario: Runtime logs change before a config request
- **WHEN** a file under the runtime log directory changes immediately after server startup
- **THEN** the watcher SHALL exclude that path

#### Scenario: Project adds custom exclusions
- **WHEN** project configuration declares additional watcher ignore patterns
- **THEN** those patterns SHALL be combined with, not replace, invariant exclusions

### Requirement: Ignored paths are filtered before output
Ignored paths SHALL be rejected before watcher logging, callback dispatch, or frontend event
broadcast.

#### Scenario: Ignored and source files change together
- **WHEN** one watch batch contains an ignored runtime file and an ordinary source file
- **THEN** only the source-file change SHALL reach logging, callbacks, and frontend events
