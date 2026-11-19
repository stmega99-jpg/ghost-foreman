// Renders the real ui/dist/index.mjs with real dashboard data in jsdom and drives it like a user.
import { JSDOM } from "jsdom";
import fs from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";

const dash = JSON.parse(fs.readFileSync(path.join(process.argv[2]), "utf8"));
const dom = new JSDOM("<!doctype html><div id=root></div>", { url: "http://localhost:5476/apps/ghost-foreman?q=" + (dash.questions.find((q) => q.status === "needs_human") || {}).id, pretendToBeVisual: true });
globalThis.window = dom.window;
globalThis.document = dom.window.document;
Object.defineProperty(globalThis, "navigator", { value: dom.window.navigator, configurable: true });
globalThis.HTMLElement = dom.window.HTMLElement;
globalThis.IS_REACT_ACT_ENVIRONMENT = true;
dom.window.HTMLElement.prototype.scrollIntoView = function () { globalThis.__scrolled = this.textContent.slice(0, 40); };

const calls = [];
globalThis.__api = {
  get: async (p) => { calls.push(["GET", p]); return JSON.parse(JSON.stringify(dash)); },
  post: async (p, b) => { calls.push(["POST", p, b]); return { ok: true }; },
};
globalThis.__confirms = [];
dom.window.confirm = (m) => { globalThis.__confirms.push(m); return true; };

const React = (await import("react")).default;
const { createRoot } = await import("react-dom/client");
const { act } = await import("react");
const mod = await import(pathToFileURL(path.resolve(process.argv[3])).href);
const App = mod.default;

const root = createRoot(document.getElementById("root"));
await act(async () => { root.render(React.createElement(App)); });
await act(async () => { await new Promise((r) => setTimeout(r, 50)); });

const text = () => document.body.textContent;
const expect = (name, cond) => { console.log((cond ? "PASS" : "FAIL") + "  " + name); if (!cond) process.exitCode = 1; };
const clickText = async (label, nth = 0) => {
  const el = [...document.querySelectorAll("button")].filter((b) => b.textContent.includes(label))[nth];
  if (!el) { console.log("  (no button: " + label + ")"); return false; }
  await act(async () => { el.dispatchEvent(new dom.window.MouseEvent("click", { bubbles: true })); });
  return true;
};

expect("header shows Gateway実接続", text().includes("Gateway実接続"));
expect("inbox shows a pending question", text().includes("AIからの確認") && text().includes("判断待ち"));
expect("deep link ?q= scrolled to the question", !!globalThis.__scrolled);
expect("answer buttons exist (今回のみ / 恒久ルール)", text().includes("今回のみ") && text().includes("恒久ルールにして回答"));

// free-text answer as permanent rule
const ta = document.querySelector("textarea");
if (ta) {
  await act(async () => {
    const setter = Object.getOwnPropertyDescriptor(dom.window.HTMLTextAreaElement.prototype, "value").set;
    setter.call(ta, "テスト回答です");
    ta.dispatchEvent(new dom.window.Event("input", { bubbles: true }));
  });
  const btn = [...ta.parentElement.querySelectorAll("button")].find((b) => b.textContent.includes("恒久ルールにして回答"));
  await act(async () => { btn.dispatchEvent(new dom.window.MouseEvent("click", { bubbles: true })); });
}
const resolveCall = calls.find((c) => c[0] === "POST" && c[1].endsWith("/questions/resolve"));
expect("free text -> POST /questions/resolve with permanent_policy", !!resolveCall && resolveCall[2].memory_mode === "permanent_policy" && resolveCall[2].answer_text === "テスト回答です");

// escaping: AI text containing HTML must be shown as text
const evil = JSON.parse(JSON.stringify(dash));
evil.questions[0].raw_question = "<img src=x onerror=alert(1)><b>bold</b>";
globalThis.__api.get = async () => JSON.parse(JSON.stringify(evil));
await act(async () => { root.render(React.createElement(App, { key: "again" })); });
await act(async () => { await new Promise((r) => setTimeout(r, 50)); });
expect("HTML in AI output is not interpreted", !document.querySelector("img[src='x']") && text().includes("<img src=x onerror=alert(1)>"));

