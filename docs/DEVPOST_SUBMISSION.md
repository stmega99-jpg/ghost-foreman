# Devpost submission text (Kiroween 2026)

Copy each section into the matching field of the Devpost form. The owner fills in and submits the form; the URLs for the video and the blog are added once they are published.

- **Project name:** Ghost Foreman
- **Tagline (one line):** Your agents work. You have a life.
- **Category:** Frankenstein · also entering Best Kiro Crew App, Bonus Blog Prize, Social Blitz Prize
- **Repository (public, MIT, `.kiro/` at the root):** https://github.com/stmega99-jpg/ghost-foreman
- **Working demo / test build:** https://stmega99-jpg.github.io/ghost-foreman/ (sample data only; see "Testing")
- **Video (under 3 minutes):** *add the YouTube URL*
- **Blog post (Bonus Blog Prize):** *add the dev.to URL*
- **Social post (Social Blitz Prize):** *add the URL of the post that starts with `#KiroweenHackathon26`*

---

## Inspiration

Adding AIs was supposed to give me time back. Instead, every AI kept stopping to ask me something, often a small decision I had already made, and when I stepped away they all sat and waited. I had become the full-time manager of my own assistants.

Anyone who works with several AIs at once runs into it: solo developers, founders, writers, researchers, and people who don't write code.

## What it does

Ghost Foreman is a Kiro Crew app that takes over the supervising, so you only make the decisions that are really yours.

- **Answers what you've already decided.** When an AI asks something your rules cover, Ghost Foreman answers, cites the rule, logs it, and the AI keeps working.
- **Brings you only what's really yours.** When no rule covers it, it doesn't guess: it asks that AI one follow-up question, then gives you one card with options, impact and a recommendation.
- **Remembers only what you choose.** Answers are one-time unless you say "make this our policy from now on". Rules stay in their project unless you make them global.
- **Lets you decide away from the desk.** An iPhone Home Screen app, reached privately over Tailscale.
- **Gets you four opinions.** A meeting of four different AIs (Kiro, Claude Code, Codex, Gemini): independent ideas, mutual critique, then one summary with options. Use it to plan, critique or get unstuck. Nothing happens until you choose.
- **Keeps the final say with you.** One button stops every AI, including those started outside Kiro Crew. Only a person can lift the stop, and nothing restarts by itself.
- **Japanese and English** throughout, including meetings held in English.

**Honest status.** Live on a real Kiro Crew Gateway: answering from rules, the follow-up question, one-time vs permanent rules, the four-AI meeting, the emergency stop, the phone app (tested in a real browser). **Not confirmed:** a push notification reaching a real iPhone. **Simulated:** PC control (state records only). **Not built:** voice control, scheduled news, detecting conflicts between AIs. The public demo uses sample data and is labelled so.

## How we built it

- **Kiro Crew** is the host: worker slots for the AI sessions, an MCP server (`foreman_ask`, `foreman_report_status`, `foreman_get_policies`) the AIs use to consult the foreman, two custom agents, a skill telling agents when to ask, push notification channels, and Kiro Crew's sign-in.
- **Python backend** for the decisions, memory, meetings and stop; **one React screen** shared by the Kiro Crew dashboard, the iPhone app and the public demo.
- **The Frankenstein part:** Kiro Crew 0.12.2 can't let an app choose which AI runs in a session, so for meetings only Ghost Foreman starts Claude Code and Codex directly (text only, no tools, no keys, inside Windows Job Objects so a stop ends them), calls Gemini's free tier, and stitches all of it into one meeting with Kiro.
- **Built with Kiro by a non-programmer.** I directed in Japanese; Kiro planned, wrote and tested every change, one pull request at a time (18), and, where it could, checked the result on the real Gateway and in a real browser before I approved the merge. Seven safety rules in `.kiro/steering` are enforced in code and tests. Details: `docs/KIRO_USAGE.md`.

## Challenges we ran into

- Making a stop truly final: the hold is saved before any AI is interrupted, and the Gemini router checks for a stop before every request so a stopped meeting can't be retried on another model.
- Gemini introduced itself as Claude in the first live meeting. The app now records which AI really answered from what it started, not from what it said.
- Keeping the app honest: README sentences that claimed more than the code did were rewritten, and every screen labels live vs sample data.
- Before submitting, my personal e-mail turned up in four early commits. I re-created the repository with a cleaned history and kept the old pull-request descriptions in `docs/PR_HISTORY.md`.

## Accomplishments that we're proud of

- A real four-AI meeting (Kiro, Claude Code, Codex, Gemini) held in English and in Japanese, with each participant's real runtime recorded.
- A stop button that reaches AIs outside Kiro Crew, and that only a person can lift.
- A public demo that physically can't connect to anything (`connect-src 'none'`), published from just five static files (plus a one-line redirect page).
- Built end to end through Kiro by someone who doesn't write code.

## What we learned

Supervising AIs is real work, and most of it is answering things you've already decided. A good assistant for that has to be honest about what it doesn't know, and must never take the final decision away from you.

## What's next for Ghost Foreman

Detecting when two AIs disagree, daily and weekly usage totals, editing and withdrawing rules on screen, and confirming push delivery on a real iPhone.

## Built with

Kiro, Kiro Crew, Python, React, MCP, Gemini API (free tier), Claude Code, Codex, Tailscale, GitHub Pages, Windows Job Objects

## Testing instructions (for judges)

1. **No account needed, about 2 minutes:** open https://stmega99-jpg.github.io/ghost-foreman/. It's the real app screen on sample data, running only in your browser and unable to open any network connection. Try: answer a question ("Answer the AIs' questions"), start a meeting ("Consult the AIs"; ticking Gemini asks for the per-meeting permission), adopt an option, press "Stop all" and lift it, switch Japanese/English. It's **simulated**, not the live app.
2. **Locally, same demo:** `python dev_server.py`, then http://127.0.0.1:8765/.
3. **The live app:** install into Kiro Crew 0.12.2 (`kirocrew app install <folder>`, `kirocrew app enable ghost-foreman`), as described in the README. Meetings with Claude Code, Codex and Gemini need those CLIs signed in and a Gemini free-tier key. The video shows the live app on a real Gateway.
4. **Tests:** `python -m unittest discover -s tests` (112 tests), `node tests/demo/engine_test.mjs`.

## Kiro usage (short form; the full write-up is `docs/KIRO_USAGE.md`)

Kiro built the app from Japanese instructions, one tested pull request at a time, and never merged or deployed without the owner's approval. Kiro Crew is the platform: slots, MCP tools, custom agents, a skill, notifications and sign-in. Steering holds seven safety rules that are also enforced in code. Not used: hooks, powers, Kiro's spec workflow (the specs in `.kiro/specs` were reconstructed from the PR history afterwards and say so).
