# 👻 Ghost Foreman — 幽霊現場監督 (Kiro Crew App)

**Your agents work. You have a life.**  
*AIたちは働く。あなたには生活がある。*

Built for **Kiroween 2026** (**Frankenstein** category, and the **Best Kiro Crew App** bonus prize).

---

## 1. What is Ghost Foreman?

When you run many AI sessions at once (Claude Code, Codex, Kiro), **the human becomes the bottleneck**: routine confirmation prompts, ambiguous design questions, and decisions that conflict with what you already decided.

Ghost Foreman is an installable **Kiro Crew app** (`app.json`) that sits between you and your AIs, like a site foreman:

- **Proxy decisions with citations (代理判断).** When an AI asks a question, Ghost Foreman answers it from the rules you already decided, and records why.
- **Reverse-probing (逆質問).** For a question no rule covers, it first asks the AI for the options and their impact (once per question), then sends you one clean decision card.
- **Selective memory (選択的記憶).** Your answer is either "this time only" or a permanent project rule. A rule is never created without your explicit choice.
- **AI meetings (AI会議室).** Ask several *different* AIs (Kiro, Claude Code, Codex, Gemini) for ideas, let them critique each other, and get one summary with options. Nothing is built until you pick an option.
- **Free-tier guard (無料API枠).** Cheap work goes to the Gemini free tier; if it runs out there is **no path to a paid API**.
- **Emergency stop (緊急停止).** One button stops everything, including AIs started outside Kiro Crew. Only a human can resume.
- **Made for non-engineers.** The app starts from "what do you want to do?"; technical settings and run records are on a separate details screen. It also runs as its own iPhone Home Screen app.

---

## 2. What works today — honest status

Everything below is labelled the same way in the app: **live** = verified against a real Kiro Crew Gateway, **simulated** = demo data only, **not implemented** = not built.

| Feature (plan section) | Status | Notes |
|---|---|---|
| Proxy decisions, reverse-probing, escalation (A) | **Live** | Verified with real Kiro Crew slots through our MCP tool `foreman_ask`. Tool approvals stay with the human; only our own `foreman_*` tools are auto-approved. A judge AI (Gemini if allowed, else a Kiro slot) matches questions to rules; if no judge is available the question is held for you. |
| Conflicts between AIs' opinions (A) | Not implemented | Only the meeting summary lists points of disagreement. |
| Slots view and stop (B) | **Live** (partial) | Managed slots, status, per-slot / per-project / global stop. **Not implemented:** priorities, dependencies, deadlines, automatic hand-off between AIs, retry limits. |
| Free-tier routing and cost view (C) | **Live** (partial) | Gemini free tier with cooldown after quota errors; per-call usage records; cost shown as 未確認 (never $0). **Not implemented:** daily/weekly/monthly totals, budget reservation, resume-after-recovery scheduling. |
| AI meetings (D) | **Live** (partial) | Kiro, Claude Code, Codex and Gemini in one meeting, three rounds, idea vault, "adopt an option → task". **Not implemented:** joining or swapping participants mid-meeting, pause/resume, time and cost limits per meeting. |
| Selective memory (E) | **Live** (partial) | One-time vs permanent rule, global/project scope, versions, batch apply. **Not implemented:** edit/withdraw screen, conflict check, hand-off document generation. |
| Notifications and modes (F) | **Live** (partial) | Home / away / sleep modes; Kiro Crew push; own iPhone app over Tailscale (end-to-end test passes). **Not confirmed:** push delivery to a real iPhone. |
| Artifact review (G) | Not implemented | Left to Kiro Crew's own diff and browser features. |
| Desktop Lease, PC control (H) | **Simulated** | A state record only. It does not control any screen, mouse or keyboard. |
| News (I) | **Live** (partial) | You give a public URL; it is summarised with facts and estimates kept apart (SSRF-guarded). **Not implemented:** automatic or scheduled collection by interest. |
| Voice (J) | Not implemented | No speech input or output exists. |

Tests: `python -m unittest discover -s tests` (unit tests, no Kiro Crew needed), `python verify_phase1_and_2.py` (acceptance), and the UI tests in `tests/ui/` (see its README).

---

## 3. Frankenstein architecture (custom brain × Kiro Crew host)

