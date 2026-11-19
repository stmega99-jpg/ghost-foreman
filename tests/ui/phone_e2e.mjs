// End-to-end test of Ghost Foreman's phone page against the REAL Gateway over the tailnet address, in real Chrome.
// Emulates an iPhone screen. Tokens are read from argv and never printed.
import puppeteer from "puppeteer-core";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";

const [, , chromePath, host, token1, token2] = process.argv;
const BASE = `https://${host}/api/apps/ghost-foreman/m/`;
const profile = fs.mkdtempSync(path.join(os.tmpdir(), "gf-phone-"));
const browser = await puppeteer.launch({ executablePath: chromePath, headless: "new", userDataDir: profile, args: ["--no-first-run"] });
const page = await browser.newPage();
await page.emulate({
  viewport: { width: 390, height: 844, deviceScaleFactor: 3, isMobile: true, hasTouch: true },
  userAgent: "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1",
});
const errors = [];
page.on("pageerror", (e) => errors.push(String(e)));
let failed = 0;
const expect = (name, cond, extra = "") => { console.log((cond ? "PASS" : "FAIL") + "  " + name + (extra ? "  " + extra : "")); if (!cond) failed++; };
const text = () => page.evaluate(() => document.body.innerText);
const waitText = async (needle, ms = 20000) => { try { await page.waitForFunction((n) => document.body.innerText.includes(n), { timeout: ms }, needle); return true; } catch { return false; } };
const cookies = async () => (await page.cookies(BASE, `https://${host}/api/auth/refresh`)).map((c) => c.name);
const client = await page.createCDPSession();
const delCookie = (name, p) => client.send("Network.deleteCookies", { name, domain: host, path: p });

// 1) First open from the QR in Safari: sign-in link
await page.goto(BASE + "?token=" + token1, { waitUntil: "domcontentloaded", timeout: 60000 });
expect("1. the Ghost Foreman screen opens directly (not the Kiro Crew dashboard)", await waitText("Gateway実接続"));
const t1 = await text();
expect("   install instructions are shown in Safari", t1.includes("ホーム画面に追加してください"));
expect("   the sign-in link stays in the address bar until it is added to the Home Screen", page.url().includes("token="));
const c1 = await cookies();
expect("   signed in: access + 30-day refresh cookies", c1.includes("mc_token_5476") && c1.includes("mc_refresh_5476"), JSON.stringify(c1));

// 2) Home Screen metadata
const meta = await page.evaluate(async () => {
  const link = document.querySelector('link[rel="manifest"]').href;
  const m = await (await fetch(link, { credentials: "include" })).json();
  const icon = await fetch(document.querySelector('link[rel="apple-touch-icon"]').href);
  return { name: m.name, start_url: m.start_url, scope: m.scope, display: m.display, icon: icon.status, iconType: icon.headers.get("content-type"), title: document.querySelector('meta[name="apple-mobile-web-app-title"]').content };
});
expect("2. Home Screen name/icon are Ghost Foreman's", meta.name === "Ghost Foreman" && meta.title === "Ghost Foreman" && meta.icon === 200 && /png/.test(meta.iconType), JSON.stringify(meta));
expect("   no fixed start_url: the installed app starts at the address it was added from", meta.start_url === undefined && meta.display === "standalone");

// 3) Service worker keeps a copy of the page
await page.waitForFunction(async () => { const r = await navigator.serviceWorker.getRegistration("/api/apps/ghost-foreman/m/"); return !!(r && r.active); }, { timeout: 20000 }).catch(() => {});
const sw = await page.evaluate(async () => {
  const r = await navigator.serviceWorker.getRegistration("/api/apps/ghost-foreman/m/");
  const keys = (await caches.has("gf-phone-v1")) ? (await (await caches.open("gf-phone-v1")).keys()).map((k) => new URL(k.url).pathname) : [];
  return { scope: r && r.scope, active: !!(r && r.active), cached: keys.sort() };
});
expect("3. page service worker active with its own scope", sw.active && sw.scope.endsWith("/api/apps/ghost-foreman/m/"), sw.scope);
expect("   the page and its two modules are cached (nothing else)", JSON.stringify(sw.cached) === JSON.stringify(["/api/apps/ghost-foreman/m/", "/api/apps/ghost-foreman/m/app.mjs", "/api/apps/ghost-foreman/m/sdk.mjs"]), JSON.stringify(sw.cached));

// 4) 20 hours later: the access cookie has expired, the refresh cookie is still there
await delCookie("mc_token_5476", "/");
expect("4. (simulated) access cookie expired", !(await cookies()).includes("mc_token_5476"));
await page.goto(BASE + "?q=test-deep-link", { waitUntil: "domcontentloaded", timeout: 60000 });
expect("   the app still opens (cached page + automatic refresh)", await waitText("Gateway実接続"));
expect("   a new access cookie was issued by the refresh", (await cookies()).includes("mc_token_5476"));

// 5) everything expired (no cookies at all)
await delCookie("mc_token_5476", "/");
await delCookie("mc_refresh_5476", "/api/auth");
await page.goto(BASE, { waitUntil: "domcontentloaded", timeout: 60000 });
expect("5. with no session left, the sign-in screen is shown (not an error)", await waitText("サインインしてください"));
const leaked = await page.evaluate(() => document.body.innerText.includes("Gateway実接続"));
expect("   and no app data is shown", !leaked);

// 6) re-sign-in by pasting a link inside the app
await page.type('input[type="url"]', `https://${host}/?token=${token2}`);
await Promise.all([page.waitForNavigation({ waitUntil: "domcontentloaded", timeout: 60000 }).catch(() => {}), page.click("button")]);
expect("6. pasting a sign-in link signs in again", await waitText("Gateway実接続"));
await page.goto(BASE, { waitUntil: "domcontentloaded" });
await page.type('input[type="url"]').catch(() => {});

// 7) pasted junk is refused without navigating anywhere
await delCookie("mc_token_5476", "/");
await delCookie("mc_refresh_5476", "/api/auth");
await page.goto(BASE, { waitUntil: "domcontentloaded" });
await waitText("サインインしてください");
const before = page.url();
await page.type('input[type="url"]', "https://evil.example/phish");
await page.click("button");
await new Promise((r) => setTimeout(r, 800));
expect("7. a pasted address without a token is refused, no navigation", page.url() === before && (await text()).includes("ログイン用リンクが見つかりません"));

expect("no JavaScript errors on the page", errors.length === 0, errors.slice(0, 2).join(" | "));
await browser.close();
fs.rmSync(profile, { recursive: true, force: true });
console.log(failed ? `${failed} FAILED` : "ALL PASSED");
process.exit(failed ? 1 : 0);
