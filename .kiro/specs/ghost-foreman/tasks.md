# Ghost Foreman — Tasks

> Reconstructed on 2026-11-19 from the merged pull requests. The work really went **one pull request at a time, each checked on a real Gateway where it could be**, and this list follows that order. Dates are the PR merge dates in UTC. `[x]` means merged **and** checked as written in the PR; "not checked" is stated where something was not. Requirement numbers refer to `requirements.md`.

## Done

- [x] **#1 (11-18) Make the app load in Kiro Crew.** Relative imports so the Kiro Crew loader accepts the package. *R-all*
- [x] **#2 (11-18) Live slots, live questions, `foreman_ask` (MCP).** Real slots from the Gateway; questions from real agents; MCP bridge. Checked on a real Gateway with real agents. *R1, R2, R9*
- [x] **#3 (11-18) Gemini free tier, switch guard, triage, news.** Real key from the vault; quota exhaustion waits instead of using a paid API; per-call usage record (billing "unconfirmed"); URL summary with facts and estimates apart. *R5, R7*
- [x] **#4 (11-18) Notifications, stop that only a human lifts, React screen.** Modes, push; emergency stop on real slots; resume does not restart work; first React screen. *R3, R6*
- [x] **#5 (11-19) Docs: Tailscale Serve.** Setup steps for private remote access (`dashboard.tailscale.enabled`). *R6*
- [x] **#6 (11-19) Phone page as its own Home Screen app.** Own manifest, service worker, sign-in renewal. Checked by a real-Chrome phone test over Tailscale (16/16). Not checked: a real iPhone. *R6*
- [x] **#7 (11-19) Meetings with Claude Code, Codex and Kiro.** Claude Code and Codex run outside Kiro Crew, text only, in Job Objects; run records; participation check. Checked live. *R4, R3*
- [x] **#8 (11-19) Gemini as a participant, per-meeting permission.** Refusal before anything is created; stop check before every request. Checked live, including a stop during a meeting. *R4, R5*
- [x] **#9 (11-19) Gemini knows its name; self-introduction check.** `check_self_report`; shows a warning without changing `verified`. *R4*
- [x] **#10 (11-19) Simple screen.** Home starts at "What would you like to do?"; details under "Details & settings"; one `parts` list for the consult form. *R8*
- [x] **#11 (11-19) The PC dashboard stops showing a connection error.** The app declares its own API path. Checked in real Chrome (PC and phone widths). *R8*
- [x] **#12 (11-19) README and plan rewritten to the real status.** Voice, PC lease and scheduled news are shown as not implemented / simulated; the video is under 3 minutes. *R9*
- [x] **#13 (11-19) Japanese / English switch.** Screen, phone page, backend fixed labels, English meetings. 95 render tests, dictionary test, 103 Python tests. Checked live: phone test and PC/phone screens after deploy. *R8, R4*
- [x] **#14 (11-19) English minutes fixes.** English participation-check prompt; Gemini location label. Checked live with a real four-AI meeting in English (Claude Code, Codex, Gemini, Kiro).
- [x] **Demo PR (#15, open when this was written).** Demo on sample data, CSP `connect-src 'none'`, `dev_server.py` serves only `demo/` and `ui/`; engine tests and a real-Chrome test with a request log. *R10*

## Remaining before submission (2026-12-03 target; deadline 2026-12-05 07:00 JST)

- [ ] Merge the demo PR. Decide, with the owner, whether to host the demo as a static site (a public action; not done).
- [ ] `docs/KIRO_USAGE.md`: how Kiro was used (mandatory submission text).
- [ ] `docs/DEMO_SCRIPT.md`: storyboard for a video under 3 minutes with English subtitles.
- [ ] Blog post in English on dev.to (honest status; says it is for Kiroween 2026).
- [ ] **Human-only:** record and upload the video (YouTube, public), publish the blog and the social post (starts with `#KiroweenHackathon26`), fill in and submit the Devpost form, re-read the Rules tab for the "working app URL" wording.
- [ ] Final check of the repository: public, MIT licence visible, `.kiro/` at the root, no personal information in files or history.

## Backlog (not started; shown as not implemented in the README)

- [ ] Detect conflicts between two AIs' opinions (A).
- [ ] Priority, dependency, deadline and hand-over between slots; retry limits (B).
- [ ] Daily/weekly/monthly usage totals, reserved amounts, resume when the quota recovers (C).
- [ ] Join late, swap participants, pause/resume, time and cost limits for a meeting (D).
- [ ] Edit / withdraw policies in the screen; conflict checks; handover documents (E).
- [ ] Confirm a push reaching a real iPhone (F).
- [ ] Scheduled news by field of interest (I).
- [ ] Deliverable review (G), real PC operation lease (H), voice (J).
