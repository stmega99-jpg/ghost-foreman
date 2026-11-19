// Ghost Foreman — Kiro Crew App UI (`ui/dist/index.mjs`, resolved relative to `<app_root>/ui/`).
// This is the screen the Gateway actually serves (index.html is only used by the local dev server).
// React renders text as text, so AI-written content is never interpreted as HTML.
import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useAppApi, useAppEvents } from "@kirocrew/app-sdk";

const h = React.createElement;
const BASE = "/api/apps/ghost-foreman";

const C = { bg: "#0d0b18", card: "#17122a", border: "#2e1f47", text: "#f3e8ff", mute: "#a89bc4", accent: "#a78bfa", ok: "#34d399", warn: "#fbbf24", bad: "#f87171" };
const S = {
  page: { background: C.bg, color: C.text, minHeight: "100vh", padding: 16, fontFamily: "system-ui, sans-serif", fontSize: 14, lineHeight: 1.5 },
  card: { background: C.card, border: `1px solid ${C.border}`, borderRadius: 10, padding: 14, marginBottom: 12 },
  row: { display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" },
  btn: { background: "#3b2a66", color: C.text, border: `1px solid ${C.accent}`, borderRadius: 8, padding: "8px 12px", cursor: "pointer", fontSize: 14 },
  btnOk: { background: "#064e3b", color: C.text, border: `1px solid ${C.ok}`, borderRadius: 8, padding: "8px 12px", cursor: "pointer", fontSize: 14 },
  btnBad: { background: "#4c0519", color: C.text, border: `1px solid ${C.bad}`, borderRadius: 8, padding: "8px 12px", cursor: "pointer", fontSize: 14 },
  input: { background: "#0d0b18", color: C.text, border: `1px solid ${C.border}`, borderRadius: 8, padding: 8, fontSize: 14, minWidth: 0, flex: 1 },
  log: { background: "#0d0b18", border: `1px solid ${C.border}`, borderRadius: 8, padding: 8, margin: "6px 0", whiteSpace: "pre-wrap", fontSize: 13 },
  mute: { color: C.mute, fontSize: 12 },
};

const STATUS = {
  needs_human: ["判断待ち", C.warn],
  probing: ["担当AIへ逆質問中…", C.accent],
  needs_human_approval: ["ツール承認待ち", C.warn],
  held_spec_violation: ["仕様変更を保留", C.bad],
  held_emergency_stop: ["緊急停止中に受信（再開後に判断）", C.bad],
  auto_resolved: ["自動回答済み", C.ok],
  human_resolved: ["回答済み", C.ok],
  batch_resolved: ["一括回答済み", C.ok],
};

function Badge({ text, color }) {
  return h("span", { style: { border: `1px solid ${color || C.border}`, color: color || C.mute, borderRadius: 999, padding: "1px 8px", fontSize: 12, whiteSpace: "nowrap" } }, text);
}
const isPending = (q) => ["needs_human", "needs_human_approval", "held_spec_violation"].includes(q.status);

// ------------------------------------------------------------------ inbox
function QuestionCard({ q, call, highlight }) {
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
    h("div", { style: { ...S.row, justifyContent: "space-between" } }, h(Badge, { text: `${q.project_id} / ${q.slot_id}` }), h(Badge, { text: label, color })),
    h("h3", { style: { margin: "8px 0" } }, "AIからの確認: " + q.raw_question),
    q.context_summary ? h("p", { style: { whiteSpace: "pre-wrap" } }, q.context_summary) : null,
    q.recommendation ? h("p", { style: { color: C.accent } }, "👻 幽霊の推奨: " + q.recommendation + " — " + (q.recommendation_reason || "")) : null,
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
              h("button", { style: S.btn, onClick: () => resolve(o.label + " を採用", "one_time") }, "今回のみこの案"),
              h("button", { style: S.btnOk, onClick: () => resolve(o.label + " を標準規約として採用", "permanent_policy") }, "🧠 恒久ルールにして回答")
            )
          : null
      )
    ),
    q.final_answer ? h("div", { style: { ...S.log, borderColor: C.ok } }, h("strong", null, "[送信済み回答] "), q.final_answer) : null,
    isPending(q)
      ? h(
          "div",
          { style: { marginTop: 10, borderTop: `1px solid ${C.border}`, paddingTop: 10 } },
          h("div", { style: S.mute }, "自由に回答する（選択肢以外でもOK）"),
          h("textarea", { style: { ...S.input, width: "100%", minHeight: 60, boxSizing: "border-box" }, value: text, onChange: (e) => setText(e.target.value), placeholder: "回答を入力…" }),
          h(
            "div",
            { style: { ...S.row, marginTop: 6 } },
            h("button", { style: S.btn, disabled: !text.trim(), onClick: () => resolve(text.trim(), "one_time") }, "今回のみ回答"),
            h("button", { style: S.btnOk, disabled: !text.trim(), onClick: () => resolve(text.trim(), "permanent_policy") }, "🧠 恒久ルールにして回答"),
            h("label", { style: S.mute }, h("input", { type: "checkbox", checked: batch, onChange: (e) => setBatch(e.target.checked) }), " 同一案件の同種確認にも一括適用")
          ),
          h("div", { style: { ...S.row, marginTop: 8 } },
            h("input", { style: S.input, value: follow, onChange: (e) => setFollow(e.target.value), placeholder: "質問で返す（例: JSONとSQLiteの違いは？）" }),
            h("button", { style: S.btn, disabled: !follow.trim(), onClick: () => call("POST", "/questions/inquire", { question_id: q.id, human_inquiry: follow.trim(), re_probe_agent: true }).then(() => setFollow("")) }, "💬 質問で返す")
          )
        )
      : null
  );
}

