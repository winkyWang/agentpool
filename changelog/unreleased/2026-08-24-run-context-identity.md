# Keep Run and tool-context identities aligned

Session-managed execution now uses the `AgentRunContext` run identifier as the
single identifier for the corresponding `RunHandle` and Session registration.
This fixes identity-sensitive tools incorrectly rejecting their active Run
because the orchestration layer previously generated two different identifiers
for one execution.
