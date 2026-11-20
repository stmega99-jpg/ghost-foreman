// Unit tests for the demo's sample-data engine (demo/engine.mjs). No browser, no network.
// Usage: node tests/demo/engine_test.mjs
import { createEngine, localize, GEMINI_CONSENT_REQUIRED } from "../../demo/engine.mjs";
let failed = 0;
const expect = (name, cond, extra = "") => { console.log((cond ? "PASS" : "FAIL") + "  " + name + (extra ? "  " + extra : "")); if (!cond) { failed++; process.exitCode = 1; } };
const rejects = async (p) => { try { await p; return null; } catch (e) { return e; } };
const JA = /[\u3040-\u30ff\u4e00-\u9fff]/;
const strings = (v, out = []) => { if (typeof v === "string") out.push(v); else if (v && typeof v === "object") Object.values(v).forEach((x) => strings(x, out)); return out; };

let lang = "ja";
let now = 1_700_000_000_000;
const make = () => createEngine({ getLang: () => lang, clock: () => new Date(now) });
let e = make();
const dash = () => e.handle("GET", "/dashboard");

// the sample data
let d = await dash();
expect("the dashboard has the pieces the screen reads", ["projects", "slots", "questions", "policies", "audits", "meetings", "ideas", "news", "halt", "mode_state", "usage", "desktop_lease"].every((k) => k in d));
expect("every slot says it is a sample, not a live AI", d.slots.length >= 6 && d.slots.every((s) => s.is_live === false));
expect("the mode is labelled simulated", d.mode_state.gateway_mode === "simulated_gateway");
expect("the sample projects come from five different fields", d.projects.map((p) => p.name).join("|") === "アクションゲーム制作（見本）|家計簿アプリ開発（見本）|YouTubeチャンネル運営（見本）|オンラインショップ開業（見本）|恋愛小説の執筆（見本）" && new Set(d.slots.map((s) => s.project_id)).size === 5 && new Set(d.questions.map((q) => q.project_id)).size === 3);
expect("two questions wait for the human and one was answered by a rule", d.questions.filter((q) => q.status === "needs_human").length === 2 && d.questions.some((q) => q.status === "auto_resolved"));
expect("the reply is Japanese in Japanese", strings(d.questions[0]).some((x) => JA.test(x)));
lang = "en";
d = await dash();
expect("the sample text switches to English with the language", !strings({ q: d.questions, p: d.projects, s: d.slots, pol: d.policies, n: d.news, a: d.audits }).some((x) => JA.test(x)), strings({ q: d.questions, s: d.slots, pol: d.policies, n: d.news, a: d.audits }).filter((x) => JA.test(x)).slice(0, 2).join(" | "));
expect("in English too", d.projects.map((p) => p.name).join("|") === "Action game (sample)|Budgeting app (sample)|Running a YouTube channel (sample)|Opening an online shop (sample)|Writing a romance novel (sample)");
lang = "ja";

// a person's answer: one-time stays one-time, only an explicit choice makes a permanent rule
const nPol = (await dash()).policies.length;
let r = await e.handle("POST", "/questions/resolve", { question_id: "q-demo-1", answer_text: "A を採用", memory_mode: "one_time" });
expect("a one-time answer resolves the question", r.status === "human_resolved" && r.final_answer === "A を採用" && r.promoted_policy_id === "");
d = await dash();
expect("a one-time answer does NOT create a permanent policy", d.policies.length === nPol);
expect("the answer is recorded in the decision log", d.audits.some((a) => a.actor === "human" && a.action_type === "human_answer_one_time"));
expect("an answered question cannot be answered twice", (await rejects(e.handle("POST", "/questions/resolve", { question_id: "q-demo-1", answer_text: "x" }))).status === 400);
r = await e.handle("POST", "/questions/resolve", { question_id: "q-demo-2", answer_text: "使わない", memory_mode: "permanent_policy", policy_title: "有料APIは使わない" });
expect("only memory_mode=permanent_policy makes a rule", r.promoted_policy_id !== "" && (await dash()).policies.length === nPol + 1);
expect("an unknown memory_mode is treated as one-time", await (async () => { e = make(); const x = await e.handle("POST", "/questions/resolve", { question_id: "q-demo-1", answer_text: "x", memory_mode: "yes" }); return x.promoted_policy_id === ""; })());

// asking back: the AI is asked at most once per question (max_probes = 1)
e = make();
await e.handle("POST", "/questions/inquire", { question_id: "q-demo-1", human_inquiry: "なぜ？", re_probe_agent: true });
await e.handle("POST", "/questions/inquire", { question_id: "q-demo-1", human_inquiry: "もう一度", re_probe_agent: true });
const q1 = (await dash()).questions.find((q) => q.id === "q-demo-1");
expect("the assigned AI is asked back only once", q1.probe_history.filter((p) => p.role === "agent_re_clarification").length === 1 && q1.probe_count === 1);
expect("the Ghost explains every time", q1.probe_history.filter((p) => p.role === "ghost_explanation").length === 2);