function Inbox({ d, call, focusQ }) {
  const sorted = [...d.questions].sort((a, b) => Number(isPending(b)) - Number(isPending(a)) || String(b.created_at).localeCompare(String(a.created_at)));
  if (!sorted.length) return h("div", { style: S.card }, "受信した確認はまだありません。管理スロットのAIが foreman_ask で質問すると、ここに表示されます。");
  return h("div", null, ...sorted.map((q) => h(QuestionCard, { key: q.id, q, call, highlight: focusQ === q.id })));
}

// ------------------------------------------------------------------ slots
const slotHalted = (d, s) => !!(d.halt && (d.halt.all || (d.halt.projects || []).includes(s.project_id) || (d.halt.slots || []).includes(s.id)));

function Slots({ d, call }) {
  return h(
    "div",
    null,
    h("div", { style: { ...S.card, ...S.mute } }, "「実接続」は Kiro Crew Gateway 上の本物のセッションです。「模擬」はデモ用のサンプルで、実在のAIではありません。"),
    ...d.slots.map((s) =>
      h(
        "div",
        { key: s.id, style: S.card },
        h("div", { style: { ...S.row, justifyContent: "space-between" } },
          h("strong", null, `${s.id} ${s.name}`),
          h("span", { style: S.row }, h(Badge, { text: s.is_live ? "実接続" : "模擬", color: s.is_live ? C.ok : C.warn }), slotHalted(d, s) ? h(Badge, { text: "停止中（人間の許可待ち）", color: C.bad }) : null, h(Badge, { text: s.status }))
        ),
        h("div", null, `案件 ${s.project_id} / 役割 ${s.role} / ${s.backend}`),
        h("div", null, "現在の仕事: " + s.current_task),
        s.waiting_reason ? h("div", { style: { color: C.warn } }, "待機理由: " + s.waiting_reason) : null,
        s.next_task ? h("div", { style: S.mute }, "次の予約: " + s.next_task) : null,
        h("div", { style: { ...S.row, marginTop: 8 } },
          h("button", { style: S.btnBad, onClick: () => call("POST", "/stop", { scope: "slot", target_id: s.id }) }, "⏹ 停止"),
          d.halt && (d.halt.slots || []).includes(s.id) ? h("button", { style: S.btnOk, onClick: () => { if (window.confirm(s.name + " の停止を解除し、再開を許可しますか？\n（解除しても自動では作業を始めません）")) call("POST", "/stop", { scope: "resume_slot", target_id: s.id }); } }, "▶ この停止を解除") : null)
      )
    )
  );
}

// ------------------------------------------------------------------ meetings
const DEFAULT_PARTICIPANTS = [
  { perspective: "設計・世界観との整合性の視点", harness: "kiro" },
  { perspective: "実装工数・リスクの視点", harness: "kiro" },
  { perspective: "プレイヤー体験・面白さの視点", harness: "kiro" },
];

