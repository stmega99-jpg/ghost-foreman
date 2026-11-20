// Ghost Foreman — Kiro Crew App UI (`ui/dist/index.mjs`, resolved relative to `<app_root>/ui/`).
// This is the screen the Gateway actually serves (index.html is only used by the local dev server).
// React renders text as text, so AI-written content is never interpreted as HTML.
//
// Layout: a HOME screen that starts from what the person wants to do (answer an AI, consult the AIs, see what the AIs
// are doing, look up news, read the rules). Technical settings, costs and run records live on the "詳細・設定" screen.
// The emergency stop button is in the header of every screen.
//
// Language: Japanese and English. The Japanese sentence itself is the key (t(japanese, vars)), so the code reads as
// before; EN holds the English. T(japanese) only marks a string that is translated later at render time. A test
// (tests/ui/i18n_test.mjs) checks that every marked string has an English entry. Text written by an AI or a person
// (questions, minutes, rules) is shown as written; fixed labels the backend produces go through `tb()`.
import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useAppApi, useAppEvents } from "@kirocrew/app-sdk";

const h = React.createElement;
const BASE = "/api/apps/ghost-foreman";

// ------------------------------------------------------------------ language
const LANG_KEY = "gf-lang";
let LANG = "ja";
export function detectLang() {
  try { const s = window.localStorage.getItem(LANG_KEY); if (s === "ja" || s === "en") return s; } catch (e) { /* storage blocked */ }
  const nav = (typeof navigator !== "undefined" && navigator.language) || "ja";
  return String(nav).toLowerCase().startsWith("ja") ? "ja" : "en";
}
const fill = (s, vars) => (vars ? s.replace(/\{(\w+)\}/g, (m, k) => (k in vars ? String(vars[k]) : m)) : s);
const t = (ja, vars) => fill(LANG === "en" && EN[ja] !== undefined ? EN[ja] : ja, vars);
const T = (ja) => ja; // marks a string that is translated at render time with t(...)

