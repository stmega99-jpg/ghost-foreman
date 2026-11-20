// Browser test of the public demo (demo/index.html) in real Chrome, served by a throw-away local server.
// Checks: the screen works on sample data in both languages, and NOTHING leaves the page (every request is a plain
// GET of a static file from this one local server; a script's own fetch/WebSocket is blocked by the page's CSP).
// Usage: node browser_test.mjs <chrome.exe> (run where puppeteer-core is installed; the repo root is found from this file)
import http from "node:http";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import puppeteer from "puppeteer-core";
const root = process.env.GF_REPO || path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const chrome = process.argv[2];
// GF_URL=https://host/path tests a hosted copy instead of a local one (this script serves nothing then).
const remote = process.env.GF_URL ? new URL(process.env.GF_URL.replace(/\/+$/, "") + "/") : null;
let failed = 0;
const expect = (name, cond, extra = "") => { console.log((cond ? "PASS" : "FAIL") + "  " + name + (extra ? "  " + extra : "")); if (!cond) failed++; };
const MIME = { ".html": "text/html; charset=utf-8", ".mjs": "text/javascript; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".json": "application/json", ".png": "image/png" };
const served = [];
const server = http.createServer((req, res) => {
  const p = decodeURIComponent(new URL(req.url, "http://x").pathname);
  const file = path.join(root, p);
  if (!file.startsWith(root) || !fs.existsSync(file) || fs.statSync(file).isDirectory()) { res.writeHead(404); res.end("no"); return; }
  served.push(req.method + " " + p);
  res.writeHead(200, { "Content-Type": MIME[path.extname(file)] || "application/octet-stream" });
  res.end(fs.readFileSync(file));
});
if (!remote) await new Promise((r) => server.listen(0, "127.0.0.1", r));
const origin = remote ? remote.origin : `http://127.0.0.1:${server.address().port}`;
const base = remote ? remote.pathname.replace(/\/$/, "") : "";
const profile = fs.mkdtempSync(path.join(process.env.TEMP || "/tmp", "gf-demo-"));
const browser = await puppeteer.launch({ executablePath: chrome, headless: "new", userDataDir: profile, args: ["--no-sandbox", "--lang=en-US"] });
const page = await browser.newPage();
await page.setViewport({ width: 420, height: 900 });
await page.setExtraHTTPHeaders({ "Accept-Language": "en-US,en;q=0.9" });
const requests = [], errors = [], csp = [];
page.on("request", (r) => requests.push({ url: r.url(), method: r.method() }));
page.on("pageerror", (e) => errors.push(String(e)));
page.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); });
page.on("dialog", (d) => d.accept());
const dump = async (name) => { if (process.env.GF_DUMP) fs.writeFileSync(path.join(process.env.GF_DUMP, name + ".txt"), await page.evaluate(() => document.body.innerText)); };
const text = () => page.evaluate(() => document.body.innerText);
const waitText = async (s, ms = 20000) => { try { await page.waitForFunction((x) => document.body.innerText.includes(x), { timeout: ms }, s); return true; } catch { return false; } };
const clickText = async (label, nth = 0) => page.evaluate((l, n) => { const b = [...document.querySelectorAll("button")].filter((x) => x.innerText.includes(l))[n]; if (!b) return false; b.click(); return true; }, label, nth);

await page.goto(origin + base + "/demo/index.html", { waitUntil: "domcontentloaded" });
expect("opens in English in an English browser", await waitText("What would you like to do?"));
expect("the sample projects show work from different fields", await (async () => { await clickText("Consult the AIs"); await waitText("Which project?"); const txt = await text(); await clickText("Back to home"); return ["Action game (sample)", "Budgeting app (sample)", "Running a YouTube channel (sample)", "Opening an online shop (sample)", "Writing a romance novel (sample)"].every((x) => txt.includes(x)); })());
expect("the banner says it is sample data, in English", (await text()).includes("Demo with sample data. No real AI, account or PC is connected"));
await clickText("See how the AIs are doing"); await new Promise((r) => setTimeout(r, 500)); await dump("ais");
expect("the screen says its AIs are samples, not real", await waitText("demo samples (not real AIs)"));
await clickText("Back to home");

// a project added on the Details screen appears in the consult screen's project list
await clickText("Details & settings"); await waitText("Projects"); await clickText("Projects", 0); await waitText("Register the work you are doing as projects");
await page.type("input[aria-label='New project name']", "My podcast");
await clickText("+ Add the project");
expect("a project can be added from the Details screen", await waitText("My podcast"));
await clickText("Back to home"); await clickText("Consult the AIs"); await waitText("Which project?");
expect("the new project can be picked when consulting", await page.evaluate(() => [...document.querySelectorAll("select[aria-label='Project'] option")].some((o) => o.textContent === "My podcast")));
await clickText("Back to home");
// language switch
await page.evaluate(() => [...document.querySelectorAll("button")].find((b) => b.getAttribute("lang") === "ja").click());
expect("choosing 日本語 switches the page and the banner", await waitText("何をしますか？") && (await text()).includes("見本データのデモです") && (await page.evaluate(() => localStorage.getItem("gf-lang"))) === "ja");

