// Ghost Foreman — Kiro Crew App UI (`ui/dist/index.mjs`, resolved relative to `<app_root>/ui/`).
// This is the screen the Gateway actually serves (index.html is only used by the local dev server).
// React renders text as text, so AI-written content is never interpreted as HTML.
//
// Layout: a HOME screen that starts from what the person wants to do (answer an AI, consult the AIs, see what the AIs
// are doing, look up news, read the rules). Technical settings, costs and run records live on the "詳細・設定" screen.
// The emergency stop button is in the header of every screen.
import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useAppApi, useAppEvents } from "@kirocrew/app-sdk";

const h = React.createElement;
const BASE = "/api/apps/ghost-foreman";

const C = { bg: "#0d0b18", card: "#17122a", border: "#2e1f47", text: "#f3e8ff", mute: "#a89bc4", accent: "#a78bfa", ok: "#34d399", warn: "#fbbf24", bad: "#f87171" };
const S = {
  page: { background: C.bg, color: C.text, minHeight: "100vh", padding: 16, fontFamily: "system-ui, sans-serif", fontSize: 15, lineHeight: 1.6 },
  wrap: { maxWidth: 760, margin: "0 auto" },
  card: { background: C.card, border: `1px solid ${C.border}`, borderRadius: 12, padding: 14, marginBottom: 12 },
  row: { display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" },
  btn: { background: "#3b2a66", color: C.text, border: `1px solid ${C.accent}`, borderRadius: 10, padding: "10px 14px", minHeight: 44, cursor: "pointer", fontSize: 15 },
  btnOk: { background: "#064e3b", color: C.text, border: `1px solid ${C.ok}`, borderRadius: 10, padding: "10px 14px", minHeight: 44, cursor: "pointer", fontSize: 15 },
  btnBad: { background: "#4c0519", color: C.text, border: `1px solid ${C.bad}`, borderRadius: 10, padding: "10px 14px", minHeight: 44, cursor: "pointer", fontSize: 15 },
  big: { fontSize: 17, padding: "14px 18px", minHeight: 52 },
  input: { background: "#0d0b18", color: C.text, border: `1px solid ${C.border}`, borderRadius: 10, padding: 10, fontSize: 15, minWidth: 0, flex: 1 },
  log: { background: "#0d0b18", border: `1px solid ${C.border}`, borderRadius: 10, padding: 10, margin: "6px 0", whiteSpace: "pre-wrap", fontSize: 14 },
  mute: { color: C.mute, fontSize: 13 },
  h2: { margin: "4px 0 10px", fontSize: 20 },
  h3: { margin: "0 0 8px", fontSize: 17 },
};

const STATUS = {
  needs_human: ["判断待ち", C.warn],
  probing: ["担当AIへ確認中…", C.accent],
  needs_human_approval: ["ツール承認待ち", C.warn],
  held_spec_violation: ["仕様変更のため保留", C.bad],
  held_emergency_stop: ["緊急停止中に受信（再開後に判断）", C.bad],
  auto_resolved: ["自動で回答済み", C.ok],
  human_resolved: ["回答済み", C.ok],
  batch_resolved: ["まとめて回答済み", C.ok],
};
const SLOT_STATUS = { working: "作業中", idle: "待機中", stopped: "停止中", waiting_human: "あなたの判断待ち", blocked: "待機中（理由あり）" };
const MEETING_STATUS = {
  running: ["相談中…（数分かかります）", C.accent],
  awaiting_human_adoption: ["結果が出ました。選んでください", C.warn],
  failed: ["うまくいきませんでした", C.bad],
  adopted_and_scheduled: ["採用して作業を頼みました", C.ok],
  saved_to_ideas: ["アイデア帳に保存しました", C.ok],
};
const SCOPE = { global: "すべての案件", project: "この案件", item: "この件だけ" };

function Badge({ text, color }) {
  return h("span", { style: { border: `1px solid ${color || C.border}`, color: color || C.mute, borderRadius: 999, padding: "1px 8px", fontSize: 12, whiteSpace: "nowrap" } }, text);
}
const isPending = (q) => ["needs_human", "needs_human_approval", "held_spec_violation"].includes(q.status);
const projectName = (d, id) => ((d.projects || []).find((p) => p.id === id) || {}).name || id;

// ------------------------------------------------------------------ small building blocks
function BackBar({ title, onBack }) {
  return h("div", { style: { ...S.row, marginBottom: 8 } },
    h("button", { style: S.btn, onClick: onBack }, "← ホームへ戻る"),
    h("h2", { style: { ...S.h2, margin: 0 } }, title));
}

function Tile({ icon, title, desc, badge, onClick, accent }) {
  return h("button", { onClick, style: { ...S.card, display: "block", width: "100%", textAlign: "left", cursor: "pointer", color: C.text, marginBottom: 10, ...(accent ? { borderColor: C.warn } : {}) } },
    h("div", { style: { ...S.row, justifyContent: "space-between" } },
      h("span", { style: { fontSize: 18, fontWeight: 600 } }, `${icon} ${title}`),
      badge ? h(Badge, { text: badge, color: C.warn }) : null),
    h("div", { style: S.mute }, desc));
}

// ------------------------------------------------------------------ answer the AIs' questions
function QuestionCard({ q, d, call, highlight }) {
  const [text, setText] = useState("");
  const [follow, setFollow] = useState("");
  const [batch, setBatch] = useState(false);
  const ref = useRef(null);
  useEffect(() => {
    if (highlight && ref.current) ref.current.scrollIntoView({ block: "center" });
  }, [highlight]);
  const [label, color] = STATUS[q.status] || [q.status, C.mute];
  const resolve = (answer, mode) =>
    call("POST", "/questions/resolve", {
      question_id: q.id,
      answer_text: answer,
      memory_mode: mode,
      policy_scope: "project",
      policy_title: "人間裁定: " + String(q.raw_question).slice(0, 30),
      batch_apply_same_project: batch,
    });
  return h(
    "div",
    { ref, style: { ...S.card, ...(highlight ? { borderColor: C.accent, boxShadow: `0 0 0 2px ${C.accent}55` } : {}) } },
    h("div", { style: { ...S.row, justifyContent: "space-between" } }, h(Badge, { text: projectName(d, q.project_id) }), h(Badge, { text: label, color })),
    h("h3", { style: { margin: "8px 0" } }, "AIからの確認: " + q.raw_question),
    q.context_summary ? h("p", { style: { whiteSpace: "pre-wrap" } }, q.context_summary) : null,
    q.recommendation ? h("p", { style: { color: C.accent } }, "👻 幽霊のおすすめ: " + q.recommendation + " — " + (q.recommendation_reason || "")) : null,
    ...(q.probe_history || []).map((p, i) => h("div", { key: "p" + i, style: S.log }, h("strong", null, `[${p.role}] `), p.text)),
    ...(q.options || []).map((o) =>
      h(
        "div",
        { key: o.id, style: { ...S.log, borderColor: C.accent } },
        h("strong", null, o.label),
        o.difference ? h("div", null, "違い: " + o.difference) : null,
        o.impact ? h("div", null, "影響: " + o.impact) : null,
        isPending(q)
          ? h(
              "div",
              { style: { ...S.row, marginTop: 6 } },
              h("button", { style: S.btn, onClick: () => resolve(o.label + " を採用", "one_time") }, "今回だけ、この案にする"),
              h("button", { style: S.btnOk, onClick: () => resolve(o.label + " を標準規約として採用", "permanent_policy") }, "🧠 これからもこの方針にする（恒久ルールにして回答）")
            )
          : null
      )
    ),
    q.final_answer ? h("div", { style: { ...S.log, borderColor: C.ok } }, h("strong", null, "[AIに送った回答] "), q.final_answer) : null,
    isPending(q)
      ? h(
          "div",
          { style: { marginTop: 10, borderTop: `1px solid ${C.border}`, paddingTop: 10 } },
          h("div", { style: S.mute }, "自分の言葉で答える（選択肢以外でもOK）"),
          h("textarea", { style: { ...S.input, width: "100%", minHeight: 70, boxSizing: "border-box" }, value: text, onChange: (e) => setText(e.target.value), placeholder: "回答を入力…" }),
          h(
            "div",
            { style: { ...S.row, marginTop: 6 } },
            h("button", { style: S.btn, disabled: !text.trim(), onClick: () => resolve(text.trim(), "one_time") }, "今回だけの回答にする"),
            h("button", { style: S.btnOk, disabled: !text.trim(), onClick: () => resolve(text.trim(), "permanent_policy") }, "🧠 これからもこの方針にする（恒久ルールにして回答）")
          ),
          h("label", { style: { ...S.mute, display: "block", marginTop: 6 } }, h("input", { type: "checkbox", checked: batch, onChange: (e) => setBatch(e.target.checked) }), " 同じ案件の似た質問にも、まとめて適用する"),
          h("div", { style: { ...S.row, marginTop: 8 } },
            h("input", { style: S.input, value: follow, onChange: (e) => setFollow(e.target.value), placeholder: "分からないときは質問で返す（例: JSONとSQLiteの違いは？）" }),
            h("button", { style: S.btn, disabled: !follow.trim(), onClick: () => call("POST", "/questions/inquire", { question_id: q.id, human_inquiry: follow.trim(), re_probe_agent: true }).then(() => setFollow("")) }, "💬 質問で返す")
          )
        )
      : null
  );
}

function Inbox({ d, call, focusQ }) {
  const sorted = [...d.questions].sort((a, b) => Number(isPending(b)) - Number(isPending(a)) || String(b.created_at).localeCompare(String(a.created_at)));
  const pending = sorted.filter(isPending).length;
  return h("div", null,
    h("div", { style: S.mute }, pending ? `あなたの判断を待っている確認が ${pending} 件あります。` : "いま、あなたの判断を待っている確認はありません。"),
    sorted.length ? null : h("div", { style: S.card }, "AIからの確認はまだ届いていません。AIが迷ったときに、ここに表示されます。"),
    ...sorted.map((q) => h(QuestionCard, { key: q.id, q, d, call, highlight: focusQ === q.id })));
}

// ------------------------------------------------------------------ see what the AIs are doing
const slotHalted = (d, s) => !!(d.halt && (d.halt.all || (d.halt.projects || []).includes(s.project_id) || (d.halt.slots || []).includes(s.id)));

function SlotCard({ d, s, call, technical }) {
  return h(
    "div",
    { style: S.card },
    h("div", { style: { ...S.row, justifyContent: "space-between" } },
      h("strong", null, technical ? `${s.id} ${s.name}` : s.name),
      h("span", { style: S.row },
        h(Badge, { text: s.is_live ? "本物のAI（実接続）" : "デモ用の見本（模擬）", color: s.is_live ? C.ok : C.warn }),
        slotHalted(d, s) ? h(Badge, { text: "停止中（人間の許可待ち）", color: C.bad }) : null,
        h(Badge, { text: SLOT_STATUS[s.status] || s.status }))),
    h("div", null, `${projectName(d, s.project_id)} ／ 役割: ${s.role}${technical ? " ／ " + s.backend : ""}`),
    h("div", null, "いまの仕事: " + s.current_task),
    s.waiting_reason ? h("div", { style: { color: C.warn } }, "待っている理由: " + s.waiting_reason) : null,
    s.next_task ? h("div", { style: S.mute }, "次の予定: " + s.next_task) : null,
    h("div", { style: { ...S.row, marginTop: 8 } },
      h("button", { style: S.btnBad, onClick: () => call("POST", "/stop", { scope: "slot", target_id: s.id }) }, "⏹ 停止"),
      d.halt && (d.halt.slots || []).includes(s.id) ? h("button", { style: S.btnOk, onClick: () => { if (window.confirm(s.name + " の停止を解除し、再開を許可しますか？\n（解除しても自動では作業を始めません）")) call("POST", "/stop", { scope: "resume_slot", target_id: s.id }); } }, "▶ この停止を解除") : null)
  );
}

function AiWatch({ d, call, go }) {
  const live = d.slots.filter((s) => s.is_live);
  const demo = d.slots.length - live.length;
  return h("div", null,
    live.length ? null : h("div", { style: S.card }, "いま、Ghost Foreman が見ている本物のAIの作業はありません。"),
    ...live.map((s) => h(SlotCard, { key: s.id, d, s, call })),
    demo ? h("div", { style: { ...S.card, ...S.mute } }, `デモ用の見本が ${demo} 件あります（実在するAIではありません）。`, " ", h("button", { style: S.btn, onClick: () => go("details:slots") }, "詳細で見る")) : null);
}

// ------------------------------------------------------------------ consult the AIs (meetings)
const PERSPECTIVES = [
  "設計・世界観との整合性の視点",
  "実装工数・リスクの視点",
  "プレイヤー体験・面白さの視点",
  "安全性・間違いにくさの視点",
  "他のアプリとの比較・市場の視点",
];
const AI_DESC = {
  kiro: "Kiro Crew の中で動くAIです。",
  claude: "Anthropic のAIです。パソコンから直接起動します（Kiro Crew の外）。",
  codex: "OpenAI のAIです。パソコンから直接起動します（Kiro Crew の外）。",
  gemini: "Google のAIです。無料枠を使います（Kiro Crew の外）。この会議の内容を送る許可が必要です。",
};
const WHERE = { external_cli: "（Kiro Crew 外で実行）", gemini_api: "（Kiro Crew 外・Gemini API 無料枠）" };

function MeetingCard({ m, d, call }) {
  const [open, setOpen] = useState(false);
  const [target, setTarget] = useState("");
  const workers = d.slots.filter((s) => s.is_live && !["会議参加者", "議事整理", "判定係"].includes(s.role));
  const chosen = target || (workers.find((w) => w.project_id === m.project_id) || workers[0] || {}).id || "";
  const sm = m.summary || {};
  const live = sm.live !== false;
  const [stLabel, stColor] = MEETING_STATUS[m.status] || [m.status, C.mute];
  const people = sm.participants_detail ? [...sm.participants_detail, ...(sm.synthesizer ? [sm.synthesizer] : [])] : [];
  return h("div", { style: S.card },
    h("div", { style: { ...S.row, justifyContent: "space-between" } },
      h(Badge, { text: projectName(d, m.project_id) }),
      h("span", { style: S.row }, live ? null : h(Badge, { text: "デモ用の見本（模擬）", color: C.warn }), h(Badge, { text: stLabel, color: stColor }))),
    h("h3", { style: { margin: "8px 0" } }, "相談: " + m.topic),
    h("div", { style: S.mute }, "参加したAI: " + m.participants.join(" ／ ")),
    sm.outside_kiro_crew ? h("div", { style: { color: C.warn, fontSize: 13, marginTop: 4 } }, "この相談には、Kiro Crew の外で動いたAI（Claude Code・Codex・Gemini。道具は使わず、文章だけ）が含まれます。") : null,
    ...people.filter((p) => p.self_report_check && p.self_report_check.status !== "ok")
      .map((p, i) => h("div", { key: "sr" + i, style: { color: C.warn, fontSize: 13, marginTop: 2 } }, `⚠️ ${p.speaker ? p.speaker.split("（")[0] : (p.label || p.harness)}: ${p.self_report_check.note}`)),
    (sm.gemini_consent && sm.gemini_consent.asked) ? h("div", { style: { color: C.warn, fontSize: 13, marginTop: 2 } },
      sm.gemini_consent.allowed ? `Gemini 無料枠への送信: この会議だけ許可（${sm.gemini_consent.decided_at}）` : "Gemini 無料枠への送信: 許可なし") : null,
    m.status === "failed" && sm.note ? h("div", { style: { ...S.log, borderColor: C.bad } }, sm.note) : null,
    sm.consensus
      ? h("div", { style: { ...S.log, borderColor: C.accent } },
          h("strong", null, "👻 幽霊のまとめ"), h("div", null, sm.consensus),
          sm.conflict_points ? h("div", { style: { color: C.warn, marginTop: 4 } }, "意見が分かれたところ: " + sm.conflict_points) : null,
          sm.unresolved ? h("div", { style: { marginTop: 4 } }, "まだ決まっていないこと: " + sm.unresolved) : null)
      : null,
    m.status === "awaiting_human_adoption"
      ? h("div", { style: { marginTop: 8 } },
          h("div", { style: { fontWeight: 600, marginBottom: 4 } }, "どの案で進めますか？（相談の段階では、まだ何も作りません）"),
          h("div", { style: S.row },
            h("span", { style: S.mute }, "作業を頼む相手:"),
            h("select", { style: { ...S.input, flex: "0 0 auto" }, value: chosen, onChange: (e) => setTarget(e.target.value), "aria-label": "作業を頼むAI" },
              ...(workers.length ? workers : [{ id: "", name: "（頼める本物のAIがいません）" }]).map((w) => h("option", { key: w.id || "none", value: w.id }, w.id ? `${w.name}（${w.role}）` : w.name)))),
          ...(sm.options_for_human || []).map((o) =>
            h("div", { key: o.id, style: { ...S.log, borderColor: C.accent } },
              h("strong", null, o.label), o.detail ? h("div", null, o.detail) : null,
              h("button", { style: { ...(o.id === "hold_as_idea" ? S.btn : S.btnOk), marginTop: 6 }, disabled: o.id !== "hold_as_idea" && !chosen,
                onClick: () => call("POST", "/meetings/adopt", { meeting_id: m.id, option_id: o.id, target_slot_id: chosen }) },
                o.id === "hold_as_idea" ? "いまは保存だけする" : "この案で進める（作業を頼む）"))))
      : null,
    m.rounds.length ? h("div", { style: { marginTop: 6 } },
      h("button", { style: S.btn, onClick: () => setOpen(!open) }, open ? "▲ やりとりを閉じる" : "▼ AIたちのやりとりを見る"),
      open ? h("div", null,
        people.length ? h("div", { style: { ...S.row, marginTop: 6 } }, ...people.map((p, i) =>
          h(Badge, { key: i, text: `${p.speaker ? p.speaker.split("（")[0] : "まとめ役"}: ${p.label || p.harness}・${p.runtime_label || ""}${p.model ? "・" + p.model : ""}${p.ran_on ? (p.verified ? "" : "（未確認）") : "（未実行）"}`, color: p.verified ? (p.runtime !== "kiro_crew" ? C.warn : C.ok) : C.mute }))) : null,
        ...m.rounds.map((r, i) => h("div", { key: i, style: S.log }, h("strong", null, r.phase), ...r.entries.map((e, j) => h("div", { key: j, style: { marginTop: 6 } }, h("strong", null, e.speaker + ": "), e.proposal || e.critique)))),
        sm.note && m.status !== "failed" ? h("div", { style: S.mute }, sm.note) : null) : null) : null);
}

function Consult({ d, call }) {
  const [topic, setTopic] = useState("");
  const [harnesses, setHarnesses] = useState({ harnesses: [] });
  const [limits, setLimits] = useState({ min: 2, max: 5 });
  // ONE list of participants (a point of view and an AI each). The ticks below are drawn from it and the detailed
  // panel edits it, so closing the panel never throws away what was changed there.
  const [parts, setParts] = useState([]);
  const [advanced, setAdvanced] = useState(false); // only whether the editor is shown
  const [organiser, setOrganiser] = useState("kiro");
  const [geminiOk, setGeminiOk] = useState(false); // the human's answer for THIS meeting; reset after each start
  const [showFailed, setShowFailed] = useState(false);
  const [project, setProject] = useState(d.projects[0] ? d.projects[0].id : "proj-foreman");
  const seeded = useRef(false);
  const apply = (r, first) => {
    if (!r) return;
    setHarnesses(r);
    setLimits({ min: r.min_participants || 2, max: r.max_participants || 5 });
    if (first && !seeded.current) {
      seeded.current = true;
      // Recommended: every AI that can run now, except Gemini (it needs a permission for each meeting).
      setParts((r.harnesses || []).filter((x) => x.available && x.id !== "gemini").map((x, i) => ({ perspective: PERSPECTIVES[i % PERSPECTIVES.length], harness: x.id })));
    }
  };
  const loadHarnesses = (refresh) => call("GET", "/meetings/harnesses" + (refresh ? "?refresh=1" : "")).then((r) => apply(r, false)).catch(() => {});
  useEffect(() => { call("GET", "/meetings/harnesses").then((r) => apply(r, true)).catch(() => {}); }, []);

  const rows = harnesses.harnesses || [];
  const rowOf = (id) => rows.find((x) => x.id === id) || {};
  // A blank point of view gets the default for its place, so a participant is never silently dropped.
  const effective = parts.map((p, i) => ({ perspective: p.perspective.trim() || PERSPECTIVES[i % PERSPECTIVES.length], harness: p.harness }));
  const countOf = (id) => parts.filter((p) => p.harness === id).length;
  const chosenIds = [...effective.map((p) => p.harness), organiser];
  const outside = chosenIds.some((id) => ["external_cli", "gemini_api"].includes(rowOf(id).runtime));
  const usesGemini = chosenIds.includes("gemini");
  const geminiRow = rowOf("gemini");
  const blocked = chosenIds.filter((id) => rows.length && !rowOf(id).available);
  const agentOptions = (rows.length ? rows : [{ id: "kiro", label: "Kiro", runtime: "kiro_crew", available: true }]).map((x) =>
    h("option", { key: x.id, value: x.id, disabled: !x.available }, x.label + (WHERE[x.runtime] || "") + (x.available ? "" : "　— 使えません")));
  const nextPerspective = () => PERSPECTIVES.find((v) => !parts.some((p) => p.perspective.trim() === v)) || PERSPECTIVES[parts.length % PERSPECTIVES.length];
  // Ticking adds one participant; unticking removes the participants of that AI. Everyone else keeps their edits.
  const togglePick = (id) => setParts(countOf(id) ? parts.filter((p) => p.harness !== id) : [...parts, { perspective: nextPerspective(), harness: id }]);
  const setPart = (i, key, value) => setParts(parts.map((p, j) => (j === i ? { ...p, [key]: value } : p)));

  let why = "";
  if (!topic.trim()) why = "相談したいことを入力してください。";
  else if (effective.length < limits.min) why = `AIを ${limits.min} つ以上選んでください。`;
  else if (effective.length > limits.max) why = `AIは ${limits.max} つまでです。`;
  else if (blocked.length) why = "使えないAIが選ばれています。外すか、「再確認」してください。";
  else if (usesGemini && !geminiOk) why = "Gemini を使うには、下の送信の許可にチェックしてください。";
  const start = () => call("POST", "/meetings", {
    project_id: project, topic: topic.trim(),
    participants: effective.map((p) => ({ perspective: p.perspective.trim(), harness: p.harness })),
    synthesizer_harness: organiser, allow_unpublished_to_gemini: usesGemini && geminiOk === true,
  }).then(() => { setTopic(""); setGeminiOk(false); });

  // Meetings that need the person (running, or waiting for a choice) stay in view. Finished ones and failed ones are folded.
  const ok = d.meetings.filter((m) => ["running", "awaiting_human_adoption"].includes(m.status));
  const past = d.meetings.filter((m) => !["running", "awaiting_human_adoption", "failed"].includes(m.status));
  const failed = d.meetings.filter((m) => m.status === "failed");
  const [showPast, setShowPast] = useState(false);
  return h("div", null,
    h("div", { style: S.card },
      h("h3", { style: S.h3 }, "① 何を相談しますか？"),
      h("div", { style: { ...S.row, marginBottom: 8 } },
        h("span", { style: S.mute }, "どの案件？"),
        h("select", { style: { ...S.input, flex: "0 0 auto" }, value: project, onChange: (e) => setProject(e.target.value), "aria-label": "案件" }, ...d.projects.map((p) => h("option", { key: p.id, value: p.id }, p.name)))),
      h("input", { style: { ...S.input, width: "100%", boxSizing: "border-box", fontSize: 16 }, value: topic, onChange: (e) => setTopic(e.target.value), placeholder: "相談したいこと（例: セーブ時の安心感を与える演出）", "aria-label": "相談したいこと" })),
    h("div", { style: S.card },
      h("h3", { style: S.h3 }, "② 誰に相談しますか？（2つ以上選んでください）"),
      ...rows.map((x) => h("label", { key: x.id, style: { display: "flex", gap: 10, alignItems: "flex-start", padding: "8px 0", borderTop: `1px solid ${C.border}`, opacity: x.available ? 1 : 0.6 } },
        h("input", { type: "checkbox", style: { width: 22, height: 22, marginTop: 2 }, checked: countOf(x.id) > 0, disabled: !x.available || (countOf(x.id) === 0 && parts.length >= limits.max), onChange: () => togglePick(x.id), "aria-label": `${x.label}に相談する` }),
        h("span", { style: { flex: 1 } },
          h("strong", null, x.label), " ", h(Badge, { text: x.available ? "使えます" : "いまは使えません", color: x.available ? C.ok : C.bad }),
          countOf(x.id) > 1 ? h(Badge, { text: `${countOf(x.id)}人参加` }) : null,
          h("div", { style: S.mute }, AI_DESC[x.id] || ""),
          !x.available && x.reason ? h("div", { style: { color: C.warn, fontSize: 13 } }, x.reason) : null))),
      h("div", { style: { ...S.row, marginTop: 6 } },
        h("button", { style: S.btn, onClick: () => loadHarnesses(true) }, "↻ 使えるか再確認"),
        h("span", { style: S.mute }, "はじめに、選んだAIへ参加確認を送ります。答えられないAIがいれば、始めずに理由をお知らせします。")),
      outside ? h("div", { style: { ...S.log, borderColor: C.warn } },
        "⚠️ Claude Code・Codex・Gemini は Kiro Crew の外で動きます（企画書で認めた、相談に限った例外です）。道具は使えず、文章のやり取りだけです。「全停止」でいつでも止められ、実行の記録は「詳細・設定」に残ります。各サービスの利用枠を使います。") : null,
      usesGemini ? h("div", { style: { ...S.log, borderColor: C.warn } },
        h("div", null, "Gemini は、使えないときに別のAIが代わりに答えることも、有料のAPIに切り替わることもありません。"),
        h("label", { style: { display: "flex", gap: 8, alignItems: "flex-start", marginTop: 6 } },
          h("input", { type: "checkbox", style: { width: 22, height: 22 }, checked: geminiOk, onChange: (e) => setGeminiOk(e.target.checked), "aria-label": "この会議の内容を Gemini 無料枠に送ることを許可する" }),
          h("span", null, h("strong", null, "この会議の内容を Gemini 無料枠に送ることを許可する"), "（この会議だけ）")),
        h("div", { style: S.mute }, geminiRow.consent_note || "議題・各AIの案など、未公開の制作情報を含みます。無料枠に送った内容は、Google がサービス改善に使う場合があります。"),
        geminiOk ? null : h("div", { style: { color: C.warn, fontSize: 13 } }, "許可しない場合は、Gemini を外してください。")) : null),
    h("div", { style: S.card },
      h("button", { style: S.btn, onClick: () => setAdvanced(!advanced) }, advanced ? "▲ くわしい設定を閉じる" : "▼ くわしく設定する（任意）"),
      advanced ? h("div", { style: { marginTop: 8 } },
        h("div", { style: S.mute }, "参加者ごとに、どの視点で意見を出すか・どのAIにするかを決められます。同じAIを何人か入れることもできます。"),
        ...parts.map((p, i) => h("div", { key: i, style: { ...S.row, marginTop: 6 } },
          h("span", { style: { width: 20 } }, String.fromCharCode(65 + i)),
          h("input", { style: S.input, value: p.perspective, onChange: (e) => setPart(i, "perspective", e.target.value), placeholder: "視点（例: 実装工数・リスクの視点）", "aria-label": `参加者${String.fromCharCode(65 + i)}の視点` }),
          h("select", { style: { ...S.input, flex: "0 0 auto" }, value: p.harness, onChange: (e) => setPart(i, "harness", e.target.value), "aria-label": `参加者${String.fromCharCode(65 + i)}のAI` }, ...agentOptions),
          h("button", { style: S.btn, disabled: parts.length <= limits.min, onClick: () => setParts(parts.filter((_, j) => j !== i)), "aria-label": `参加者${String.fromCharCode(65 + i)}を外す` }, "−"))),
        h("div", { style: { ...S.row, marginTop: 6 } },
          h("button", { style: S.btn, disabled: parts.length >= limits.max, onClick: () => setParts([...parts, { perspective: "", harness: "kiro" }]) }, "＋ 参加者を追加"),
          h("span", { style: S.mute }, "まとめ役（意見を整理するAI）:"),
          h("select", { style: { ...S.input, flex: "0 0 auto" }, value: organiser, onChange: (e) => setOrganiser(e.target.value), "aria-label": "まとめ役のAI" }, ...agentOptions))) : null),
    h("div", { style: S.card },
      h("button", { style: { ...S.btnOk, ...S.big, width: "100%" }, disabled: !!why, onClick: start }, "💬 この内容で相談を始める"),
      why ? h("div", { style: { ...S.mute, marginTop: 6 } }, why) : null,
      h("div", { style: { ...S.mute, marginTop: 6 } }, "相談の段階では、何も作りません。あなたが案を選んだときだけ、作業を頼みます。")),
    ok.length ? h("h3", { style: { ...S.h3, marginTop: 16 } }, "相談中・結果待ち") : null,
    ...ok.map((m) => h(MeetingCard, { key: m.id, m, d, call })),
    past.length ? h("div", { style: { marginTop: 8 } },
      h("button", { style: S.btn, onClick: () => setShowPast(!showPast) }, showPast ? "▲ 過去の相談を閉じる" : `▼ 過去の相談（${past.length} 件）を見る`),
      showPast ? h("div", { style: { marginTop: 8 } }, ...past.map((m) => h(MeetingCard, { key: m.id, m, d, call }))) : null) : null,
    failed.length ? h("div", { style: { marginTop: 8 } },
      h("button", { style: S.btn, onClick: () => setShowFailed(!showFailed) }, showFailed ? "▲ うまくいかなかった相談を閉じる" : `▼ うまくいかなかった相談（${failed.length} 件）を見る`),
      showFailed ? h("div", { style: { marginTop: 8 } }, ...failed.map((m) => h(MeetingCard, { key: m.id, m, d, call }))) : null) : null);
}

// ------------------------------------------------------------------ rules / news
function Rules({ d }) {
  if (!d.policies.length) return h("div", { style: S.card }, "決めたルールはまだありません。AIの質問に「これからもこの方針にする」で答えると、ここに増えていきます。");
  return h("div", null,
    h("div", { style: S.mute }, "あなたが決めた方針の一覧です。AIが迷ったとき、幽霊はこれを根拠に代わりに答えます。"),
    ...d.policies.map((p) => h("div", { key: p.id, style: S.card },
      h("div", { style: { ...S.row, justifyContent: "space-between" } }, h("strong", null, p.title), h(Badge, { text: `${SCOPE[p.scope] || p.scope}${p.scope === "project" ? "（" + projectName(d, p.project_id) + "）" : ""}` })),
      h("div", { style: { marginTop: 6, whiteSpace: "pre-wrap" } }, p.rule_text),
      h("div", { style: S.mute }, `${p.locked ? "確定仕様（無断では変えません）　" : ""}${p.id}・第${p.version}版`))));
}

function News({ d, call }) {
  const [url, setUrl] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const add = async () => {
    setBusy(true); setErr("");
    try { await call("POST", "/news/summarize", { project_id: (d.projects[0] || {}).id || "proj-foreman", url: url.trim(), reason: "手動で指定されたURL" }); setUrl(""); }
    catch (e) { setErr(String((e && e.message) || e)); }
    setBusy(false);
  };
  return h("div", null,
    h("div", { style: S.card },
      h("div", { style: S.mute }, "気になる記事やページのURLを貼ってください。要約して、「事実」と「推測」を分けて保存します。"),
      h("div", { style: { ...S.row, marginTop: 6 } }, h("input", { style: S.input, value: url, onChange: (e) => setUrl(e.target.value), placeholder: "https://… 公開ページのURL" }), h("button", { style: S.btnOk, disabled: busy || !url.trim(), onClick: add }, busy ? "要約中…" : "要約して保存")),
      err ? h("div", { style: { color: C.bad, marginTop: 6 } }, err) : null,
      h("div", { style: S.mute }, "公開されているページだけを取得します（社内のアドレスなどは拒否します）。")),
    ...d.news.map((n) => h("div", { key: n.id, style: S.card },
      h("strong", null, n.title), h("div", { style: S.mute }, `${n.category} ／ 掲載日 ${n.published_date} ／ 集めた理由: ${n.relevance_reason}`),
      h("div", { style: { ...S.log, borderColor: C.ok } }, h("strong", null, "事実\n"), n.facts_summary),
      h("div", { style: { ...S.log, borderColor: C.warn } }, h("strong", null, "推測\n"), n.estimates_summary),
      h("div", { style: S.mute }, "元の記事: " + n.url))));
}

// ------------------------------------------------------------------ details (technical settings and records)
function Audit({ d }) {
  if (!d.audits.length) return h("div", { style: S.card }, "判断の記録はまだありません。");
  return h("div", null, ...d.audits.map((a) => h("div", { key: a.id, style: S.card },
    h("div", { style: { ...S.row, justifyContent: "space-between" } }, h(Badge, { text: `${a.project_id} / ${a.slot_id}` }), h(Badge, { text: `${a.actor}: ${a.action_type}` })),
    h("div", { style: { marginTop: 6 } }, "原文: " + a.raw_question),
    a.referenced_policy_id ? h("div", { style: S.mute }, "適用ルール: " + a.referenced_policy_id) : null,
    h("div", { style: S.log }, a.answer_sent), h("div", { style: S.mute }, (a.rationale || "") + " / " + a.created_at))));
}

// Only on Ghost Foreman's own phone page (ui/m/index.html sets window.__gfPush). Inside the Kiro Crew dashboard the
// host's own notification settings are used instead.
function PhoneNotifications({ call }) {
  const push = typeof window !== "undefined" ? window.__gfPush : null;
  const [st, setSt] = useState(null);
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);
  const load = useCallback(() => { if (push) push.status().then(setSt).catch((e) => setMsg(String(e.message || e))); }, [push]);
  useEffect(load, [load]);
  if (!push) return null;
  const enable = async () => {
    setBusy(true); setMsg("");
    try { await push.enable(); setMsg("通知をオンにしました。「テスト通知を送る」で確認できます。"); }
    catch (e) { setMsg(String((e && e.message) || e)); }
    setBusy(false); load();
  };
  const test = async () => {
    setBusy(true); setMsg("");
    try { const r = await call("POST", "/notify/test", {}); setMsg(r && r.ok ? "テスト通知を送りました。数秒で届きます（アプリを閉じると見やすいです）。" : "送信に失敗しました: " + ((r && r.error) || "")); }
    catch (e) { setMsg(String((e && e.message) || e)); }
    setBusy(false);
  };
  const on = st && st.subscribed && st.permission === "granted";
  return h("div", { style: S.card },
    h("h3", { style: S.h3 }, "📲 このiPhoneへの通知"),
    st ? h("div", null, on ? "オン（判断待ちが出たらこの端末に通知します）" : st.standalone ? "オフ" : "ホーム画面に追加したアプリから開くと、オンにできます") : h("div", null, "確認中…"),
    h("div", { style: { ...S.row, marginTop: 8 } },
      !on ? h("button", { style: S.btnOk, disabled: busy || !(st && st.standalone), onClick: enable }, "🔔 通知をオンにする") : null,
      on ? h("button", { style: S.btn, disabled: busy, onClick: test }, "テスト通知を送る") : null),
    msg ? h("div", { style: { marginTop: 6 } }, msg) : null,
    h("div", { style: S.mute }, "通知がいつ届くかは、ホームの「いまの状況」（家にいる／外出中／おやすみ）で変わります。テスト通知は状況に関係なく送ります。"));
}