const EN = {
  // status words
  "判断待ち": "Waiting for you",
  "担当AIへ確認中…": "Asking the AI…",
  "ツール承認待ち": "Tool approval needed",
  "仕様変更のため保留": "Held: it would change a decided spec",
  "緊急停止中に受信（再開後に判断）": "Received during the emergency stop (decide after resuming)",
  "自動で回答済み": "Answered automatically",
  "回答済み": "Answered",
  "まとめて回答済み": "Answered together",
  "作業中": "Working",
  "待機中": "Idle",
  "停止中": "Stopped",
  "あなたの判断待ち": "Waiting for your decision",
  "待機中（理由あり）": "Waiting (see reason)",
  "相談中…（数分かかります）": "Consulting… (takes a few minutes)",
  "結果が出ました。選んでください": "Results are in. Please choose",
  "うまくいきませんでした": "Did not work out",
  "採用して作業を頼みました": "Adopted; work was ordered",
  "アイデア帳に保存しました": "Saved to the idea notebook",
  "すべての案件": "All projects",
  "この案件": "This project",
  "この件だけ": "This item only",
  // building blocks
  "← ホームへ戻る": "← Back to home",
  // questions
  "AIからの確認: {q}": "A question from an AI: {q}",
  "👻 幽霊のおすすめ: {rec} — {why}": "👻 The Ghost recommends: {rec} — {why}",
  "違い: {x}": "Difference: {x}",
  "影響: {x}": "Impact: {x}",
  "{label} を採用": "Adopt: {label}",
  "{label} を標準規約として採用": "Adopt as a standing rule: {label}",
  "今回だけ、この案にする": "Use this option, this time only",
  "🧠 これからもこの方針にする（恒久ルールにして回答）": "🧠 Make this our policy from now on (answer as a permanent rule)",
  "[AIに送った回答] ": "[Answer sent to the AI] ",
  "自分の言葉で答える（選択肢以外でもOK）": "Answer in your own words (anything is fine, not only the options)",
  "回答を入力…": "Type your answer…",
  "今回だけの回答にする": "Answer this time only",
  " 同じ案件の似た質問にも、まとめて適用する": " Apply the same answer to similar questions in this project",
  "分からないときは質問で返す（例: JSONとSQLiteの違いは？）": "If unsure, ask back (e.g. What is the difference between JSON and SQLite?)",
  "💬 質問で返す": "💬 Ask back",
  "人間裁定: {x}": "Human decision: {x}",
  "あなたの判断を待っている確認が {n} 件あります。": "{n} question(s) are waiting for your decision.",
  "いま、あなたの判断を待っている確認はありません。": "Nothing is waiting for your decision right now.",
  "AIからの確認はまだ届いていません。AIが迷ったときに、ここに表示されます。": "No questions from the AIs yet. They appear here when an AI is unsure.",
  // slots / AIs at work
  "本物のAI（実接続）": "Real AI (live connection)",
  "デモ用の見本（模擬）": "Demo sample (simulated)",
  "停止中（人間の許可待ち）": "Stopped (waiting for a human to allow it)",
  "{project} ／ 役割: {role}": "{project} / role: {role}",
  "いまの仕事: {x}": "Current job: {x}",
  "待っている理由: {x}": "Waiting because: {x}",
  "次の予定: {x}": "Next: {x}",
  "⏹ 停止": "⏹ Stop",
  "▶ この停止を解除": "▶ Lift this stop",
  "{name} の停止を解除し、再開を許可しますか？\n（解除しても自動では作業を始めません）": "Lift the stop on {name} and allow it to resume?\n(Lifting it does not start any work by itself.)",
  "いま、Ghost Foreman が見ている本物のAIの作業はありません。": "Ghost Foreman is not watching any real AI at work right now.",
  "デモ用の見本が {n} 件あります（実在するAIではありません）。": "There are {n} demo samples (not real AIs).",
  "詳細で見る": "See in details",
  // consult
  "設計・世界観との整合性の視点": "Fit with the design and the world",
  "実装工数・リスクの視点": "Effort and risk of building it",
  "プレイヤー体験・面白さの視点": "Player experience and fun",
  "安全性・間違いにくさの視点": "Safety and resistance to mistakes",
  "他のアプリとの比較・市場の視点": "Comparison with other apps and the market",
  "Kiro Crew の中で動くAIです。": "Runs inside Kiro Crew.",
  "Anthropic のAIです。パソコンから直接起動します（Kiro Crew の外）。": "Anthropic's AI. Started directly from your PC (outside Kiro Crew).",
  "OpenAI のAIです。パソコンから直接起動します（Kiro Crew の外）。": "OpenAI's AI. Started directly from your PC (outside Kiro Crew).",
  "Google のAIです。無料枠を使います（Kiro Crew の外）。この会議の内容を送る許可が必要です。": "Google's AI. Uses the free tier (outside Kiro Crew). You must allow sending this meeting's content.",
  "（Kiro Crew 外で実行）": " (runs outside Kiro Crew)",
  "（Kiro Crew 外・Gemini API 無料枠）": " (outside Kiro Crew, Gemini API free tier)",
  "　— 使えません": " — not available",
  "相談: {x}": "Consultation: {x}",
  "参加したAI: {x}": "AIs taking part: {x}",
  "この相談には、Kiro Crew の外で動いたAI（Claude Code・Codex・Gemini。道具は使わず、文章だけ）が含まれます。": "This consultation includes AIs that ran outside Kiro Crew (Claude Code, Codex, Gemini; text only, no tools).",
  "Gemini 無料枠への送信: この会議だけ許可（{when}）": "Sending to the Gemini free tier: allowed for this meeting only ({when})",
  "Gemini 無料枠への送信: 許可なし": "Sending to the Gemini free tier: not allowed",
  "👻 幽霊のまとめ": "👻 The Ghost's summary",
  "意見が分かれたところ: {x}": "Where opinions differ: {x}",
  "まだ決まっていないこと: {x}": "Still undecided: {x}",
  "どの案で進めますか？（相談の段階では、まだ何も作りません）": "Which option do we go with? (Nothing is built at the consultation stage.)",
  "作業を頼む相手:": "Ask this AI to do the work:",
  "作業を頼むAI": "AI to do the work",
  "（頼める本物のAIがいません）": "(no real AI is available to ask)",
  "・見本": " (sample)",
  "見本のAIに頼みます。実際のAIには何も送られません。": "The request goes to a sample AI. Nothing is sent to a real AI.",
  "{name}（{role}）": "{name} ({role})",
  "いまは保存だけする": "Just save it for now",
  "この案で進める（作業を頼む）": "Go with this option (order the work)",
  "▲ やりとりを閉じる": "▲ Hide the exchange",
  "▼ AIたちのやりとりを見る": "▼ See the AIs' exchange",
  "まとめ役": "Organiser",
  "（未確認）": " (unconfirmed)",
  "（未実行）": " (did not run)",
  "① 何を相談しますか？": "① What do you want to consult about?",
  "どの案件？": "Which project?",
  "案件": "Project",
  "相談したいこと（例: セーブ時の安心感を与える演出）": "What you want to consult about (e.g. an effect that reassures players when they save)",
  "相談したいこと": "What you want to consult about",
  "② 誰に相談しますか？（2つ以上選んでください）": "② Who do you want to consult? (pick two or more)",
  "{label}に相談する": "Consult {label}",
  "使えます": "Available",
  "いまは使えません": "Not available now",
  "{n}人参加": "{n} taking part",
  "↻ 使えるか再確認": "↻ Check availability again",
  "はじめに、選んだAIへ参加確認を送ります。答えられないAIがいれば、始めずに理由をお知らせします。": "First, a participation check is sent to each chosen AI. If one cannot answer, nothing starts and you are told why.",
  "⚠️ Claude Code・Codex・Gemini は Kiro Crew の外で動きます（企画書で認めた、相談に限った例外です）。道具は使えず、文章のやり取りだけです。「全停止」でいつでも止められ、実行の記録は「詳細・設定」に残ります。各サービスの利用枠を使います。": "⚠️ Claude Code, Codex and Gemini run outside Kiro Crew (a documented exception, for consultations only). They cannot use tools; it is text only. \"Stop all\" halts them at any time, and a record of each run is kept under \"Details & settings\". Each service's own usage allowance is used.",
  "Gemini は、使えないときに別のAIが代わりに答えることも、有料のAPIに切り替わることもありません。": "If Gemini cannot answer, no other AI answers in its place, and it never switches to a paid API.",
  "この会議の内容を Gemini 無料枠に送ることを許可する": "Allow sending this meeting's content to the Gemini free tier",
  "（この会議だけ）": " (this meeting only)",
  "議題・各AIの案など、未公開の制作情報を含みます。無料枠に送った内容は、Google がサービス改善に使う場合があります。": "It includes unpublished project information such as the topic and each AI's ideas. Google may use what is sent to the free tier to improve its services.",
  "許可しない場合は、Gemini を外してください。": "If you do not allow it, please remove Gemini.",
  "▲ くわしい設定を閉じる": "▲ Close detailed settings",
  "▼ くわしく設定する（任意）": "▼ Detailed settings (optional)",
  "参加者ごとに、どの視点で意見を出すか・どのAIにするかを決められます。同じAIを何人か入れることもできます。": "For each participant you can choose the point of view and the AI. You can also add the same AI more than once.",
  "参加者{n}の視点": "Participant {n}'s point of view",
  "参加者{n}のAI": "Participant {n}'s AI",
  "参加者{n}を外す": "Remove participant {n}",
  "＋ 参加者を追加": "+ Add a participant",
  "まとめ役（意見を整理するAI）:": "Organiser (the AI that sums up):",
  "まとめ役のAI": "Organiser AI",
  "💬 この内容で相談を始める": "💬 Start this consultation",
  "相談の段階では、何も作りません。あなたが案を選んだときだけ、作業を頼みます。": "Nothing is built at the consultation stage. Work is ordered only when you choose an option.",
  "相談したいことを入力してください。": "Please type what you want to consult about.",
  "AIを {min} つ以上選んでください。": "Please pick at least {min} AIs.",
  "AIは {max} つまでです。": "At most {max} AIs.",
  "使えないAIが選ばれています。外すか、「再確認」してください。": "An unavailable AI is selected. Remove it, or check again.",
  "Gemini を使うには、下の送信の許可にチェックしてください。": "To use Gemini, tick the permission to send below.",
  "相談中・結果待ち": "In progress / results waiting",
  "▲ 過去の相談を閉じる": "▲ Hide past consultations",
  "▼ 過去の相談（{n} 件）を見る": "▼ See past consultations ({n})",
  "▲ うまくいかなかった相談を閉じる": "▲ Hide consultations that did not work out",
  "▼ うまくいかなかった相談（{n} 件）を見る": "▼ See consultations that did not work out ({n})",
  // rules / news
  "決めたルールはまだありません。AIの質問に「これからもこの方針にする」で答えると、ここに増えていきます。": "No rules decided yet. Answer an AI's question with \"make this our policy from now on\" and they will appear here.",
  "あなたが決めた方針の一覧です。AIが迷ったとき、幽霊はこれを根拠に代わりに答えます。": "These are the policies you decided. When an AI is unsure, the Ghost answers for you based on them.",
  "{scope}（{project}）": "{scope} ({project})",
  "確定仕様（無断では変えません）　": "Fixed spec (never changed without you)  ",
  "{id}・第{v}版": "{id} · version {v}",
  "手動で指定されたURL": "URL given by hand",
  "気になる記事やページのURLを貼ってください。要約して、「事実」と「推測」を分けて保存します。": "Paste the URL of an article or page you care about. It is summarised, with \"facts\" and \"estimates\" kept apart.",
  "https://… 公開ページのURL": "https://… URL of a public page",
  "要約中…": "Summarising…",
  "要約して保存": "Summarise and save",
  "公開されているページだけを取得します（社内のアドレスなどは拒否します）。": "Only public pages are fetched (internal addresses and the like are refused).",
  "{category} ／ 掲載日 {date} ／ 集めた理由: {why}": "{category} / published {date} / collected because: {why}",
  "事実\n": "Facts\n",
  "推測\n": "Estimates\n",
  "元の記事: {url}": "Source: {url}",
  // details
  "判断の記録はまだありません。": "No decision records yet.",
  "原文: {x}": "Original: {x}",
  "適用ルール: {x}": "Rule applied: {x}",
  "通知をオンにしました。「テスト通知を送る」で確認できます。": "Notifications are on. You can check with \"Send a test notification\".",
  "テスト通知を送りました。数秒で届きます（アプリを閉じると見やすいです）。": "A test notification was sent. It arrives in a few seconds (it is easier to see if you close the app).",
  "送信に失敗しました: {x}": "Sending failed: {x}",
  "📲 このiPhoneへの通知": "📲 Notifications to this iPhone",
  "オン（判断待ちが出たらこの端末に通知します）": "On (you will be notified here when something is waiting)",
  "オフ": "Off",
  "ホーム画面に追加したアプリから開くと、オンにできます": "Open it from the app added to the Home Screen to turn this on",
  "確認中…": "Checking…",
  "🔔 通知をオンにする": "🔔 Turn notifications on",
  "テスト通知を送る": "Send a test notification",
  "通知がいつ届くかは、ホームの「いまの状況」（家にいる／外出中／おやすみ）で変わります。テスト通知は状況に関係なく送ります。": "When notifications arrive depends on \"What is your situation?\" on the home screen (at home / out / sleeping). A test notification is sent regardless.",
  "制作内容（AIからの質問・確定ルールの本文）を Gemini の無料枠へ送信します。\n無料枠に送った内容は、Google によって製品改善などに利用される可能性があります。\n\n許可しますか？": "Your project content (the AIs' questions and the text of decided rules) will be sent to the Gemini free tier.\nGoogle may use content sent to the free tier to improve its products.\n\nAllow it?",
  "🔒 制作内容を Gemini の無料枠へ送ってよいか（常時の設定）": "🔒 May project content be sent to the Gemini free tier? (standing setting)",
  "AIからの質問や確定ルールの本文を、判定のために Gemini の無料枠へ送ってよいかを決めます。AI会議で Gemini を使うときは、この設定とは別に、会議ごとに許可を聞きます。": "Decide whether the AIs' questions and the text of decided rules may be sent to the Gemini free tier for judging. When Gemini joins an AI meeting, you are asked separately for each meeting.",
  "許可している（制作内容を無料枠へ送信する）": "Allowed (project content is sent to the free tier)",
  "許可していない（制作内容は送信しない）": "Not allowed (project content is not sent)",
  "許可しない場合、制作内容の判定は Kiro Crew の実セッションで行います。公開ニュースの整理は、この設定に関係なく Gemini を使います。": "If not allowed, judging project content is done in a real Kiro Crew session. Summarising public news uses Gemini regardless of this setting.",
  "💰 費用と使用量": "💰 Cost and usage",
  "実際の請求額: ": "Actual billing: ",
  "未確認": "Unconfirmed",
  "Gemini無料枠は上限により待機中です（有料APIには切り替えません）": "The Gemini free tier is waiting because it hit its limit (it never switches to a paid API)",
  "Gemini無料枠: 利用可能（または未使用）": "Gemini free tier: available (or unused)",
  "提供元": "Provider",
  "呼び出し": "Calls",
  "成功": "OK",
  "トークン(入/出)": "Tokens (in/out)",
  "請求額": "Billing",
  "トークン数は提供元の実測値です。Kiro の使用量はホストが公開していないため、0ではなく未確認として扱います。有料APIへの切替機能は実装していません。": "Token counts are measured by the provider. Kiro's usage is not exposed by the host, so it is shown as unconfirmed, not 0. There is no switch to a paid API.",
  "🧪 Kiro Crew 外で実行したAIの記録": "🧪 Record of AIs run outside Kiro Crew",
  "AI会議のために Ghost Foreman が直接起動した Claude Code / Codex の記録です。質問の本文は保存せず、ハッシュだけを残します。請求額は確認できないため「未確認」です。": "A record of Claude Code / Codex runs that Ghost Foreman started directly for AI meetings. The prompt text is not stored, only its hash. Billing cannot be confirmed, so it is shown as \"unconfirmed\".",
  "{started}　{sec}秒　トークン {tin}/{tout}　会議 {meeting}": "{started}  {sec}s  tokens {tin}/{tout}  meeting {meeting}",
  "まだ記録はありません。": "No records yet.",
  "🔔 通知の履歴": "🔔 Notification history",
  "sent=送信 / held=おやすみ中に保留 / held_resident=家にいるため通知せず / failed=失敗 / not_sent=模擬モード": "sent = sent / held = held while sleeping / held_resident = not sent because you are at home / failed = failed / not_sent = simulated mode",
  "「本物のAI（実接続）」は Kiro Crew Gateway 上の本物のセッションです。「デモ用の見本（模擬）」は動作を見せるためのサンプルで、実在のAIではありません。": "\"Real AI (live connection)\" is a real session on the Kiro Crew Gateway. \"Demo sample (simulated)\" is sample data to show how it works, not a real AI.",
  "通知・送信の設定": "Notification & sending settings",
  "費用と使用量": "Cost and usage",
  "外部AIの実行記録": "Outside-AI run record",
  "通知の履歴": "Notification history",
  "判断の記録": "Decision record",
  "AIの一覧（技術情報）": "List of AIs (technical)",
  "ふだんは使わない、設定と記録です。": "Settings and records you rarely need.",
  // home
  "🏠 家にいる": "🏠 At home",
  "通知しません": "No notifications",
  "🚃 外出中": "🚃 Out",
  "判断待ちをスマホに通知": "Notify my phone when something waits",
  "🌙 おやすみ": "🌙 Sleeping",
  "朝にまとめて通知": "One summary in the morning",
  "👻 あなたの判断を待っているAIがいます": "👻 An AI is waiting for your decision",
  "{n} 件の確認が届いています。": "{n} question(s) have arrived.",
  "答える →": "Answer →",
  "✅ いま、あなたの判断を待っているものはありません。": "✅ Nothing is waiting for your decision right now.",
  "💬 AIたちが相談中です（{n} 件）。数分かかります。": "💬 The AIs are consulting ({n}). It takes a few minutes.",
  "様子を見る": "Take a look",
  "💬 相談の結果が出ています（{n} 件）。どの案で進めるか選べます。": "💬 Consultation results are in ({n}). You can choose which option to go with.",
  "結果を見る": "See the results",
  "何をしますか？": "What would you like to do?",
  "AIたちに相談する": "Consult the AIs",
  "企画の悩みを、いろいろなAIに聞いて、意見をまとめてもらいます。": "Ask several different AIs about a planning problem and get their opinions summed up.",
  "結果 {n} 件": "{n} result(s)",
  "AIからの質問に答える": "Answer the AIs' questions",
  "AIが迷ったときの確認に答えます。": "Answer the questions the AIs ask when they are unsure.",
  "{n} 件待ち": "{n} waiting",
  "AIたちの様子を見る": "See how the AIs are doing",
  "本物のAIが {n} 体、動いています。": "{n} real AI(s) at work.",
  "誰がいま何をしているか見て、止めたりできます。": "See who is doing what, and stop them if needed.",
  "ニュースを調べる": "Look up news",
  "気になる記事のURLを貼ると、要約して保存します。": "Paste an article's URL and it is summarised and saved.",
  "決めたルールを見る": "See the rules you decided",
  "あなたが決めた方針の一覧です。": "The list of policies you decided.",
  "いま、どんな状況ですか？（通知の出し方が変わります）": "What is your situation? (it changes how you are notified)",
  "⚙️ 詳細・設定（通知・費用・記録）": "⚙️ Details & settings (notifications, cost, records)",
  // app shell
  "📥 AIからの質問に答える": "📥 Answer the AIs' questions",
  "💬 AIたちに相談する": "💬 Consult the AIs",
  "🤖 AIたちの様子": "🤖 How the AIs are doing",
  "📰 ニュースを調べる": "📰 Look up news",
  "🧠 決めたルール": "🧠 Decided rules",
  "⚙️ 詳細・設定": "⚙️ Details & settings",
  "AIたちは働く。あなたには生活がある。": "Your agents work. You have a life.",
  "接続エラー: {x}": "Connection error: {x}",
  "👻 Ghost Foreman 起動中…": "👻 Ghost Foreman is starting…",
  "停止を解除し、再開を許可しますか？\n\n・解除しても、止まっていた作業は自動では再開しません\n・停止中に届いた確認は、人間の判断待ちとして表示されます": "Lift the stop and allow resuming?\n\n• Work that was stopped does not restart by itself\n• Questions that arrived during the stop are shown as waiting for a human decision",
  "● つながっています（Gateway実接続）": "● Connected (live Gateway connection)",
  "デモ表示（模擬モード）": "Demo (simulated mode)",
  "すべての実スロットを停止します。人間が再開を許可するまで、自動では何も再開されません。よろしいですか？": "This stops every real slot. Nothing restarts by itself until a human allows it. Continue?",
  "🛑 全停止": "🛑 Stop all",
  "🛑 緊急停止中": "🛑 Emergency stop in force",
  "人間が再開を許可するまで、自動回答・自動発注・メッセージ送信・会議の開催・ツールの自動承認は行いません。停止中に届いた確認は、解除後も自動では回答せず、判断待ちとして表示します。": "Until a human allows it, there is no automatic answering, ordering, message sending, meeting, or automatic tool approval. Questions that arrive during the stop are not answered automatically even after lifting it; they are shown as waiting for you.",
  "対象: {target}　開始: {since}": "Scope: {target}  Since: {since}",
  "すべて": "Everything",
  "案件 {p}": "Project {p}",
  "スロット {s}": "Slot {s}",
  "▶ 停止をすべて解除（再開を許可）": "▶ Lift every stop (allow resuming)",
  "案件 {p} の停止を解除しますか？": "Lift the stop on project {p}?",
  "案件 {p} だけ解除": "Lift only project {p}",
  "📥 判断待ちが {n} 件あります。": "📥 {n} question(s) waiting for you.",
  "答える": "Answer",
  "言語": "Language",
};

