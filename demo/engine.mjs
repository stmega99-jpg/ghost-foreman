// Ghost Foreman sample-data engine for the public demo (demo/index.html).
//
// This is NOT the real backend. It is a small in-memory stand-in that answers the same API paths the screen uses
// (ui/dist/index.mjs), with made-up sample data. It never makes a network request, never reads a file, and has no
// way to reach an AI service, an API key or the owner's PC. Everything shown is labelled as a sample
// ("デモ用の見本（模擬）" / "Demo sample (simulated)") by the screen itself, because every slot reports is_live=false
// and every meeting reports summary.live=false.
//
// Texts written by an AI or a person in the real app are written here as {ja, en} pairs and picked by the language
// chosen on the screen each time the dashboard is read (so the language switch works on the sample data too).
// Fixed backend labels (status names, "Kiro Crew で実行", the round titles ...) are the same Japanese strings the real
// backend writes; the screen translates those itself.

const L = (ja, en) => ({ ja, en });
const isPair = (v) => v && typeof v === "object" && !Array.isArray(v) && typeof v.ja === "string" && typeof v.en === "string" && Object.keys(v).length === 2;
export function localize(v, lang) {
  if (isPair(v)) return v[lang === "en" ? "en" : "ja"];
  if (Array.isArray(v)) return v.map((x) => localize(x, lang));
  if (v && typeof v === "object") return Object.fromEntries(Object.entries(v).map(([k, x]) => [k, localize(x, lang)]));
  return v;
}

export const GEMINI_CONSENT_REQUIRED = L(
  "Gemini を参加させるには、この会議の内容（議題・各AIの案など、未公開の制作情報を含みます）を Gemini 無料枠に送る許可が必要です。無料枠に送った内容は、Google がサービス改善に使う場合があります。",
  "To let Gemini take part, you must allow sending this meeting's content (which includes unpublished project information) to the Gemini free tier. Google may use what is sent to the free tier to improve its services.");

const RUNTIME = { kiro: "Kiro Crew で実行", claude: "Kiro Crew 外で実行", codex: "Kiro Crew 外で実行", gemini: "Kiro Crew 外で実行（Gemini API 無料枠）" };
const HARNESS_LABEL = { kiro: "Kiro", claude: "Claude Code", codex: "Codex", gemini: "Gemini" };

