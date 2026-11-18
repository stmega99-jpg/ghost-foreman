"""Persistent SQLite storage for Ghost Foreman (Managed Slots, Policies, Questions, Audit Log, Meetings, News, Budgets, Desktop Lease)."""

from __future__ import annotations

import json
import os
import sqlite3
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


class ForemanStore:
    """App-scoped SQLite storage that survives restarts and deduplicates question IDs."""

    def __init__(self, db_path: Optional[str] = None) -> None:
        if db_path is None:
            data_dir = Path(os.environ.get("GHOST_FOREMAN_DATA_DIR", Path(__file__).resolve().parent.parent / "data"))
            data_dir.mkdir(parents=True, exist_ok=True)
            db_path = str(data_dir / "ghost_foreman.db")
        self.db_path = db_path
        self._init_db()

    @contextmanager
    def _conn(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _migrate(self, conn: sqlite3.Connection) -> None:
        cols = {r["name"] for r in conn.execute("PRAGMA table_info(managed_slots)").fetchall()}
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS llm_usage (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TEXT NOT NULL,
                provider_id TEXT NOT NULL,
                model TEXT NOT NULL DEFAULT '',
                task TEXT NOT NULL DEFAULT '',
                input_tokens INTEGER NOT NULL DEFAULT 0,
                output_tokens INTEGER NOT NULL DEFAULT 0,
                cost_usd REAL,
                cost_basis TEXT NOT NULL DEFAULT '',
                ok INTEGER NOT NULL DEFAULT 1,
                note TEXT NOT NULL DEFAULT ''
            )
            """
        )
        # cost_usd must be NULL ("unconfirmed") when no billed amount is known; an earlier build stored 0.0 here.
        info = {r["name"]: r for r in conn.execute("PRAGMA table_info(llm_usage)").fetchall()}
        if info.get("cost_usd") is not None and info["cost_usd"]["notnull"]:
            conn.executescript(
                """
                ALTER TABLE llm_usage RENAME TO llm_usage_old;
                CREATE TABLE llm_usage (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT NOT NULL, provider_id TEXT NOT NULL,
                    model TEXT NOT NULL DEFAULT '', task TEXT NOT NULL DEFAULT '',
                    input_tokens INTEGER NOT NULL DEFAULT 0, output_tokens INTEGER NOT NULL DEFAULT 0,
                    cost_usd REAL, cost_basis TEXT NOT NULL DEFAULT '', ok INTEGER NOT NULL DEFAULT 1, note TEXT NOT NULL DEFAULT ''
                );
                INSERT INTO llm_usage (id, ts, provider_id, model, task, input_tokens, output_tokens, cost_usd, cost_basis, ok, note)
                    SELECT id, ts, provider_id, model, task, input_tokens, output_tokens, NULL, cost_basis, ok, note FROM llm_usage_old;
                DROP TABLE llm_usage_old;
                """
            )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS notifications_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT NOT NULL, question_id TEXT NOT NULL, kind TEXT NOT NULL,
                title TEXT NOT NULL DEFAULT '', body TEXT NOT NULL DEFAULT '', delivery TEXT NOT NULL, detail TEXT NOT NULL DEFAULT ''
            )
            """
        )
        if "live_key" not in cols:
            # Non-empty live_key marks a slot backed by a real Kiro Crew Gateway slot.
            conn.execute("ALTER TABLE managed_slots ADD COLUMN live_key TEXT NOT NULL DEFAULT ''")

    def _init_db(self) -> None:
        with self._conn() as conn:
            self._init_schema(conn)
            self._migrate(conn)

    def _init_schema(self, conn: sqlite3.Connection) -> None:
        if True:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS kv_state (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS projects (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT NOT NULL,
                    priority INTEGER NOT NULL DEFAULT 1,
                    status TEXT NOT NULL DEFAULT 'active',
                    budget_usd REAL NOT NULL DEFAULT 0.0,
                    spent_usd REAL NOT NULL DEFAULT 0.0,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS managed_slots (
                    id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    backend TEXT NOT NULL,
                    role TEXT NOT NULL,
                    ownership TEXT NOT NULL DEFAULT 'managed',
                    status TEXT NOT NULL DEFAULT 'working',
                    current_task TEXT NOT NULL DEFAULT '',
                    waiting_reason TEXT NOT NULL DEFAULT '',
                    next_task TEXT NOT NULL DEFAULT '',
                    worktree_branch TEXT NOT NULL DEFAULT '',
                    history_json TEXT NOT NULL DEFAULT '[]',
                    context_json TEXT NOT NULL DEFAULT '[]',
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS policies (
                    id TEXT PRIMARY KEY,
                    scope TEXT NOT NULL,
                    project_id TEXT NOT NULL DEFAULT '*',
                    title TEXT NOT NULL,
                    rule_text TEXT NOT NULL,
                    keywords_json TEXT NOT NULL DEFAULT '[]',
                    locked INTEGER NOT NULL DEFAULT 1,
                    version INTEGER NOT NULL DEFAULT 1,
                    active INTEGER NOT NULL DEFAULT 1,
                    source TEXT NOT NULL DEFAULT 'human',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS questions (
                    id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    slot_id TEXT NOT NULL,
                    kind TEXT NOT NULL DEFAULT 'natural_question',
                    raw_question TEXT NOT NULL,
                    context_summary TEXT NOT NULL DEFAULT '',
                    options_json TEXT NOT NULL DEFAULT '[]',
                    recommendation TEXT NOT NULL DEFAULT '',
                    recommendation_reason TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL DEFAULT 'pending',
                    probe_count INTEGER NOT NULL DEFAULT 0,
                    probe_history_json TEXT NOT NULL DEFAULT '[]',
                    proposes_spec_change INTEGER NOT NULL DEFAULT 0,
                    conflict_with_slot TEXT NOT NULL DEFAULT '',
                    resolution_source TEXT NOT NULL DEFAULT '',
                    final_answer TEXT NOT NULL DEFAULT '',
                    policy_id_applied TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS decisions_audit (
                    id TEXT PRIMARY KEY,
                    question_id TEXT NOT NULL,
                    project_id TEXT NOT NULL,
                    slot_id TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    action_type TEXT NOT NULL,
                    raw_question TEXT NOT NULL,
                    referenced_policy_id TEXT NOT NULL DEFAULT '',
                    answer_sent TEXT NOT NULL,
                    rationale TEXT NOT NULL,
                    promoted_to_policy_id TEXT NOT NULL DEFAULT '',
                    reverted INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS meetings (
                    id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    topic TEXT NOT NULL,
                    participants_json TEXT NOT NULL DEFAULT '[]',
                    rounds_json TEXT NOT NULL DEFAULT '[]',
                    summary_json TEXT NOT NULL DEFAULT '{}',
                    status TEXT NOT NULL DEFAULT 'completed',
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS ideas (
                    id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    source TEXT NOT NULL DEFAULT 'human',
                    status TEXT NOT NULL DEFAULT 'saved',
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS news_items (
                    id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    category TEXT NOT NULL,
                    title TEXT NOT NULL,
                    url TEXT NOT NULL,
                    published_date TEXT NOT NULL,
                    facts_summary TEXT NOT NULL,
                    estimates_summary TEXT NOT NULL,
                    relevance_reason TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS provider_budgets (
                    provider_id TEXT PRIMARY KEY,
                    display_name TEXT NOT NULL,
                    tier_type TEXT NOT NULL,
                    free_quota_limit INTEGER NOT NULL DEFAULT 100,
                    free_quota_used INTEGER NOT NULL DEFAULT 0,
                    paid_allowed INTEGER NOT NULL DEFAULT 0,
                    paid_budget_usd REAL NOT NULL DEFAULT 0.0,
                    paid_spent_usd REAL NOT NULL DEFAULT 0.0,
                    cost_tracking_mode TEXT NOT NULL DEFAULT 'measured',
                    status TEXT NOT NULL DEFAULT 'available'
                );

                CREATE TABLE IF NOT EXISTS desktop_leases (
                    device_id TEXT PRIMARY KEY,
                    holder_type TEXT NOT NULL DEFAULT 'human',
                    holder_slot_id TEXT NOT NULL DEFAULT '',
                    purpose TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL DEFAULT 'human_active',
                    queue_json TEXT NOT NULL DEFAULT '[]',
                    last_recording_note TEXT NOT NULL DEFAULT '',
                    updated_at TEXT NOT NULL
                );
                """
            )

    def get_state(self, key: str, default: Any = None) -> Any:
        with self._conn() as conn:
            row = conn.execute("SELECT value FROM kv_state WHERE key = ?", (key,)).fetchone()
            if not row:
                return default
            return json.loads(row["value"])

    def set_state(self, key: str, value: Any) -> None:
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO kv_state (key, value, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
                """,
                (key, json.dumps(value, ensure_ascii=False), _now_iso()),
            )

    def seed_defaults_if_empty(self) -> None:
        with self._conn() as conn:
            count = conn.execute("SELECT COUNT(*) AS c FROM projects").fetchone()["c"]
            if count > 0:
                return

        # Notification / Operation Mode ('resident', 'away', 'sleep')
        self.set_state(
            "foreman_mode",
            {
                "mode": "away",
                "quiet_until": "07:30",
                "allow_unpublished_to_free_tier": False,
                "gateway_mode": "simulated_gateway",
            },
        )

        now = _now_iso()
        projects = [
            ("proj-game", "アクションゲーム制作（見本）", "横スクロールのアクションゲーム（見本の案件）", 1, "active", 20.0, 0.0, now),
            ("proj-budget", "家計簿アプリ開発（見本）", "毎月の支出を記録する家計簿アプリ（見本の案件）", 2, "active", 15.0, 0.0, now),
            ("proj-foreman", "Ghost Foreman Crew App", "Kiroween 2026 出品用 Kiro Crew 現場監督アプリ", 1, "active", 10.0, 0.0, now),
        ]
        with self._conn() as conn:
            conn.executemany(
                "INSERT INTO projects (id, name, description, priority, status, budget_usd, spent_usd, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                projects,
            )

        # Initial Policies (Selective Memory)
        policies = [
            (
                "pol-global-01",
                "global",
                "*",
                "外部有料APIの無断課金禁止",
                "無料枠または契約済み定額枠を優先し、人間の明示的な許可なしに従量課金APIへ切り替えない。",
                json.dumps(["課金", "有料API", "paid", "billing", "レート制限", "クォータ"], ensure_ascii=False),
                1,
                1,
                1,
                "human_spec",
                now,
                now,
            ),
            (
                "pol-game-01",
                "project",
                "proj-game",
                "セーブデータ形式とタイムスタンプ規約",
                "アクションゲームのローカルセーブデータは JSON 形式（UTF-8）とし、日時はすべて ISO8601 UTC 文字列で保存する。バイナリ独自形式は使わない。",
                json.dumps(["セーブ", "save", "日付", "時刻", "timestamp", "UNIX", "ISO8601", "JSON", "フォーマット"], ensure_ascii=False),
                1,
                1,
                1,
                "human_spec",
                now,
                now,
            ),
            (
                "pol-game-02",
                "project",
                "proj-game",
                "3Dモデルポリゴン上限とアセット規約",
                "キャラクター1体あたりのポリゴン数は最大 12,000 tris 以下とし、テクスチャは 2048x2048 PNG に統一する。",
                json.dumps(["ポリゴン", "tris", "テクスチャ", "解像度", "モデル", "FBX", "GLB"], ensure_ascii=False),
                1,
                1,
                1,
                "human_spec",
                now,
                now,
            ),
            (
                "pol-budget-01",
                "project",
                "proj-budget",
                "金額の計算ルール（確定仕様）",
                "家計簿アプリの金額は1円単位の整数で保存し、税額の端数は切り捨てで固定する。四捨五入は導入しない。",
                json.dumps(["金額", "計算", "端数", "四捨五入", "切り捨て", "税額"], ensure_ascii=False),
                1,
                1,
                1,
                "human_spec",
                now,
                now,
            ),
        ]
        with self._conn() as conn:
            conn.executemany(
                """
                INSERT INTO policies (id, scope, project_id, title, rule_text, keywords_json, locked, version, active, source, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                policies,
            )

        # Provider Budgets (Free-tier first)
        providers = [
            ("gemini-free", "Google Gemini 2.5 Flash (Free Tier API)", "free_api", 50, 12, 0, 0.0, 0.0, "measured", "available"),
            ("claude-max-sub", "Claude Code (Max 20x Subscription)", "subscription", 1000, 340, 0, 200.0, 0.0, "estimated", "available"),
            ("codex-sub", "OpenAI Codex CLI (Pro Subscription)", "subscription", 1000, 210, 0, 200.0, 0.0, "estimated", "available"),
            ("kiro-bot", "Kiro Crew Built-in Bot Harness", "host_included", 500, 95, 0, 0.0, 0.0, "measured", "available"),
            ("anthropic-paid-api", "Anthropic Paid Per-Token API (Fallback)", "paid_api", 0, 0, 0, 5.0, 0.0, "measured", "locked_by_policy"),
        ]
        with self._conn() as conn:
            conn.executemany(
                """
                INSERT INTO provider_budgets (provider_id, display_name, tier_type, free_quota_limit, free_quota_used, paid_allowed, paid_budget_usd, paid_spent_usd, cost_tracking_mode, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                providers,
            )

        # Seed 18 sessions across projects to demonstrate full multi-session scale (Spec B & Section 5/7)
        slot_defs = [
            ("slot-01", "proj-game", "Claude-Code #1 (Save/API)", "claude-code", "実装担当", "managed", "working", "セーブデータ読み書きモジュールの実装", "", "オートセーブ単体テスト作成", "feat/game-save"),
            ("slot-02", "proj-game", "Claude-Code #2 (DB/Cache)", "claude-code", "設計・実装", "managed", "working", "アイテムインベントリの永続化・検索層の設計", "", "インデックス最適化", "feat/game-inventory"),
            ("slot-03", "proj-game", "Codex #1 (3D Physics)", "codex", "物理挙動", "managed", "working", "ジャンプ時の重力・慣性バランスの調整", "", "ステージ2の衝突判定", "feat/game-physics"),
            ("slot-04", "proj-game", "Kiro-Bot #1 (Code Review)", "kiro-bot", "査読担当", "managed", "working", "PR #14 の差分レビューと仕様整合チェック", "", "PR #15 のレビュー待機", "review/game-pr14"),
            ("slot-05", "proj-game", "Codex #2 (Auto-Playtest)", "codex", "テスト担当", "managed", "queued_desktop", "ステージ2ボス戦の自動通しプレイ検証（PC操作枠待ち）", "人間がPC使用中のため待機（離席時間に予約済）", "録画とクラッシュログ提出", "test/game-playtest"),
            ("slot-06", "proj-game", "Gemini-Worker #1 (Dialogue)", "gemini-free", "テキスト補助", "managed", "working", "NPC 24人分の台詞バリエーション生成", "", "誤字脱字チェック", "feat/game-npc"),
            ("slot-07", "proj-budget", "Claude-Code #3 (Core)", "claude-code", "集計ロジック", "managed", "working", "月別・費目別の集計処理の実装", "", "予算超過の警告表示", "feat/budget-core"),
            ("slot-08", "proj-budget", "Claude-Code #4 (UI)", "claude-code", "画面実装", "managed", "working", "支出入力フォームと一覧画面の実装", "", "スマホ画面比率調整", "feat/budget-ui"),
            ("slot-09", "proj-budget", "Codex #3 (Import)", "codex", "取込処理", "managed", "working", "銀行CSVの取込と重複検出", "", "取込エラーの一覧表示", "feat/budget-import"),
            ("slot-10", "proj-budget", "Kiro-Bot #2 (Test Runner)", "kiro-bot", "単体テスト", "managed", "working", "集計処理の回帰テストスイート実行", "", "境界値テスト追加", "test/budget-core"),
            ("slot-11", "proj-budget", "Gemini-Worker #2 (Docs)", "gemini-free", "資料整理", "managed", "working", "使い方ガイドと用語集の整理", "", "用語集の更新", "docs/budget-guide"),
            ("slot-12", "proj-budget", "Claude-Code #5 (Notify)", "claude-code", "通知実装", "managed", "working", "予算超過の通知タイミング調整", "", "通知文言の確認", "feat/budget-notify"),
            ("slot-13", "proj-foreman", "Claude-Code #6 (Foreman UI)", "claude-code", "UI実装", "managed", "working", "レスポンシブ監督ダッシュボードと幽霊アニメ実装", "", "モバイル通知カード調整", "feat/foreman-ui"),
            ("slot-14", "proj-foreman", "Codex #4 (SDK Adapter)", "codex", "基盤実装", "managed", "working", "Managed Slots API と MCP 相談窓口の結合検証", "", "再起動リカバリ検証", "feat/foreman-sdk"),
            ("slot-15", "proj-foreman", "Kiro-Bot #3 (Spec Guard)", "kiro-bot", "仕様監査", "managed", "working", "Policy Store の版管理と無断仕様変更ブロック検証", "", "監査ログエクスポート", "feat/foreman-policy"),
            ("slot-16", "proj-foreman", "Gemini-Worker #3 (News Bot)", "gemini-free", "情報収集", "managed", "working", "インディーゲーム市場・AIツール・ハッカソン情報の巡回", "", "朝刊ダイジェスト生成", "chore/foreman-news"),
            ("slot-17", "proj-game", "Claude-Code #7 (Shader)", "claude-code", "描画担当", "external_mcp", "working", "夕暮れステージのトゥーンシェーダー調整（MCP連携セッション）", "", "軽量化プロファイル測定", "feat/game-shader"),
            ("slot-18", "proj-budget", "Codex #5 (Data Check)", "codex", "数値検証", "external_mcp", "working", "10,000件の取引データで集計結果を検証（MCP連携セッション）", "", "差分レポート作成", "test/budget-data"),
        ]
        with self._conn() as conn:
            for s in slot_defs:
                conn.execute(
                    """
                    INSERT INTO managed_slots
                    (id, project_id, name, backend, role, ownership, status, current_task, waiting_reason, next_task, worktree_branch, history_json, context_json, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        s[0],
                        s[1],
                        s[2],
                        s[3],
                        s[4],
                        s[5],
                        s[6],
                        s[7],
                        s[8],
                        s[9],
                        s[10],
                        json.dumps([{"role": "system", "text": f"Initialized {s[2]} on branch {s[10]}"}], ensure_ascii=False),
                        json.dumps([], ensure_ascii=False),
                        now,
                    ),
                )

        # Seed News Items (Spec I: Facts vs Estimates separated)
        news_items = [
            (
                "news-01",
                "proj-game",
                "インディーゲーム市場動向",
                "Steam『アクション』タグの新作フェス注目作分析（見本）",
                "https://store.steampowered.com/news/",
                "2026-11-18",
                "【事実（見本）】直近30日で公開されたアクションのインディー作品4本のうち、3本がデモ版で『コントローラー振動と手触りのよい操作感』を主要訴求に採用。レビュー数はそれぞれ 140〜420 件。",
                "【推定】レビュー数からの推定販売本数は 4,500〜15,000 本規模（Boxleiter法による推計であり公式発表値ではない）。短時間でリトライできるタイムアタック要素が好評とみられる。",
                "見本のアクションゲームの体験版設計の参考として収集（見本）。",
                now,
            ),
            (
                "news-02",
                "proj-foreman",
                "AI開発ツール・ハッカソン",
                "Kiro Crew 0.12 リリース：Bots 昇格・Live Browser Takeover・PWA Push 対応",
                "https://kiro.dev/changelog/crew/0-12/",
                "2026-11-18",
                "【事実】Kiro Crew 0.12 にて旧 Mates が Bots に改称され標準有効化。各 Bot に Git working tree と Work Ledger が付与され、iOS PWA プッシュ通知とブラウザ操作のリアルタイム引き継ぎが公式サポートされた。",
                "【推定】Kiroween の Best Kiro Crew App 審査では、ホスト標準機能を再発明するより、Slots / Notifications の上で独自の自律判断・会議・記憶層を提供するアプリが高く評価される可能性が高い。",
                "Ghost Foreman のアーキテクチャおよび Kiroween 2026 提出戦略に直結するため収集。",
                now,
            ),
            (
                "news-03",
                "proj-budget",
                "家計簿アプリ・市場動向",
                "個人向け家計管理アプリの比較記事まとめ（見本）",
                "https://www.ipa.go.jp/",
                "2026-11-17",
                "【事実】家計管理アプリの比較記事で、銀行明細の自動取込と予算アラートが主な比較項目として挙げられている（見本）。",
                "【推定】銀行CSV取込と予算超過の通知を優先すると、比較記事で取り上げられやすい見込み（見本）。",
                "家計簿アプリの機能の優先順位の参考として収集（見本）。",
                now,
            ),
        ]
        with self._conn() as conn:
            conn.executemany(
                """
                INSERT INTO news_items (id, project_id, category, title, url, published_date, facts_summary, estimates_summary, relevance_reason, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                news_items,
            )

        # Seed Desktop Lease (Spec H)
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO desktop_leases (device_id, holder_type, holder_slot_id, purpose, status, queue_json, last_recording_note, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "main-workstation",
                    "human",
                    "",
                    "人間がPCを使用中（最優先）",
                    "human_active",
                    json.dumps(
                        [
                            {
                                "slot_id": "slot-05",
                                "slot_name": "Codex #2 (Auto-Playtest)",
                                "project_id": "proj-game",
                                "scheduled_window": "21:00-21:45 (離席枠)",
                                "task": "アクションゲーム ステージ2自動テストプレイ＆録画",
                            }
                        ],
                        ensure_ascii=False,
                    ),
                    "前回録画: 2026-11-18 03:15 (夜間バッチ・クラッシュ0件・FPS平均58.4)",
                    now,
                ),
            )

        # Seed Ideas
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO ideas (id, project_id, title, content, source, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "idea-01",
                    "proj-game",
                    "雨のステージで足場が滑る仕掛けの案（見本）",
                    "見本のアイデア：雨のステージでは足場が少し滑るが、滑り止めの靴を取ると滑らなくなる駆け引きを入れてはどうか？（未決・AI会議で検討）",
                    "human_commute_memo",
                    "saved",
                    now,
                ),
            )