function DetailSettings({ d, call }) {
  const allow = !!(d.mode_state && d.mode_state.allow_unpublished_to_free_tier);
  const toggle = () => {
    const want = !allow;
    if (want && !window.confirm("制作内容（AIからの質問・確定ルールの本文）を Gemini の無料枠へ送信します。\n無料枠に送った内容は、Google によって製品改善などに利用される可能性があります。\n\n許可しますか？")) return;
    call("POST", "/mode", { allow_unpublished_to_free_tier: want });
  };
  return h("div", null,
    h(PhoneNotifications, { call }),
    h("div", { style: S.card },
      h("h3", { style: S.h3 }, "🔒 制作内容を Gemini の無料枠へ送ってよいか（常時の設定）"),
      h("div", null, "AIからの質問や確定ルールの本文を、判定のために Gemini の無料枠へ送ってよいかを決めます。AI会議で Gemini を使うときは、この設定とは別に、会議ごとに許可を聞きます。"),
      h("label", { style: { ...S.row, margin: "8px 0" } }, h("input", { type: "checkbox", style: { width: 22, height: 22 }, checked: allow, onChange: toggle }), h("strong", null, allow ? "許可している（制作内容を無料枠へ送信する）" : "許可していない（制作内容は送信しない）")),
      h("div", { style: S.mute }, "許可しない場合、制作内容の判定は Kiro Crew の実セッションで行います。公開ニュースの整理は、この設定に関係なく Gemini を使います。")));
}

