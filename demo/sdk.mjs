// Stand-in for "@kirocrew/app-sdk" in the public demo. The API client is the in-memory sample engine
// (demo/engine.mjs): no fetch, no XHR, no WebSocket. The page's Content-Security-Policy also forbids any
// connection (connect-src 'none'), so even a mistake here could not reach the network.
import { createEngine } from "./engine.mjs";

const lang = () => {
  try { const s = localStorage.getItem("gf-lang"); if (s === "ja" || s === "en") return s; } catch (e) { /* storage blocked */ }
  return String(navigator.language || "ja").toLowerCase().startsWith("ja") ? "ja" : "en";
};
const engine = createEngine({ getLang: lang });
const PREFIX = "/api/apps/ghost-foreman";
const route = (path) => (String(path).startsWith(PREFIX) ? String(path).slice(PREFIX.length) || "/" : String(path));
// A short pause, like a real round trip, so buttons show their busy state.
const later = (v) => new Promise((r) => setTimeout(() => r(v), 60));
const api = {
  get: (path) => engine.handle("GET", route(path)).then(later),
  post: (path, body) => engine.handle("POST", route(path), body === undefined ? {} : body).then(later),
  put: () => Promise.reject(new Error("not available in the demo")),
  patch: () => Promise.reject(new Error("not available in the demo")),
  del: () => Promise.reject(new Error("not available in the demo")),
};
export const useAppApi = () => api;
export const useAppEvents = () => {};
export const useAppInfo = () => ({ name: "ghost-foreman", version: "demo" });
export const useNotify = () => () => {};
export const __engine = engine; // for the tests