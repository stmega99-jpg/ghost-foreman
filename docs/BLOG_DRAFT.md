---
title: "Ghost Foreman: your agents work, you have a life (built with Kiro for Kiroween 2026)"
published: false
description: "More AIs were supposed to mean more free time. Instead I became the full-time manager of my own assistants. Ghost Foreman is a Kiro Crew app that takes that supervising off your hands."
tags: kiro, ai, productivity, kiroween
cover_image:
---

> **Draft.** Before publishing: set `published: true`, add a cover image, check every link, and keep the sentence below that says this post is for Kiroween 2026. Publish it during the submission period (it must be a public post on a third-party site such as dev.to).

*This post is my entry for the Bonus Blog Prize of **Kiroween 2026**, the Kiro hackathon. The project is in the Frankenstein category and is also a Best Kiro Crew App entry.*

## More AIs, more supervising

I started running several AIs at once to get more done. It worked, but it changed my day in a way I didn't expect. Every few minutes one of them stopped to ask me something, often a small decision I had already made before. When I stepped away, all of them sat and waited. I had become the full-time manager of my own assistants.

If you're a solo developer, a founder, a writer, a researcher, or someone who doesn't write code at all and just works with several AIs, you've probably felt the same thing.

**Ghost Foreman** is my answer: a foreman that stands between your AIs and you, so you only make the decisions that are really yours.

> **Your agents work. You have a life.**

Code (MIT): https://github.com/stmega99-jpg/ghost-foreman · Demo with sample data: https://stmega99-jpg.github.io/ghost-foreman/

## What changes in your day

**You stop answering the same question twice.** When an AI asks something your rules already cover, Ghost Foreman answers for you, cites the rule, and the AI keeps working. Every answer goes into a decision record.

**You only see the questions that are really yours.** When no rule covers a question, Ghost Foreman doesn't guess. It asks that AI one follow-up question to find out what's at stake, then gives you one card with the options, the difference, the impact and a recommendation.

**Nothing becomes a rule by accident.** Your answer is one-time unless you say "make this our policy from now on". Rules stay inside their project unless you make them global.

**You can step away from the desk.** Switch to "Out" and answer from the Ghost Foreman app on your iPhone. It reaches your PC privately through Tailscale, not through the open internet. (Honest note: the phone app and its sign-in are tested in a real browser, but a push notification arriving on a real iPhone is not confirmed yet. Opening the app by hand always works.)

**You get four opinions instead of one.** The meeting room asks four *different* AIs (Kiro, Claude Code, Codex and Gemini) the same question. They write their ideas on their own, critique each other, and a separate organiser sums up what they agreed on, where they differ and what's still open, with options for you. Any topic works: planning something, critiquing a draft, getting unstuck on a problem. Nothing happens until you pick an option.

**You always have the final say.** One button stops every AI that Ghost Foreman manages: the Kiro Crew sessions it runs, and the Claude Code and Codex programs it started outside Kiro Crew for a meeting. (Apps and AI sessions you started yourself are not touched.) Only a person can lift the stop, and lifting it doesn't restart anything by itself.

## What works today (and what doesn't)

| Feature | Status |
|---|---|
| Answering from your rules, one follow-up question, a decision card for you | **Works** on a real Kiro Crew Gateway |
| One-time vs permanent answers, rules kept per project | **Works** |
| Emergency stop that only a person can lift | **Works**, including AIs started outside Kiro Crew |
| Meeting of four different AIs | **Works**. Not built yet: joining late, pausing, time and cost limits |
| Phone app over Tailscale | **Works** in a real-browser test. Push delivery to a real iPhone **not confirmed** |
| Japanese / English | **Works**, including meetings held in English |
| Public demo | **Sample data only**, labelled on screen |
| PC control | **Simulated** (records state only; no screen, mouse or keyboard control) |
| Voice control, scheduled news, conflict detection between AIs | **Not built** |

## Three design choices I care about

**1. A stop that only a human can undo.** When you press stop, the hold is saved *before* any AI is interrupted, so nothing can restart in between. Lifting it doesn't restart the work either. AIs started outside Kiro Crew run inside Windows Job Objects, so a stop ends the program and everything it started.

**2. Permission per meeting, for the one AI that needs it.** Gemini joins on its free tier, which means the meeting's text leaves your machine. So Gemini only takes part if you allow it **for that meeting**. Without that, the server refuses before anything is created or sent. The app also checks for a stop before every request to Gemini, so after a stop the same text is never retried on another model. There is no code path to a pay-per-use API at all.

**3. Don't trust what an AI says about itself.** In my first live four-AI meeting, Gemini introduced itself as Claude. Ghost Foreman records which AI really answered from *what it started*, not from what the AI wrote, and flags a self-introduction that doesn't match.

## The one place I left Kiro Crew

Kiro Crew 0.12.2 doesn't let an app choose which AI runs in a session. For the meeting room only, Ghost Foreman starts `claude` and `codex` directly, as text only: tools, MCP, web search, hooks and file writes are off, and there are no API keys in their environment. The screen and the minutes label them "outside Kiro Crew". Everything else uses Kiro Crew's own sessions, notifications and sign-in.

## How Kiro helped a non-programmer build this

I don't write code. I gave Kiro instructions in Japanese, and Kiro planned, wrote and tested the code one pull request at a time (18 so far). For each one it ran the tests and, where it could, checked the result on the real Gateway and in a real browser on PC and phone widths before I approved the merge. Kiro never merged or deployed on its own.

Some honest notes:

- The steering file holds seven safety rules (for example "never switch to a paid API without permission" and "ask an AI back at most once per question"). They're also enforced in code and tests.
- I did **not** use hooks, powers or Kiro's spec workflow. The `.kiro/specs` requirements, design and tasks were **reconstructed afterwards** from the pull-request history, and they say so.
- Real testing found real bugs, and later pull requests fixed them: a Gemini retry that could continue after a stop, Japanese text left in English meeting minutes, README sentences that claimed more than the code did.

## Try it without any account

The demo runs the same screen on made-up sample data inside your browser: https://stmega99-jpg.github.io/ghost-foreman/. The page can't open any network connection (its Content-Security-Policy is `connect-src 'none'`), so it can't reach an AI, an API key or anyone's computer. Only the five files the page needs are published (plus a one-line redirect page). It's labelled "Demo sample (simulated)": it shows how the app works, not the live app.

## What's next

Spotting when two AIs disagree with each other, daily and weekly usage totals, editing and withdrawing rules on screen, and confirming push delivery on a real iPhone.

*Built for Kiroween 2026. #KiroweenHackathon26*