function DetailCost({ d }) {
  const u = d.usage || { totals: [] };
  const cooling = u.gemini_cooldown_until && u.gemini_cooldown_until * 1000 > Date.now();
  return h("div", { style: S.card },
    h("h3", { style: S.h3 }, "💰 費用と使用量"),
    h("div", null, "実際の請求額: ", h(Badge, { text: u.actual_billing || "未確認", color: C.warn })),
    h("div", { style: S.mute }, u.billing_note || ""),
    h("div", { style: { margin: "6px 0" } }, cooling ? "Gemini無料枠は上限により待機中です（有料APIには切り替えません）" : "Gemini無料枠: 利用可能（または未使用）"),
    h("div", { style: { overflowX: "auto" } },
      h("table", { style: { width: "100%", borderCollapse: "collapse", fontSize: 13 } },
        h("thead", null, h("tr", { style: { textAlign: "left" } }, ...["提供元", "呼び出し", "成功", "トークン(入/出)", "請求額"].map((t) => h("th", { key: t }, t)))),
        h("tbody", null, ...(u.totals || []).map((t) => h("tr", { key: t.provider_id }, h("td", null, t.provider_id), h("td", null, t.calls), h("td", null, t.ok_calls), h("td", null, `${t.input_tokens} / ${t.output_tokens}`), h("td", null, t.cost_display || "未確認")))))),
    h("div", { style: S.mute }, "トークン数は提供元の実測値です。Kiro の使用量はホストが公開していないため、0ではなく未確認として扱います。有料APIへの切替機能は実装していません。"));
}

