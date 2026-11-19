# Ghost Foreman — Design

> Reconstructed on 2026-11-19 from the code and PRs #1–#14 (see the note in `requirements.md`). It describes what exists. Items that are planned but not built are listed at the end.

## 1. Shape of the system

```
iPhone / PC browser ──(Tailscale Serve, private)──► Kiro Crew Gateway (127.0.0.1:5476)
                                                      │  app: ghost-foreman (app.json)
   React screen  ui/dist/index.mjs  ◄── routes ──────► backend/routes.py ──► supervisor.py (decisions)
   phone page    ui/m/index.html                         │                    meeting.py   (AI meetings)
                                                         │                    llm_router.py + gemini.py (free tier)
   AI agents ──MCP `foreman_ask`──► backend/mcp_server.py│                    external_ai.py + winjob.py (Claude Code / Codex)
   (Kiro Crew slots)                                     │                    halt.py (emergency stop)
                                                         └─► store.py (SQLite)  notifier.py   news.py
```

- **Host first.** Slots, sessions, push, auth and the dashboard come from Kiro Crew 0.12.2. The app adds the foreman's judgement, memory, meetings and stop rules.
- **One exception to "Kiro Crew first".** Kiro Crew 0.12.2 cannot let an app choose a slot's backend, so meetings start `claude` and `codex` directly (text only) and call Gemini through its API. Everything else stays on Kiro Crew. (PR #7, #8)

## 2. Components

| Part | File | Job |
|---|---|---|
| Manifest | `app.json` | Declares routes, agents, skill, MCP server, permissions (`spawn`, `sessionApproval`, own API path `/api/apps/ghost-foreman` and `/*`). |
| Routes | `backend/routes.py` | `/dashboard`, `/questions`, `/questions/inquire`, `/questions/resolve`, `/meetings`, `/meetings/adopt`, `/stop`, `/mode`, `/news/summarize`, `/notify/test`, `/meetings/harnesses`, `/usage`, … One `dispatch_api_request` serves both the Gateway and `dev_server.py`. |
| Decisions | `backend/supervisor.py` | Policy matching, reverse probe (cap 1), options with a recommendation, one-time vs permanent answers, batch answers, held questions, audit log. |
| Live slots | `backend/live_gateway.py`, `crew_adapter.py` | Real slots and replies through the Gateway's HTTP API; marks each slot `is_live`. |
| MCP bridge | `backend/mcp_server.py` | `foreman_ask`, `foreman_report_status`, `foreman_get_policies` for agents. |
| Meetings | `backend/meeting.py` | Rounds 0–3, participants (Kiro, Claude Code, Codex, Gemini), consent flag, self-report check, language suffix. |
| Outside AIs | `backend/external_ai.py`, `winjob.py` | Starts the CLIs without tools or keys, one Job Object each, records every run (prompt only as a SHA-256). |
| Free tier | `backend/llm_router.py`, `gemini.py` | Gemini free tier only; `gemini_only()` has no fallback; stop check before every request. |
| Stop | `backend/halt.py` | Persistent hold (all / project / slot). Engaged before sessions are interrupted. Lifted only by an explicit resume call. |
| Notices | `backend/notifier.py` | Modes, push through Kiro Crew, test notification. |
| Store | `backend/store.py` | SQLite: projects, slots, questions, policies, decisions audit, meetings, ideas, news, budgets, state. |
| Screens | `ui/dist/index.mjs`, `ui/m/` | One React file for dashboard and phone; the phone page adds a service worker and sign-in renewal. |
| Demo | `demo/` | Same screen on in-browser sample data (see §6). |

## 3. Key decisions and why

