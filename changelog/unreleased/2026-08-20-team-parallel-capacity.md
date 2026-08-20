# Enforce Dynamic Team parallel capacity

Dynamic Team now enforces `max_parallel_members` for non-lead Session runs. The Team creation limit is persisted as the single capacity fact; Team-managed member activation uses file-locked pending-reservation tokens, reconciles stale slots against SessionPool, releases capacity across completion and cleanup paths, and reports active capacity in `team_status`. Standalone member-eligible Sessions no longer receive Team tools, and invalid initial roster identities are rejected before side effects.

Standalone sessions for member-eligible agents no longer expose Team instructions or tools. Lead sessions expose only `team_create` until a Team exists.