function Meetings({ d, call }) {
  const [topic, setTopic] = useState("");
  const [parts, setParts] = useState(DEFAULT_PARTICIPANTS);
  const [organiser, setOrganiser] = useState("kiro");
  const [harnesses, setHarnesses] = useState({ harnesses: [] });
  const [limits, setLimits] = useState({ min: 2, max: 5 });
  const loadHarnesses = (refresh) => call("GET", "/meetings/harnesses" + (refresh ? "?refresh=1" : "")).then((r) => {
      if (!r) return;
      setHarnesses(r);
      setLimits({ min: r.min_participants || 2, max: r.max_participants || 5 });
    }).catch(() => {});
  useEffect(() => {
    call("GET", "/meetings/harnesses").then((r) => {
      if (!r) return;
      setHarnesses(r);
      setLimits({ min: r.min_participants || 2, max: r.max_participants || 5 });
    }).catch(() => {});
  }, []);
  const rows = harnesses.harnesses || [];
  const agentOptions = (rows.length ? rows : [{ id: "kiro", label: "Kiro", runtime: "kiro_crew", available: true }]).map((x) =>
    h("option", { key: x.id, value: x.id, disabled: !x.available }, x.label + (x.runtime === "external_cli" ? "（Kiro Crew 外で実行）" : "") + (x.available ? "" : "　— 使えません: " + (x.reason || ""))));
  const outside = [...parts.map((p) => p.harness), organiser].some((id) => (rows.find((x) => x.id === id) || {}).runtime === "external_cli");
  const blocked = [...parts.map((p) => p.harness), organiser].filter((id) => rows.length && !(rows.find((x) => x.id === id) || {}).available);
  const setPart = (i, key, value) => setParts(parts.map((p, j) => (j === i ? { ...p, [key]: value } : p)));
  const validParts = parts.filter((p) => p.perspective.trim());
  const [project, setProject] = useState(d.projects[0] ? d.projects[0].id : "proj-foreman");
  const workers = d.slots.filter((s) => s.is_live && !["会議参加者", "議事整理", "判定係"].includes(s.role));
  const [target, setTarget] = useState({});
  return h(
    "div",
    null,
    h("div", { style: S.card },
      h("h3", { style: { marginTop: 0 } }, "💬 AI会議を開く（実エージェントが独立案出し→相互批評→整理）"),
      h("div", { style: S.row },
        h("select", { style: { ...S.input, flex: "0 0 auto" }, value: project, onChange: (e) => setProject(e.target.value) }, ...d.projects.map((p) => h("option", { key: p.id, value: p.id }, p.name))),
        h("input", { style: S.input, value: topic, onChange: (e) => setTopic(e.target.value), placeholder: "議題（例: セーブ時の安心感を与える演出）" }),
        h("button", { style: S.btnOk, disabled: !topic.trim() || validParts.length < limits.min || blocked.length > 0, onClick: () => call("POST", "/meetings", { project_id: project, topic: topic.trim(), participants: validParts.map((p) => ({ perspective: p.perspective.trim(), harness: p.harness })), synthesizer_harness: organiser }).then(() => setTopic("")) }, "開催")
      ),
      h("div", { style: { marginTop: 10 } },
        h("div", { style: S.mute }, `参加者（${limits.min}〜${limits.max}人）: それぞれの視点と、どのAIで参加するか`),
        ...parts.map((p, i) => h("div", { key: i, style: { ...S.row, marginTop: 6 } },
          h("span", { style: { width: 20 } }, String.fromCharCode(65 + i)),
          h("input", { style: S.input, value: p.perspective, onChange: (e) => setPart(i, "perspective", e.target.value), placeholder: "視点（例: 実装工数・リスクの視点）", "aria-label": `参加者${String.fromCharCode(65 + i)}の視点` }),
          h("select", { style: { ...S.input, flex: "0 0 auto" }, value: p.harness, onChange: (e) => setPart(i, "harness", e.target.value), "aria-label": `参加者${String.fromCharCode(65 + i)}のAI` }, ...agentOptions),
          h("button", { style: S.btn, disabled: parts.length <= limits.min, onClick: () => setParts(parts.filter((_, j) => j !== i)), "aria-label": `参加者${String.fromCharCode(65 + i)}を外す` }, "−"))),
        h("div", { style: { ...S.row, marginTop: 6 } },
          h("button", { style: S.btn, disabled: parts.length >= limits.max, onClick: () => setParts([...parts, { perspective: "", harness: "kiro" }]) }, "＋ 参加者を追加"),
          h("span", { style: S.mute }, "整理役（幽霊）:"),
          h("select", { style: { ...S.input, flex: "0 0 auto" }, value: organiser, onChange: (e) => setOrganiser(e.target.value), "aria-label": "整理役のAI" }, ...agentOptions)),
        h("div", { style: S.mute }, "開始前に全員へ参加確認を送り、答えられないAI（未ログインなど）がいれば会議を始めずに理由を表示します。各AIは道具（ファイル操作など）を持たず、文章で答えるだけです。"),
        h("div", { style: { ...S.row, marginTop: 4 } },
          ...rows.map((x) => h(Badge, { key: x.id, text: `${x.label}: ${x.available ? "使えます" : "使えません"}`, color: x.available ? C.ok : C.bad })),
          h("button", { style: S.btn, onClick: () => loadHarnesses(true) }, "↻ 再確認")),
        ...rows.filter((x) => !x.available && x.reason).map((x) => h("div", { key: "r" + x.id, style: { color: C.warn, fontSize: 12 } }, `${x.label}: ${x.reason}`)),
        outside ? h("div", { style: { ...S.log, borderColor: C.warn } },
          "⚠️ Claude Code / Codex は Kiro Crew の外で、Ghost Foreman が直接起動します（ブレストに限った例外）。道具（ツール）は使えず文章のやり取りだけです。緊急停止・実行記録・メモリ管理は Ghost Foreman が行います。各サービスの利用枠を使います。") : null),
      h("div", { style: S.mute }, "相談段階では何も実装しません。あなたが案を採用したときだけ、担当スロットへ発注します。")
    ),
    ...d.meetings.map((m) => {
      const live = m.summary && m.summary.live !== false;
      const chosen = target[m.id] || (workers.find((w) => w.project_id === m.project_id) || workers[0] || {}).id || "";
      return h(
        "div",
        { key: m.id, style: S.card },
        h("div", { style: { ...S.row, justifyContent: "space-between" } }, h(Badge, { text: m.project_id }), h("span", { style: S.row }, h(Badge, { text: live ? "実AI" : "模擬", color: live ? C.ok : C.warn }), h(Badge, { text: m.status === "running" ? "進行中…" : m.status, color: m.status === "running" ? C.accent : C.mute }))),
        h("h3", { style: { margin: "8px 0" } }, "議題: " + m.topic),
        h("div", { style: S.mute }, "参加: " + m.participants.join(" / ")),
        (m.summary && m.summary.participants_detail) ? h("div", { style: { ...S.row, marginTop: 4 } },
          ...[...m.summary.participants_detail, ...(m.summary.synthesizer ? [{ ...m.summary.synthesizer, speaker: "整理役（" }] : [])].map((p, i) =>
            h(Badge, { key: i, text: `${p.speaker ? p.speaker.split("（")[0] : ""}: ${p.label || p.harness}・${p.runtime_label || ""}${p.model ? "・" + p.model : ""}${p.ran_on ? (p.verified ? "" : "（未確認）") : "（未実行）"}`, color: p.verified ? (p.runtime === "external_cli" ? C.warn : C.ok) : C.mute }))) : null,
        (m.summary && m.summary.outside_kiro_crew) ? h("div", { style: { color: C.warn, fontSize: 12, marginTop: 4 } }, "この会議には、Kiro Crew の外で Ghost Foreman が直接起動したAI（ツールなし・文章のみ）が含まれます。") : null,
        ...m.rounds.map((r, i) => h("div", { key: i, style: S.log }, h("strong", null, r.phase), ...r.entries.map((e, j) => h("div", { key: j, style: { marginTop: 6 } }, h("strong", null, e.speaker + ": "), e.proposal || e.critique)))),
        m.summary && m.summary.consensus
          ? h("div", { style: { ...S.log, borderColor: C.accent } },
              h("strong", null, "👻 幽霊の論点整理"), h("div", null, m.summary.consensus),
              m.summary.conflict_points ? h("div", { style: { color: C.warn, marginTop: 4 } }, "対立点: " + m.summary.conflict_points) : null,
              m.summary.unresolved ? h("div", { style: { marginTop: 4 } }, "未決事項: " + m.summary.unresolved) : null)
          : null,
        m.summary && m.summary.note ? h("div", { style: S.mute }, m.summary.note) : null,
        m.status === "awaiting_human_adoption"
          ? h("div", { style: { marginTop: 8 } },
              h("div", { style: S.row },
                h("span", { style: S.mute }, "発注先:"),
                h("select", { style: { ...S.input, flex: "0 0 auto" }, value: chosen, onChange: (e) => setTarget({ ...target, [m.id]: e.target.value }) },
                  ...(workers.length ? workers : [{ id: "", name: "（実スロットなし）" }]).map((w) => h("option", { key: w.id || "none", value: w.id }, w.id ? `${w.id} ${w.name}` : w.name)))),
              ...(m.summary.options_for_human || []).map((o) =>
                h("div", { key: o.id, style: { ...S.log, borderColor: C.accent } },
                  h("strong", null, o.label), o.detail ? h("div", null, o.detail) : null,
                  h("button", { style: o.id === "hold_as_idea" ? S.btn : S.btnOk, disabled: o.id !== "hold_as_idea" && !chosen, onClick: () => call("POST", "/meetings/adopt", { meeting_id: m.id, option_id: o.id, target_slot_id: chosen }) }, o.id === "hold_as_idea" ? "保存のみ" : "この案を採用して発注"))))
          : null
      );
    })
  );
}

