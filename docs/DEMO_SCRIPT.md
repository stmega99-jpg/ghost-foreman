# Demo video script (under 3 minutes, English subtitles)

Rules this script follows (Kiroween 2026 Devpost): under 3 minutes (target **2:50 or less**), public on YouTube, shows the app **running on the device it runs on**, no copyrighted music. Only features that really work are shown. Voice control, PC operation (simulated) and scheduled news are **not** shown.

Record in **English** (screen language switch: English) so the picture and the subtitles match. Subtitles are on-screen text or an `.srt` file; no voice-over is required.

## Before recording (checklist)

- [ ] Gateway running with the **current `main`** deployed. Emergency stop **not** in force.
- [ ] Two real AI agents in slots (for example Kiro and Claude Code) on a harmless sample task. Policies exist for one topic (for example "dates are saved as ISO 8601 UTC") and **not** for another (for example "SQLite or JSON?").
- [ ] **Push is not confirmed on a real iPhone, so plan for it not arriving.** Record Version B of the 1:00–1:20 scene (open the app yourself) as the main take. Only if a push really arrives while you record, you may add Version A as an extra. Never write "notification" in a subtitle for a take where none arrived.
- [ ] Phone: the Ghost Foreman Home Screen app, signed in. **Hide** the address bar, the tailnet name, the device name, notifications from other apps, and any email or account name. Crop or blur if they appear.
- [ ] A meeting topic that is not private (for example "make approving a task one-handed and safe on a phone"). The Gemini permission is for **this meeting only**; use a non-confidential topic.
- [ ] Run each scene once beforehand. Cut waiting time in editing, but **say in a subtitle when a scene is cut** ("sped up") rather than hiding it.
- [ ] Mode labels visible on screen: "live" slots must show as real, demo data must not appear.

## Storyboard

| Time | Picture | Subtitle (English) |
|---|---|---|
| 0:00–0:08 | Title card: "Ghost Foreman — Your agents work. You have a life." Then the home screen "What would you like to do?" | Ghost Foreman is a Kiro Crew app: a foreman that answers your AI agents' questions so they don't stop while you're away. |
| 0:08–0:20 | The PC dashboard: agents listed as real (live) with their tasks. One agent shows "waiting". | Several AI agents work in parallel. Each one stops whenever it needs a decision. |
| 0:20–0:40 | An agent asks a question that matches a rule. The question appears, then "Answered automatically", with the rule cited in the decision log. | If a rule you set already covers the question, the Ghost answers for you, cites the rule, and the agent keeps going. |
| 0:40–1:00 | A different agent asks something no rule covers. The Ghost asks the agent **one** follow-up. Options with a recommendation appear. | If nothing covers it, the Ghost doesn't guess. It asks the agent once for missing details, then offers you clear options. |
| 1:00–1:20 | **Phone (works with or without a push).** Version A, only if a push really arrives while recording: the notification shows on the lock screen, tap it. Version B (use this whenever the push does not arrive): open the Ghost Foreman Home Screen app yourself; the home screen shows "Answer the AIs' questions" with a count, and the question is waiting. Then tap "Just this once" (and show "Keep as a rule" without pressing it). | On your phone, the question is waiting for you. You answer from there. "Just this once" is not remembered. Only "Keep as a rule" becomes a rule. |
| 1:20–1:30 | PC: the agent resumes; the decision log shows the human answer. | The agent resumes at once, and every decision is logged. |
| 1:30–1:45 | "Consult the AIs": type the topic, four AIs shown with where each runs (Kiro Crew vs outside Kiro Crew). Tick Gemini → the permission box appears. | Meeting room: Kiro, Claude Code, Codex and Gemini. Gemini sends text to a free tier, so you must allow it **for this meeting only**. |
| 1:45–2:00 | Tick the permission, start. Round 0 "participation check" shows each AI's real reply and where it ran. | Every AI must answer a check first, and the minutes record which AI really ran and where. |
| 2:00–2:20 | Rounds 1–2 scroll by (sped up). The Ghost's summary: agreement, disagreement, options. Tap "Save only" (or adopt an option). | Independent ideas, mutual critique, then a summary. Nothing is built until you choose. |
| 2:20–2:40 | Tap **Stop all**. Slots show "stopped". Show that a running outside AI ended. Then the human-only "Lift every stop". | One button stops everything, including AIs started outside Kiro Crew. Only a human can lift it, and lifting it doesn't restart work. |
| 2:40–2:50 | Card: GitHub URL, "Demo with sample data" URL (if hosted), and the status line. | Not built yet: voice control, scheduled news. PC control is simulated. Code is MIT-licensed, built with Kiro. |

Total: 2:50. If it runs long, drop the 1:20–1:30 scene first.

## Subtitle file

Use the table's times and text as an `.srt` (keep each line to two lines of about 40 characters). Check that the **last subtitle ends before 2:55**.

## Say this honestly in the video or the description

- The demo is recorded on a real Kiro Crew Gateway. The public **demo page** uses sample data and is labelled so; do not present it as the live app.
- Claude Code, Codex and Gemini in meetings run **outside** Kiro Crew (text only); the screen says so.
- A push reaching a real iPhone is not yet confirmed. The video must work without it: the question scene opens the app by hand (Version B). If a push does arrive, record it as it happens; never stage or fake one. The app can show what it **sent** (Details & settings → Notification history), but "sent" is not "delivered", so do not describe it as delivered.

## After recording (human-only)

1. Upload to YouTube as **Public**. Add the subtitles. Put the repository URL in the description.
2. Paste the video URL into the Devpost form.