// Fixed labels the backend writes into its records (shown in the language of the screen). Anything not listed, and all
// text written by an AI or a person, is shown as it was written.
const EN_B = {
  "Kiro Crew で実行": "Runs inside Kiro Crew",
  "Kiro Crew 外で実行": "Runs outside Kiro Crew",
  "Kiro Crew 外で実行（Gemini API 無料枠）": "Runs outside Kiro Crew (Gemini API free tier)",
  "0. 参加確認 (各AIの実際の返答と実行場所)": "0. Participation check (each AI's real answer and where it ran)",
  "1. 独立案出し (Independent Ideation)": "1. Independent ideas",
  "2. 相互批評・改善 (Mutual Critique & Refinement)": "2. Mutual critique and refinement",
  "実エージェントによる会議の結果です。人間が採用ボタンを押すまで勝手に実装タスクへは移しません（仕様D準拠）。": "The result of a meeting held by real agents. Nothing becomes an implementation task until a human adopts an option.",
  "実エージェントによる会議を実行中です。人間が採用ボタンを押すまで制作には移しません（仕様D）。": "A meeting by real agents is running. Nothing is built until a human adopts an option.",
  "まだ制作には移さず、アイデア帳に議事録として保存のみ行う": "Do not build yet; just save the minutes to the idea notebook",
  "幽霊（整理役）": "Ghost (organiser)",
  "Gateway未接続（模擬モード）": "Gateway not connected (simulated mode)",
  "未設定": "Not set up",
  "人間による個別停止（再開は人間の許可が必要）": "Stopped by a human, this AI only (a human must allow the restart)",
  "人間によるプロジェクト一括停止（再開は人間の許可が必要）": "Stopped by a human, the whole project (a human must allow the restart)",
  "人間による全エージェント緊急停止（再開は人間の許可が必要）": "Emergency stop of every AI by a human (a human must allow the restart)",
  "人間の許可により停止を解除（自動では作業を再開しません）": "Stop lifted by a human (work does not restart by itself)",
  "人間による緊急停止": "Emergency stop by a human",
  "ツール実行承認待ち（ホスト権限）": "Waiting for a tool approval (host permission)",
  "確定仕様変更の保留（人間確認待ち）": "Held: it would change the agreed spec (waiting for a human)",
  "幽霊が逆質問で論点整理済 → 人間の判断待ち（独立タスクへ一時切替中）": "The Ghost asked back and summarised the options → waiting for your decision (working on another task meanwhile)",
  "幽霊が担当AIへ逆質問中": "The Ghost is asking the AI a follow-up question",
  "幽霊が逆質問で論点整理済 → 人間の判断待ち": "The Ghost asked back and summarised the options → waiting for your decision",
};
const EN_BP = [
  [/^参加者([A-E])（(.*)／(.*)）$/, (m) => `Participant ${m[1]} (${m[2]} / ${m[3]})`],
  [/^幽霊（整理役／(.*)）$/, (m) => `Ghost (organiser / ${m[1]})`],
  [/^緊急停止により終了しました$/, () => "Ended by the emergency stop"],
  [/^(\d+)秒のタイムアウトにより終了しました$/, (m) => `Ended after a ${m[1]}-second time limit`],
  [/^報告: ([\s\S]*)$/, (m) => `Report: ${m[1]}`],
  [/^会議が失敗しました: (.*)$/, (m) => `The meeting failed: ${tb(m[1])}`],
  [/^会議を中止しました: (.*)$/, (m) => `The meeting was cancelled: ${tb(m[1])}`],
  [/^緊急停止されたため、会議を中止しました$/, () => "The meeting was cancelled because of the emergency stop"],
  [/^自己紹介に別のAIの名前（(.*)）が含まれています。実際に答えたのは (.*) です（呼び出し先で確認）。$/, (m) => `The self-introduction names another AI (${m[1]}). The one that actually answered was ${m[2]} (confirmed from what was called).`],
  [/^自己紹介で (.*) と名乗っていません。実際に答えたのは (.*) です（呼び出し先で確認）。$/, (m) => `The self-introduction does not say ${m[1]}. The one that actually answered was ${m[2]} (confirmed from what was called).`],
  [/^Gemini を参加させるには、この会議の内容.*送る許可が必要です。.*$/, () => "To let Gemini take part, you must allow sending this meeting's content (which includes unpublished project information) to the Gemini free tier. Google may use what is sent to the free tier to improve its services."],
];
// Fixed sentences the backend puts inside its records (replaced wherever they appear; the AI's own words are left alone).
const EN_FRAG = [
  ["参加できないAIがあるため会議を始めませんでした — ", "The meeting did not start because some AIs could not take part: "],
  ["参加者から案が得られませんでした", "No participant produced a proposal"],
  ["Gateway再起動により会議が中断されました。途中までの発言は保存されています。", "The meeting was interrupted by a Gateway restart. What was said so far is saved."],
  ["幽霊の論点整理を得られませんでした。各ラウンドの発言をご確認ください。", "The Ghost could not produce a summary. Please read what was said in each round."],
  ["整理役の返答が構造化されていませんでした。採用は保存のみ可能です。", "The organiser's answer was not in the expected structure. Only saving is possible."],
  ["【模擬】Gateway未接続の固定サンプルです。実AIによる会議ではありません。人間が採用ボタンを押すまで制作には移しません。", "[Simulated] A fixed sample, because no Gateway is connected. This is not a meeting held by real AIs. Nothing is built until a human adopts an option."],
  ["（返答なし: ", "(no answer: "],
  ["返答なし", "no answer"],
  ["時間内に返答がありませんでした", "No answer within the time limit"],
  ["送信できませんでした: ", "Could not send: "],
  ["Gemini が設定されていません", "Gemini is not set up"],
  ["緊急停止中のため送信しません", "Not sent because an emergency stop is in force"],
  ["緊急停止されたため、届いた回答は使いません", "The emergency stop was used, so the answer that arrived is discarded"],
  ["Gemini が回答できませんでした", "Gemini could not answer"],
  ["この会議のみ", "this meeting only"],
  ["この会議の内容を Gemini 無料枠に送ることを許可", "Allowed sending this meeting's content to the Gemini free tier"],
];function tb(s) {
  if (LANG !== "en" || typeof s !== "string") return s;
  if (EN_B[s] !== undefined) return EN_B[s];
  for (const [re, fn] of EN_BP) { const m = s.match(re); if (m) return fn(m); }
  // A participation-check line: "［where・model］ answer　⚠️ note" (the answer itself is the AI's own words).
  const warn = s.indexOf("　⚠️ ");
  if (warn > 0) return tb(s.slice(0, warn)) + "  ⚠️ " + tb(s.slice(warn + 4));
  const r = (re, fn) => { const m = s.match(re); return m ? fn(m) : null; };
  const shaped = r(/^【(.*?)】([\s\S]*)（利点: ([\s\S]*) \/ リスク: ([\s\S]*)）$/, (m) => `[${m[1]}] ${m[2]} (Pros: ${m[3]} / Risks: ${m[4]})`)
    || r(/^批評: ([\s\S]*) → 改善案: ([\s\S]*)$/, (m) => `Critique: ${m[1]} → Improved proposal: ${m[2]}`);
  if (shaped) return shaped;
  let out = s;
  out = out.replace(/（返答なし: ([^（）]*)）/g, "(no answer: $1)")
    .replace(/参加者([A-E])（([^（）]*)／([^（）]*)）/g, "Participant $1 ($2 / $3)")
    .replace(/幽霊（整理役／([^（）]*)）/g, "Ghost (organiser / $1)");
  for (const [ja, en] of EN_FRAG) out = out.split(ja).join(en);
  return out
    .replace(/［([^］]*)］/g, (all, inner) => `[${inner.replace(/^Kiro Crew 外で実行（Gemini API 無料枠）/, "Outside Kiro Crew (Gemini API free tier)").replace(/^Kiro Crew 外で実行/, "Outside Kiro Crew").replace(/^Kiro Crew で実行/, "Inside Kiro Crew").replace("Gemini API 無料枠", "Gemini API free tier")}]`)
    .replace(/（参加できません: ([^）]*)）/g, "(cannot take part: $1)");
}
const shortName = (s) => (LANG === "en" ? tb(s).split(" (")[0] : String(s).split("（")[0]);
export const I18N = { EN, EN_B, detectLang, tb, setLangForTest: (l) => { LANG = l; } };

