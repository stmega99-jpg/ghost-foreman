# 👻 Ghost Foreman — 幽霊現場監督 (Kiro Crew App)

**Your agents work. You have a life.**  
*AIたちは働く。あなたには生活がある。*

Built for **Kiroween 2026** (**Frankenstein Category** & **Best Kiro Crew App Bonus Prize**).

---

## 1. What is Ghost Foreman?

When running 10–18+ concurrent coding and creative AI sessions (Claude Code, Codex, Kiro Bots), **the human becomes the bottleneck**—constantly interrupted by routine confirmation prompts, ambiguous design questions, and cross-agent specification conflicts.

**Ghost Foreman** is an installable **Kiro Crew App** (`app.json`) that acts as an autonomous site foreman between you and your multi-agent workspace:
- **Proxy Decisions with Citations (代理判断)**: Answers routine agent questions automatically by citing locked project specifications and Selective Memory.
- **Pre-flight Reverse-Probing (事前逆質問)**: When an agent asks an open-ended question not covered by current policies, Ghost Foreman probes the agent *first* for option trade-offs and file impacts before escalating a clean decision card to your smartphone.
- **Bidirectional Human Q&A & Selective Memory (双方向質問・選択的記憶)**: Ask Ghost Foreman follow-up questions (*"JSONとSQLiteの違いは？今回ならどちらが便利？"*), then resolve once (`one_time`) or promote your decision to a permanent project rule (`permanent_policy`) with scoped batch resolution.
- **AI Brainstorming Room & Idea Vault (AI会議室・企画秘書)**: Run structured multi-agent ideation (`Independent Ideation → Mutual Critique → Ghost Synthesis`) and convert adopted proposals directly into scheduled slot tasks.
- **Free-Tier Router & Budget Guard (無料API枠優先ルーティング)**: Uses authorized free API tiers (e.g., Gemini Free Tier) for supervision and summarization, and strictly blocks unauthorized fallback to paid per-token APIs.
- **Project News & Desktop Lease (制作ニュース収集・PC操作権管理)**: Separates verified facts from estimates in industry news, and manages exclusive PC screen/input leases for automated playtesting with immediate human preemption.

---

## 2. Frankenstein Architecture (Custom Brain × Kiro Crew Host)

| Feature Area | Implementation Strategy | How It Works |
|---|---|---|
| **Proxy Decisions & Reverse-Probing** | **Custom Implementation** | `ForemanSupervisor` triages questions against `PolicyStore`, probes agents for impact, blocks locked-spec violations, and logs every decision to `decisions_audit`. |
| **Multi-Session & Worktree Management** | **Uses Kiro Crew Host** | Uses Kiro Crew's `/api/chat/slots` (**Ghost Foreman Managed Slots**) + MCP consultation bridge (`foreman_ask`) to respect Kiro Crew's cross-session privacy boundaries. |
| **Notifications & Remote Control** | **Uses Kiro Crew Host** | Leverages Kiro Crew's PWA Push Notifications & event bus with Ghost Foreman's Resident / Away / Sleep mode filtering. |
| **Brainstorming & Selective Memory** | **Custom Implementation** | Multi-round ideation/critique engine and versioned Global/Project policy promotion. |
| **Free-Tier Routing & News** | **Custom + SDK Telemetry** | Prioritizes Gemini Free Tier / host-included bots and combines `/api/sessions/usage` with explicit `measured` / `estimated` / `unknown` cost labels. |
| **Desktop Lease & Voice** | **Tech Verification + Web Speech** | Exclusive workstation lease reservation with instant human reclaim + Web Speech API voice briefing readout for commuting/gym use. |

---

## 3. Repository Structure