| Area | Built by | How |
|---|---|---|
| Proxy decisions, memory, audit log | **Ghost Foreman** | `ForemanSupervisor`, SQLite store, `decisions_audit`. |
| Slots, approvals, notifications | **Kiro Crew host** | `acquire_worker_slot`, `/api/chat/slots`, push notifications. Ghost Foreman's own slots are created and read through the host's in-process API. |
| Bridge for any AI | **Ghost Foreman MCP server** | `backend/mcp_server.py` exposes `foreman_ask`, `foreman_report_status`, `foreman_get_policies`. |
| Different AIs in one meeting | **Ghost Foreman + CLIs + Gemini API** | Kiro runs inside Kiro Crew; Claude Code and Codex are started directly (see §5); Gemini is called through the official API. |
| Free tier | **Ghost Foreman** | `backend/llm_router.py`, `backend/gemini.py`. |
| Emergency stop | **Ghost Foreman** | `backend/halt.py`, `backend/winjob.py` (Windows Job Objects). |
| Screens | **Ghost Foreman** | React bundle `ui/dist/index.mjs` for the Kiro Crew dashboard; `ui/m/` for the phone page. |

---

## 4. Try it

**Requirements:** Kiro Crew 0.12.2 (`kirocrew`), Python 3.13, a signed-in Kiro. For the meeting AIs you also need the CLIs signed in with a subscription (not an API key): `claude` then `/login`, and `codex login`. Gemini needs `GEMINI_API_KEY` from Google AI Studio's **free tier** (a project without billing), registered in Kiro Crew under *Settings → Secrets*.

### A. Inside Kiro Crew (all "live" features)
```bash
kirocrew gateway                   # start the Gateway
kirocrew app install <this-folder> # installs Ghost Foreman
kirocrew app enable ghost-foreman
```
Open the Kiro Crew dashboard → *Apps → Ghost Foreman*. When you update the app later, restart the Gateway (`kirocrew restart`) so the Python code reloads. You may be asked to approve the app's permissions in the dashboard.

### B. Demo with sample data (no Kiro Crew, no accounts)
```bash
python dev_server.py               # http://127.0.0.1:8765/  (opens demo/index.html)
python verify_phase1_and_2.py      # 8 acceptance suites
python -m unittest discover -s tests
```
`demo/index.html` runs the **same screen as the real app** (`ui/dist/index.mjs`, Japanese and English) on **made-up sample data** that lives in the browser (`demo/engine.mjs`). It is labelled "Demo sample (simulated)" on screen and is **not live**: no AI is called, and nothing you type is sent anywhere.
- The page's Content-Security-Policy is `connect-src 'none'`, so the page cannot open any connection (fetch, XHR, WebSocket), even to its own server.
- `dev_server.py` serves files only from `demo/` and `ui/` (everything else on disk is 404). It **also still exposes the Python backend's simulated API under `/api/...`** on 127.0.0.1, for API checks; the demo page does not use it and, because of the CSP, cannot call it. Its news endpoint can fetch a public web address you give it, so treat it as a local tool and do not expose it beyond 127.0.0.1. A hosted static copy has no `/api` at all.
- The demo page cannot reach an AI contract, an API key or the owner's PC, because it has no code path to them. Questions, the emergency stop (only a person can lift it), the 4-AI meeting (including the per-meeting Gemini permission rule) and the language switch all work on the sample data. The meeting's answers are fixed sample text.
- Tests: `node tests/demo/engine_test.mjs` (rules of the sample engine) and `tests/demo/browser_test.mjs` (real Chrome: both languages, a question, a meeting, the stop, and that no request leaves the page).
- The same folder can be hosted as a static site. That is not enabled yet; if it is, this section will give the address.
---

## 5. Safety design

- **Emergency stop is human-only to lift.** While it is in force, nothing is auto-answered, auto-ordered, resumed, or auto-approved; questions that arrive are held for you.
- **Free-tier guard.** There is no code path to a metered paid API (`cost_usd` is NULL = unconfirmed). If Gemini's free tier is exhausted, a meeting's Gemini participant simply has no answer; no other AI answers in its place.
- **Per-meeting permission for Gemini.** A meeting's content is unpublished project text. Gemini takes part only if you tick the permission for *that meeting*; the server refuses otherwise and nothing is created or sent. It is kept in the minutes, ends with the meeting, and does not change the global `allow_unpublished_to_free_tier` switch. Before **every** request to the Gemini API (model list and each model tried) the stop state is checked, so after a stop the same text is not retried on another model.
- **Kiro Crew first, one exception.** Development work and progress stay on Kiro Crew's own features. Because Kiro Crew 0.12.2 gives an app no way to choose a slot's backend, **brainstorming only** may start `claude` and `codex` directly (`backend/external_ai.py`). They get text only: tools, MCP, web search, hooks and file writes are off, the environment contains no API keys, and a run that tries a tool is killed. The screen and the minutes label them "Kiro Crew 外で実行". At most 2 run at once, and only with at least 1.5 GB of free memory.
- **A stop reaches everything those CLIs started.** On Windows each CLI is created suspended, put in its own Job Object, then resumed, so a stop ends it and every child, even one being created at that moment. If the job cannot be set up, the CLI is not started.
- **Records.** Every outside run is recorded (CLI, model, time, outcome; the prompt only as a SHA-256 hash). Round 0 of a meeting asks each AI to name itself; a self-introduction that does not match the AI actually called is flagged in the minutes (it never changes which AI is recorded as having answered).
- **Gemini and spending notes.** The key is read from the Kiro Crew vault at call time and sent only in a header. Ghost Foreman cannot see whether a key's Google project has billing enabled; use a free-tier key.

