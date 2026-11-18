# Kiro（きろﾁｬﾝ）への丸投げ指示書 — Ghost Foreman 実装＆実機接続

## 使い方（人間用・コピペするだけ）

1. Kiro で作業フォルダ（`<作業フォルダ>\ghost-foreman` または新規リポジトリ）を開く。
2. 企画書 `Ghost_Foreman_企画書_v2.md` をワークスペースに置く（または添付する）。
3. 下の **「▼ Kiro にコピペするプロンプト」** をそのまま Kiro のチャット欄に貼り付けて送信するだけ！

---

## ▼ Kiro にコピペするプロンプト（ここから下をコピー）

```markdown
`Ghost_Foreman_企画書_v2.md`（および `.kiro/specs/ghost-foreman.md`、`.kiro/steering/foreman-rules.md`）を読み、Kiroween 2026（Frankenstein部門 ＋ Best Kiro Crew App Bonus Prize）向けの Kiro Crew App **「Ghost Foreman（幽霊現場監督）」** を実装・実機検証してください。

### 絶対ルール
- **モックやダミーデータの成功を「実装完了」として扱わないでください。**
- 企画書 v2.0 の機能分担に従い、Kiro Crew に既存の機能（並列稼働・進行管理、通知・遠隔操作、成果物差分管理、音声操作）は Kiro Crew 0.12.2 本体の機能を最大限利用し、Ghost Foreman 独自の価値（代理判断・逆質問、AI会議室・ブレスト、選択的記憶、無料API枠の活用、ニュース収集、PC操作権管理の技術検証）と結合してください。
- 実装中、人間の判断や環境設定（APIキーやiPhone側のPWA登録など）が必要な箇所だけ私に手順を教えてください。それ以外は自律的に進めてください。

### Kiro Crew 0.12.2 実機仕様（ハマり防止の必須規約）
1. **`backend.hooks.routes` (`RouteRegistry`)**:
   - `register_routes(ctx: AppContext)` は `app.router.add_*` を直接呼ぶのではなく、`method` / `path`（`/api/apps/ghost-foreman` からの相対パス、例: `"/dashboard"`） / `handler(request: web.Request, ctx: AppContext)` を持つルート定義オブジェクトの **`list` を return** してください。
2. **`backend.hooks.on_startup` / `on_shutdown`**:
   - `async def on_startup(ctx: AppContext) -> None` / `async def on_shutdown(ctx: AppContext) -> None` として `ctx` を受け取り、`ctx.data_dir`, `ctx.events`, `ctx.spawn`, `ctx.storage`, `ctx.http_app["state"]` を使用してください。
3. **UI エントリのパス**:
   - `app.json` の `"ui": {"entry": "dist/index.mjs"}` は `<app_root>/ui/` 相対で解決されるため、バンドルは `<app_root>/ui/dist/index.mjs` に出力してください。
4. **Ghost Foreman 管理スロットと権限**:
   - 他セッションの履歴取得には権限制約があるため、`kiro_crew.apps.worker_slots` の `set_worker_slot_limit("ghost-foreman", 20)` と `acquire_worker_slot(state, "ghost-foreman", key, project=..., agent=..., model=...)`（または Ghost Foreman 自身が管理するスロット＋外部セッション用の MCP 相談ツール `foreman_ask`）を使ってください。
   - `app.json` の `permissions` には `"spawn": true`, `"sessionApproval": true`, `"storage": true`, `"cron": true`, `"jobs": true` を含めてください。

### 進める順番（1ステップずつ実機で動作確認しながら進めること）
1. **Kiro Crew 本体の導入とアプリの登録**
   - Kiro Crew Gateway を起動し、`ghost-foreman` を `~/.kiro/crew/apps/ghost-foreman` に登録・有効化し、ダッシュボードと `/api/apps/ghost-foreman/dashboard` が実 Gateway 経由で動くことを確認する。
2. **Claude・Codex・Kiro の実セッションとの接続**
   - ダミー配列ではなく、実際の Claude Code / Codex / Kiro セッション（管理スロットおよび MCP 接続）と疎通し、状態監視・メッセージ送受信ができることを確認する。
3. **実際の質問に対する幽霊の代理回答・逆質問**
   - 実セッションからの確認に対し、①確定仕様（選択的記憶）に基づく自動回答と再開、②未知の質問に対する担当AIへの逆質問→選択肢と影響の整理→人間へのエスカレーション→人間の再質問・回答→元セッション再開を実機で動かす。
4. **iPhone への通知と遠隔回答**
   - Kiro Crew の PWA プッシュ通知／リモート接続を使い、iPhone への通知と iPhone からの回答・指示で実セッションが動くことを確認する。
5. **Gemini 無料 API 枠との実接続**
   - 公式 Gemini API（無料枠）に実接続して幽霊の判断・要約・ニュース整理を動かし、無料枠上限時の安全な切替と有料 API 無断課金防止ガードを確認する。
6. **ダミーデータを使わないブレスト（AI会議室）の実行**
   - 固定文字列ではなく、複数AIの実推論によって「独立案出し → 相互批評・改善 → 幽霊の整理」を実行し、人間が採用した案だけを次のタスクとして発注・予約できるようにする。

まずは現状の `ghost-foreman/` フォルダのコードと Kiro Crew 環境を確認し、ステップ1（Kiro Crew 本体の導入・Gateway 起動・アプリ登録と疎通確認）から開始してください。
```