// ------------------------------------------------------------------ look
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
  needs_human: [T("判断待ち"), C.warn],
  probing: [T("担当AIへ確認中…"), C.accent],
  needs_human_approval: [T("ツール承認待ち"), C.warn],
  held_spec_violation: [T("仕様変更のため保留"), C.bad],
  held_emergency_stop: [T("緊急停止中に受信（再開後に判断）"), C.bad],
  auto_resolved: [T("自動で回答済み"), C.ok],
  human_resolved: [T("回答済み"), C.ok],
  batch_resolved: [T("まとめて回答済み"), C.ok],
};
const SLOT_STATUS = { working: T("作業中"), idle: T("待機中"), stopped: T("停止中"), waiting_human: T("あなたの判断待ち"), blocked: T("待機中（理由あり）") };
const MEETING_STATUS = {
  running: [T("相談中…（数分かかります）"), C.accent],
  awaiting_human_adoption: [T("結果が出ました。選んでください"), C.warn],
  failed: [T("うまくいきませんでした"), C.bad],
  adopted_and_scheduled: [T("採用して作業を頼みました"), C.ok],
  saved_to_ideas: [T("アイデア帳に保存しました"), C.ok],
};
const SCOPE = { global: T("すべての案件"), project: T("この案件"), item: T("この件だけ") };

function Badge({ text, color }) {
  return h("span", { style: { border: `1px solid ${color || C.border}`, color: color || C.mute, borderRadius: 999, padding: "1px 8px", fontSize: 12, whiteSpace: "nowrap" } }, text);
}
const isPending = (q) => ["needs_human", "needs_human_approval", "held_spec_violation"].includes(q.status);
const projectName = (d, id) => ((d.projects || []).find((p) => p.id === id) || {}).name || id;

// ------------------------------------------------------------------ small building blocks
function BackBar({ title, onBack }) {
  return h("div", { style: { ...S.row, marginBottom: 8 } },
    h("button", { style: S.btn, onClick: onBack }, t("← ホームへ戻る")),
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
  const [labelJa, color] = STATUS[q.status] || [q.status, C.mute];
  const label = STATUS[q.status] ? t(labelJa) : labelJa;
  const resolve = (answer, mode) =>
    call("POST", "/questions/resolve", {
      question_id: q.id,
      answer_text: answer,
      memory_mode: mode,
      policy_scope: "project",
      policy_title: t("人間裁定: {x}", { x: String(q.raw_question).slice(0, 30) }),
      batch_apply_same_project: batch,
    });
  return h(
    "div",
    { ref, style: { ...S.card, ...(highlight ? { borderColor: C.accent, boxShadow: `0 0 0 2px ${C.accent}55` } : {}) } },
    h("div", { style: { ...S.row, justifyContent: "space-between" } }, h(Badge, { text: projectName(d, q.project_id) }), h(Badge, { text: label, color })),
    h("h3", { style: { margin: "8px 0" } }, t("AIからの確認: {q}", { q: q.raw_question })),
    q.context_summary ? h("p", { style: { whiteSpace: "pre-wrap" } }, q.context_summary) : null,
    q.recommendation ? h("p", { style: { color: C.accent } }, t("👻 幽霊のおすすめ: {rec} — {why}", { rec: q.recommendation, why: q.recommendation_reason || "" })) : null,
    ...(q.probe_history || []).map((p, i) => h("div", { key: "p" + i, style: S.log }, h("strong", null, `[${p.role}] `), p.text)),
    ...(q.options || []).map((o) =>
      h(
        "div",
        { key: o.id, style: { ...S.log, borderColor: C.accent } },
        h("strong", null, o.label),
        o.difference ? h("div", null, t("違い: {x}", { x: o.difference })) : null,
        o.impact ? h("div", null, t("影響: {x}", { x: o.impact })) : null,
        isPending(q)
          ? h(
              "div",
              { style: { ...S.row, marginTop: 6 } },
              h("button", { style: S.btn, onClick: () => resolve(t("{label} を採用", { label: o.label }), "one_time") }, t("今回だけ、この案にする")),
              h("button", { style: S.btnOk, onClick: () => resolve(t("{label} を標準規約として採用", { label: o.label }), "permanent_policy") }, t("🧠 これからもこの方針にする（恒久ルールにして回答）"))
            )
          : null
      )
    ),
    q.final_answer ? h("div", { style: { ...S.log, borderColor: C.ok } }, h("strong", null, t("[AIに送った回答] ")), q.final_answer) : null,
    isPending(q)
      ? h(
          "div",
          { style: { marginTop: 10, borderTop: `1px solid ${C.border}`, paddingTop: 10 } },
          h("div", { style: S.mute }, t("自分の言葉で答える（選択肢以外でもOK）")),
          h("textarea", { style: { ...S.input, width: "100%", minHeight: 70, boxSizing: "border-box" }, value: text, onChange: (e) => setText(e.target.value), placeholder: t("回答を入力…") }),
          h(
            "div",
            { style: { ...S.row, marginTop: 6 } },
            h("button", { style: S.btn, disabled: !text.trim(), onClick: () => resolve(text.trim(), "one_time") }, t("今回だけの回答にする")),
            h("button", { style: S.btnOk, disabled: !text.trim(), onClick: () => resolve(text.trim(), "permanent_policy") }, t("🧠 これからもこの方針にする（恒久ルールにして回答）"))
          ),
          h("label", { style: { ...S.mute, display: "block", marginTop: 6 } }, h("input", { type: "checkbox", checked: batch, onChange: (e) => setBatch(e.target.checked) }), t(" 同じ案件の似た質問にも、まとめて適用する")),
          h("div", { style: { ...S.row, marginTop: 8 } },
            h("input", { style: S.input, value: follow, onChange: (e) => setFollow(e.target.value), placeholder: t("分からないときは質問で返す（例: JSONとSQLiteの違いは？）") }),
            h("button", { style: S.btn, disabled: !follow.trim(), onClick: () => call("POST", "/questions/inquire", { question_id: q.id, human_inquiry: follow.trim(), re_probe_agent: true }).then(() => setFollow("")) }, t("💬 質問で返す"))
          )
        )
      : null
  );
}

function Inbox({ d, call, focusQ }) {
  const sorted = [...d.questions].sort((a, b) => Number(isPending(b)) - Number(isPending(a)) || String(b.created_at).localeCompare(String(a.created_at)));
  const pending = sorted.filter(isPending).length;
  return h("div", null,
    h("div", { style: S.mute }, pending ? t("あなたの判断を待っている確認が {n} 件あります。", { n: pending }) : t("いま、あなたの判断を待っている確認はありません。")),
    sorted.length ? null : h("div", { style: S.card }, t("AIからの確認はまだ届いていません。AIが迷ったときに、ここに表示されます。")),
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
        h(Badge, { text: s.is_live ? t("本物のAI（実接続）") : t("デモ用の見本（模擬）"), color: s.is_live ? C.ok : C.warn }),
        slotHalted(d, s) ? h(Badge, { text: t("停止中（人間の許可待ち）"), color: C.bad }) : null,
        h(Badge, { text: SLOT_STATUS[s.status] ? t(SLOT_STATUS[s.status]) : s.status }))),
    h("div", null, t("{project} ／ 役割: {role}", { project: projectName(d, s.project_id), role: s.role }) + (technical ? " ／ " + s.backend : "")),
    h("div", null, t("いまの仕事: {x}", { x: s.current_task })),
    s.waiting_reason ? h("div", { style: { color: C.warn } }, t("待っている理由: {x}", { x: tb(s.waiting_reason) })) : null,
    s.next_task ? h("div", { style: S.mute }, t("次の予定: {x}", { x: s.next_task })) : null,
    h("div", { style: { ...S.row, marginTop: 8 } },
      h("button", { style: S.btnBad, onClick: () => call("POST", "/stop", { scope: "slot", target_id: s.id }) }, t("⏹ 停止")),
      d.halt && (d.halt.slots || []).includes(s.id) ? h("button", { style: S.btnOk, onClick: () => { if (window.confirm(t("{name} の停止を解除し、再開を許可しますか？\n（解除しても自動では作業を始めません）", { name: s.name }))) call("POST", "/stop", { scope: "resume_slot", target_id: s.id }); } }, t("▶ この停止を解除")) : null)
  );
}

