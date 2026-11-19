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
process.exit(process.exitCode || 0);