```text
ghost-foreman/
├── app.json                         # Official Kiro Crew App Manifest
├── .kiro/                           # Kiroween required specs & steering rules
│   ├── specs/ghost-foreman.md
│   └── steering/foreman-rules.md
├── agents/
│   └── ghost-foreman-agent.json     # Custom supervisor agent definition
├── skills/
│   └── foreman-protocol/SKILL.md    # Agent consultation skill
├── backend/
│   ├── store.py                     # SQLite persistent storage & idempotency
│   ├── crew_adapter.py              # Managed Slots & Kiro Crew Gateway adapter
│   ├── supervisor.py                # Proxy judgment, reverse-probe, meetings, budget router
│   ├── hooks.py                     # on_startup / on_shutdown lifecycle hooks
│   ├── routes.py                    # register_routes for Kiro Crew Gateway
│   └── mcp_server.py                # MCP consultation server for external sessions
├── dist/
│   └── index.mjs                    # @kirocrew/app-sdk React dashboard module
├── ui/
│   └── index.html                   # Desktop & Mobile responsive Halloween UI
├── dev_server.py                    # Standalone local server & simulator
└── verify_phase1_and_2.py           # Automated acceptance test suite
```

---

## 4. Installation & Usage

### A. Inside Kiro Crew (0.12+)
1. Copy or symlink this repository into `~/.kiro/crew/apps/ghost-foreman`.
2. Enable **Ghost Foreman** in the Kiro Crew App Store / Dashboard (`/apps/ghost-foreman`).

### B. Standalone Local Demo & Verification
Run the automated acceptance test suite (verifies all 8 core acceptance criteria):
```bash
python verify_phase1_and_2.py
```

Launch the interactive Desktop & Mobile Web UI:
```bash
python dev_server.py
# Open http://127.0.0.1:8765/apps/ghost-foreman
```

---

## 5. License
MIT License — see [LICENSE](./LICENSE).


## Gemini (free tier) and spending safety

Ghost Foreman can use the official Gemini API for low-cost work (news summaries, and question triage if you allow it).

- Register your key in Kiro Crew: **Settings → Secrets → `GEMINI_API_KEY`**. The key is read from the vault at call time, sent only in the `x-goog-api-key` header, and never written to logs, URLs or the repository.
- Use a key from **Google AI Studio's free tier (a project without billing)**. Ghost Foreman cannot detect whether a key's project has billing enabled, and Google charges such projects.
- Order of providers: Gemini free tier → a real Kiro Crew session → hold. When the free tier is exhausted (HTTP 429) Gemini is paused for the retry delay and the next provider is used. **There is no code path to a metered paid API.**
- Privacy switch: unpublished project text (questions, rules) is **not** sent to the Gemini free tier unless you turn on `allow_unpublished_to_free_tier` (`POST /api/apps/ghost-foreman/mode`). Free-tier inputs may be used by the provider. Public pages (news) are always allowed.
- `GET /api/apps/ghost-foreman/usage` shows calls and measured tokens per provider. Kiro session usage is not exposed by the host and is shown as unknown.

Tests for the failure paths (quota exhaustion, overloaded model, rejected key, SSRF guard) use an injected transport: `python -m unittest discover -s tests -v`.


## Remote access from an iPhone (Tailscale Serve)

The Gateway listens on `127.0.0.1` only. To reach it from a phone **without opening a port to the internet**, publish it inside your private tailnet with Tailscale Serve (not Funnel). Only devices signed in to your Tailscale account can connect, and the dashboard still requires its access token.

**PC (one time)**
1. Install Tailscale and sign in: `winget install --id Tailscale.Tailscale -e`.
2. In the Tailscale admin console enable **MagicDNS** and **HTTPS Certificates** (DNS page), and enable **Serve** for this node (the CLI prints a link the first time).
3. `tailscale serve --bg 5476` publishes `https://<pc-name>.<tailnet>.ts.net/` inside the tailnet. Check with `tailscale serve status` that it says *(tailnet only)* and that Funnel is off.
4. `scripts\phone-link.ps1` copies a sign-in link for the iPhone to the clipboard (it is never printed). The link contains an access token (20 h by default, `-Ttl 2h` for shorter): send it only to your own phone.

**iPhone**
1. Install the Tailscale app and sign in with the same account; keep the VPN switch on.
2. Open the link in Safari, then Share → **Add to Home Screen**.
3. Open Ghost Foreman from the Home Screen icon (the installed web app), go to Kiro Crew *Settings → Notifications* and allow notifications. iOS only allows this from the installed web app, over HTTPS.

Notes: push subscriptions belong to the address they were created on, so subscribe again after switching to the `ts.net` address. `tailscale serve reset` removes the publication. Never run `tailscale funnel` for this app.
