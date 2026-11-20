// Checks the Japanese/English dictionary of ui/dist/index.mjs against the source: every string the screen can show
// through t("…") / T("…") has an English entry, the English keeps the same {placeholders}, contains no Japanese
// characters, and no entry is left over. Usage: node i18n_test.mjs <path to index.mjs>
import fs from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { JSDOM } from "jsdom";

const file = path.resolve(process.argv[2]);
const dom = new JSDOM("<!doctype html><div id=root></div>", { url: "http://localhost:5476/" });
globalThis.window = dom.window;
globalThis.document = dom.window.document;
Object.defineProperty(globalThis, "navigator", { value: dom.window.navigator, configurable: true });

const src = fs.readFileSync(file, "utf8");
const mod = await import(pathToFileURL(file).href);
const { EN, EN_B, detectLang } = mod.I18N;

const expect = (name, cond, extra = "") => { console.log((cond ? "PASS" : "FAIL") + "  " + name + (extra ? "  " + extra : "")); if (!cond) process.exitCode = 1; };
const JA = /[\u3040-\u30ff\u4e00-\u9fff\uff00-\uffef]/;
const holes = (s) => [...s.matchAll(/\{(\w+)\}/g)].map((m) => m[1]).sort().join(",");

// every literal passed to t(...) or T(...) (a plain double-quoted JS string, which is also valid JSON)
const used = new Set();
for (const m of src.matchAll(/(?<![\w$.])[tT]\(\s*("(?:[^"\\\n]|\\.)*")/g)) used.add(JSON.parse(m[1]));
expect("the source uses translated strings", used.size > 200, `${used.size} strings`);

const missing = [...used].filter((k) => EN[k] === undefined);
expect("every string shown through t()/T() has an English entry", missing.length === 0, missing.slice(0, 5).map((s) => JSON.stringify(s.slice(0, 40))).join(" "));

const unused = Object.keys(EN).filter((k) => !used.has(k));
expect("no English entry is left over without a use", unused.length === 0, unused.slice(0, 5).map((s) => JSON.stringify(s.slice(0, 40))).join(" "));

const badHoles = Object.keys(EN).filter((k) => holes(k) !== holes(EN[k]));
expect("the English keeps the same {placeholders} as the Japanese", badHoles.length === 0, badHoles.slice(0, 3).map((s) => JSON.stringify(s.slice(0, 40))).join(" "));

const jaLeft = Object.entries(EN).filter(([, v]) => JA.test(v));
expect("no English entry contains Japanese characters", jaLeft.length === 0, jaLeft.slice(0, 3).map(([k]) => JSON.stringify(k.slice(0, 30))).join(" "));

const empty = Object.entries(EN).filter(([, v]) => !String(v).trim());
expect("no English entry is empty", empty.length === 0);

const jaBackendLeft = Object.entries(EN_B).filter(([, v]) => JA.test(v));
expect("backend labels are fully English", jaBackendLeft.length === 0);

// the language is read from storage first, then from the browser
dom.window.localStorage.setItem("gf-lang", "en");
expect("a saved choice wins (English)", detectLang() === "en");
dom.window.localStorage.setItem("gf-lang", "ja");
expect("a saved choice wins (Japanese)", detectLang() === "ja");
dom.window.localStorage.removeItem("gf-lang");
expect("with nothing saved, a non-Japanese browser gets English", detectLang() === "en");
Object.defineProperty(dom.window.navigator, "language", { value: "ja-JP", configurable: true });
expect("with nothing saved, a Japanese browser gets Japanese", detectLang() === "ja");
// Fixed sentences the backend writes into the minutes: none may stay Japanese on an English screen.
mod.I18N.setLangForTest("en");
const tb = mod.I18N.tb;
const samples = [
  "【Plan】Do it（利点: fast / リスク: cost）",
  "批評: too slow → 改善案: use a cache",
  "（返答なし: Gemini が回答できませんでした）",
  "会議が失敗しました: 参加できないAIがあるため会議を始めませんでした — 参加者A（x／Codex）: 時間内に返答がありませんでした / 幽霊（整理役／Kiro）: （返答なし: 緊急停止中のため送信しません）",
  "参加者から案が得られませんでした",
  "Gateway再起動により会議が中断されました。途中までの発言は保存されています。",
  "幽霊の論点整理を得られませんでした。各ラウンドの発言をご確認ください。",
  "整理役の返答が構造化されていませんでした。採用は保存のみ可能です。",
  "この会議のみ",
  "この会議の内容を Gemini 無料枠に送ることを許可",
  "送信できませんでした: boom",
  "緊急停止されたため、届いた回答は使いません",
  "確定ルール pol-shop-01 に合致したため人間を呼ばずに自動回答しました（判定: kiro-bot/kiro-session 確信度0.95 The rule answers it.）。",
  "【Ghost Foreman 代理判断（根拠: pol-shop-01 / Prices）】\nShow every price including tax.\n上記確定ルールに従い実装を継続してください。",
  "幽霊・判定係(proj-shop)",
  "判定: proj-shop",
  "制作ルールに未登録の判断事項です。担当AIが示した選択肢を、そのまま表示しています。",
  "人間の判断待ち（担当AIが示した選択肢）",
  "人間による全エージェント緊急停止（再開は人間の許可が必要）",
  "人間による個別停止（再開は人間の許可が必要）",
  "人間の許可により停止を解除（自動では作業を再開しません）",
  "緊急停止により終了しました",
  "300秒のタイムアウトにより終了しました",
  "幽霊が担当AIへ逆質問中",
  "ツール実行承認待ち（ホスト権限）",
  "［Kiro Crew 外で実行］ I am Codex",
  "［Kiro Crew 外で実行（Gemini API 無料枠）］ I am Gemini",
];
const left = samples.map(tb).filter((x) => JA.test(x));
expect("fixed backend sentences in the minutes are translated", left.length === 0, left.slice(0, 2).join(" | "));
expect("AI-written words stay as written", tb("批評: これは日本語 → 改善案: そのまま") === "Critique: これは日本語 → Improved proposal: そのまま");
mod.I18N.setLangForTest("ja");
process.exit(process.exitCode || 0);
