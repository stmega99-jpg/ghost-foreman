// Creates a stand-in for the host-provided "@kirocrew/app-sdk" (the Gateway resolves it through its import map at runtime)
// so the real ui/dist/index.mjs can be rendered in Node. Run once after `npm install`.
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const dir = path.join(here, "node_modules", "@kirocrew", "app-sdk");
fs.mkdirSync(dir, { recursive: true });
fs.writeFileSync(path.join(dir, "package.json"), JSON.stringify({ name: "@kirocrew/app-sdk", version: "0.0.0", type: "module", main: "index.js" }));
fs.copyFileSync(path.join(here, "sdk_stub.mjs"), path.join(dir, "index.js"));
console.log("sdk stub installed");
