// Renders the real ui/dist/index.mjs with real dashboard data in jsdom and drives it like a user.
import { JSDOM } from "jsdom";
import fs from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";

const dash = JSON.parse(fs.readFileSync(path.join(process.argv[2]), "utf8"));
const pendingId = (dash.questions.find((q) => q.status === "needs_human") || {}).id;
const dom = new JSDOM("<!doctype html><div id=root></div>", { url: "http://localhost:5476/apps/ghost-foreman?q=" + pendingId, pretendToBeVisual: true });
globalThis.window = dom.window;
globalThis.document = dom.window.document;
Object.defineProperty(globalThis, "navigator", { value: dom.window.navigator, configurable: true });
globalThis.HTMLElement = dom.window.HTMLElement;
globalThis.IS_REACT_ACT_ENVIRONMENT = true;
dom.window.HTMLElement.prototype.scrollIntoView = function () { globalThis.__scrolled = this.textContent.slice(0, 40); };
dom.window.scrollTo = () => {};

const calls = [];
const clone = (x) => JSON.parse(JSON.stringify(x));
globalThis.__api = {
  get: async (p) => { calls.push(["GET", p]); return clone(dash); },
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
const settle = (ms = 50) => act(async () => { await new Promise((r) => setTimeout(r, ms)); });
const render = async (key, data) => {
  if (data) globalThis.__api.get = async (p) => { calls.push(["GET", p]); return clone(typeof data === "function" ? data(p) : data); };
  await act(async () => { root.render(React.createElement(App, { key })); });
  await settle();
};
const text = () => document.body.textContent;
const expect = (name, cond) => { console.log((cond ? "PASS" : "FAIL") + "  " + name); if (!cond) process.exitCode = 1; };
const buttons = (label) => [...document.querySelectorAll("button")].filter((b) => b.textContent.includes(label));
const clickText = async (label, nth = 0) => {
  const el = buttons(label)[nth];
  if (!el) { console.log("  (no button: " + label + ")"); return false; }
  await act(async () => { el.dispatchEvent(new dom.window.MouseEvent("click", { bubbles: true })); });
  return true;
};
const click = async (el) => { await act(async () => { el.dispatchEvent(new dom.window.MouseEvent("click", { bubbles: true })); }); };
const setValue = async (el, value, proto, ev) => {
  await act(async () => {
    Object.getOwnPropertyDescriptor(proto, "value").set.call(el, value);
    el.dispatchEvent(new dom.window.Event(ev, { bubbles: true }));
  });
};
const home = async () => { await clickText("ホームへ戻る"); await settle(10); };
const noHalt = clone(dash);
noHalt.halt = { all: false, projects: [], slots: [], since: "", reason: "", active: false };

// ---------------------------------------------------------------- opening
await render("first");
expect("header shows Gateway実接続 with a plain-words label", text().includes("Gateway実接続") && text().includes("つながっています"));
expect("a deep link ?q= opens the AI's question directly", text().includes("AIからの確認") && text().includes("判断待ち") && !!globalThis.__scrolled);
expect("answer buttons are in plain words, with the permanent rule marked", text().includes("今回だけ") && text().includes("これからもこの方針にする") && text().includes("恒久ルールにして回答"));

const ta = document.querySelector("textarea");
if (ta) {
  await setValue(ta, "テスト回答です", dom.window.HTMLTextAreaElement.prototype, "input");
  const btn = [...ta.parentElement.querySelectorAll("button")].find((b) => b.textContent.includes("恒久ルールにして回答"));
  await click(btn);
}
const resolveCall = calls.find((c) => c[0] === "POST" && c[1].endsWith("/questions/resolve"));
expect("free text -> POST /questions/resolve with permanent_policy", !!resolveCall && resolveCall[2].memory_mode === "permanent_policy" && resolveCall[2].answer_text === "テスト回答です");

// escaping: AI text containing HTML must be shown as text
const evil = clone(dash);
evil.questions[0].raw_question = "<img src=x onerror=alert(1)><b>bold</b>";
await render("evil", evil);
expect("HTML in AI output is not interpreted", !document.querySelector("img[src='x']") && text().includes("<img src=x onerror=alert(1)>"));

// ---------------------------------------------------------------- home: starts from what the person wants to do
await render("home", dash);
await home();
const homeText = text();
expect("home asks 何をしますか？ and offers the five things to do", homeText.includes("何をしますか？") && ["AIたちに相談する", "AIからの質問に答える", "AIたちの様子を見る", "ニュースを調べる", "決めたルールを見る"].every((t) => homeText.includes(t)));
expect("home says there is something waiting for the human, with a button", homeText.includes("あなたの判断を待っているAIがいます") && buttons("答える →").length === 1);
expect("home has the three situations, in plain words", ["家にいる", "外出中", "おやすみ"].every((t) => homeText.includes(t)));
expect("technical words are not on the home screen", !["スロット", "監査", "実行記録", "トークン", "ハッシュ", "external", "harness"].some((t) => homeText.includes(t)));
expect("the stop button is on the home screen", buttons("全停止").length === 1);
calls.length = 0;
await clickText("外出中");
expect("choosing a situation -> POST /mode", calls.some((c) => c[0] === "POST" && c[1].endsWith("/mode") && c[2].mode === "away"));
const quiet = clone(dash); quiet.questions = quiet.questions.map((q) => ({ ...q, status: "human_resolved" }));
await render("quiet", quiet);
await home();
expect("with nothing waiting, home says so", text().includes("判断を待っているものはありません") && buttons("答える →").length === 0);

// each thing to do opens its own screen, with a way back
for (const [tile, needle] of [["AIたちに相談する", "何を相談しますか"], ["AIからの質問に答える", "AIからの確認"], ["AIたちの様子を見る", "本物のAI"], ["ニュースを調べる", "要約して保存"], ["決めたルールを見る", "あなたが決めた方針"], ["詳細・設定", "ふだんは使わない"]]) {
  await render("nav-" + tile, dash);
  await home();
  await clickText(tile);
  await settle(20);
  expect(`"${tile}" opens its screen (${needle}) with a way back`, text().includes(needle) && buttons("ホームへ戻る").length === 1);
}

// ---------------------------------------------------------------- details: technical settings and records
const goDetails = async (section) => { await render("d-" + section); await home(); await clickText("詳細・設定"); await settle(20); await clickText(section); await settle(20); };
for (const [section, needle] of [["通知・送信の設定", "Gemini"], ["費用と使用量", "未確認"], ["外部AIの実行記録", "ハッシュだけ"], ["通知の履歴", "held_resident"], ["判断の記録", "原文"], ["AIの一覧", "本物のAI"]]) {
  await goDetails(section);
  expect(`details: ${section} (${needle})`, text().includes(needle));
}

// settings: enabling the privacy switch asks first
await goDetails("通知・送信の設定");
const cb = document.querySelector("input[type=checkbox]");
calls.length = 0;
await click(cb);
expect("enabling the privacy switch shows a confirm dialog", globalThis.__confirms.length === 1 && globalThis.__confirms[0].includes("Gemini"));
const modeCall = calls.find((c) => c[1] && c[1].endsWith("/mode"));
expect("...and then POST /mode allow_unpublished_to_free_tier=true", !!modeCall && modeCall[2].allow_unpublished_to_free_tier === true);

// ---------------------------------------------------------------- stop buttons
await goDetails("AIの一覧");
calls.length = 0;
await clickText("⏹ 停止", 0);
expect("slot stop -> POST /stop scope=slot", calls.some((c) => c[1] && c[1].endsWith("/stop") && c[2].scope === "slot"));
calls.length = 0;
await clickText("全停止");
expect("全停止 confirms then POST /stop scope=all", calls.some((c) => c[1] && c[1].endsWith("/stop") && c[2].scope === "all"));
// emergency stop banner: shown on every screen while a hold is active, and only an explicit confirmed click lifts it
const halted = clone(dash);
halted.halt = { all: false, projects: [], slots: [halted.slots[0].id], since: "2026-11-18T00:00:00", reason: "x", active: true };
await render("halted", halted);
expect("stop banner is shown while a hold is active", text().includes("緊急停止中") && text().includes("人間が再開を許可するまで"));
await home();
expect("...also on the home screen", text().includes("緊急停止中"));
await clickText("詳細・設定"); await settle(20); await clickText("AIの一覧"); await settle(20);
expect("the stopped slot is marked as waiting for human permission", text().includes("停止中（人間の許可待ち）"));
calls.length = 0; globalThis.__confirms.length = 0;
await clickText("▶ この停止を解除");
expect("slot resume asks first, then POST /stop resume_slot", globalThis.__confirms.length === 1 && calls.some((c) => c[1] && c[1].endsWith("/stop") && c[2].scope === "resume_slot" && c[2].target_id === halted.slots[0].id));
calls.length = 0; globalThis.__confirms.length = 0;
await clickText("停止をすべて解除");
expect("global resume asks first (and says nothing restarts by itself), then POST /stop resume_all", globalThis.__confirms.length === 1 && globalThis.__confirms[0].includes("自動では再開しません") && calls.some((c) => c[1] && c[1].endsWith("/stop") && c[2].scope === "resume_all"));
await render("nohalt", noHalt);
expect("no banner when nothing is stopped", !text().includes("🛑 緊急停止中"));

// ---------------------------------------------------------------- consulting the AIs (meetings), Gemini permission per meeting
const listing = { min_participants: 2, max_participants: 5, harnesses: [
  { id: "kiro", label: "Kiro", runtime: "kiro_crew", available: true, reason: "" },
  { id: "claude", label: "Claude Code", runtime: "external_cli", available: true, reason: "" },
  { id: "codex", label: "Codex", runtime: "external_cli", available: false, reason: "Codex にログインしていません" },
  { id: "gemini", label: "Gemini", runtime: "gemini_api", available: true, reason: "", needs_consent: true, consent_note: "未公開の制作情報を含みます" },
] };
const serve = (base) => (p) => (String(p).includes("/meetings/harnesses") ? listing : base);
const consultScreen = async (key, base) => { await render(key, serve(base)); await home(); await clickText("AIたちに相談する"); await settle(30); };
const box = (label) => [...document.querySelectorAll("input[type=checkbox]")].find((el) => el.getAttribute("aria-label") === label);
const consentBox = () => box("この会議の内容を Gemini 無料枠に送ることを許可する");
const startButton = () => buttons("この内容で相談を始める")[0];
const topicInput = () => document.querySelector("input[aria-label='相談したいこと']");

await consultScreen("consult", noHalt);
expect("each AI is offered as a choice, with a plain description and where it runs", ["Kiro", "Claude Code", "Codex", "Gemini"].every((n) => !!box(n + "に相談する")) && text().includes("Google のAIです") && text().includes("Kiro Crew の外"));
expect("an AI that cannot run is shown with the reason and cannot be picked", box("Codexに相談する").disabled === true && text().includes("Codex にログインしていません") && text().includes("いまは使えません"));
expect("the AIs that can run are picked for you (not Gemini, which needs a permission)", box("Kiroに相談する").checked && box("Claude Codeに相談する").checked && !box("Geminiに相談する").checked);
expect("no Gemini permission box while Gemini is not picked", !consentBox());
expect("the start button is off until a topic is typed, and says why", startButton().disabled === true && text().includes("相談したいことを入力してください"));
await setValue(topicInput(), "Gemini込みの議題", dom.window.HTMLInputElement.prototype, "input");
expect("with a topic and two AIs the meeting can start", startButton().disabled === false);
await click(box("Geminiに相談する"));
expect("picking Gemini shows the per-meeting permission box, unchecked", !!consentBox() && consentBox().checked === false && text().includes("この会議だけ"));
expect("...and the meeting cannot start until it is checked, and says why", startButton().disabled === true && text().includes("Gemini を使うには"));
await click(consentBox());
expect("checking it enables the start button", consentBox().checked === true && startButton().disabled === false);
calls.length = 0;
await click(startButton());
await settle(20);
const startCall = calls.find((c) => c[0] === "POST" && c[1].endsWith("/meetings"));
expect("POST /meetings carries allow_unpublished_to_gemini=true and the Gemini participant", !!startCall && startCall[2].allow_unpublished_to_gemini === true && startCall[2].participants.some((p) => p.harness === "gemini") && startCall[2].participants.length === 3);
expect("each picked AI got its own point of view", new Set(startCall[2].participants.map((p) => p.perspective)).size === 3);
expect("the permission is reset for the next meeting", !!consentBox() && consentBox().checked === false && startButton().disabled === true);
await click(box("Geminiに相談する"));
await setValue(topicInput(), "Kiroだけの議題", dom.window.HTMLInputElement.prototype, "input");
calls.length = 0;
await click(startButton());
await settle(20);
const noGemini = calls.find((c) => c[0] === "POST" && c[1].endsWith("/meetings"));
expect("a meeting without Gemini sends no permission", !!noGemini && noGemini[2].allow_unpublished_to_gemini === false && !consentBox());

// the detailed settings: a point of view and an AI for each participant, and the organiser
await clickText("くわしく設定する");
expect("detailed settings show a point of view and an AI per participant", !!document.querySelector("input[aria-label='参加者Aの視点']") && !!document.querySelector("select[aria-label='参加者AのAI']") && !!document.querySelector("select[aria-label='まとめ役のAI']"));
await setValue(document.querySelector("select[aria-label='参加者BのAI']"), "gemini", dom.window.HTMLSelectElement.prototype, "change");
await setValue(topicInput(), "くわしい設定の議題", dom.window.HTMLInputElement.prototype, "input");
expect("Gemini chosen there also needs the permission for this meeting", !!consentBox() && startButton().disabled === true);
await click(consentBox());
calls.length = 0;
await click(startButton());
await settle(20);
const adv = calls.find((c) => c[0] === "POST" && c[1].endsWith("/meetings"));
expect("the detailed settings are what is sent", !!adv && adv[2].allow_unpublished_to_gemini === true && adv[2].participants[1].harness === "gemini" && adv[2].participants[0].perspective.length > 0);

// the minutes
const minutes = clone(noHalt);
const person = { speaker: "参加者A（x／Gemini）", label: "Gemini", harness: "gemini", runtime: "gemini_api", runtime_label: "Kiro Crew 外で実行（Gemini API 無料枠）", ran_on: "gemini", model: "gemini-2.5-flash-lite", verified: true };
minutes.meetings = [
  { id: "mtg-g", project_id: "proj-foreman", topic: "スマホ画面の工夫", status: "awaiting_human_adoption", participants: ["参加者A（x／Gemini）"], created_at: "",
    rounds: [{ phase: "1. 独立案出し", entries: [{ speaker: "参加者A", proposal: "案です" }] }],
    summary: { participants_detail: [{ ...person, self_report_check: { status: "other_name", names: ["Claude"], note: "自己紹介に別のAIの名前（Claude）が含まれています。実際に答えたのは Gemini です（呼び出し先で確認）。" } }],
      outside_kiro_crew: true, gemini_consent: { asked: true, allowed: true, scope: "この会議のみ", decided_at: "2026-11-19T20:30:00+0900" },
      consensus: "1件ずつ表示する", conflict_points: "確認の回数", unresolved: "長押しの時間", options_for_human: [{ id: "opt1", label: "全画面カード", detail: "1問ずつ" }, { id: "hold_as_idea", label: "保存", detail: "" }] } },
  { id: "mtg-f", project_id: "proj-foreman", topic: "失敗した相談", status: "failed", participants: ["参加者A（x／Kiro）"], rounds: [], created_at: "", summary: { note: "会議が失敗しました: 参加できないAIがあるため会議を始めませんでした" } },
];
minutes.meetings.push({ id: "mtg-p", project_id: "proj-foreman", topic: "採用済みの相談", status: "adopted_and_scheduled", participants: ["参加者A（x／Kiro）"], rounds: [], created_at: "", summary: { consensus: "終わった相談のまとめ" } });
await consultScreen("minutes", minutes);
expect("a finished meeting is folded under 過去の相談, with a count", !text().includes("採用済みの相談") && text().includes("過去の相談（1 件）"));
await clickText("過去の相談");
expect("...and opens when asked", text().includes("採用済みの相談") && text().includes("採用して作業を頼みました"));
await clickText("過去の相談を閉じる");
expect("a finished meeting shows the result in plain words and asks which option to take", text().includes("結果が出ました。選んでください") && text().includes("幽霊のまとめ") && text().includes("意見が分かれたところ") && text().includes("どの案で進めますか"));
expect("Gemini permission for that meeting is stated", text().includes("Gemini 無料枠への送信: この会議だけ許可"));
expect("a wrong self-introduction is flagged without opening anything", text().includes("⚠️ 参加者A: 自己紹介に別のAIの名前（Claude）が含まれています。実際に答えたのは Gemini です"));
expect("the AIs' exchange is folded away until asked for", !text().includes("案です") && !text().includes("gemini-2.5-flash-lite"));
await clickText("AIたちのやりとりを見る");
expect("...and shows the rounds and which AI really answered, once opened", text().includes("案です") && text().includes("Gemini・Kiro Crew 外で実行（Gemini API 無料枠）・gemini-2.5-flash-lite") && !text().includes("（未確認）"));
expect("a failed meeting is folded away, with a count", !text().includes("失敗した相談") && text().includes("うまくいかなかった相談（1 件）"));
await clickText("うまくいかなかった相談");
expect("...and its reason is shown once opened", text().includes("失敗した相談") && text().includes("参加できないAIがあるため"));
calls.length = 0;
await clickText("この案で進める");
expect("choosing an option -> POST /meetings/adopt", calls.some((c) => c[0] === "POST" && c[1].endsWith("/meetings/adopt") && c[2].meeting_id === "mtg-g" && c[2].option_id === "opt1"));
process.exit(process.exitCode || 0);
