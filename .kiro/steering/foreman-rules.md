# Ghost Foreman — Steering & Safety Rules (`.kiro/steering/foreman-rules.md`)

1. **No Unfounded Guessing**: Never invent specification changes when answering an agent's question. Auto-reply only when an active Policy or approved past Decision matches the project scope.
2. **Distinguish Questions from Tool Approvals**: Natural-language design questions are handled via slot messages; host tool execution requests go through `/api/approvals` and never bypass mandatory human security gates.
3. **One-Time vs. Permanent Memory**: Never promote a human's answer to a permanent Policy without explicit confirmation (`promote_to_policy = true`).
4. **Strict Project Isolation**: Never leak policies, batch answers, or context from one Project to another unless the Policy scope is explicitly `global`.
5. **Budget & Free-Tier Guard**: When a free-tier quota reaches 100%, switch to another permitted free/included backend or hold the task. Never switch to a paid per-token API without explicit user permission and remaining budget.
6. **Ping-Pong Prevention**: Reverse-probing an agent for missing impact details is capped at `max_probes = 1` per question ID.
7. **Honest Mode Labeling**: Always display whether a session or telemetry metric is `live_gateway`, `simulated_gateway`, `estimated`, or `unknown`.