function AiWatch({ d, call, go }) {
  const live = d.slots.filter((s) => s.is_live);
  const demo = d.slots.length - live.length;
  return h("div", null,
    live.length ? null : h("div", { style: S.card }, t("いま、Ghost Foreman が見ている本物のAIの作業はありません。")),
    ...live.map((s) => h(SlotCard, { key: s.id, d, s, call })),
    demo ? h("div", { style: { ...S.card, ...S.mute } }, t("デモ用の見本が {n} 件あります（実在するAIではありません）。", { n: demo }), " ", h("button", { style: S.btn, onClick: () => go("details:slots") }, t("詳細で見る"))) : null);
}

// ------------------------------------------------------------------ consult the AIs (meetings)
const PERSPECTIVES = [
  T("設計・世界観との整合性の視点"),
  T("実装工数・リスクの視点"),
  T("プレイヤー体験・面白さの視点"),
  T("安全性・間違いにくさの視点"),
  T("他のアプリとの比較・市場の視点"),
];
const defaultPerspective = (i) => t(PERSPECTIVES[i % PERSPECTIVES.length]);
const AI_DESC = {
  kiro: T("Kiro Crew の中で動くAIです。"),
  claude: T("Anthropic のAIです。パソコンから直接起動します（Kiro Crew の外）。"),
  codex: T("OpenAI のAIです。パソコンから直接起動します（Kiro Crew の外）。"),
  gemini: T("Google のAIです。無料枠を使います（Kiro Crew の外）。この会議の内容を送る許可が必要です。"),
};
const WHERE = { external_cli: T("（Kiro Crew 外で実行）"), gemini_api: T("（Kiro Crew 外・Gemini API 無料枠）") };