function DetailRuns({ d }) {
  return h("div", { style: S.card },
    h("h3", { style: S.h3 }, "🧪 Kiro Crew 外で実行したAIの記録"),
    h("div", { style: S.mute }, "AI会議のために Ghost Foreman が直接起動した Claude Code / Codex の記録です。質問の本文は保存せず、ハッシュだけを残します。請求額は確認できないため「未確認」です。"),
    ...(d.external_runs || []).map((r) => h("div", { key: r.id, style: { ...S.log, borderColor: r.status === "ok" ? C.ok : C.bad } },
      h("strong", null, `[${r.status}] ${r.harness}${r.model ? "・" + r.model : ""}`), ` ${r.started_at}　${Math.round((r.duration_ms || 0) / 100) / 10}秒　トークン ${r.input_tokens}/${r.output_tokens}　会議 ${r.meeting_id || "-"}`,
      r.error ? h("div", { style: { color: C.bad } }, r.error) : null)),
    (d.external_runs || []).length ? null : h("div", { style: S.mute }, "まだ記録はありません。"));
}

function DetailNotices({ d }) {
  return h("div", { style: S.card },
    h("h3", { style: S.h3 }, "🔔 通知の履歴"),
    h("div", { style: S.mute }, "sent=送信 / held=おやすみ中に保留 / held_resident=家にいるため通知せず / failed=失敗 / not_sent=模擬モード"),
    ...(d.notifications || []).map((n) => h("div", { key: n.id, style: S.log }, h("strong", null, `[${n.delivery}] `), `${n.title} ${n.body}`, h("div", { style: S.mute }, `${n.ts} ${n.detail || ""}`))));
}