// ------------------------------------------------------------------ sample data
// Five different kinds of work on purpose (a game, an app, a channel, a shop, a novel): Ghost Foreman is not tied to one field.
function initialProjects(ts) {
  return [
    { id: "proj-game", name: L("アクションゲーム制作（見本）", "Action game (sample)"), description: L("見本の案件です", "A sample project"), priority: 1, status: "active", budget_usd: 20, spent_usd: 0, created_at: ts },
    { id: "proj-budget", name: L("家計簿アプリ開発（見本）", "Budgeting app (sample)"), description: L("見本の案件です", "A sample project"), priority: 1, status: "active", budget_usd: 10, spent_usd: 0, created_at: ts },
    { id: "proj-youtube", name: L("YouTubeチャンネル運営（見本）", "Running a YouTube channel (sample)"), description: L("見本の案件です", "A sample project"), priority: 2, status: "active", budget_usd: 5, spent_usd: 0, created_at: ts },
    { id: "proj-shop", name: L("オンラインショップ開業（見本）", "Opening an online shop (sample)"), description: L("見本の案件です", "A sample project"), priority: 1, status: "active", budget_usd: 10, spent_usd: 0, created_at: ts },
    { id: "proj-novel", name: L("恋愛小説の執筆（見本）", "Writing a romance novel (sample)"), description: L("見本の案件です", "A sample project"), priority: 2, status: "active", budget_usd: 5, spent_usd: 0, created_at: ts },
  ];
}
const SLOT_DEFS = [
  ["slot-01", "proj-game", "Claude-Code #1 (Save data)", "claude-code", L("実装担当", "Implementation"), "working", L("セーブデータ読み書きの実装", "Implementing save-data read/write"), L("オートセーブのテスト作成", "Write auto-save tests"), "feat/save"],
  ["slot-02", "proj-game", "Codex #1 (Data design)", "codex", L("データ設計", "Data design"), "waiting_human", L("セーブ形式の検討", "Choosing the save format"), "", "feat/save-format"],
  ["slot-03", "proj-game", "Kiro #1 (Review)", "kiro", L("査読担当", "Review"), "idle", L("待機中", "Waiting for work"), L("セーブ実装のレビュー", "Review the save implementation"), ""],
  ["slot-04", "proj-shop", "Kiro #2 (Research)", "kiro", L("市場調査", "Market research"), "working", L("似た商品3つの価格の比較", "Comparing the prices of three similar products"), L("発売時期の候補を出す", "Suggest launch dates"), ""],
  ["slot-05", "proj-shop", "Claude-Code #2 (Launch plan)", "claude-code", L("開業計画", "Launch plan"), "waiting_human", L("開店までの作業表づくり", "Writing the opening checklist"), "", ""],
  ["slot-06", "proj-novel", "Codex #2 (Draft)", "codex", L("下書き", "Drafting"), "working", L("第1章の下書き（約2,000字）", "Drafting chapter 1 (about 1,000 words)"), L("題名の案を3つ", "Three title ideas"), ""],
  ["slot-07", "proj-budget", "Claude-Code #3 (Charts)", "claude-code", L("画面実装", "Screens"), "working", L("月ごとの支出グラフの実装", "Building the monthly spending chart"), "", "feat/charts"],
  ["slot-08", "proj-youtube", "Kiro #3 (Scripts)", "kiro", L("台本", "Scripts"), "idle", L("待機中", "Waiting for work"), L("次の動画の台本", "Script for the next video"), ""],
];
function initialSlots(ts) {
  return SLOT_DEFS.map(([id, project_id, name, backend, role, status, current_task, next_task, worktree_branch]) => ({
    id, project_id, name, backend, role, ownership: "managed", status, current_task, waiting_reason: status === "waiting_human" ? L("あなたの判断待ち", "Waiting for your decision") : "",
    next_task, worktree_branch, updated_at: ts, agent: "", live_key: "", history: [{ role: "system", text: L("見本のスロットです", "A sample slot") }], context: [], is_live: false, gateway_mode: "simulated",
  }));
}
function initialQuestions(ts) {
  return [
    {
      id: "q-demo-1", project_id: "proj-game", slot_id: "slot-02", kind: "natural_question",
      raw_question: L("セーブデータの形式は JSON と SQLite のどちらにしますか？", "Should the save data use JSON or SQLite?"),
      context_summary: L("方針に合うルールが見つからなかったため、あなたの判断を待っています。", "No policy matched, so this waits for your decision."),
      recommendation: L("案A（SQLite）", "Option A (SQLite)"),
      recommendation_reason: L("データが約2,000件あり、途中で止まっても壊れにくいためです。", "There are about 2,000 records, and it is less likely to break if it stops midway."),
      status: "needs_human", probe_count: 0, proposes_spec_change: 0, conflict_with_slot: "", resolution_source: "", final_answer: "", policy_id_applied: "",
      created_at: ts, updated_at: ts,
      options: [
        { id: "A", label: L("案A: SQLite", "Option A: SQLite"), difference: L("1つのファイルで検索が速く、書き込み途中の停止にも強い", "One file, fast search, and safe if it stops while writing"), impact: L("標準ライブラリだけで動く。手戻りが少ない", "Works with the standard library only. Little rework") },
        { id: "B", label: L("案B: JSON", "Option B: JSON"), difference: L("テキストで読めて単純だが、件数が増えると遅い", "Readable text and simple, but slow as records grow"), impact: L("後で移行する可能性が高い", "Likely to need a migration later") },
      ],
      probe_history: [],
    },
    {
      id: "q-demo-2", project_id: "proj-shop", slot_id: "slot-05", kind: "natural_question",
      raw_question: L("価格の比較のために、有料のAI APIを少しだけ使ってもよいですか？", "May I use a paid AI API a little, to compare prices?"),
      context_summary: L("お金がかかる話なので、幽霊は代わりに答えません。", "This involves cost, so the Ghost does not answer for you."),
      recommendation: "", recommendation_reason: "",
      status: "needs_human", probe_count: 0, proposes_spec_change: 0, conflict_with_slot: "", resolution_source: "", final_answer: "", policy_id_applied: "",
      created_at: ts, updated_at: ts,
      options: [],
      probe_history: [],
    },
    {
      id: "q-demo-3", project_id: "proj-novel", slot_id: "slot-06", kind: "natural_question",
      raw_question: L("物語は一人称と三人称のどちらで書きますか？", "Should the story be told in the first or the third person?"),
      context_summary: L("決めてあるルール（pol-novel-01）に合ったため、あなたを呼ばずに幽霊が答えました。", "A rule you set earlier (pol-novel-01) matched, so the Ghost answered without calling you."),
      recommendation: "", recommendation_reason: "",
      status: "auto_resolved", probe_count: 0, proposes_spec_change: 0, conflict_with_slot: "", resolution_source: "ghost_policy",
      final_answer: L("【幽霊の代理判断（根拠: pol-novel-01）】主人公の一人称で書いてください。", "[The Ghost's decision on your behalf (basis: pol-novel-01)] Write it in the first person, as the heroine."),
      policy_id_applied: "pol-novel-01", created_at: ts, updated_at: ts, options: [], probe_history: [],
    },
  ];
}
function initialPolicies(ts) {
  const mk = (id, scope, project_id, title, rule_text, locked) => ({ id, scope, project_id, title, rule_text, locked, version: 1, active: 1, source: "sample", created_at: ts, updated_at: ts, keywords: [] });
  return [
    mk("pol-global-01", "global", "*", L("有料APIを勝手に使わない", "Never use a paid API without permission"), L("無料枠か契約済みの枠を優先し、人間の許可なしに従量課金のAPIへ切り替えない。", "Prefer free or already-contracted quotas, and never switch to a pay-per-use API without a human's permission."), 1),
    mk("pol-global-02", "global", "*", L("緊急停止のあとは、人間が許可するまで再開しない", "After an emergency stop, nothing resumes until a human allows it"), L("停止を解除できるのは人間だけ。解除しても、止まっていた作業は自動では再開しない。", "Only a human can release a stop. Releasing it does not restart stopped work by itself."), 1),
    mk("pol-game-01", "project", "proj-game", L("日時の保存形式", "Date format"), L("日時はすべて ISO8601 の UTC 文字列で保存する。", "Save every date as an ISO 8601 UTC string."), 0),
    mk("pol-shop-01", "project", "proj-shop", L("価格の表示", "How prices are shown"), L("価格はすべて税込みで表示する。", "Show every price including tax."), 0),
    mk("pol-novel-01", "project", "proj-novel", L("語りの視点", "Point of view"), L("物語は主人公の一人称で書く。", "Tell the story in the first person, as the heroine."), 0),
    mk("pol-budget-01", "project", "proj-budget", L("金額の扱い", "Amounts"), L("金額は1円単位の整数で保存する。", "Store amounts as whole numbers of the smallest currency unit."), 0),
    mk("pol-youtube-01", "project", "proj-youtube", L("動画の長さ", "Video length"), L("動画は10分以内にまとめる。", "Keep every video under 10 minutes."), 0),
  ];
}
function initialNews(ts) {
  return [
    {
      id: "news-demo-1", project_id: "proj-shop", category: L("市場の動き（見本）", "Market trends (sample)"), title: L("小さな商品の発売時期の傾向（見本）", "When small products tend to launch (sample)"),
      url: "https://example.com/sample-news", published_date: ts.slice(0, 10),
      facts_summary: L("【事実（見本）】これは見本のデータです。実際のニュースではありません。", "[Fact (sample)] This is sample data, not real news."),
      estimates_summary: L("【推定（見本）】推定は事実と分けて書きます。", "[Estimate (sample)] Estimates are written apart from facts."),
      relevance_reason: L("事実と推定を分けて表示する例です。", "An example of showing facts and estimates separately."), created_at: ts,
    },
  ];
}
// ------------------------------------------------------------------ the meeting sample
const CANNED = [
  {
    title: L("下側に承認ボタン＋長押し", "Bottom approve button with press-and-hold"),
    proposal: L("承認ボタンを画面の下側に置き、1秒の長押しで確定する。", "Put the approve button at the bottom and confirm with a one-second press-and-hold."),
    pros: L("片手で届く／押し間違いを防げる", "Reachable with one hand / prevents mistaken taps"), risks: L("急ぐときに少し手間", "Slightly slower when in a hurry"),
    critique: L("長押しは揺れる電車では難しい。重要度で分けるとよい。", "Holding is hard on a shaking train. Splitting by importance would help."),
    improved: L("重要な承認だけ長押しにし、普段は1タップ＋取り消し。", "Hold only for important approvals; otherwise one tap plus undo."),
  },
  {
    title: L("1タップ＋3秒の取り消し", "One tap with a 3-second undo"),
    proposal: L("1タップで承認し、3秒間は取り消せるバーを出す。", "Approve with one tap and show a bar that can undo for 3 seconds."),
    pros: L("速い／確認ダイアログが不要", "Fast / no confirmation dialog"), risks: L("取り消せない操作には使えない", "Cannot be used for actions that cannot be undone"),
    critique: L("取り消せない承認には向かない。分類が必要。", "Not suited to approvals that cannot be undone. A classification is needed."),
    improved: L("取り消せる承認だけ使い、取り消せないものは長押し。", "Use it only for undoable approvals; use hold for the rest."),
  },
  {
    title: L("下側のボタンをまとめたバー", "A bottom bar that groups the buttons"),
    proposal: L("承認・却下を下側の固定バーにまとめる。", "Group approve and reject in a fixed bar at the bottom."),
    pros: L("親指で届く", "Within thumb reach"), risks: L("押し間違いの対策が別に必要", "Needs a separate guard against mistaken taps"),
    critique: L("位置だけでは安全にならない。確認の仕組みを足す。", "Position alone does not make it safe. Add a confirmation mechanism."),
    improved: L("固定バーに、重要度に応じた確認を組み合わせる。", "Combine the fixed bar with a confirmation that depends on importance."),
  },
  {
    title: L("まず位置だけ変えて、後で確認方法を決める", "Move the buttons first, decide the guard later"),
    proposal: L("まずボタンを下側へ移し、押し間違いの数を測ってから確認方法を決める。", "Move the buttons down first, measure mistaken taps, then decide the guard."),
    pros: L("小さく始められる", "A small start"), risks: L("測るまでは安全性が上がらない", "Safety does not improve until it is measured"),
    critique: L("測定の期間を決めておかないと、決まらないままになる。", "Without a fixed measuring period, it may never be decided."),
    improved: L("2週間測って、結果で長押しか取り消しかを決める。", "Measure for two weeks, then choose hold or undo from the result."),
  },
];

