# How Kiro was used to build Ghost Foreman

Ghost Foreman is a Kiro Crew app, and most of it was written by Kiro working in Kiro IDE while the owner (a non-programmer, working in Japanese) directed it. This page says what was used and, just as important, what was **not**.

## 1. Kiro as the builder ("vibe coding")

- The owner described goals in plain Japanese ("make it usable by someone who is not an engineer", "add a Japanese/English switch", "the demo must not touch my real AI contracts or my PC"). Kiro read the plan (`Ghost_Foreman_企画書_v2.md`), proposed an approach, wrote code and tests, ran them, and reported back in Japanese.
- Work went **one pull request at a time (#1–#14 merged as of 2026-11-19)**. For each one Kiro ran the tests, and where possible checked the result on the real Kiro Crew Gateway and in real Chrome (PC and phone widths) before asking the owner to approve a merge. **Kiro never merged or deployed on its own.** The owner approved each merge and each deploy (database backup → app update → `kirocrew restart`).
- Problems found by Kiro's own testing, or reported by the owner, were fixed in later pull requests, for example: a Gemini retry that could continue after an emergency stop (PR #8), a Gemini answer that called itself Claude (PR #9), edits lost when a settings panel was closed (PR #10), a dashboard error caused by a missing API declaration (PR #11), README claims that were larger than the code (PR #12), and Japanese text left in English meeting minutes (PR #14, found by running a real four-AI meeting in English).

## 2. Kiro Crew as the host (what the app is built on)

| Kiro Crew feature | How Ghost Foreman uses it | Where |
|---|---|---|
| App package (`app.json`) | Routes, agents, skill, MCP server, notification channels, permissions (`spawn`, `sessionApproval`, own API path) | `app.json` |
| Worker slots | Real agent sessions the foreman watches, stops and talks to | `backend/live_gateway.py`, `crew_adapter.py` |
| MCP server | Agents ask the foreman with `foreman_ask`, report with `foreman_report_status`, read rules with `foreman_get_policies` | `backend/mcp_server.py` |
| Custom agents | `ghost-foreman-supervisor` (the foreman) and `meeting-participant` (a Kiro participant with no tools, by design) | `agents/*.json` |
| Skill | `foreman-protocol`: tells agents when and how to consult the foreman | `skills/foreman-protocol/SKILL.md` |
| Steering | Seven safety rules, loaded into every Kiro session that works on this repo | `.kiro/steering/foreman-rules.md` |
| Push notifications and modes | "Decision needed" and "morning digest" channels | `backend/notifier.py` |
| Gateway auth, vault, Tailscale Serve | Access token, the Gemini key kept in the vault, private phone access | README §6 |
| Docs MCP tools | The Kiro participant may use `search_docs` and `find_capabilities` only | `agents/meeting-participant.json` |

## 3. Steering that is enforced, not just written

The seven rules in `.kiro/steering/foreman-rules.md` are also in code and tests:

| Rule | Where it is enforced |
|---|---|
| 1 No unfounded guessing | Auto-answer only on an active policy or earlier approved decision (`supervisor.py`) |
| 2 Questions vs tool approvals | Approvals are never bypassed; only the app's own `foreman_*` tools are auto-approved |
| 3 One-time vs permanent | `memory_mode` must be exactly `permanent_policy` to create a rule; any other value is one-time |
| 4 Project isolation | Policies and batch answers are filtered by project unless the scope is `global` |
| 5 Free-tier guard | No code path to a pay-per-use API; the Gemini router has no fallback (`llm_router.py`, `gemini.py`) |
| 6 Ping-pong prevention | One reverse probe per question (`probe_count`), also in the demo engine |
| 7 Honest labels | `live_gateway` / `simulated_gateway`, `is_live` per slot, billing "unconfirmed" |

## 4. Specs

The first spec (`.kiro/specs/ghost-foreman/original-spec.md`) was a 20-line checklist; the real detail was in the plan document. `requirements.md`, `design.md` and `tasks.md` were **reconstructed on 2026-11-19** from the merged pull requests, the code and the tests, and say so at the top. They were not written first, so this project is **not** an example of spec-driven development in Kiro's own spec workflow.

## 5. What was not used

- **Agent hooks:** none are configured in `.kiro/hooks`.
- **Kiro powers:** none.
- **Property-based testing:** none; tests are example-based (Python `unittest`, jsdom render tests, real-Chrome checks).
- **Kiro's spec workflow** (requirements → design → tasks created and approved in the IDE before coding): not used, see §4.

## 6. The "Frankenstein" part

Ghost Foreman stitches together parts that were not made to work together: Kiro Crew's slots and MCP, Claude Code and Codex started as separate CLIs under Windows Job Objects, the Gemini free-tier API, Tailscale Serve for the phone, and one React screen shared by the dashboard, the phone page and a public demo. Kiro Crew 0.12.2 gives an app no way to choose a slot's backend, so Claude Code and Codex are started outside Kiro Crew (for meetings only, text only) and are labelled that way on screen.

## 7. Honest status

Voice control is not implemented. PC operation (Desktop Lease) is simulated and does not touch the screen, mouse or keyboard. Scheduled news collection is not implemented. A push notification reaching a real iPhone is not confirmed. See the README status table.
