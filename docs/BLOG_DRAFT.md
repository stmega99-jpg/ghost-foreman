---
title: "Ghost Foreman: a foreman for your AI agents, built with Kiro (Kiroween 2026)"
published: false
description: "A Kiro Crew app that answers your AI agents' questions from rules you set, runs a four-AI meeting room, and has a stop button only a human can undo. Built for the Kiroween 2026 hackathon."
tags: kiro, ai, hackathon, kiroween
cover_image:
---

> **Draft.** Before publishing: set `published: true`, add a cover image, check every link, and keep the sentence below that says this post is for Kiroween 2026. Publish it during the submission period (it must be a public post on a third-party site such as dev.to).

*This post is my entry for the Bonus Blog Prize of **Kiroween 2026** (Kiro hackathon). The project is in the Frankenstein category and is also a Best Kiro Crew App entry.*

## The problem

I run several AI coding agents at once. They are fast, but each one stops every few minutes to ask something: "JSON or SQLite?", "may I add a dependency?". If I'm away from the PC, all of them sit and wait. I also don't want one agent to quietly decide something that changes my design.

**Ghost Foreman** is a small foreman that sits between the agents and me:

- If a rule I already set covers the question, it answers for me, **cites the rule**, and the agent keeps going.
- If nothing covers it, it **does not guess**. It asks the agent one follow-up question, then sends me clear options with a recommendation, on my phone.
- Whatever I answer is **one-time by default**. Only an explicit "keep as a rule" becomes a rule.

It is a [Kiro Crew](https://kiro.dev) app: it uses Kiro Crew's slots, MCP, agents, notifications and auth, and adds the foreman's judgement on top.

Code: https://github.com/stmega99-jpg/ghost-foreman (MIT).

## What works today (and what doesn't)

I would rather tell you this up front.

| Feature | Status |
|---|---|
| Answering agents' questions from rules, one reverse question, options for me | **Works** on a real Kiro Crew Gateway |
| One-time vs permanent answers, project isolation | **Works** |
| Emergency stop that only a human can lift (also ends AIs started outside Kiro Crew) | **Works** |
| Four-AI meeting room (Kiro, Claude Code, Codex, Gemini) | **Works**; some controls are missing (joining late, pausing) |
| Phone app over Tailscale | **Works** in a real-Chrome test; a push reaching a real iPhone is **not confirmed** |
| Japanese / English screen | **Works**, including English meetings |
| PC operation lease | **Simulated only** (state is recorded; no screen, mouse or keyboard control) |
| Scheduled news, voice control | **Not implemented** |

## Three design choices I'm happy with

**1. A stop button that only a human can undo.** When I press stop, the hold is stored *before* any session is interrupted, so nothing can restart in between. Lifting the stop does not restart the work either. AIs I started outside Kiro Crew run inside Windows Job Objects, so a stop ends the CLI and every child process.

**2. Permission per meeting, for the one AI that needs it.** The meeting room can include Gemini on its free tier. A meeting's text is unpublished project text, so Gemini only takes part if I tick a permission **for that meeting**. Without it the server refuses before anything is created or sent. Only the literal JSON `true` counts. The permission ends with the meeting. Before every request to the Gemini API the app checks for a stop, because an HTTP request can't be cancelled: after a stop, the same text must not be retried on another model.

**3. Don't trust what an AI says about itself.** In my first live four-AI meeting, Gemini introduced itself as Claude. The app records which AI really ran from *what it started*, not from the text, and shows a warning when the self-introduction doesn't match.

## The one place I left Kiro Crew

Kiro Crew 0.12.2 doesn't let an app choose a slot's backend. For the meeting room only, Ghost Foreman starts `claude` and `codex` directly, with tools, MCP, web search, hooks and file writes turned off, and no API keys in their environment. They are labelled "outside Kiro Crew" on screen and in the minutes. Everything else stays inside Kiro Crew.

## How Kiro helped

I'm not a programmer; I directed in Japanese and Kiro wrote and tested the code, one pull request at a time (14 merged so far). For each one it ran the tests and, where it could, checked the result on the real Gateway and in real Chrome before I approved the merge. Kiro never merged or deployed by itself.

Some honest notes:

- The steering file has seven safety rules (for example "never switch to a paid API without permission" and "at most one reverse question per agent question"). They are also enforced in code and tests.
- I did **not** use hooks, powers or Kiro's spec workflow. The `.kiro/specs` requirements, design and tasks were **reconstructed afterwards** from the pull-request history, and say so at the top.
- Real testing found real bugs: a Gemini retry that could continue after a stop, Japanese text left in English meeting minutes, README sentences that claimed more than the code did. They were fixed in later pull requests.

## Try it without any account

There is a demo page that runs the same screen on made-up sample data in the browser. Its Content-Security-Policy is `connect-src 'none'`, so the page can't open any connection: no AI, no key, no personal computer. It is labelled "Demo sample (simulated)". Open the hosted copy at https://stmega99-jpg.github.io/ghost-foreman/ (it is published from only five static files), or run it yourself with `python dev_server.py`.

## What's next

Conflict detection between two AIs' opinions, daily and weekly usage totals, editing and withdrawing rules in the screen, and confirming a push on a real iPhone.

*Built for Kiroween 2026. #KiroweenHackathon26*
