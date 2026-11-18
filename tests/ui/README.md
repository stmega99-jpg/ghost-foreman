# UI render test

Renders the real `ui/dist/index.mjs` in jsdom with a dashboard payload and drives it like a user (tabs, deep link `?q=`,
free-text answer, privacy-switch confirm, stop buttons, and that HTML inside AI output is shown as text, not interpreted).

```
cd tests/ui
npm install
node setup.mjs
node render_test.mjs dash.sample.json ../../ui/dist/index.mjs
```

`dash.sample.json` is a payload captured from a running Gateway (demo data only). The SDK is replaced by `sdk_stub.mjs`;
the real hooks are verified on a running Gateway.