// answer a question
await clickText("AIからの質問に答える");
expect("the sample questions are shown in Japanese", await waitText("セーブデータの形式は JSON と SQLite のどちらにしますか？"));
await clickText("今回だけ、この案にする", 0);
expect("a one-time answer resolves the question", await waitText("回答済み") && await waitText("案A: SQLite を採用"));
await clickText("ホームへ戻る");
await clickText("詳細・設定"); await new Promise((r) => setTimeout(r, 300)); await clickText("決めたルール");
expect("a one-time answer did not add a permanent rule", !(await text()).includes("案A: SQLite を採用"));
await clickText("ホームへ戻る");

// a meeting (Kiro + Claude Code, no Gemini) runs through the sample stages and then waits for the human
await clickText("AIたちに相談する");
await page.waitForSelector("input[type=checkbox]:checked");
await page.waitForSelector("input[aria-label='相談したいこと']");
await page.type("input[aria-label='相談したいこと']", "承認ボタンの置き場所");
await page.waitForFunction(() => [...document.querySelectorAll("button")].find((b) => b.innerText.includes("この内容で相談を始める") && !b.disabled));
await clickText("この内容で相談を始める");
const reached = await waitText("結果が出ました。選んでください", 40000);
if (!reached) fs.writeFileSync(path.join(process.env.TEMP, "gf_race", "screen.txt"), await text());
expect("the sample meeting reaches the 'choose' stage", reached);
expect("it is labelled as a sample, and no AI is shown as having run", (await text()).includes("デモ用の見本（模擬）"));

// English: the same meeting is shown in English
await page.evaluate(() => [...document.querySelectorAll("button")].find((b) => b.getAttribute("lang") === "en").click());
expect("switching to English translates the meeting too", await waitText("Everyone agreed to put the approve button at the bottom"));
await dump("meeting_en");
expect("no Japanese is left in the English meeting card", await page.evaluate(() => { const card = [...document.querySelectorAll("div")].filter((d) => d.innerText.includes("The Ghost's summary")).pop(); return !/[\u3040-\u30ff\u4e00-\u9fff]/.test(card.innerText.replace("日本語", "")); }));

// adopt an option: the sample AI is offered, with a note that nothing goes to a real AI
expect("a sample AI can be asked to do the adopted work, and the screen says nothing goes to a real AI", (await text()).includes("The request goes to a sample AI. Nothing is sent to a real AI.") && (await page.evaluate(() => [...document.querySelectorAll("select")].some((s) => /sample/.test(s.innerText)))));
await clickText("Go with this option");
await waitText("See past consultations", 8000);
await clickText("See past consultations");
const adopted = await waitText("Adopted; work was ordered", 8000);
expect("adopting an option works on the demo", adopted);
await clickText("Back to home");
await clickText("See how the AIs are doing");
await waitText("See in details", 8000);
await clickText("See in details");
await dump("ais2");
expect("the sample AI shows the adopted plan as its next task", await waitText("Adopted from a meeting"));
await clickText("Back to home");

// emergency stop and the human-only resume
await clickText("Back to home");
await clickText("Stop all");
expect("the emergency stop shows as in force", await waitText("Resume") || await waitText("stop"));
const afterStop = await text();
expect("the stop is visible in the header", /stopp|Stopp|Stop/.test(afterStop));
await clickText("Lift every stop");
await new Promise((r) => setTimeout(r, 800));
expect("the human can release the stop", !(await text()).includes("Lift every stop"));

// nothing left the page
const bad = requests.filter((r) => { const u = new URL(r.url); return u.origin !== origin || r.method !== "GET" || u.pathname.startsWith(base + "/api"); });
expect("every request is a GET of a static file from the demo's own server", bad.length === 0, bad.slice(0, 3).map((r) => r.method + " " + r.url).join(" | "));
const netTry = await page.evaluate(async () => {
  const out = {};
  try { await fetch("https://example.com/"); out.fetch = "allowed"; } catch (e) { out.fetch = "blocked"; }
  try { await fetch("/api/apps/ghost-foreman/dashboard"); out.same = "allowed"; } catch (e) { out.same = "blocked"; }
  try { out.ws = await new Promise((res) => { const w = new WebSocket("wss://example.com/"); w.onerror = () => res("blocked"); w.onopen = () => res("allowed"); setTimeout(() => res("blocked"), 3000); }); } catch (e) { out.ws = "blocked"; }
  return out;
});
expect("the page's own fetch (even to its own origin) and WebSocket are blocked by the CSP", netTry.fetch === "blocked" && netTry.same === "blocked" && netTry.ws === "blocked", JSON.stringify(netTry));
const pages = requests.map((r) => new URL(r.url).pathname.slice(base.length));
expect("only the demo page, its code and React were requested", pages.every((p) => /^\/(demo|ui)\//.test(p)) && (remote || served.every((s) => s.startsWith("GET ") && /^GET \/(demo|ui)\//.test(s))), pages.filter((p) => !/^\/(demo|ui)\//.test(p)).join(","));
const realErrors = errors.filter((e) => !/Content Security Policy|violates|Failed to fetch|net::ERR_FAILED|WebSocket/.test(e));
expect("no JavaScript errors", realErrors.length === 0, realErrors.slice(0, 2).join(" | "));
await browser.close();
if (!remote) server.close();
fs.rmSync(profile, { recursive: true, force: true });
console.log(failed ? `${failed} FAILED` : "ALL PASSED");
process.exit(failed ? 1 : 0);