1. **The human keeps tool approvals.** Questions (design choices) go through the app; tool-execution requests go to `/api/approvals` and are never bypassed. *Why:* an auto-approver would be an unreviewed shell. (rule 2)
2. **Answers are one-time unless the human says otherwise.** `memory_mode` defaults to `one_time`; any other value is treated as one-time. *Why:* a permanent rule created by accident would answer for the human later. (rule 3)
3. **Reverse probe is capped at one per question.** *Why:* two AIs can ask each other forever. (rule 6)
4. **Stop first, interrupt second.** The hold is stored before sessions are touched, so nothing restarts in between. Resume is its own call and does not restart work. (PR #4)
5. **Jobs for outside CLIs.** Each CLI is created suspended, put into a Job Object, then resumed; if the job cannot be made, the CLI is not started. A stop ends the whole tree. (PR #7)
6. **Gemini permission is per meeting and literal.** Only JSON `true` counts. Checked before the meeting row exists. Never merged into the global switch. (PR #8)
7. **Which AI answered is known from the call, not from the text.** `verified` comes from what was started; a mismatched self-introduction is only a warning (PR #9, after Gemini introduced itself as Claude).
8. **Slot keys get a random suffix; the Kiro participant agent is found by its declared name** (`meeting-participant`). *Why:* Kiro Crew resolves an app's agent by its declared name, not by file name.
9. **The app declares its own API path** in `app.json`, so the dashboard works inside Kiro Crew without a separate approval. (PR #11)
10. **Language by sentence key.** `t("日本語の文")` returns the English from one dictionary; a test checks every literal has an English entry with the same `{placeholders}`. Fixed backend labels go through `tb()`; AI and human text is shown as written. English meetings append an instruction to each prompt and store `summary.language`. (PR #13, #14)
11. **Home starts at "What would you like to do?".** Technical items sit under "Details & settings"; the consult form keeps one `parts` list so edits survive closing the panel. (PR #10)
12. **Honest mode labels.** Each slot says `is_live`; the gateway mode is `live_gateway` or `simulated_gateway`; costs are `null` ("unconfirmed"), never 0. (rule 7)

## 4. Data and flows

**A question.** Agent → `foreman_ask` → `receive_agent_question` → (policy match? answer + audit) / (spec change? hold) / (else probe once → options → notify human) → human answers on the phone → answer sent to the slot → session resumes. While a stop is in force the question is stored as `held_emergency_stop`.

**A meeting.** `POST /meetings` (topic, participants, organiser, `allow_unpublished_to_gemini`, `language`) → refuse if a stop is in force, a participant is unavailable, or Gemini lacks the literal `true` → round 0 participation check → round 1 ideas (independent) → round 2 critique → round 3 summary by the organiser → `awaiting_human_adoption`. Adoption schedules work on a slot the human picked, or saves an idea.

**A stop.** `POST /stop {scope}` → hold engaged → slots marked stopped → outside runs killed (Job Object) → the screen shows the stop. `resume_*` releases the hold; slots go to `idle`, not `working`.

## 5. Safety and privacy design

- Keys are read from Kiro Crew's vault at call time and sent only in a header; the outside CLIs get an environment with no keys.
- Outside CLIs run with tools, MCP, web search, hooks and file writes off; a run that tries a tool is killed. At most 2 at once, and only with enough free memory.
- Project isolation: queries filter by project; a policy leaves its project only with scope `global`.
- Untrusted text (other participants' proposals, news pages, AI answers) is passed as data, not instructions.
- News fetch refuses internal addresses.
- The phone page is reachable only inside the owner's tailnet and still needs the Gateway's access token.

## 6. The public demo

`demo/index.html` loads the real screen (`ui/dist/index.mjs`) with an import map that swaps `@kirocrew/app-sdk` for `demo/sdk.mjs`. That module answers the screen's API calls from `demo/engine.mjs`, an in-memory engine with made-up data. The page's CSP is `connect-src 'none'`, so even a code mistake could not make a request. The engine copies the app's rules (one-time answers, one probe, human-only resume, Gemini literal `true`) so the demo does not teach wrong behaviour. Sample text is stored as `{ja, en}` and picked at each read, so the language switch works. A meeting reveals one round per 1.2 s from a fake-able clock, so tests need no timers. `dev_server.py` serves only `demo/` and `ui/`.

## 7. Testing

| Layer | What | Where |
|---|---|---|
| Python unit tests | store, halt, router, Gemini rules, meeting rounds and language, Job Objects, notifier, manifest, dev server | `tests/test_*.py` (103 on main; 4 more with the demo PR) |
| Acceptance | 8 suites for phases 1–2 | `verify_phase1_and_2.py` |
| Screen render (jsdom) | home, inbox, consult form, meetings, stop, English | `tests/ui/render_test.mjs` (95) |
| Dictionary | every `t()` string has English, same placeholders, none unused; backend labels translated | `tests/ui/i18n_test.mjs` (13) |
| Phone | real Chrome over Tailscale: install, service worker, expired cookie, sign-in, English | `tests/ui/phone_e2e.mjs` |
| Demo | engine rules; real Chrome with request log and CSP checks | `tests/demo/` |

Tests marked "real Chrome" need a PC with Chrome; they are run by hand and not in `unittest discover`.

## 8. Known gaps (design level)

- No dependency or deadline model between slots; no automatic hand-over between AIs.
- Budget view has no daily/weekly/monthly totals.
- Policies cannot be edited or withdrawn in the screen.
- Push to a real iPhone is unconfirmed.
- Spec items G (review), H (PC lease: simulated) and J (voice) are not built.