function MeetingCard({ m, d, call }) {
  const [open, setOpen] = useState(false);
  const [target, setTarget] = useState("");
  // A real Gateway: only real AIs can be asked to work. A demo (sample data): the sample AIs can, so the whole flow can be tried; nothing is sent to a real AI.
  const demoMode = !!(d.mode_state && d.mode_state.gateway_mode !== "live_gateway");
  const workers = d.slots.filter((s) => (s.is_live || demoMode) && !["会議参加者", "議事整理", "判定係"].includes(s.role));
  const chosen = target || (workers.find((w) => w.project_id === m.project_id) || workers[0] || {}).id || "";
  const sm = m.summary || {};
  const live = sm.live !== false;
  const [stJa, stColor] = MEETING_STATUS[m.status] || [m.status, C.mute];
  const stLabel = MEETING_STATUS[m.status] ? t(stJa) : stJa;
  const people = sm.participants_detail ? [...sm.participants_detail, ...(sm.synthesizer ? [sm.synthesizer] : [])] : [];
  return h("div", { style: S.card },
    h("div", { style: { ...S.row, justifyContent: "space-between" } },
      h(Badge, { text: projectName(d, m.project_id) }),
      h("span", { style: S.row }, live ? null : h(Badge, { text: t("デモ用の見本（模擬）"), color: C.warn }), h(Badge, { text: stLabel, color: stColor }))),
    h("h3", { style: { margin: "8px 0" } }, t("相談: {x}", { x: m.topic })),
    h("div", { style: S.mute }, t("参加したAI: {x}", { x: m.participants.map(tb).join(LANG === "en" ? " / " : " ／ ") })),
    sm.outside_kiro_crew ? h("div", { style: { color: C.warn, fontSize: 13, marginTop: 4 } }, t("この相談には、Kiro Crew の外で動いたAI（Claude Code・Codex・Gemini。道具は使わず、文章だけ）が含まれます。")) : null,
    ...people.filter((p) => p.self_report_check && p.self_report_check.status !== "ok")
      .map((p, i) => h("div", { key: "sr" + i, style: { color: C.warn, fontSize: 13, marginTop: 2 } }, `⚠️ ${p.speaker ? shortName(p.speaker) : (p.label || p.harness)}: ${tb(p.self_report_check.note)}`)),
    (sm.gemini_consent && sm.gemini_consent.asked) ? h("div", { style: { color: C.warn, fontSize: 13, marginTop: 2 } },
      sm.gemini_consent.allowed ? t("Gemini 無料枠への送信: この会議だけ許可（{when}）", { when: sm.gemini_consent.decided_at }) : t("Gemini 無料枠への送信: 許可なし")) : null,
    m.status === "failed" && sm.note ? h("div", { style: { ...S.log, borderColor: C.bad } }, tb(sm.note)) : null,
    sm.consensus
      ? h("div", { style: { ...S.log, borderColor: C.accent } },
          h("strong", null, t("👻 幽霊のまとめ")), h("div", null, tb(sm.consensus)),
          sm.conflict_points ? h("div", { style: { color: C.warn, marginTop: 4 } }, t("意見が分かれたところ: {x}", { x: tb(sm.conflict_points) })) : null,
          sm.unresolved ? h("div", { style: { marginTop: 4 } }, t("まだ決まっていないこと: {x}", { x: tb(sm.unresolved) })) : null)
      : null,
    m.status === "awaiting_human_adoption"
      ? h("div", { style: { marginTop: 8 } },
          h("div", { style: { fontWeight: 600, marginBottom: 4 } }, t("どの案で進めますか？（相談の段階では、まだ何も作りません）")),
          h("div", { style: S.row },
            h("span", { style: S.mute }, t("作業を頼む相手:")),
            h("select", { style: { ...S.input, flex: "0 0 auto" }, value: chosen, onChange: (e) => setTarget(e.target.value), "aria-label": t("作業を頼むAI") },
              ...(workers.length ? workers : [{ id: "", name: t("（頼める本物のAIがいません）") }]).map((w) => h("option", { key: w.id || "none", value: w.id }, w.id ? t("{name}（{role}）", { name: w.name, role: w.role }) + (w.is_live ? "" : t("・見本")) : w.name)))),
          workers.length && workers.every((w) => !w.is_live) ? h("div", { style: S.mute }, t("見本のAIに頼みます。実際のAIには何も送られません。")) : null,
          ...(sm.options_for_human || []).map((o) =>
            h("div", { key: o.id, style: { ...S.log, borderColor: C.accent } },
              h("strong", null, tb(o.label)), o.detail ? h("div", null, o.detail) : null,
              h("button", { style: { ...(o.id === "hold_as_idea" ? S.btn : S.btnOk), marginTop: 6 }, disabled: o.id !== "hold_as_idea" && !chosen,
                onClick: () => call("POST", "/meetings/adopt", { meeting_id: m.id, option_id: o.id, target_slot_id: chosen }) },
                o.id === "hold_as_idea" ? t("いまは保存だけする") : t("この案で進める（作業を頼む）")))))
      : null,
    m.rounds.length ? h("div", { style: { marginTop: 6 } },
      h("button", { style: S.btn, onClick: () => setOpen(!open) }, open ? t("▲ やりとりを閉じる") : t("▼ AIたちのやりとりを見る")),
      open ? h("div", null,
        people.length ? h("div", { style: { ...S.row, marginTop: 6 } }, ...people.map((p, i) =>
          h(Badge, { key: i, text: `${p.speaker ? shortName(p.speaker) : t("まとめ役")}: ${p.label || p.harness}・${tb(p.runtime_label || "")}${p.model ? "・" + p.model : ""}${p.ran_on ? (p.verified ? "" : t("（未確認）")) : t("（未実行）")}`, color: p.verified ? (p.runtime !== "kiro_crew" ? C.warn : C.ok) : C.mute }))) : null,
        ...m.rounds.map((r, i) => h("div", { key: i, style: S.log }, h("strong", null, tb(r.phase)), ...r.entries.map((e, j) => h("div", { key: j, style: { marginTop: 6 } }, h("strong", null, tb(e.speaker) + ": "), tb(e.proposal || e.critique))))),
        sm.note && m.status !== "failed" ? h("div", { style: S.mute }, tb(sm.note)) : null) : null) : null);
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
      setParts((r.harnesses || []).filter((x) => x.available && x.id !== "gemini").map((x) => ({ perspective: "", harness: x.id })));
    }
  };
  const loadHarnesses = (refresh) => call("GET", "/meetings/harnesses" + (refresh ? "?refresh=1" : "")).then((r) => apply(r, false)).catch(() => {});
  useEffect(() => { call("GET", "/meetings/harnesses").then((r) => apply(r, true)).catch(() => {}); }, []);

  const rows = harnesses.harnesses || [];
  const rowOf = (id) => rows.find((x) => x.id === id) || {};
  // A blank point of view gets the default for its place, so a participant is never silently dropped.
  const effective = parts.map((p, i) => ({ perspective: p.perspective.trim() || defaultPerspective(i), harness: p.harness }));
  const countOf = (id) => parts.filter((p) => p.harness === id).length;
  const chosenIds = [...effective.map((p) => p.harness), organiser];
  const outside = chosenIds.some((id) => ["external_cli", "gemini_api"].includes(rowOf(id).runtime));
  const usesGemini = chosenIds.includes("gemini");
  const geminiRow = rowOf("gemini");
  const blocked = chosenIds.filter((id) => rows.length && !rowOf(id).available);
  const agentOptions = (rows.length ? rows : [{ id: "kiro", label: "Kiro", runtime: "kiro_crew", available: true }]).map((x) =>
    h("option", { key: x.id, value: x.id, disabled: !x.available }, x.label + (WHERE[x.runtime] ? t(WHERE[x.runtime]) : "") + (x.available ? "" : t("　— 使えません"))));
  // Ticking adds one participant; unticking removes the participants of that AI. Everyone else keeps their edits.
  const togglePick = (id) => setParts(countOf(id) ? parts.filter((p) => p.harness !== id) : [...parts, { perspective: "", harness: id }]);
  const setPart = (i, key, value) => setParts(parts.map((p, j) => (j === i ? { ...p, [key]: value } : p)));
  const letter = (i) => String.fromCharCode(65 + i);

  let why = "";
  if (!topic.trim()) why = t("相談したいことを入力してください。");
  else if (effective.length < limits.min) why = t("AIを {min} つ以上選んでください。", { min: limits.min });
  else if (effective.length > limits.max) why = t("AIは {max} つまでです。", { max: limits.max });
  else if (blocked.length) why = t("使えないAIが選ばれています。外すか、「再確認」してください。");
  else if (usesGemini && !geminiOk) why = t("Gemini を使うには、下の送信の許可にチェックしてください。");
  const start = () => call("POST", "/meetings", {
    project_id: project, topic: topic.trim(),
    participants: effective.map((p) => ({ perspective: p.perspective.trim(), harness: p.harness })),
    synthesizer_harness: organiser, allow_unpublished_to_gemini: usesGemini && geminiOk === true,
    language: LANG,
  }).then(() => { setTopic(""); setGeminiOk(false); });

  // Meetings that need the person (running, or waiting for a choice) stay in view. Finished ones and failed ones are folded.
  const ok = d.meetings.filter((m) => ["running", "awaiting_human_adoption"].includes(m.status));
  const past = d.meetings.filter((m) => !["running", "awaiting_human_adoption", "failed"].includes(m.status));
  const failed = d.meetings.filter((m) => m.status === "failed");
  const [showPast, setShowPast] = useState(false);
  return h("div", null,
    h("div", { style: S.card },
      h("h3", { style: S.h3 }, t("① 何を相談しますか？")),
      h("div", { style: { ...S.row, marginBottom: 8 } },
        h("span", { style: S.mute }, t("どの案件？")),
        h("select", { style: { ...S.input, flex: "0 0 auto" }, value: project, onChange: (e) => setProject(e.target.value), "aria-label": t("案件") }, ...d.projects.map((p) => h("option", { key: p.id, value: p.id }, p.name)))),
      h("input", { style: { ...S.input, width: "100%", boxSizing: "border-box", fontSize: 16 }, value: topic, onChange: (e) => setTopic(e.target.value), placeholder: t("相談したいこと（例: セーブ時の安心感を与える演出）"), "aria-label": t("相談したいこと") })),
    h("div", { style: S.card },
      h("h3", { style: S.h3 }, t("② 誰に相談しますか？（2つ以上選んでください）")),
      ...rows.map((x) => h("label", { key: x.id, style: { display: "flex", gap: 10, alignItems: "flex-start", padding: "8px 0", borderTop: `1px solid ${C.border}`, opacity: x.available ? 1 : 0.6 } },
        h("input", { type: "checkbox", style: { width: 22, height: 22, marginTop: 2 }, checked: countOf(x.id) > 0, disabled: !x.available || (countOf(x.id) === 0 && parts.length >= limits.max), onChange: () => togglePick(x.id), "aria-label": t("{label}に相談する", { label: x.label }) }),
        h("span", { style: { flex: 1 } },
          h("strong", null, x.label), " ", h(Badge, { text: x.available ? t("使えます") : t("いまは使えません"), color: x.available ? C.ok : C.bad }),
          countOf(x.id) > 1 ? h(Badge, { text: t("{n}人参加", { n: countOf(x.id) }) }) : null,
          h("div", { style: S.mute }, AI_DESC[x.id] ? t(AI_DESC[x.id]) : ""),
          !x.available && x.reason ? h("div", { style: { color: C.warn, fontSize: 13 } }, tb(x.reason)) : null))),
      h("div", { style: { ...S.row, marginTop: 6 } },
        h("button", { style: S.btn, onClick: () => loadHarnesses(true) }, t("↻ 使えるか再確認")),
        h("span", { style: S.mute }, t("はじめに、選んだAIへ参加確認を送ります。答えられないAIがいれば、始めずに理由をお知らせします。"))),
      outside ? h("div", { style: { ...S.log, borderColor: C.warn } },
        t("⚠️ Claude Code・Codex・Gemini は Kiro Crew の外で動きます（企画書で認めた、相談に限った例外です）。道具は使えず、文章のやり取りだけです。「全停止」でいつでも止められ、実行の記録は「詳細・設定」に残ります。各サービスの利用枠を使います。")) : null,
      usesGemini ? h("div", { style: { ...S.log, borderColor: C.warn } },
        h("div", null, t("Gemini は、使えないときに別のAIが代わりに答えることも、有料のAPIに切り替わることもありません。")),
        h("label", { style: { display: "flex", gap: 8, alignItems: "flex-start", marginTop: 6 } },
          h("input", { type: "checkbox", style: { width: 22, height: 22 }, checked: geminiOk, onChange: (e) => setGeminiOk(e.target.checked), "aria-label": t("この会議の内容を Gemini 無料枠に送ることを許可する") }),
          h("span", null, h("strong", null, t("この会議の内容を Gemini 無料枠に送ることを許可する")), t("（この会議だけ）"))),
        h("div", { style: S.mute }, geminiRow.consent_note ? tb(geminiRow.consent_note) : t("議題・各AIの案など、未公開の制作情報を含みます。無料枠に送った内容は、Google がサービス改善に使う場合があります。")),
        geminiOk ? null : h("div", { style: { color: C.warn, fontSize: 13 } }, t("許可しない場合は、Gemini を外してください。"))) : null),
    h("div", { style: S.card },
      h("button", { style: S.btn, onClick: () => setAdvanced(!advanced) }, advanced ? t("▲ くわしい設定を閉じる") : t("▼ くわしく設定する（任意）")),
      advanced ? h("div", { style: { marginTop: 8 } },
        h("div", { style: S.mute }, t("参加者ごとに、どの視点で意見を出すか・どのAIにするかを決められます。同じAIを何人か入れることもできます。")),
        ...parts.map((p, i) => h("div", { key: i, style: { ...S.row, marginTop: 6 } },
          h("span", { style: { width: 20 } }, letter(i)),
          h("input", { style: S.input, value: p.perspective, onChange: (e) => setPart(i, "perspective", e.target.value), placeholder: defaultPerspective(i), "aria-label": t("参加者{n}の視点", { n: letter(i) }) }),
          h("select", { style: { ...S.input, flex: "0 0 auto" }, value: p.harness, onChange: (e) => setPart(i, "harness", e.target.value), "aria-label": t("参加者{n}のAI", { n: letter(i) }) }, ...agentOptions),
          h("button", { style: S.btn, disabled: parts.length <= limits.min, onClick: () => setParts(parts.filter((_, j) => j !== i)), "aria-label": t("参加者{n}を外す", { n: letter(i) }) }, "−"))),
        h("div", { style: { ...S.row, marginTop: 6 } },
          h("button", { style: S.btn, disabled: parts.length >= limits.max, onClick: () => setParts([...parts, { perspective: "", harness: "kiro" }]) }, t("＋ 参加者を追加")),
          h("span", { style: S.mute }, t("まとめ役（意見を整理するAI）:")),
          h("select", { style: { ...S.input, flex: "0 0 auto" }, value: organiser, onChange: (e) => setOrganiser(e.target.value), "aria-label": t("まとめ役のAI") }, ...agentOptions))) : null),
    h("div", { style: S.card },
      h("button", { style: { ...S.btnOk, ...S.big, width: "100%" }, disabled: !!why, onClick: start }, t("💬 この内容で相談を始める")),
      why ? h("div", { style: { ...S.mute, marginTop: 6 } }, why) : null,
      h("div", { style: { ...S.mute, marginTop: 6 } }, t("相談の段階では、何も作りません。あなたが案を選んだときだけ、作業を頼みます。"))),
    ok.length ? h("h3", { style: { ...S.h3, marginTop: 16 } }, t("相談中・結果待ち")) : null,
    ...ok.map((m) => h(MeetingCard, { key: m.id, m, d, call })),
    past.length ? h("div", { style: { marginTop: 8 } },
      h("button", { style: S.btn, onClick: () => setShowPast(!showPast) }, showPast ? t("▲ 過去の相談を閉じる") : t("▼ 過去の相談（{n} 件）を見る", { n: past.length })),
      showPast ? h("div", { style: { marginTop: 8 } }, ...past.map((m) => h(MeetingCard, { key: m.id, m, d, call }))) : null) : null,
    failed.length ? h("div", { style: { marginTop: 8 } },
      h("button", { style: S.btn, onClick: () => setShowFailed(!showFailed) }, showFailed ? t("▲ うまくいかなかった相談を閉じる") : t("▼ うまくいかなかった相談（{n} 件）を見る", { n: failed.length })),
      showFailed ? h("div", { style: { marginTop: 8 } }, ...failed.map((m) => h(MeetingCard, { key: m.id, m, d, call }))) : null) : null);
}

// ------------------------------------------------------------------ rules / news
function Rules({ d }) {
  if (!d.policies.length) return h("div", { style: S.card }, t("決めたルールはまだありません。AIの質問に「これからもこの方針にする」で答えると、ここに増えていきます。"));
  return h("div", null,
    h("div", { style: S.mute }, t("あなたが決めた方針の一覧です。AIが迷ったとき、幽霊はこれを根拠に代わりに答えます。")),
    ...d.policies.map((p) => h("div", { key: p.id, style: S.card },
      h("div", { style: { ...S.row, justifyContent: "space-between" } }, h("strong", null, p.title), h(Badge, { text: p.scope === "project" ? t("{scope}（{project}）", { scope: t(SCOPE.project), project: projectName(d, p.project_id) }) : (SCOPE[p.scope] ? t(SCOPE[p.scope]) : p.scope) })),
      h("div", { style: { marginTop: 6, whiteSpace: "pre-wrap" } }, p.rule_text),
      h("div", { style: S.mute }, (p.locked ? t("確定仕様（無断では変えません）　") : "") + t("{id}・第{v}版", { id: p.id, v: p.version })))));
}

