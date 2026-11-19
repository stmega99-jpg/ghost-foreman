// Builds ui/m/vendor/react.mjs: React + ReactDOM client as ONE ES module for Ghost Foreman's phone page.
//
// Why: outside the Kiro Crew dashboard the host's /vendor/react.mjs stub cannot be used (it only re-exports the
// dashboard's own React instance). React and ReactDOM must come from the SAME module, otherwise hooks break, so both
// "react" and "react-dom/client" are mapped to this single file by the import map in ui/m/index.html.
//
//   cd ui/m/vendor
//   npm install --no-save react@19.3.1 react-dom@19.3.1 esbuild@0.28.2
//   node build.mjs
import { build } from "esbuild";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const entry = path.join(here, ".entry.mjs");
fs.writeFileSync(
  entry,
  `import React from "react";
import { createRoot, hydrateRoot } from "react-dom/client";
export default React;
export const { Children, Component, Fragment, PureComponent, StrictMode, Suspense, cloneElement, createContext, createElement,
  createRef, forwardRef, isValidElement, lazy, memo, startTransition, use, useCallback, useContext, useDebugValue,
  useDeferredValue, useEffect, useId, useImperativeHandle, useInsertionEffect, useLayoutEffect, useMemo, useReducer,
  useRef, useState, useSyncExternalStore, useTransition, version } = React;
export { createRoot, hydrateRoot };
`
);
const versions = ["react", "react-dom"].map((p) => `${p}@${JSON.parse(fs.readFileSync(path.join(here, "node_modules", p, "package.json"), "utf8")).version}`);
await build({
  entryPoints: [entry],
  outfile: path.join(here, "react.mjs"),
  bundle: true,
  format: "esm",
  minify: true,
  legalComments: "eof",
  define: { "process.env.NODE_ENV": '"production"' },
  banner: { js: `/* Bundled for Ghost Foreman's phone page: ${versions.join(", ")} (MIT License, Copyright (c) Meta Platforms, Inc. and affiliates). Rebuild with ui/m/vendor/build.mjs */` },
  absWorkingDir: here,
});
fs.rmSync(entry);
console.log("built react.mjs from", versions.join(", "), fs.statSync(path.join(here, "react.mjs")).size, "bytes");