// tabs
for (const [label, needle] of [["スロット", "実接続"], ["AI会議", "開催"], ["記憶・ルール", "確定"], ["ニュース", "要約して保存"], ["設定・費用", "未確認"], ["監査ログ", "監査"]]) {
  await clickText(label);
  expect("tab " + label + " renders (" + needle + ")", text().includes(needle));
}

// settings: enabling the privacy switch asks first
await clickText("設定・費用");
const cb = document.querySelector("input[type=checkbox]");
calls.length = 0;
await act(async () => { cb.dispatchEvent(new dom.window.MouseEvent("click", { bubbles: true })); });
expect("enabling the privacy switch shows a confirm dialog", globalThis.__confirms.length === 1 && globalThis.__confirms[0].includes("Gemini"));
const modeCall = calls.find((c) => c[1] && c[1].endsWith("/mode"));
expect("...and then POST /mode allow_unpublished_to_free_tier=true", !!modeCall && modeCall[2].allow_unpublished_to_free_tier === true);

// stop buttons
await clickText("スロット");
calls.length = 0;
await clickText("⏹ 停止", 0);
expect("slot stop -> POST /stop scope=slot", calls.some((c) => c[1] && c[1].endsWith("/stop") && c[2].scope === "slot"));
calls.length = 0;
await clickText("全停止");
expect("全停止 confirms then POST /stop scope=all", calls.some((c) => c[1] && c[1].endsWith("/stop") && c[2].scope === "all"));
// emergency stop banner: shown while a hold is active, and only an explicit confirmed click lifts it
const halted = JSON.parse(JSON.stringify(dash));
halted.halt = { all: false, projects: [], slots: [halted.slots[0].id], since: "2026-11-18T00:00:00", reason: "x", active: true };
globalThis.__api.get = async () => JSON.parse(JSON.stringify(halted));
await act(async () => { root.render(React.createElement(App, { key: "halted" })); });
await act(async () => { await new Promise((r) => setTimeout(r, 50)); });
expect("stop banner is shown while a hold is active", text().includes("緊急停止中") && text().includes("人間が再開を許可するまで"));
await clickText("スロット");
expect("the stopped slot is marked as waiting for human permission", text().includes("停止中（人間の許可待ち）"));
calls.length = 0; globalThis.__confirms.length = 0;
await clickText("▶ この停止を解除");
expect("slot resume asks first, then POST /stop resume_slot", globalThis.__confirms.length === 1 && calls.some((c) => c[1] && c[1].endsWith("/stop") && c[2].scope === "resume_slot" && c[2].target_id === halted.slots[0].id));
calls.length = 0; globalThis.__confirms.length = 0;
await clickText("停止をすべて解除");
expect("global resume asks first (and says nothing restarts by itself), then POST /stop resume_all", globalThis.__confirms.length === 1 && globalThis.__confirms[0].includes("自動では再開しません") && calls.some((c) => c[1] && c[1].endsWith("/stop") && c[2].scope === "resume_all"));
const noHalt = JSON.parse(JSON.stringify(dash));
noHalt.halt = { all: false, projects: [], slots: [], since: "", reason: "", active: false };
globalThis.__api.get = async () => JSON.parse(JSON.stringify(noHalt));
await act(async () => { root.render(React.createElement(App, { key: "nohalt" })); });
await act(async () => { await new Promise((r) => setTimeout(r, 50)); });
expect("no banner when nothing is stopped", !text().includes("🛑 緊急停止中"));