// ------------------------------------------------------------------ policies / news / audit
function Policies({ d }) {
  if (!d.policies.length) return h("div", { style: S.card }, "確定ルールはまだありません。");
  return h("div", null, ...d.policies.map((p) => h("div", { key: p.id, style: S.card },
    h("div", { style: { ...S.row, justifyContent: "space-between" } }, h("strong", null, p.title), h(Badge, { text: `${p.scope} / ${p.project_id} / v${p.version}` })),
    h("div", { style: { marginTop: 6, whiteSpace: "pre-wrap" } }, p.rule_text),
    h("div", { style: S.mute }, `${p.id} / 由来 ${p.source}${p.locked ? " / 確定仕様（無断変更不可）" : ""} / キーワード ${(p.keywords || []).join(", ")}`))));
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
      h("div", { style: S.row }, h("input", { style: S.input, value: url, onChange: (e) => setUrl(e.target.value), placeholder: "https://… 公開ページのURL" }), h("button", { style: S.btnOk, disabled: busy || !url.trim(), onClick: add }, busy ? "要約中…" : "要約して保存")),
      err ? h("div", { style: { color: C.bad, marginTop: 6 } }, err) : null,
      h("div", { style: S.mute }, "公開ページだけを取得します（内部アドレスは拒否）。事実と推定を分けて保存します。")),
    ...d.news.map((n) => h("div", { key: n.id, style: S.card },
      h("strong", null, n.title), h("div", { style: S.mute }, `${n.category} / 掲載日 ${n.published_date} / 収集理由: ${n.relevance_reason}`),
      h("div", { style: { ...S.log, borderColor: C.ok } }, h("strong", null, "事実\n"), n.facts_summary),
      h("div", { style: { ...S.log, borderColor: C.warn } }, h("strong", null, "推定\n"), n.estimates_summary),
      h("div", { style: S.mute }, "元記事: " + n.url))));
}