function DetailSlots({ d, call }) {
  return h("div", null,
    h("div", { style: { ...S.card, ...S.mute } }, "「本物のAI（実接続）」は Kiro Crew Gateway 上の本物のセッションです。「デモ用の見本（模擬）」は動作を見せるためのサンプルで、実在のAIではありません。"),
    ...d.slots.map((s) => h(SlotCard, { key: s.id, d, s, call, technical: true })));
}

const DETAIL_SECTIONS = [["settings", "通知・送信の設定"], ["cost", "費用と使用量"], ["runs", "外部AIの実行記録"], ["notices", "通知の履歴"], ["audit", "判断の記録"], ["slots", "AIの一覧（技術情報）"]];

function Details({ d, call, section, setSection }) {
  const body = { settings: DetailSettings, cost: DetailCost, runs: DetailRuns, notices: DetailNotices, audit: Audit, slots: DetailSlots }[section] || DetailSettings;
  return h("div", null,
    h("div", { style: S.mute }, "ふだんは使わない、設定と記録です。"),
    h("div", { style: { ...S.row, margin: "8px 0 12px" } }, ...DETAIL_SECTIONS.map(([k, t]) => h("button", { key: k, style: { ...S.btn, ...(section === k ? { background: C.accent, color: "#0d0b18" } : {}) }, onClick: () => setSection(k) }, t))),
    h(body, { d, call }));
}