// AI meeting with Gemini: the permission to send this meeting's content is asked per meeting
const listing = { min_participants: 2, max_participants: 5, harnesses: [
  { id: "kiro", label: "Kiro", runtime: "kiro_crew", available: true, reason: "" },
  { id: "claude", label: "Claude Code", runtime: "external_cli", available: true, reason: "" },
  { id: "codex", label: "Codex", runtime: "external_cli", available: true, reason: "" },
  { id: "gemini", label: "Gemini", runtime: "gemini_api", available: true, reason: "", needs_consent: true, consent_note: "未公開の制作情報を含みます" },
] };
globalThis.__api.get = async (p) => { calls.push(["GET", p]); return JSON.parse(JSON.stringify(String(p).includes("/meetings/harnesses") ? listing : noHalt)); };
await act(async () => { root.render(React.createElement(App, { key: "gemini" })); });
await act(async () => { await new Promise((r) => setTimeout(r, 50)); });
await clickText("AI会議");
await act(async () => { await new Promise((r) => setTimeout(r, 30)); });
const setValue = async (el, value, proto, ev) => {
  await act(async () => {
    Object.getOwnPropertyDescriptor(proto, "value").set.call(el, value);
    el.dispatchEvent(new dom.window.Event(ev, { bubbles: true }));
  });
};
const consentBox = () => document.querySelector("input[type=checkbox][aria-label='この会議の内容を Gemini 無料枠に送ることを許可する']");
const holdButton = () => [...document.querySelectorAll("button")].find((b) => b.textContent === "開催");
expect("Gemini is offered with where it runs", [...document.querySelectorAll("option")].some((o) => o.value === "gemini" && o.textContent.includes("Gemini API 無料枠")));
expect("no Gemini permission box while Gemini is not chosen", !consentBox());
await setValue(document.querySelector("input[placeholder^='議題']"), "Gemini込みの議題", dom.window.HTMLInputElement.prototype, "input");
await setValue(document.querySelector("select[aria-label='参加者BのAI']"), "gemini", dom.window.HTMLSelectElement.prototype, "change");
expect("choosing Gemini shows the per-meeting permission box, unchecked", !!consentBox() && consentBox().checked === false && text().includes("この会議だけ"));
expect("...and the meeting cannot be started until it is checked", holdButton().disabled === true);
await act(async () => { consentBox().dispatchEvent(new dom.window.MouseEvent("click", { bubbles: true })); });
expect("checking it enables 開催", consentBox().checked === true && holdButton().disabled === false);
calls.length = 0;
await clickText("開催");
await act(async () => { await new Promise((r) => setTimeout(r, 20)); });
const startCall = calls.find((c) => c[0] === "POST" && c[1].endsWith("/meetings"));
expect("POST /meetings carries allow_unpublished_to_gemini=true and the Gemini participant",
  !!startCall && startCall[2].allow_unpublished_to_gemini === true && startCall[2].participants.some((p) => p.harness === "gemini"));
expect("the permission is reset for the next meeting", consentBox() && consentBox().checked === false);
await setValue(document.querySelector("select[aria-label='参加者BのAI']"), "kiro", dom.window.HTMLSelectElement.prototype, "change");
await setValue(document.querySelector("input[placeholder^='議題']"), "Kiroだけの議題", dom.window.HTMLInputElement.prototype, "input");
calls.length = 0;
await clickText("開催");
await act(async () => { await new Promise((r) => setTimeout(r, 20)); });
const kiroOnly = calls.find((c) => c[0] === "POST" && c[1].endsWith("/meetings"));
expect("a meeting without Gemini sends no permission", !!kiroOnly && kiroOnly[2].allow_unpublished_to_gemini === false && !consentBox());
// the minutes show what was decided for that meeting
const withMinutes = JSON.parse(JSON.stringify(noHalt));
withMinutes.meetings = [{ id: "mtg-g", topic: "t", status: "awaiting_human_adoption", participants: ["参加者A（x／Gemini）"], rounds: [], created_at: "",
  summary: { participants_detail: [{ speaker: "参加者A（x／Gemini）", label: "Gemini", harness: "gemini", runtime: "gemini_api", runtime_label: "Kiro Crew 外で実行（Gemini API 無料枠）", ran_on: "gemini", model: "gemini-2.5-flash-lite", verified: true }],
    outside_kiro_crew: true, gemini_consent: { asked: true, allowed: true, scope: "この会議のみ", decided_at: "2026-11-19T20:30:00+0900" }, options_for_human: [] } }];
globalThis.__api.get = async (p) => JSON.parse(JSON.stringify(String(p).includes("/meetings/harnesses") ? listing : withMinutes));
await act(async () => { root.render(React.createElement(App, { key: "minutes" })); });
await act(async () => { await new Promise((r) => setTimeout(r, 50)); });
await clickText("AI会議");
expect("the minutes say Gemini was allowed for this meeting only", text().includes("Gemini 無料枠への送信: この会議だけ許可") && text().includes("gemini-2.5-flash-lite"));
process.exit(process.exitCode || 0);