function Audit({ d }) {
  if (!d.audits.length) return h("div", { style: S.card }, "監査ログはまだありません。");
  return h("div", null, ...d.audits.map((a) => h("div", { key: a.id, style: S.card },
    h("div", { style: { ...S.row, justifyContent: "space-between" } }, h(Badge, { text: `${a.project_id} / ${a.slot_id}` }), h(Badge, { text: `${a.actor}: ${a.action_type}` })),
    h("div", { style: { marginTop: 6 } }, "原文: " + a.raw_question),
    a.referenced_policy_id ? h("div", { style: S.mute }, "適用ルール: " + a.referenced_policy_id) : null,
    h("div", { style: S.log }, a.answer_sent), h("div", { style: S.mute }, (a.rationale || "") + " / " + a.created_at))));
}

// ------------------------------------------------------------------ settings
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
    h("h3", { style: { marginTop: 0 } }, "📲 このiPhoneへの通知"),
    st ? h("div", null, on ? "オン（判断待ちが出たらこの端末に通知します）" : st.standalone ? "オフ" : "ホーム画面に追加したアプリから開くと、オンにできます") : h("div", null, "確認中…"),
    h("div", { style: { ...S.row, marginTop: 8 } },
      !on ? h("button", { style: S.btnOk, disabled: busy || !(st && st.standalone), onClick: enable }, "🔔 通知をオンにする") : null,
      on ? h("button", { style: S.btn, disabled: busy, onClick: test }, "テスト通知を送る") : null),
    msg ? h("div", { style: { marginTop: 6 } }, msg) : null,
    h("div", { style: S.mute }, "通知がいつ届くかは、上部のモード（離席=すぐ / 常駐=送らない / おやすみ=朝にまとめて）で変わります。テスト通知はモードに関係なく送ります。"));
}

