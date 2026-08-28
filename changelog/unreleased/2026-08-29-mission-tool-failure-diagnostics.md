# Preserve mission tool failure diagnostics

Mission-scoped tool failure accounting now logs the exact Session, Agent, tool,
and bounded error result at the typed event boundary. This keeps recovered
structured-call failures diagnosable after short-lived child Sessions are
closed, without changing retry or terminal behavior.