// the emergency stop and the human-only resume
e = make();
r = await e.handle("POST", "/stop", { scope: "all" });
d = await dash();
expect("the emergency stop stops every slot", r.ok && d.halt.active && d.slots.every((s) => s.status === "stopped"));
expect("no meeting can start during a stop", (await rejects(e.handle("POST", "/meetings", { topic: "x", participants: [{ perspective: "a", harness: "kiro" }, { perspective: "b", harness: "kiro" }] }))).status === 409);
await e.handle("POST", "/stop", { scope: "resume_all" });
d = await dash();
expect("a resume releases the stop but does not restart work", !d.halt.active && d.slots.every((s) => s.status === "idle"));
await e.handle("POST", "/stop", { scope: "slot", target_id: "slot-01" });
expect("one slot can be stopped alone", (await dash()).slots.filter((s) => s.status === "stopped").map((s) => s.id).join() === "slot-01");
expect("a bad stop scope is refused", (await rejects(e.handle("POST", "/stop", { scope: "slot" }))).status === 400);

// meetings: the Gemini permission is enforced the same way as in the real app
e = make();
const withGemini = [{ perspective: "a", harness: "gemini" }, { perspective: "b", harness: "kiro" }];
const nM = (await dash()).meetings.length;
for (const bad of [undefined, false, "true", 1, "yes"]) {
  const err = await rejects(e.handle("POST", "/meetings", { topic: "t", participants: withGemini, ...(bad === undefined ? {} : { allow_unpublished_to_gemini: bad }) }));
  expect(`Gemini without the literal true is refused (${JSON.stringify(bad)})`, err && err.status === 400 && err.message === localize(GEMINI_CONSENT_REQUIRED, "ja"));
}
expect("a refused request creates no meeting", (await dash()).meetings.length === nM);
lang = "en";
expect("the refusal is in English on an English screen", (await rejects(e.handle("POST", "/meetings", { topic: "t", participants: withGemini }))).message === localize(GEMINI_CONSENT_REQUIRED, "en"));
lang = "ja";
expect("a topic is required", (await rejects(e.handle("POST", "/meetings", { topic: " ", participants: withGemini, allow_unpublished_to_gemini: true }))).status === 400);
expect("2 to 5 participants", (await rejects(e.handle("POST", "/meetings", { topic: "t", participants: [{ perspective: "a", harness: "kiro" }] }))).status === 400);
const m = await e.handle("POST", "/meetings", { project_id: "proj-game", topic: "ボタンの置き場所", participants: withGemini, synthesizer_harness: "kiro", allow_unpublished_to_gemini: true });
expect("an allowed meeting starts and is recorded as a sample", m.status === "running" && m.summary.live === false && m.summary.gemini_consent.allowed === true && m.summary.gemini_consent.scope === "この会議のみ");
expect("no AI is shown as having really run", m.summary.participants_detail.every((p) => p.ran_on === "" && p.verified === false));
expect("it cannot be adopted before it has finished", (await rejects(e.handle("POST", "/meetings/adopt", { meeting_id: m.id, option_id: "opt1", target_slot_id: "slot-03" }))).status === 400);
let seen = [];
for (let i = 0; i < 6; i++) { now += 1300; const x = (await dash()).meetings.find((y) => y.id === m.id); seen.push(`${x.status}:${x.rounds.length}`); }
expect("the rounds appear one by one, then it waits for the human", seen.join() === "running:1,running:2,running:3,awaiting_human_adoption:3,awaiting_human_adoption:3,awaiting_human_adoption:3", seen.join());
d = await dash();
const fin = d.meetings.find((y) => y.id === m.id);
expect("the finished meeting offers options, with a save-only choice", fin.summary.options_for_human.length === 3 && fin.summary.options_for_human.some((o) => o.id === "hold_as_idea"));
r = await e.handle("POST", "/meetings/adopt", { meeting_id: m.id, option_id: "opt2", target_slot_id: "slot-03" });
expect("adopting schedules work only on a slot the human picked", r.action === "scheduled_to_slot" && (await dash()).slots.find((s) => s.id === "slot-03").next_task.includes("opt2"));
{ const sl = (await dash()).slots.find((x) => x.id === "slot-03"); expect("the sample AI only records that it got the plan, and stays a sample", sl.is_live === false && sl.history.at(-1).text.includes("見本") && sl.history.at(-1).text.includes("実際のAIには何も送っていません")); }
expect("an adopted meeting cannot be adopted again", (await rejects(e.handle("POST", "/meetings/adopt", { meeting_id: m.id, option_id: "opt1", target_slot_id: "slot-03" }))).status === 400);
const m2 = await e.handle("POST", "/meetings", { topic: "もう一つ", participants: [{ perspective: "a", harness: "claude" }, { perspective: "b", harness: "codex" }] });
now += 6000;
r = await e.handle("POST", "/meetings/adopt", { meeting_id: m2.id, option_id: "hold_as_idea" });
expect("save-only puts the minutes in the idea notebook", r.action === "saved_to_ideas" && (await dash()).ideas.some((i) => i.id === r.idea_id));
await e.handle("POST", "/stop", { scope: "all" });
expect("work cannot be handed to a stopped slot", (await rejects((async () => { const m3 = (e = make(), await e.handle("POST", "/meetings", { topic: "x", participants: [{ perspective: "a", harness: "kiro" }, { perspective: "b", harness: "kiro" }] })); now += 6000; await e.handle("POST", "/stop", { scope: "slot", target_id: "slot-03" }); return e.handle("POST", "/meetings/adopt", { meeting_id: m3.id, option_id: "opt1", target_slot_id: "slot-03" }); })())).status === 409);