function Settings({ d, call }) {
  const allow = !!(d.mode_state && d.mode_state.allow_unpublished_to_free_tier);
  const u = d.usage || { totals: [] };
  const cooling = u.gemini_cooldown_until && u.gemini_cooldown_until * 1000 > Date.now();
  const toggle = () => {
    const want = !allow;
    if (want && !window.confirm("制作内容（AIからの質問・確定ルールの本文）を Gemini の無料枠へ送信します。\n無料枠に送った内容は、Google によって製品改善などに利用される可能性があります。\n\n許可しますか？")) return;
    call("POST", "/mode", { allow_unpublished_to_free_tier: want });
  };
  return h("div", null,
    h(PhoneNotifications, { call }),
    h("div", { style: S.card },
      h("h3", { style: { marginTop: 0 } }, "🔒 制作内容の Gemini 無料枠への送信"),
      h("div", null, "AIからの質問や確定ルールの本文を、判定のために Gemini の無料枠へ送ってよいかを決めます。"),
      h("label", { style: { ...S.row, margin: "8px 0" } }, h("input", { type: "checkbox", checked: allow, onChange: toggle }), h("strong", null, allow ? "許可している（制作内容を無料枠へ送信する）" : "許可していない（制作内容は送信しない）")),
      h("div", { style: S.mute }, "許可しない場合、制作内容の判定は Kiro Crew の実セッションで行います。公開ニュースの整理はこの設定に関係なく Gemini を使います。")),
    h("div", { style: S.card },
      h("h3", { style: { marginTop: 0 } }, "💰 費用と使用量"),
      h("div", null, "実際の請求額: ", h(Badge, { text: u.actual_billing || "未確認", color: C.warn })),
      h("div", { style: S.mute }, u.billing_note || ""),
      h("div", { style: { margin: "6px 0" } }, cooling ? "Gemini無料枠は上限により待機中（Kiroの実セッションに切替。有料APIには切り替えません）" : "Gemini無料枠: 利用可能（または未使用）"),
      h("table", { style: { width: "100%", borderCollapse: "collapse", fontSize: 13 } },
        h("thead", null, h("tr", { style: { textAlign: "left" } }, ...["提供元", "呼び出し", "成功", "トークン(入/出)", "請求額"].map((t) => h("th", { key: t }, t)))),
        h("tbody", null, ...(u.totals || []).map((t) => h("tr", { key: t.provider_id }, h("td", null, t.provider_id), h("td", null, t.calls), h("td", null, t.ok_calls), h("td", null, `${t.input_tokens} / ${t.output_tokens}`), h("td", null, t.cost_display || "未確認"))))),
      h("div", { style: S.mute }, "トークン数は提供元の実測値です。Kiro の使用量はホストが公開していないため、0ではなく未確認として扱います。有料APIへの切替機能は実装していません。")),
    h("div", { style: S.card },
      h("h3", { style: { marginTop: 0 } }, "🧪 Kiro Crew 外で実行したAI（会議の参加者）"),
      h("div", { style: S.mute }, "Claude Code / Codex を Ghost Foreman が直接起動した記録です。質問の本文は保存せず、ハッシュだけを残します。請求額は確認できないため「未確認」です。"),
      ...(d.external_runs || []).map((r) => h("div", { key: r.id, style: { ...S.log, borderColor: r.status === "ok" ? C.ok : C.bad } },
        h("strong", null, `[${r.status}] ${r.harness}${r.model ? "・" + r.model : ""}`), ` ${r.started_at}　${Math.round((r.duration_ms || 0) / 100) / 10}秒　トークン ${r.input_tokens}/${r.output_tokens}　会議 ${r.meeting_id || "-"}`,
        r.error ? h("div", { style: { color: C.bad } }, r.error) : null)),
      (d.external_runs || []).length ? null : h("div", { style: S.mute }, "まだ記録はありません。")),
    h("div", { style: S.card },
      h("h3", { style: { marginTop: 0 } }, "🔔 通知の履歴"),
      h("div", { style: S.mute }, "sent=送信 / held=おやすみ中に保留 / held_resident=常駐モードのため通知せず / failed=失敗 / not_sent=模擬モード"),
      ...(d.notifications || []).map((n) => h("div", { key: n.id, style: S.log }, h("strong", null, `[${n.delivery}] `), `${n.title} ${n.body}`, h("div", { style: S.mute }, `${n.ts} ${n.detail || ""}`)))));
}