function buildMeeting(id, projectId, topic, specs, organiser, lang, consent, ts) {
  const letters = "ABCDE";
  const speakers = specs.map((s, i) => `参加者${letters[i]}（${s.perspective}／${HARNESS_LABEL[s.harness]}）`);
  const person = (harness, speaker, perspective) => ({ harness, label: HARNESS_LABEL[harness], speaker, perspective, runtime: harness === "kiro" ? "kiro_crew" : harness === "gemini" ? "gemini_api" : "external_cli", runtime_label: RUNTIME[harness], ran_on: "", model: "", verified: false });
  const rounds = [
    { phase: "0. 参加確認 (各AIの実際の返答と実行場所)", entries: [...speakers, "幽霊（整理役／" + HARNESS_LABEL[organiser] + "）"].map((sp, i) => ({
      speaker: sp, proposal: L("（見本）この参加確認は固定の見本です。実際のAIには送っていません。", "(Sample) This participation check is fixed sample text. Nothing was sent to a real AI."), live: false, ok: true, runtime: "simulated", self_report_check: "ok" })) },
    { phase: "1. 独立案出し (Independent Ideation)", entries: specs.map((s, i) => {
      const c = CANNED[i % CANNED.length];
      return { speaker: speakers[i], proposal: L(`【${c.title.ja}】${c.proposal.ja}（利点: ${c.pros.ja} / リスク: ${c.risks.ja}）`, `[${c.title.en}] ${c.proposal.en} (Pros: ${c.pros.en} / Risks: ${c.risks.en})`), live: false, runtime: "simulated" };
    }) },
    { phase: "2. 相互批評・改善 (Mutual Critique & Refinement)", entries: specs.map((s, i) => {
      const c = CANNED[i % CANNED.length];
      return { speaker: speakers[i], critique: L(`批評: ${c.critique.ja} → 改善案: ${c.improved.ja}`, `Critique: ${c.critique.en} → Improved proposal: ${c.improved.en}`), live: false, runtime: "simulated" };
    }) },
  ];
  const summary = {
    note: "【模擬】固定のサンプルです。実際のAIによる会議ではありません。人間が採用ボタンを押すまで制作には移しません。",
    live: false,
    participants_detail: specs.map((s, i) => person(s.harness, speakers[i], s.perspective)),
    synthesizer: person(organiser, "幽霊（整理役）", ""),
    language: lang,
    outside_kiro_crew: [...specs.map((s) => s.harness), organiser].some((h) => h !== "kiro"),
    gemini_consent: { asked: consent.asked, allowed: consent.allowed, scope: "この会議のみ", decided_at: consent.asked ? ts : "", text: consent.allowed ? "この会議の内容を Gemini 無料枠に送ることを許可" : "" },
    consensus: L("全員が「承認ボタンを下側に置く」ことに賛成でした。押し間違いを防ぐ方法だけが分かれました。", "Everyone agreed to put the approve button at the bottom. They differed only on how to prevent mistaken taps."),
    conflict_points: L("長押し（確実だが遅い）と、1タップ＋取り消し（速いが取り消せない承認には使えない）で分かれました。", "Press-and-hold (certain but slow) versus one tap plus undo (fast, but unusable for approvals that cannot be undone)."),
    unresolved: L("取り消せる承認と取り消せない承認の分け方。", "How to split approvals that can be undone from those that cannot."),
    options_for_human: [
      { id: "opt1", label: L("すべて1秒の長押し", "One-second hold for everything"), detail: L("下側のボタンを長押しで確定する。", "Confirm with a press-and-hold on the bottom button.") },
      { id: "opt2", label: L("取り消せるものは1タップ＋取り消し、重要なものだけ長押し", "One tap plus undo for undoable ones; hold only for important ones"), detail: L("重要度の分類を作り、分けて使う。", "Build an importance classification and use each accordingly.") },
      { id: "hold_as_idea", label: "まだ制作には移さず、アイデア帳に議事録として保存のみ行う", detail: "" },
    ],
  };
  return { id, project_id: projectId, topic, participants: speakers, created_at: ts, rounds, summary, status: "awaiting_human_adoption", _t0: 0, _lang: lang };
}