// projects: add, rename, archive, re-open; no delete
e = make();
lang = "ja";
const np = await e.handle("POST", "/projects", { name: " 家計簿アプリ ", description: "毎月の支出" });
expect("a project can be added, with a generated id", /^proj-/.test(np.id) && np.name === "家計簿アプリ" && np.status === "active" && (await dash()).projects.some((p) => p.id === np.id));
expect("an empty or too long name is refused", (await rejects(e.handle("POST", "/projects", { name: " " }))).status === 400 && (await rejects(e.handle("POST", "/projects", { name: "x".repeat(81) }))).status === 400);
expect("two active projects cannot share a name", (await rejects(e.handle("POST", "/projects", { name: "家計簿アプリ" }))).status === 400);
r = await e.handle("POST", "/projects/update", { project_id: np.id, name: "家計簿アプリ開発" });
expect("a project can be renamed", r.name === "家計簿アプリ開発" && r.description === "毎月の支出");
r = await e.handle("POST", "/projects/update", { project_id: "proj-game", status: "archived" });
d = await dash();
expect("archiving keeps the project, its questions and its rules", r.status === "archived" && d.projects.some((p) => p.id === "proj-game") && d.questions.some((q) => q.project_id === "proj-game") && d.policies.some((p) => p.project_id === "proj-game"));
expect("a bad status or an unknown project is refused", (await rejects(e.handle("POST", "/projects/update", { project_id: "proj-game", status: "deleted" }))).status === 400 && (await rejects(e.handle("POST", "/projects/update", { project_id: "nope", name: "x" }))).status === 400);
r = await e.handle("POST", "/projects/update", { project_id: "proj-game", status: "active" });
expect("an archived project can be re-opened", r.status === "active");
// the rest
e = make();
expect("the harness list has all four AIs and the Gemini consent note", await (async () => { const h = await e.handle("GET", "/meetings/harnesses"); return h.harnesses.length === 4 && h.harnesses.find((x) => x.id === "gemini").consent_note.length > 20; })());
expect("a test notification is refused (the demo sends none)", (await e.handle("POST", "/notify/test", {})).ok === false);
r = await e.handle("POST", "/news/summarize", { url: "https://example.org/a", project_id: "proj-game" });
expect("a news address is never opened: a fixed sample comes back", r.title.includes("見本") && (await dash()).news[0].url === "https://example.org/a");
expect("a bad news address is refused", (await rejects(e.handle("POST", "/news/summarize", { url: "javascript:alert(1)" }))).status === 422);
r = await e.handle("POST", "/mode", { allow_unpublished_to_free_tier: "yes" });
expect("the free-tier switch only turns on with a real true", r.allow_unpublished_to_free_tier === false);
r = await e.handle("POST", "/mode", { allow_unpublished_to_free_tier: true, mode: "sleep" });
expect("the mode and the switch can be changed", r.allow_unpublished_to_free_tier === true && r.mode === "sleep");
expect("an unknown endpoint is a 404", (await rejects(e.handle("POST", "/nope", {}))).status === 404);
expect("the engine source makes no network call", await (async () => { const fs = await import("node:fs"); const src = fs.readFileSync(new URL("../../demo/engine.mjs", import.meta.url), "utf8") + fs.readFileSync(new URL("../../demo/sdk.mjs", import.meta.url), "utf8"); return !/\bfetch\s*\(|XMLHttpRequest|WebSocket|EventSource|sendBeacon|import\s*\(\s*["']https?:/.test(src.replace(/\/\/.*$/gm, "")); })());
console.log(failed ? `${failed} FAILED` : "ALL PASSED");
process.exit(failed ? 1 : 0);