// ------------------------------------------------------------------ home
const MODES = [
  ["resident", "🏠 家にいる", "通知しません"],
  ["away", "🚃 外出中", "判断待ちをスマホに通知"],
  ["sleep", "🌙 おやすみ", "朝にまとめて通知"],
];

function Home({ d, call, go }) {
  const pending = d.questions.filter(isPending).length;
  const running = d.meetings.filter((m) => m.status === "running").length;
  const waiting = d.meetings.filter((m) => m.status === "awaiting_human_adoption").length;
  const mode = (d.mode_state && d.mode_state.mode) || "away";
  const liveSlots = d.slots.filter((s) => s.is_live).length;
  return h("div", null,
    pending
      ? h("div", { style: { ...S.card, borderColor: C.warn } },
          h("div", { style: { fontSize: 18, fontWeight: 600 } }, "👻 あなたの判断を待っているAIがいます"),
          h("div", null, `${pending} 件の確認が届いています。`),
          h("button", { style: { ...S.btnOk, ...S.big, marginTop: 8 }, onClick: () => go("inbox") }, "答える →"))
      : h("div", { style: S.card }, "✅ いま、あなたの判断を待っているものはありません。"),
    running ? h("div", { style: { ...S.card, borderColor: C.accent } }, `💬 AIたちが相談中です（${running} 件）。数分かかります。`, " ", h("button", { style: S.btn, onClick: () => go("consult") }, "様子を見る")) : null,
    waiting && !running ? h("div", { style: { ...S.card, borderColor: C.warn } }, `💬 相談の結果が出ています（${waiting} 件）。どの案で進めるか選べます。`, " ", h("button", { style: S.btn, onClick: () => go("consult") }, "結果を見る")) : null,
    h("h2", { style: S.h2 }, "何をしますか？"),
    h(Tile, { icon: "💬", title: "AIたちに相談する", desc: "企画の悩みを、いろいろなAIに聞いて、意見をまとめてもらいます。", onClick: () => go("consult"), badge: waiting ? `結果 ${waiting} 件` : "" }),
    h(Tile, { icon: "📥", title: "AIからの質問に答える", desc: "AIが迷ったときの確認に答えます。", onClick: () => go("inbox"), badge: pending ? `${pending} 件待ち` : "", accent: !!pending }),
    h(Tile, { icon: "🤖", title: "AIたちの様子を見る", desc: liveSlots ? `本物のAIが ${liveSlots} 体、動いています。` : "誰がいま何をしているか見て、止めたりできます。", onClick: () => go("ais") }),
    h(Tile, { icon: "📰", title: "ニュースを調べる", desc: "気になる記事のURLを貼ると、要約して保存します。", onClick: () => go("news") }),
    h(Tile, { icon: "🧠", title: "決めたルールを見る", desc: "あなたが決めた方針の一覧です。", onClick: () => go("rules") }),
    h("div", { style: S.card },
      h("div", { style: { fontWeight: 600, marginBottom: 6 } }, "いま、どんな状況ですか？（通知の出し方が変わります）"),
      h("div", { style: { display: "grid", gridTemplateColumns: "repeat(3, minmax(0, 1fr))", gap: 8 } }, ...MODES.map(([k, t, sub]) => h("button", { key: k, "aria-pressed": mode === k, style: { ...S.btn, padding: "10px 8px", textAlign: "center", ...(mode === k ? { background: C.accent, color: "#0d0b18" } : {}) }, onClick: () => call("POST", "/mode", { mode: k }) }, h("div", null, t), h("div", { style: { fontSize: 11 } }, sub))))),
    h("div", { style: { textAlign: "center", marginTop: 16 } }, h("button", { style: S.btn, onClick: () => go("details") }, "⚙️ 詳細・設定（通知・費用・記録）")));
}

