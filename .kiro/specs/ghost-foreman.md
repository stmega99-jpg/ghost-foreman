# Ghost Foreman — Kiro Spec (`.kiro/specs/ghost-foreman.md`)

## 1. Overview
Ghost Foreman is an installable Kiro Crew App (`app.json`) built for **Kiroween 2026 (Frankenstein Category & Best Kiro Crew App Bonus Prize)**.
Full specification: see `Ghost_Foreman_企画書_v2.md`.

## 2. Implementation & Real-Device Verification Order (No Mock-Only Completion!)
Do NOT treat mock or dummy data tests as implementation completion. Proceed in this exact order:
1. **Kiro Crew Host Setup & App Registration**: Start Kiro Crew Gateway, register and enable `ghost-foreman` in `~/.kiro/crew/apps/ghost-foreman` (including `sessionApproval` owner consent in dashboard), and verify `/apps/ghost-foreman` and `/api/apps/ghost-foreman/dashboard` over HTTP.
2. **Real Session Connection (Claude Code / Codex / Kiro)**: Connect to real agent sessions via Ghost Foreman Managed Worker Slots (`kiro_crew.apps.worker_slots`) and MCP consultation tools (`foreman_ask`).
3. **Real Proxy Answers & Reverse-Probing**: Verify with live agent questions that (a) policy-covered questions are auto-answered with citations and resume the session, and (b) unknown questions trigger a reverse-probe to the asking agent first, then escalate structured options to the human.
4. **iPhone Notification & Remote Reply**: Verify mobile push notification (iOS PWA / Kiro Crew remote channel) and remote reply / follow-up inquiry from iPhone resuming the live session.
5. **Live Gemini Free-Tier API Integration**: Connect real `GEMINI_API_KEY` (free tier) for Ghost Foreman's triage, reverse-probing, and summarization, and verify quota-exhaustion failover without unauthorized paid API charges.
6. **Live Multi-Agent Brainstorming (No Dummy Data)**: Run real multi-agent inference for `Independent Ideation -> Mutual Critique -> Ghost Synthesis`, and schedule only human-adopted proposals onto worker slots.

## 3. Kiro Crew 0.12.2 Technical Requirements
- **`backend.hooks.routes` (`RouteRegistry`)**: `register_routes(ctx: AppContext)` MUST return a `list` of route objects (`method`, `path` relative to `/api/apps/ghost-foreman`, `handler(request, ctx)`).
- **`backend.hooks.on_startup` / `on_shutdown`**: Must accept `ctx: AppContext` (`async def on_startup(ctx: AppContext) -> None`). Use `ctx.data_dir`, `ctx.events`, `ctx.spawn`, `ctx.storage`, and `ctx.http_app["state"]`.
- **Frontend Bundle Path**: `ui.entry` (`"dist/index.mjs"`) resolves relative to `<app_root>/ui/`, i.e. `<app_root>/ui/dist/index.mjs`.
- **Managed Worker Slots & Permissions**: Use `set_worker_slot_limit("ghost-foreman", 20)` and `acquire_worker_slot(state, "ghost-foreman", key, project=..., agent=..., model=...)`. Declare `"spawn": true` and `"sessionApproval": true` in `app.json`.
