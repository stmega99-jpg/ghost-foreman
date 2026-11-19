# Ghost Foreman — Requirements

> **How to read this file (honest note).** These requirements were written down on **2026-11-19**, after PRs #1–#14 were merged, from the full plan (`Ghost_Foreman_企画書_v2.md`), the pull-request history and the tests. The project did **not** start from this file: it started from the plan and a 20-line spec (kept as `../ghost-foreman.md`). Each requirement carries the status it has today (**Live**, **Partial**, **Simulated**, **Not implemented**), taken from the plan's "implementation status" table and from the tests. Nothing here claims more than that.

## Glossary

- **Ghost / foreman**: the app's agent that answers other AI agents' questions on the human's behalf, within rules the human set.
- **Slot**: one AI agent session managed through Kiro Crew.
- **Policy**: a rule the human chose to keep. **One-time answer**: an answer that is not kept.
- **Live**: confirmed on a real Kiro Crew Gateway. **Simulated**: sample data only, no real AI.
- **Outside Kiro Crew**: an AI started directly by this app (Claude Code, Codex, Gemini API) because Kiro Crew 0.12.2 gives an app no way to choose a slot's backend. Used for meetings only.

## R1. Answer an AI's question on the human's behalf (plan A) — Live

**User story.** As a creator who is away from the PC, I want routine questions from my AI agents answered from rules I already set, so that work does not stop.

1. WHEN an agent asks a question through the `foreman_ask` MCP tool or a question endpoint, THE APP SHALL record it with its project and slot.
2. WHEN an active policy or an earlier approved decision for the same project matches, THE APP SHALL answer using it, cite the policy id, and write the answer to the decision log.
3. IF nothing matches, THEN THE APP SHALL NOT invent an answer. It SHALL ask the asking agent once for the missing impact details (reverse probe, `max_probes = 1` per question), then show the human structured options with a recommendation.
4. IF a proposal would change the specification, THEN THE APP SHALL hold it for the human instead of answering.
5. IF the judging AI is unavailable, THEN THE APP SHALL hold the question for the human.
6. Tool-execution approvals (`/api/approvals`) SHALL stay with the human. Only the app's own `foreman_*` tools are auto-approved.
- *Not implemented:* detecting conflicts between two AIs' opinions (a meeting summary lists points of disagreement only).

## R2. Remember selectively (plan E) — Partial

1. WHEN the human answers, THE APP SHALL treat the answer as one-time unless the human explicitly chooses to keep it (`memory_mode = permanent_policy`).
2. WHEN a policy is kept, THE APP SHALL store its scope (all projects or one project) and version, and SHALL NOT use a project's policy or batch answer in another project unless its scope is global.
3. WHEN the human asks, THE APP SHALL apply one answer to similar open questions of the same project.
- *Not implemented:* editing or withdrawing a policy in the screen, conflict checks between policies, handover documents.

## R3. Emergency stop that only a human can lift (plan: emergency stop) — Live

1. WHEN the human presses stop (all, one project, or one slot), THE APP SHALL stop the real sessions and hold new work before anything else happens.
2. WHILE a stop is in force, THE APP SHALL NOT auto-answer, auto-order, resume or auto-approve. Questions that arrive SHALL be held.
3. WHEN the human lifts a stop, THE APP SHALL NOT restart the stopped work by itself. Held questions become waiting-for-human questions.
4. Only an explicit human request SHALL lift a stop; no agent or timer SHALL do so.
5. WHEN an AI was started outside Kiro Crew, THE APP SHALL end it and all its child processes (Windows Job Objects).

## R4. AI meeting room (plan D) — Partial

1. WHEN the human starts a meeting, THE APP SHALL first send each chosen AI a participation check. IF any cannot answer, THEN THE APP SHALL NOT start and SHALL say why.
2. THE APP SHALL run: independent ideas → mutual critique → a summary by an organiser who did not take part → options for the human.
3. THE APP SHALL NOT turn a meeting into work until the human adopts an option; "save as idea only" SHALL always be offered.
4. WHEN Gemini takes part, THE APP SHALL require a per-meeting permission (the literal `true`) to send the meeting's text to the Gemini free tier. Without it, THE APP SHALL refuse before anything is created or sent. The permission SHALL end with the meeting and SHALL NOT change the global switch.
5. Before every request to the Gemini API, THE APP SHALL check for a stop. IF Gemini cannot answer, THEN no other AI SHALL answer in its place.
6. THE APP SHALL record, for each participant, which AI really ran, where (inside or outside Kiro Crew), and the model, and SHALL flag a self-introduction that does not match.
7. WHEN the screen language is English, THE APP SHALL ask the AIs to answer in English while keeping the program's JSON keys.
- *Not implemented:* joining late, swapping participants, pausing and resuming, per-meeting time and cost limits.

## R5. Free-tier guard (plan C) — Partial

1. THE APP SHALL have no code path to a pay-per-use API. WHEN the Gemini free tier is exhausted, THE APP SHALL wait or use another included backend, never a paid one.
2. THE APP SHALL record every call, and SHALL show billing as "unconfirmed" (never "0 dollars").
3. THE APP SHALL NOT send unpublished project text to the free tier unless the human allowed it (globally, or for one meeting).
- *Not implemented:* daily/weekly/monthly totals, reserved amounts, a reservation to resume when the quota recovers.

## R6. Notifications and remote use (plan F) — Partial

1. THE APP SHALL support the modes at home / away / sleep and Kiro Crew's push notifications.
2. THE APP SHALL provide its own phone page (Home Screen app) reachable through Tailscale Serve (private tailnet, not the public internet), that signs in again by itself while its refresh cookie is valid.
- *Not confirmed:* a push notification actually reaching a real iPhone. The browser-driven phone test passes.

## R7. News (plan I) — Partial

1. WHEN the human gives a public URL, THE APP SHALL summarise it with facts and estimates kept apart, and SHALL refuse internal addresses.
- *Not implemented:* scheduled collection by field of interest.

## R8. Simple screen, in Japanese and English — Live

1. THE SCREEN SHALL start with "What would you like to do?" and keep technical items under "Details & settings".
2. THE SCREEN SHALL work in Japanese and English on the PC and on the phone, remember the choice, and default to the browser's language.
3. Text written by an AI or a person SHALL stay as written. Fixed labels from the backend SHALL be shown in the chosen language.

## R9. Honest labelling — Live

1. THE APP SHALL show whether a session or figure is `live_gateway`, `simulated_gateway`, `estimated` or `unknown`.
2. THE APP SHALL NOT show simulated or unimplemented features as working.

## R10. Public demo that cannot reach anything — Live (this repository)

1. THE DEMO SHALL run the same screen on built-in sample data, labelled as a sample.
2. THE DEMO SHALL NOT be able to open any connection (Content-Security-Policy `connect-src 'none'`) and SHALL NOT contain a path to an AI contract, an API key, or the owner's PC.
3. THE DEMO SHALL keep the app's rules: a stop is lifted only by a person; Gemini needs the per-meeting permission; a one-time answer is not kept.

## Out of scope (stated, not hidden)

- **G. Deliverable review**: left to Kiro Crew and Git.
- **H. PC operation lease**: records state only. Simulated; no screen, mouse or keyboard control.
- **J. Voice control**: not implemented.