function News({ d, call }) {
  const [url, setUrl] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const add = async () => {
    setBusy(true); setErr("");
    try { await call("POST", "/news/summarize", { project_id: (d.projects[0] || {}).id || "proj-foreman", url: url.trim(), reason: t("手動で指定されたURL") }); setUrl(""); }
    catch (e) { setErr(String((e && e.message) || e)); }
    setBusy(false);
  };
  return h("div", null,
    h("div", { style: S.card },
      h("div", { style: S.mute }, t("気になる記事やページのURLを貼ってください。要約して、「事実」と「推測」を分けて保存します。")),
      h("div", { style: { ...S.row, marginTop: 6 } }, h("input", { style: S.input, value: url, onChange: (e) => setUrl(e.target.value), placeholder: t("https://… 公開ページのURL") }), h("button", { style: S.btnOk, disabled: busy || !url.trim(), onClick: add }, busy ? t("要約中…") : t("要約して保存"))),
      err ? h("div", { style: { color: C.bad, marginTop: 6 } }, err) : null,
      h("div", { style: S.mute }, t("公開されているページだけを取得します（社内のアドレスなどは拒否します）。"))),
    ...d.news.map((n) => h("div", { key: n.id, style: S.card },
      h("strong", null, n.title), h("div", { style: S.mute }, t("{category} ／ 掲載日 {date} ／ 集めた理由: {why}", { category: n.category, date: n.published_date, why: n.relevance_reason })),
      h("div", { style: { ...S.log, borderColor: C.ok } }, h("strong", null, t("事実\n")), n.facts_summary),
      h("div", { style: { ...S.log, borderColor: C.warn } }, h("strong", null, t("推測\n")), n.estimates_summary),
      h("div", { style: S.mute }, t("元の記事: {url}", { url: n.url })))));
}

// ------------------------------------------------------------------ details (technical settings and records)
function Audit({ d }) {
  if (!d.audits.length) return h("div", { style: S.card }, t("判断の記録はまだありません。"));
  return h("div", null, ...d.audits.map((a) => h("div", { key: a.id, style: S.card },
    h("div", { style: { ...S.row, justifyContent: "space-between" } }, h(Badge, { text: `${a.project_id} / ${a.slot_id}` }), h(Badge, { text: `${a.actor}: ${a.action_type}` })),
    h("div", { style: { marginTop: 6 } }, t("原文: {x}", { x: a.raw_question })),
    a.referenced_policy_id ? h("div", { style: S.mute }, t("適用ルール: {x}", { x: a.referenced_policy_id })) : null,
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
    try { await push.enable(); setMsg(t("通知をオンにしました。「テスト通知を送る」で確認できます。")); }
    catch (e) { setMsg(String((e && e.message) || e)); }
    setBusy(false); load();
  };
  const test = async () => {
    setBusy(true); setMsg("");
    try { const r = await call("POST", "/notify/test", {}); setMsg(r && r.ok ? t("テスト通知を送りました。数秒で届きます（アプリを閉じると見やすいです）。") : t("送信に失敗しました: {x}", { x: (r && r.error) || "" })); }
    catch (e) { setMsg(String((e && e.message) || e)); }
    setBusy(false);
  };
  const on = st && st.subscribed && st.permission === "granted";
  return h("div", { style: S.card },
    h("h3", { style: S.h3 }, t("📲 このiPhoneへの通知")),
    st ? h("div", null, on ? t("オン（判断待ちが出たらこの端末に通知します）") : st.standalone ? t("オフ") : t("ホーム画面に追加したアプリから開くと、オンにできます")) : h("div", null, t("確認中…")),
    h("div", { style: { ...S.row, marginTop: 8 } },
      !on ? h("button", { style: S.btnOk, disabled: busy || !(st && st.standalone), onClick: enable }, t("🔔 通知をオンにする")) : null,
      on ? h("button", { style: S.btn, disabled: busy, onClick: test }, t("テスト通知を送る")) : null),
    msg ? h("div", { style: { marginTop: 6 } }, msg) : null,
    h("div", { style: S.mute }, t("通知がいつ届くかは、ホームの「いまの状況」（家にいる／外出中／おやすみ）で変わります。テスト通知は状況に関係なく送ります。")));
}

function DetailSettings({ d, call }) {
  const allow = !!(d.mode_state && d.mode_state.allow_unpublished_to_free_tier);
  const toggle = () => {
    const want = !allow;
    if (want && !window.confirm(t("制作内容（AIからの質問・確定ルールの本文）を Gemini の無料枠へ送信します。\n無料枠に送った内容は、Google によって製品改善などに利用される可能性があります。\n\n許可しますか？"))) return;
    call("POST", "/mode", { allow_unpublished_to_free_tier: want });
  };
  return h("div", null,
    h(PhoneNotifications, { call }),
    h("div", { style: S.card },
      h("h3", { style: S.h3 }, t("🔒 制作内容を Gemini の無料枠へ送ってよいか（常時の設定）")),
      h("div", null, t("AIからの質問や確定ルールの本文を、判定のために Gemini の無料枠へ送ってよいかを決めます。AI会議で Gemini を使うときは、この設定とは別に、会議ごとに許可を聞きます。")),
      h("label", { style: { ...S.row, margin: "8px 0" } }, h("input", { type: "checkbox", style: { width: 22, height: 22 }, checked: allow, onChange: toggle }), h("strong", null, allow ? t("許可している（制作内容を無料枠へ送信する）") : t("許可していない（制作内容は送信しない）"))),
      h("div", { style: S.mute }, t("許可しない場合、制作内容の判定は Kiro Crew の実セッションで行います。公開ニュースの整理は、この設定に関係なく Gemini を使います。"))));
}

function DetailCost({ d }) {
  const u = d.usage || { totals: [] };
  const cooling = u.gemini_cooldown_until && u.gemini_cooldown_until * 1000 > Date.now();
  const cols = [T("提供元"), T("呼び出し"), T("成功"), T("トークン(入/出)"), T("請求額")];
  return h("div", { style: S.card },
    h("h3", { style: S.h3 }, t("💰 費用と使用量")),
    h("div", null, t("実際の請求額: "), h(Badge, { text: !u.actual_billing || u.actual_billing === "未確認" ? t("未確認") : u.actual_billing, color: C.warn })),
    h("div", { style: S.mute }, u.billing_note || ""),
    h("div", { style: { margin: "6px 0" } }, cooling ? t("Gemini無料枠は上限により待機中です（有料APIには切り替えません）") : t("Gemini無料枠: 利用可能（または未使用）")),
    h("div", { style: { overflowX: "auto" } },
      h("table", { style: { width: "100%", borderCollapse: "collapse", fontSize: 13 } },
        h("thead", null, h("tr", { style: { textAlign: "left" } }, ...cols.map((col) => h("th", { key: col }, t(col))))),
        h("tbody", null, ...(u.totals || []).map((row) => h("tr", { key: row.provider_id }, h("td", null, row.provider_id), h("td", null, row.calls), h("td", null, row.ok_calls), h("td", null, `${row.input_tokens} / ${row.output_tokens}`), h("td", null, row.cost_display === "未確認" || !row.cost_display ? t("未確認") : row.cost_display)))))),
    h("div", { style: S.mute }, t("トークン数は提供元の実測値です。Kiro の使用量はホストが公開していないため、0ではなく未確認として扱います。有料APIへの切替機能は実装していません。")));
}

function DetailRuns({ d }) {
  return h("div", { style: S.card },
    h("h3", { style: S.h3 }, t("🧪 Kiro Crew 外で実行したAIの記録")),
    h("div", { style: S.mute }, t("AI会議のために Ghost Foreman が直接起動した Claude Code / Codex の記録です。質問の本文は保存せず、ハッシュだけを残します。請求額は確認できないため「未確認」です。")),
    ...(d.external_runs || []).map((r) => h("div", { key: r.id, style: { ...S.log, borderColor: r.status === "ok" ? C.ok : C.bad } },
      h("strong", null, `[${r.status}] ${r.harness}${r.model ? "・" + r.model : ""}`), " " + t("{started}　{sec}秒　トークン {tin}/{tout}　会議 {meeting}", { started: r.started_at, sec: Math.round((r.duration_ms || 0) / 100) / 10, tin: r.input_tokens, tout: r.output_tokens, meeting: r.meeting_id || "-" }),
      r.error ? h("div", { style: { color: C.bad } }, tb(r.error)) : null)),
    (d.external_runs || []).length ? null : h("div", { style: S.mute }, t("まだ記録はありません。")));
}

function DetailNotices({ d }) {
  return h("div", { style: S.card },
    h("h3", { style: S.h3 }, t("🔔 通知の履歴")),
    h("div", { style: S.mute }, t("sent=送信 / held=おやすみ中に保留 / held_resident=家にいるため通知せず / failed=失敗 / not_sent=模擬モード")),
    ...(d.notifications || []).map((n) => h("div", { key: n.id, style: S.log }, h("strong", null, `[${n.delivery}] `), `${n.title} ${n.body}`, h("div", { style: S.mute }, `${n.ts} ${n.detail || ""}`))));
}

function DetailSlots({ d, call }) {
  return h("div", null,
    h("div", { style: { ...S.card, ...S.mute } }, t("「本物のAI（実接続）」は Kiro Crew Gateway 上の本物のセッションです。「デモ用の見本（模擬）」は動作を見せるためのサンプルで、実在のAIではありません。")),
    ...d.slots.map((s) => h(SlotCard, { key: s.id, d, s, call, technical: true })));
}

const DETAIL_SECTIONS = [["settings", T("通知・送信の設定")], ["cost", T("費用と使用量")], ["runs", T("外部AIの実行記録")], ["notices", T("通知の履歴")], ["audit", T("判断の記録")], ["slots", T("AIの一覧（技術情報）")]];

function Details({ d, call, section, setSection }) {
  const body = { settings: DetailSettings, cost: DetailCost, runs: DetailRuns, notices: DetailNotices, audit: Audit, slots: DetailSlots }[section] || DetailSettings;
  return h("div", null,
    h("div", { style: S.mute }, t("ふだんは使わない、設定と記録です。")),
    h("div", { style: { ...S.row, margin: "8px 0 12px" } }, ...DETAIL_SECTIONS.map(([key, label]) => h("button", { key, style: { ...S.btn, ...(section === key ? { background: C.accent, color: "#0d0b18" } : {}) }, onClick: () => setSection(key) }, t(label)))),
    h(body, { d, call }));
}

// ------------------------------------------------------------------ home
const MODES = [
  ["resident", T("🏠 家にいる"), T("通知しません")],
  ["away", T("🚃 外出中"), T("判断待ちをスマホに通知")],
  ["sleep", T("🌙 おやすみ"), T("朝にまとめて通知")],
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
          h("div", { style: { fontSize: 18, fontWeight: 600 } }, t("👻 あなたの判断を待っているAIがいます")),
          h("div", null, t("{n} 件の確認が届いています。", { n: pending })),
          h("button", { style: { ...S.btnOk, ...S.big, marginTop: 8 }, onClick: () => go("inbox") }, t("答える →")))
      : h("div", { style: S.card }, t("✅ いま、あなたの判断を待っているものはありません。")),
    running ? h("div", { style: { ...S.card, borderColor: C.accent } }, t("💬 AIたちが相談中です（{n} 件）。数分かかります。", { n: running }), " ", h("button", { style: S.btn, onClick: () => go("consult") }, t("様子を見る"))) : null,
    waiting && !running ? h("div", { style: { ...S.card, borderColor: C.warn } }, t("💬 相談の結果が出ています（{n} 件）。どの案で進めるか選べます。", { n: waiting }), " ", h("button", { style: S.btn, onClick: () => go("consult") }, t("結果を見る"))) : null,
    h("h2", { style: S.h2 }, t("何をしますか？")),
    h(Tile, { icon: "💬", title: t("AIたちに相談する"), desc: t("企画の悩みを、いろいろなAIに聞いて、意見をまとめてもらいます。"), onClick: () => go("consult"), badge: waiting ? t("結果 {n} 件", { n: waiting }) : "" }),
    h(Tile, { icon: "📥", title: t("AIからの質問に答える"), desc: t("AIが迷ったときの確認に答えます。"), onClick: () => go("inbox"), badge: pending ? t("{n} 件待ち", { n: pending }) : "", accent: !!pending }),
    h(Tile, { icon: "🤖", title: t("AIたちの様子を見る"), desc: liveSlots ? t("本物のAIが {n} 体、動いています。", { n: liveSlots }) : t("誰がいま何をしているか見て、止めたりできます。"), onClick: () => go("ais") }),
    h(Tile, { icon: "📰", title: t("ニュースを調べる"), desc: t("気になる記事のURLを貼ると、要約して保存します。"), onClick: () => go("news") }),
    h(Tile, { icon: "🧠", title: t("決めたルールを見る"), desc: t("あなたが決めた方針の一覧です。"), onClick: () => go("rules") }),
    h("div", { style: S.card },
      h("div", { style: { fontWeight: 600, marginBottom: 6 } }, t("いま、どんな状況ですか？（通知の出し方が変わります）")),
      h("div", { style: { display: "grid", gridTemplateColumns: "repeat(3, minmax(0, 1fr))", gap: 8 } }, ...MODES.map(([key, label, sub]) => h("button", { key, "aria-pressed": mode === key, style: { ...S.btn, padding: "10px 8px", textAlign: "center", ...(mode === key ? { background: C.accent, color: "#0d0b18" } : {}) }, onClick: () => call("POST", "/mode", { mode: key }) }, h("div", null, t(label)), h("div", { style: { fontSize: 11 } }, t(sub)))))),
    h("div", { style: { textAlign: "center", marginTop: 16 } }, h("button", { style: S.btn, onClick: () => go("details") }, t("⚙️ 詳細・設定（通知・費用・記録）"))));
}