// ------------------------------------------------------------------ the engine
const STAGE_MS = 1200;
const nowIso = (d) => new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 19) + "+0900";

export function createEngine({ getLang = () => "ja", clock = () => new Date() } = {}) {
  const ts0 = nowIso(clock());
  const s = {
    mode_state: { mode: "away", quiet_until: "07:30", allow_unpublished_to_free_tier: false, gateway_mode: "simulated_gateway" },
    projects: initialProjects(ts0), slots: initialSlots(ts0), questions: initialQuestions(ts0), policies: initialPolicies(ts0),
    audits: [], meetings: [], ideas: [], news: initialNews(ts0),
    halt: { all: false, projects: [], slots: [], since: "", reason: "", active: false },
    lease: { device_id: "main-workstation", holder_type: "human", holder_slot_id: "", purpose: L("人間がPCを使用中（最優先）", "A human is using the PC (top priority)"), status: "human_active", last_recording_note: "", updated_at: ts0, queue: [] },
    counter: 0,
  };
  const uid = (p) => `${p}-${(++s.counter).toString(36).padStart(4, "0")}`;
  const fail = (status, ja, en) => { const e = new Error(getLang() === "en" ? en : ja); e.status = status; throw e; };
  const slotOf = (id) => s.slots.find((x) => x.id === id);
  const anyPending = (slotId) => s.questions.some((q) => q.slot_id === slotId && ["needs_human", "needs_human_approval", "held_spec_violation"].includes(q.status));
  const refreshSlotStatus = (slotId) => {
    const sl = slotOf(slotId);
    if (!sl || sl.status === "stopped") return;
    sl.status = anyPending(slotId) ? "waiting_human" : sl.status === "waiting_human" ? "working" : sl.status;
    sl.waiting_reason = sl.status === "waiting_human" ? L("あなたの判断待ち", "Waiting for your decision") : "";
  };
  const halted = (sl) => s.halt.all || s.halt.projects.includes(sl.project_id) || s.halt.slots.includes(sl.id);
  const snapshotHalt = () => ({ ...s.halt, projects: [...s.halt.projects], slots: [...s.halt.slots], active: s.halt.all || s.halt.projects.length > 0 || s.halt.slots.length > 0 });
  const audit = (q, actor, action_type, answer_sent, rationale, policy = "") =>
    s.audits.unshift({ id: uid("aud"), question_id: q.id, project_id: q.project_id, slot_id: q.slot_id, actor, action_type, raw_question: q.raw_question, referenced_policy_id: policy, answer_sent, rationale, promoted_to_policy_id: "", reverted: 0, created_at: nowIso(clock()) });
  audit(s.questions[2], "ghost_foreman", "auto_reply", s.questions[2].final_answer, L("決めてあるルール pol-novel-01 を適用して、すぐに作業を続けさせました。", "Applied the rule pol-novel-01 and let the work continue at once."), "pol-novel-01");

  // A meeting reveals one round per STAGE_MS since it started (so it can be tested with a fake clock).
  function visibleMeeting(m) {
    const stage = Math.floor((clock().getTime() - m._t0) / STAGE_MS);
    const done = stage >= 4;
    const { _t0, _lang, ...rest } = m;
    if (done) return rest;
    const running = { ...rest, status: "running", rounds: rest.rounds.slice(0, Math.max(0, stage)), summary: { note: "【模擬】固定のサンプルの会議を進めています。", live: false, participants_detail: rest.summary.participants_detail, synthesizer: rest.summary.synthesizer, language: rest.summary.language, outside_kiro_crew: rest.summary.outside_kiro_crew, gemini_consent: rest.summary.gemini_consent } };
    return running;
  }
  const meetingStatus = (m) => (m.status !== "awaiting_human_adoption" ? m.status : Math.floor((clock().getTime() - m._t0) / STAGE_MS) >= 4 ? "awaiting_human_adoption" : "running");
  const shown = (m) => (m.status === "awaiting_human_adoption" ? visibleMeeting(m) : (({ _t0, _lang, ...r }) => r)(m));

  function dashboard() {
    const lang = getLang();
    const usage = { totals: [], recent: [], gemini_cooldown_until: 0, allow_unpublished_to_free_tier: s.mode_state.allow_unpublished_to_free_tier, actual_billing: "未確認",
      billing_note: L("これは見本の画面です。実際の請求額は表示できません。", "This is a sample screen. A real billing amount cannot be shown."), paid_api: "not implemented: no path to a metered paid API exists" };
    const slots = s.slots.map((x) => ({ ...x, status: x.status }));
    const body = {
      app: "ghost-foreman", version: "0.2.0-demo", mode_state: { ...s.mode_state }, projects: s.projects, slots, questions: s.questions, policies: s.policies,
      budgets: [], audits: s.audits, meetings: s.meetings.map(shown), ideas: s.ideas, news: s.news,
      desktop_lease: { ...s.lease, queue: [...s.lease.queue] }, usage, halt: snapshotHalt(), external_runs: [], notifications: [],
    };
    return localize(body, lang);
  }

  const handlers = {
    "GET /dashboard": () => dashboard(),
    "GET /usage": () => dashboard().usage,
    "GET /policies": () => ({ policies: localize(s.policies, getLang()) }),
    "GET /meetings/external-runs": () => ({ runs: [] }),
    "GET /m/ping": () => ({ ok: true }),
    "GET /meetings/harnesses": () => ({
      max_participants: 5, min_participants: 2,
      harnesses: ["kiro", "claude", "codex", "gemini"].map((id) => ({
        id, label: HARNESS_LABEL[id], runtime: id === "kiro" ? "kiro_crew" : id === "gemini" ? "gemini_api" : "external_cli", runtime_label: RUNTIME[id], available: true, reason: "",
        ...(id === "gemini" ? { needs_consent: true, consent_note: localize(GEMINI_CONSENT_REQUIRED, getLang()) } : {}),
      })),
    }),
    // Projects: the same rules as the real app (generated id, no duplicate active names, archive instead of delete).
    "POST /projects": (b) => {
      const name = String(b.name ?? "").trim(), description = String(b.description ?? "").trim();
      if (!name || name.length > 80 || description.length > 300) fail(400, "案件の名前は1〜80文字、説明は300文字までです", "A project name needs 1 to 80 characters, and a description up to 300");
      if (s.projects.some((p) => p.status === "active" && localize(p.name, getLang()) === name)) fail(400, "同じ名前の進行中の案件があります", "An active project with this name already exists");
      const p = { id: uid("proj"), name, description, priority: 2, status: "active", budget_usd: 0, spent_usd: 0, created_at: nowIso(clock()) };
      s.projects.push(p);
      return localize(p, getLang());
    },
    "POST /projects/update": (b) => {
      const p = s.projects.find((x) => x.id === b.project_id);
      if (!p) fail(400, "その案件は見つかりません", "That project was not found");
      const name = b.name == null ? localize(p.name, getLang()) : String(b.name).trim();
      const description = b.description == null ? localize(p.description, getLang()) : String(b.description).trim();
      const status = b.status == null ? p.status : String(b.status);
      if (!name || name.length > 80 || description.length > 300) fail(400, "案件の名前は1〜80文字、説明は300文字までです", "A project name needs 1 to 80 characters, and a description up to 300");
      if (!["active", "archived"].includes(status)) fail(400, "その状態にはできません", "That status is not allowed");
      if (status === "active" && s.projects.some((x) => x !== p && x.status === "active" && localize(x.name, getLang()) === name)) fail(400, "同じ名前の進行中の案件があります", "An active project with this name already exists");
      if (b.name != null) p.name = name;
      if (b.description != null) p.description = description;
      p.status = status;
      return localize(p, getLang());
    },
    "POST /questions/inquire": (b) => {
      const q = s.questions.find((x) => x.id === b.question_id);
      if (!q) fail(404, "その確認は見つかりません", "That question was not found");
      const text = String(b.human_inquiry || "").trim();
      if (!text) fail(400, "質問を入力してください", "Please type a question");
      const ts = nowIso(clock());
      q.probe_history.push({ role: "human_inquiry", text, ts });
      // At most one question back to the AI per question (max_probes = 1); after that only the Ghost explains.
      if (b.re_probe_agent !== false && q.probe_count < 1) {
        q.probe_count += 1;
        q.probe_history.push({ role: "agent_re_clarification", text: L("【見本】担当AIへの再確認結果（固定の見本）。実際のAIには送っていません。", "[Sample] The assigned AI's answer to the follow-up (fixed sample). Nothing was sent to a real AI."), ts });
      }
      q.probe_history.push({ role: "ghost_explanation", text: L("【見本】幽霊の解説（固定の見本）\n・案A: 1つのファイルで扱えて、書き込み途中で止まっても壊れにくい。\n・案B: 人が読めて単純だが、件数が増えると遅い。\n→ 今回の用途なら案Aの手戻りが少ないです。", "[Sample] The Ghost's explanation (fixed sample)\n- Option A: one file, and hard to break if it stops mid-write.\n- Option B: human-readable and simple, but slow as records grow.\n→ For this use, Option A means the least rework."), ts });
      q.updated_at = ts;
      return localize(q, getLang());
    },
    "POST /questions/resolve": (b) => {
      const q = s.questions.find((x) => x.id === b.question_id);
      if (!q) fail(404, "その確認は見つかりません", "That question was not found");
      if (!["needs_human", "needs_human_approval", "held_spec_violation"].includes(q.status)) fail(400, "この確認はすでに回答済みです", "This question has already been answered");
      const answer = String(b.answer_text || "").trim();
      if (!answer) fail(400, "回答を入力してください", "Please type an answer");
      const mode = b.memory_mode === "permanent_policy" ? "permanent_policy" : "one_time"; // only an explicit choice makes a permanent rule
      q.status = "human_resolved"; q.final_answer = answer; q.resolution_source = `human (${mode})`; q.updated_at = nowIso(clock());
      audit(q, "human", `human_answer_${mode}`, answer, L("人間の回答により解決（1回限りか恒久ルールかを区別して記録）", "Resolved by a human answer (one-time or permanent is recorded apart)"));
      let promoted = "";
      if (mode === "permanent_policy") {
        promoted = uid("pol-demo");
        s.policies.push({ id: promoted, scope: b.policy_scope || "project", project_id: q.project_id, title: String(b.policy_title || answer).slice(0, 60), rule_text: answer, locked: 0, version: 1, active: 1, source: "human_answer", created_at: q.updated_at, updated_at: q.updated_at, keywords: [] });
        s.audits[0].promoted_to_policy_id = promoted;
      }
      const batch = [];
      if (b.batch_apply_same_project === true) {
        for (const o of s.questions) if (o !== q && o.project_id === q.project_id && o.status === "needs_human") { o.status = "batch_resolved"; o.final_answer = answer; o.resolution_source = "human (batch)"; batch.push(o.id); refreshSlotStatus(o.slot_id); }
      }
      refreshSlotStatus(q.slot_id);
      return { ...localize(q, getLang()), promoted_policy_id: promoted, batch_resolved_ids: batch };
    },
    "POST /meetings": (b) => {
      const topic = String(b.topic || "").trim();
      if (!topic) fail(400, "議題を入力してください", "Please enter a topic");
      if (s.halt.active || s.halt.all) fail(409, "緊急停止中のため、会議は開けません", "An emergency stop is in force, so a meeting cannot be started");
      const raw = Array.isArray(b.participants) && b.participants.length ? b.participants : [{ perspective: "A", harness: "kiro" }, { perspective: "B", harness: "claude" }];
      const specs = raw.map((p, i) => (typeof p === "string" ? { perspective: p, harness: "kiro" } : { perspective: String(p.perspective || `視点${i + 1}`).slice(0, 60), harness: HARNESS_LABEL[p.harness] ? p.harness : "kiro" }));
      if (specs.length < 2 || specs.length > 5) fail(400, "参加者は2〜5人にしてください", "Use between 2 and 5 participants");
      const organiser = HARNESS_LABEL[b.synthesizer_harness] ? b.synthesizer_harness : "kiro";
      const withGemini = [...specs.map((x) => x.harness), organiser].includes("gemini");
      // Same rule as the real app: only the literal true counts, and without it nothing is created.
      if (withGemini && b.allow_unpublished_to_gemini !== true) fail(400, localize(GEMINI_CONSENT_REQUIRED, "ja"), localize(GEMINI_CONSENT_REQUIRED, "en"));
      const m = buildMeeting(uid("mtg-demo"), b.project_id || "proj-game", topic, specs, organiser, b.language === "en" ? "en" : "ja", { asked: withGemini, allowed: withGemini }, nowIso(clock()));
      m._t0 = clock().getTime();
      m.status = "awaiting_human_adoption";
      s.meetings.unshift(m);
      return localize(shown(m), getLang());
    },
    "POST /meetings/adopt": (b) => {
      const m = s.meetings.find((x) => x.id === b.meeting_id);
      if (!m) fail(404, "その相談は見つかりません", "That meeting was not found");
      if (meetingStatus(m) !== "awaiting_human_adoption") fail(400, "この相談は、まだ結果が出ていないか、すでに処理済みです", "This meeting is not finished yet or was already handled");
      const opt = m.summary.options_for_human.find((o) => o.id === b.option_id);
      if (!opt) fail(400, "その選択肢はありません", "No such option");
      if (b.option_id === "hold_as_idea") {
        m.status = "saved_to_ideas";
        const idea = { id: uid("idea"), project_id: m.project_id, title: m.topic, content: m.summary.consensus, source: "meeting_saved", status: "saved", created_at: nowIso(clock()) };
        s.ideas.unshift(idea);
        return { meeting_id: m.id, action: "saved_to_ideas", idea_id: idea.id };
      }
      const target = slotOf(b.target_slot_id);
      if (!target) fail(400, "作業を頼む相手が見つかりません", "The assignee was not found");
      if (halted(target)) fail(409, "停止中のスロットには頼めません", "A stopped slot cannot be given work");
      m.status = "adopted_and_scheduled";
      // The sample AI only "receives" the plan here (a line in its history). Nothing is sent anywhere.
      target.history.push({ role: "system", text: L("【見本】採用された案を受け取りました（実際のAIには何も送っていません）", "[Sample] Received an adopted plan (nothing was sent to a real AI)") });
      target.next_task = L(`［会議の採用案］${m.topic}（${b.option_id}）`, `[Adopted from a meeting] ${m.topic} (${b.option_id})`);
      return { meeting_id: m.id, action: "scheduled_to_slot", slot_id: target.id };
    },
    "POST /stop": (b) => {
      const scope = b.scope || "all", target = b.target_id || "", ts = nowIso(clock());
      if (["resume_all", "resume_slot", "resume_project"].includes(scope)) {
        // Only a person's explicit call gets here; nothing in this demo calls it by itself.
        if (scope === "resume_all") { s.halt = { all: false, projects: [], slots: [], since: "", reason: "", active: false }; }
        if (scope === "resume_slot") s.halt.slots = s.halt.slots.filter((x) => x !== target);
        if (scope === "resume_project") s.halt.projects = s.halt.projects.filter((x) => x !== target);
        for (const sl of s.slots) if (sl.status === "stopped" && !halted(sl)) { sl.status = "idle"; sl.waiting_reason = L("人間の許可により停止を解除（自動では作業を再開しません）", "Stop released by a human (work does not restart by itself)"); }
        s.halt.active = s.halt.all || s.halt.projects.length > 0 || s.halt.slots.length > 0;
        return { ok: true, scope, target_id: target, updated_at: ts, live_stopped: [], live_errors: [], halt: snapshotHalt(), released_questions: [] };
      }
      if (!["slot", "project", "all"].includes(scope) || (scope !== "all" && !target)) fail(400, "その停止の指定はできません", "That stop cannot be applied");
      if (scope === "all") s.halt.all = true;
      if (scope === "project" && !s.halt.projects.includes(target)) s.halt.projects.push(target);
      if (scope === "slot" && !s.halt.slots.includes(target)) s.halt.slots.push(target);
      s.halt.since = ts; s.halt.reason = "人間による緊急停止"; s.halt.active = true;
      for (const sl of s.slots) if (halted(sl)) { sl.status = "stopped"; sl.waiting_reason = L("人間による緊急停止（再開は人間の許可が必要）", "Emergency stop by a human (a human must allow the restart)"); }
      return { ok: true, scope, target_id: target, updated_at: ts, live_stopped: [], live_errors: [], stopped_outside_kiro_crew: [], halt: snapshotHalt() };
    },
    "POST /mode": (b) => {
      if (b.mode !== undefined) {
        if (!["away", "sleep", "home"].includes(b.mode)) fail(400, "そのモードはありません", "No such mode");
        s.mode_state.mode = b.mode;
      }
      if ("quiet_until" in b) s.mode_state.quiet_until = String(b.quiet_until).slice(0, 5);
      if ("allow_unpublished_to_free_tier" in b) s.mode_state.allow_unpublished_to_free_tier = b.allow_unpublished_to_free_tier === true;
      return { ...s.mode_state };
    },
    "POST /notify/test": () => ({ ok: false, error: getLang() === "en" ? "The demo sends no notifications." : "デモでは通知を送りません。" }),
    "POST /news/summarize": (b) => {
      const url = String(b.url || "").trim();
      let ok = false;
      try { const u = new URL(url); ok = u.protocol === "https:" || u.protocol === "http:"; } catch { ok = false; }
      if (!ok) { const e = new Error(getLang() === "en" ? "Please enter a web address that starts with https://" : "https:// で始まるWebアドレスを入力してください"); e.status = 422; throw e; }
      // Canned on purpose: the address is never opened, so the demo cannot fetch anything.
      const item = { id: uid("news-demo"), project_id: b.project_id || "proj-shop", category: L("ニュース（見本）", "News (sample)"), title: L("見本のまとめ（このアドレスは開いていません）", "A sample summary (this address was not opened)"), url, published_date: nowIso(clock()).slice(0, 10),
        facts_summary: L("【事実（見本）】デモでは、入力されたアドレスを開きません。固定の見本を表示しています。", "[Fact (sample)] The demo does not open the address you typed. It shows a fixed sample."), estimates_summary: L("【推定（見本）】なし", "[Estimate (sample)] None"),
        relevance_reason: String(b.reason || ""), created_at: nowIso(clock()) };
      s.news.unshift(item);
      return localize(item, getLang());
    },
    "POST /desktop-lease": (b) => {
      const action = b.action || "reclaim_for_human";
      if (action === "reclaim_for_human") { s.lease.holder_type = "human"; s.lease.holder_slot_id = ""; s.lease.status = "human_active"; s.lease.purpose = L("人間がPCを使用中（最優先）", "A human is using the PC (top priority)"); }
      s.lease.updated_at = nowIso(clock());
      return { ok: true, action, lease: localize(s.lease, getLang()), note: getLang() === "en" ? "Simulated: no real PC is controlled." : "模擬: 実際のPCは操作しません。" };
    },
  };

  /** @returns {Promise<any>} the response body, or throws an Error with .status */
  return {
    handle(method, path, body) {
      const [p, qs] = String(path).split("?");
      const key = `${String(method).toUpperCase()} ${p}`;
      if (p === "/slots/history" && method.toUpperCase() === "GET") {
        const id = new URLSearchParams(qs || "").get("slot_id") || "";
        const sl = slotOf(id);
        return Promise.resolve(localize({ slot_id: id, messages: sl ? sl.history : [] }, getLang()));
      }
      const fn = handlers[key];
      if (!fn) { const e = new Error(`Unknown endpoint: ${key}`); e.status = 404; return Promise.reject(e); }
      try { return Promise.resolve(fn(body || {})); } catch (e) { return Promise.reject(e); }
    },
    _state: s,
  };
}