---

## 6. Remote access from an iPhone (Tailscale Serve)

The Gateway listens on `127.0.0.1` only. To reach it from a phone **without opening a port to the internet**, publish it inside your private tailnet with Tailscale Serve (not Funnel). Only devices signed in to your Tailscale account can connect, and the dashboard still requires its access token.

**PC (one time)**
1. Install Tailscale and sign in: `winget install --id Tailscale.Tailscale -e`.
2. In the Tailscale admin console enable **MagicDNS** and **HTTPS Certificates**, and enable **Serve** for this node (the CLI prints a link the first time).
3. Let the Gateway accept its own tailnet name (otherwise `403 Host header not allowed`): `kirocrew config set dashboard.tailscale.enabled true`, then `kirocrew restart`.
4. `tailscale serve --bg 5476` publishes `https://<pc-name>.<tailnet>.ts.net/` inside the tailnet. Check with `tailscale serve status` that it says *(tailnet only)*. Run it again after a PC reboot.
5. `scripts\phone-link.ps1` copies a sign-in link for the iPhone to the clipboard (it is never printed). With `-Qr` it shows a QR code in a window on the PC instead (`pip install segno`; nothing is written to disk; the window closes by itself). The link contains an access token (20 h by default, `-Ttl 1h` for shorter): send it only to your own phone.

**iPhone (Ghost Foreman as its own Home Screen app)**
1. Install the Tailscale app, sign in with the same account, keep the VPN switch on.
2. On the PC run `scripts\phone-link.ps1 -Qr -Ttl 1h` and scan the QR code. It opens Ghost Foreman's own page (`/api/apps/ghost-foreman/m/`), not the Kiro Crew dashboard.
3. In Safari: Share → **Add to Home Screen**, then open the new icon right away (the link expires after `-Ttl`).
4. In the app: **⚙️ 詳細・設定 → 通知・送信の設定 → 通知をオンにする**, then **テスト通知を送る**.

The app signs in once with the link it was added from and then renews itself with the Gateway's 30-day refresh cookie. A small service worker (scope `/api/apps/ghost-foreman/m/`) keeps only the page and its two modules so it can renew after the 20-hour access cookie expires; it never caches API data. React is bundled in `ui/m/vendor/react.mjs` (rebuild: `ui/m/vendor/build.mjs`); no CDN is used. The browser end-to-end test is `tests/ui/phone_e2e.mjs`. Never run `tailscale funnel` for this app.

---

## 7. Repository structure

```text
ghost-foreman/
├── app.json                      # Kiro Crew app manifest (permissions, agents, MCP server)
├── .kiro/                        # specs/ and steering/ (Kiroween requires this folder)
├── agents/                       # ghost-foreman-agent.json, meeting-participant.json
├── skills/foreman-protocol/      # how an AI should consult Ghost Foreman
├── backend/
│   ├── supervisor.py             # proxy decisions, reverse-probe, policies, adoption
│   ├── meeting.py                # AI meetings (four kinds of AI)
│   ├── external_ai.py, winjob.py # Claude Code / Codex outside Kiro Crew; Job Objects
│   ├── gemini.py, llm_router.py  # Gemini free tier, router, free-tier guard
│   ├── halt.py                   # emergency stop (human-only resume)
│   ├── crew_adapter.py, live_gateway.py  # managed slots on the real Gateway
│   ├── notifier.py, news.py, store.py, routes.py, hooks.py, mcp_server.py
├── ui/dist/index.mjs             # the app screen (Kiro Crew dashboard)
├── ui/m/                         # the iPhone page (manifest, service worker, bundled React)
├── scripts/                      # phone-link.ps1, QR window, icons
├── tests/                        # unit tests; tests/ui = screen and phone end-to-end tests
├── demo/, dev_server.py          # public demo on sample data (same screen as the app)
├── ui/index.html                 # older single-file screen (no longer served)
└── verify_phase1_and_2.py        # acceptance suite
```

---

## 8. License
MIT License — see [LICENSE](./LICENSE).