// ------------------------------------------------------------------ app
const TITLES = { inbox: T("📥 AIからの質問に答える"), consult: T("💬 AIたちに相談する"), ais: T("🤖 AIたちの様子"), news: T("📰 ニュースを調べる"), rules: T("🧠 決めたルール"), details: T("⚙️ 詳細・設定") };

export default function GhostForemanApp() {
  const api = useAppApi();
  const [d, setD] = useState(null);
  const [error, setError] = useState("");
  const [lang, setLangState] = useState(detectLang);
  LANG = lang; // read by t() while this render builds the tree
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
  const chooseLang = (next) => {
    try { window.localStorage.setItem(LANG_KEY, next); } catch (e) { /* storage blocked */ }
    try { window.dispatchEvent(new window.Event("gf-lang")); } catch (e) { /* the phone page's install note listens for this */ }
    setLangState(next);
    refresh(); // a demo serves its sample data in the chosen language
  };

  useEffect(() => { refresh(); }, [refresh]);
  useEffect(() => { try { document.documentElement.lang = lang; } catch (e) { /* no document */ } }, [lang]);
  useAppEvents("slots", () => refresh());
  useAppEvents("onChatDone", () => refresh());
  const busy = d && (d.meetings.some((m) => m.status === "running") || d.questions.some((q) => q.status === "probing"));
  useEffect(() => { const timer = setInterval(refresh, busy ? 5000 : 20000); return () => clearInterval(timer); }, [refresh, busy]);

  if (!d) return h("div", { style: S.page }, error ? t("接続エラー: {x}", { x: error }) : t("👻 Ghost Foreman 起動中…"));
  const resumeAll = () => {
    if (window.confirm(t("停止を解除し、再開を許可しますか？\n\n・解除しても、止まっていた作業は自動では再開しません\n・停止中に届いた確認は、人間の判断待ちとして表示されます"))) call("POST", "/stop", { scope: "resume_all" });
  };
  const live = d.mode_state && d.mode_state.gateway_mode === "live_gateway";
  const pending = d.questions.filter(isPending).length;
  const body = { home: Home, inbox: Inbox, consult: Consult, ais: AiWatch, news: News, rules: Rules, details: null }[view];
  const langButton = (code, label) => h("button", { key: code, "aria-pressed": lang === code, lang: code, style: { ...S.btn, padding: "6px 10px", minHeight: 36, fontSize: 13, ...(lang === code ? { background: C.accent, color: "#0d0b18" } : {}) }, onClick: () => chooseLang(code) }, label);
  return h("div", { style: S.page }, h("div", { style: S.wrap },
    h("div", { style: { ...S.row, justifyContent: "space-between", marginBottom: 10 } },
      h("div", null, h("strong", { style: { fontSize: 20 } }, "👻 Ghost Foreman"), h("div", { style: S.mute }, t("AIたちは働く。あなたには生活がある。"))),
      h("div", { style: S.row },
        h(Badge, { text: live ? t("● つながっています（Gateway実接続）") : t("デモ表示（模擬モード）"), color: live ? C.ok : C.warn }),
        h("span", { role: "group", "aria-label": t("言語"), style: { display: "inline-flex", gap: 4 } }, langButton("ja", "日本語"), langButton("en", "English")),
        h("button", { style: { ...S.btnBad, ...S.big }, onClick: () => { if (window.confirm(t("すべての実スロットを停止します。人間が再開を許可するまで、自動では何も再開されません。よろしいですか？"))) call("POST", "/stop", { scope: "all" }); } }, t("🛑 全停止")))),
    d.halt && d.halt.active
      ? h("div", { style: { ...S.card, borderColor: C.bad, background: "#2a0a14" } },
          h("strong", { style: { color: C.bad, fontSize: 17 } }, t("🛑 緊急停止中")),
          h("div", null, t("人間が再開を許可するまで、自動回答・自動発注・メッセージ送信・会議の開催・ツールの自動承認は行いません。停止中に届いた確認は、解除後も自動では回答せず、判断待ちとして表示します。")),
          h("div", { style: S.mute }, t("対象: {target}　開始: {since}", { target: d.halt.all ? t("すべて") : [...(d.halt.projects || []).map((p) => t("案件 {p}", { p })), ...(d.halt.slots || []).map((x) => t("スロット {s}", { s: x }))].join(", "), since: d.halt.since || "" })),
          h("div", { style: { ...S.row, marginTop: 8 } },
            h("button", { style: { ...S.btnOk, ...S.big }, onClick: () => resumeAll() }, t("▶ 停止をすべて解除（再開を許可）")),
            ...(d.halt.all ? [] : (d.halt.projects || []).map((p) => h("button", { key: "p" + p, style: S.btn, onClick: () => { if (window.confirm(t("案件 {p} の停止を解除しますか？", { p }))) call("POST", "/stop", { scope: "resume_project", target_id: p }); } }, t("案件 {p} だけ解除", { p }))))))
      : null,
    error ? h("div", { style: { ...S.card, borderColor: C.bad, color: C.bad } }, error) : null,
    view === "home" ? null : h(BackBar, { title: TITLES[view] ? t(TITLES[view]) : "", onBack: () => go("home") }),
    view === "details" ? h(Details, { d, call, section, setSection }) : h(body, { d, call, focusQ, go }),
    view === "home" || !pending || view === "inbox" ? null : h("div", { style: { ...S.card, borderColor: C.warn, marginTop: 12 } }, t("📥 判断待ちが {n} 件あります。", { n: pending }), " ", h("button", { style: S.btn, onClick: () => go("inbox") }, t("答える")))));
}

export function mount() {
  return GhostForemanApp;
}
