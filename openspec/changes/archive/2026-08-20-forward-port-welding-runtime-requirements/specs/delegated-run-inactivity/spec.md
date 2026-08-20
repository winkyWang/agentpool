## Purpose

Allows deployments to govern how long a delegated run may remain silent without imposing a fixed
framework deadline on long-running specialist-agent work.

## ADDED Requirements

### Requirement: Delegated event inactivity deadline is configurable
The session-pool configuration SHALL accept a positive inactivity timeout in seconds or null, and
the configured value SHALL govern waits for the next delegated-agent event.

#### Scenario: Deployment configures a longer deadline
- **WHEN** a deployment configures a delegated-run inactivity timeout
- **THEN** the event wait SHALL use that timeout instead of a fixed framework constant

#### Scenario: Deployment disables the deadline
- **WHEN** the configured delegated-run inactivity timeout is null
- **THEN** the event wait SHALL continue until an event or explicit cancellation occurs

### Requirement: Deadline measures silence rather than total duration
Receiving an event SHALL restart the inactivity wait so a productive delegated run is not rejected
solely because its total duration exceeds one inactivity interval.

#### Scenario: Long delegated run continues to emit events
- **WHEN** a delegated run exceeds the configured interval in total duration but emits each event
  before the current inactivity wait expires
- **THEN** the run SHALL continue

#### Scenario: Delegated run stops emitting events
- **WHEN** no event arrives before the configured inactivity deadline
- **THEN** the wait SHALL fail with a diagnostic containing the session and configured deadline