// ------------------------------------------------------------------ app
const TABS = [["inbox", "📥 判断待ち"], ["slots", "🤖 スロット"], ["meetings", "💬 AI会議"], ["policies", "🧠 記憶・ルール"], ["news", "📰 ニュース"], ["settings", "⚙️ 設定・費用"], ["audit", "📜 監査ログ"]];

export default function GhostForemanApp() {
  const api = useAppApi();
  const [d, setD] = useState(null);
  const [error, setError] = useState("");
  const focusQ = useMemo(() => new URLSearchParams(window.location.search).get("q") || "", []);
  const [tab, setTab] = useState(focusQ ? "inbox" : "inbox");

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
  const body = { inbox: Inbox, slots: Slots, meetings: Meetings, policies: Policies, news: News, settings: Settings, audit: Audit }[tab];
  return h("div", { style: S.page },
    h("div", { style: { ...S.row, justifyContent: "space-between", marginBottom: 10 } },
      h("div", null, h("strong", { style: { fontSize: 18 } }, "👻 Ghost Foreman"), h("div", { style: S.mute }, "Your agents work. You have a life.")),
      h("div", { style: S.row },
        h(Badge, { text: live ? "Gateway実接続" : "模擬モード", color: live ? C.ok : C.warn }),
        h("select", { style: { ...S.input, flex: "0 0 auto" }, value: (d.mode_state && d.mode_state.mode) || "away", onChange: (e) => call("POST", "/mode", { mode: e.target.value }) },
          h("option", { value: "resident" }, "🏠 常駐（通知しない）"), h("option", { value: "away" }, "🚃 離席（判断待ちを通知）"), h("option", { value: "sleep" }, "🌙 おやすみ（朝にまとめて通知）")),
        h("button", { style: S.btnBad, onClick: () => { if (window.confirm("すべての実スロットを停止します。人間が再開を許可するまで、自動では何も再開されません。よろしいですか？")) call("POST", "/stop", { scope: "all" }); } }, "🛑 全停止"),
        h("button", { style: S.btnOk, onClick: () => resumeAll() }, "▶ 停止を解除"))),
    d.halt && d.halt.active
      ? h("div", { style: { ...S.card, borderColor: C.bad, background: "#2a0a14" } },
          h("strong", { style: { color: C.bad, fontSize: 16 } }, "🛑 緊急停止中"),
          h("div", null, "人間が再開を許可するまで、自動回答・自動発注・メッセージ送信・会議の開催・ツールの自動承認は行いません。停止中に届いた確認は、解除後も自動では回答せず、判断待ちとして表示します。"),
          h("div", { style: S.mute }, "対象: " + (d.halt.all ? "すべて" : [...(d.halt.projects || []).map((p) => "案件 " + p), ...(d.halt.slots || []).map((x) => "スロット " + x)].join(", ")) + "　開始: " + (d.halt.since || "")),
          h("div", { style: { ...S.row, marginTop: 8 } },
            h("button", { style: S.btnOk, onClick: () => resumeAll() }, "▶ 停止をすべて解除（再開を許可）"),
            ...(d.halt.all ? [] : (d.halt.projects || []).map((p) => h("button", { key: "p" + p, style: S.btn, onClick: () => { if (window.confirm("案件 " + p + " の停止を解除しますか？")) call("POST", "/stop", { scope: "resume_project", target_id: p }); } }, "案件 " + p + " だけ解除")))))
      : null,
    error ? h("div", { style: { ...S.card, borderColor: C.bad, color: C.bad } }, error) : null,
    h("div", { style: { ...S.row, marginBottom: 10 } }, ...TABS.map(([k, t]) => h("button", { key: k, style: { ...S.btn, ...(tab === k ? { background: C.accent, color: "#0d0b18" } : {}) }, onClick: () => setTab(k) }, t + (k === "inbox" && pending ? ` (${pending})` : "")))),
    h(body, { d, call, focusQ })
  );
}

export function mount() {
  return GhostForemanApp;
}