// ------------------------------------------------------------------ app
const TITLES = { inbox: "📥 AIからの質問に答える", consult: "💬 AIたちに相談する", ais: "🤖 AIたちの様子", news: "📰 ニュースを調べる", rules: "🧠 決めたルール", details: "⚙️ 詳細・設定" };

export default function GhostForemanApp() {
  const api = useAppApi();
  const [d, setD] = useState(null);
  const [error, setError] = useState("");
  const focusQ = useMemo(() => new URLSearchParams(window.location.search).get("q") || "", []);
  const [view, setView] = useState(focusQ ? "inbox" : "home");
  const [section, setSection] = useState("settings");
  const go = (target) => {
    if (target.startsWith("details:")) { setSection(target.split(":")[1]); setView("details"); }
    else setView(target);
    if (typeof window !== "undefined" && window.scrollTo) { try { window.scrollTo(0, 0); } catch (e) { /* jsdom */ } }
  };

  const refresh = useCallback(async () => {
    try { setD(await api.get(BASE + "/dashboard")); setError(""); }
    catch (e) { setError(String((e && e.message) || e)); }
  }, [api]);
  const call = useCallback(async (method, path, body) => {
    try {
      const res = method === "GET" ? await api.get(BASE + path) : await api.post(BASE + path, body || {});
      await refresh();
      return res;
    } catch (e) {
      setError(String((e && e.message) || e));
      throw e;
    }
  }, [api, refresh]);

  useEffect(() => { refresh(); }, [refresh]);
  useAppEvents("slots", () => refresh());
  useAppEvents("onChatDone", () => refresh());
  const busy = d && (d.meetings.some((m) => m.status === "running") || d.questions.some((q) => q.status === "probing"));
  useEffect(() => { const t = setInterval(refresh, busy ? 5000 : 20000); return () => clearInterval(t); }, [refresh, busy]);

  if (!d) return h("div", { style: S.page }, error ? "接続エラー: " + error : "👻 Ghost Foreman 起動中…");
  const resumeAll = () => {
    if (window.confirm("停止を解除し、再開を許可しますか？\n\n・解除しても、止まっていた作業は自動では再開しません\n・停止中に届いた確認は、人間の判断待ちとして表示されます")) call("POST", "/stop", { scope: "resume_all" });
  };
  const live = d.mode_state && d.mode_state.gateway_mode === "live_gateway";
  const pending = d.questions.filter(isPending).length;
  const body = { home: Home, inbox: Inbox, consult: Consult, ais: AiWatch, news: News, rules: Rules, details: null }[view];
  return h("div", { style: S.page }, h("div", { style: S.wrap },
    h("div", { style: { ...S.row, justifyContent: "space-between", marginBottom: 10 } },
      h("div", null, h("strong", { style: { fontSize: 20 } }, "👻 Ghost Foreman"), h("div", { style: S.mute }, "AIたちは働く。あなたには生活がある。")),
      h("div", { style: S.row },
        h(Badge, { text: live ? "● つながっています（Gateway実接続）" : "デモ表示（模擬モード）", color: live ? C.ok : C.warn }),
        h("button", { style: { ...S.btnBad, ...S.big }, onClick: () => { if (window.confirm("すべての実スロットを停止します。人間が再開を許可するまで、自動では何も再開されません。よろしいですか？")) call("POST", "/stop", { scope: "all" }); } }, "🛑 全停止"))),
    d.halt && d.halt.active
      ? h("div", { style: { ...S.card, borderColor: C.bad, background: "#2a0a14" } },
          h("strong", { style: { color: C.bad, fontSize: 17 } }, "🛑 緊急停止中"),
          h("div", null, "人間が再開を許可するまで、自動回答・自動発注・メッセージ送信・会議の開催・ツールの自動承認は行いません。停止中に届いた確認は、解除後も自動では回答せず、判断待ちとして表示します。"),
          h("div", { style: S.mute }, "対象: " + (d.halt.all ? "すべて" : [...(d.halt.projects || []).map((p) => "案件 " + p), ...(d.halt.slots || []).map((x) => "スロット " + x)].join(", ")) + "　開始: " + (d.halt.since || "")),
          h("div", { style: { ...S.row, marginTop: 8 } },
            h("button", { style: { ...S.btnOk, ...S.big }, onClick: () => resumeAll() }, "▶ 停止をすべて解除（再開を許可）"),
            ...(d.halt.all ? [] : (d.halt.projects || []).map((p) => h("button", { key: "p" + p, style: S.btn, onClick: () => { if (window.confirm("案件 " + p + " の停止を解除しますか？")) call("POST", "/stop", { scope: "resume_project", target_id: p }); } }, "案件 " + p + " だけ解除")))))
      : null,
    error ? h("div", { style: { ...S.card, borderColor: C.bad, color: C.bad } }, error) : null,
    view === "home" ? null : h(BackBar, { title: TITLES[view] || "", onBack: () => go("home") }),
    view === "details" ? h(Details, { d, call, section, setSection }) : h(body, { d, call, focusQ, go }),
    view === "home" || !pending || view === "inbox" ? null : h("div", { style: { ...S.card, borderColor: C.warn, marginTop: 12 } }, `📥 判断待ちが ${pending} 件あります。`, " ", h("button", { style: S.btn, onClick: () => go("inbox") }, "答える"))));
}

export function mount() {
  return GhostForemanApp;
}
