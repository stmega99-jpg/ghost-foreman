"""Automated verification suite for Ghost Foreman Phase 1–3 acceptance criteria (Section 7 of Ghost_Foreman_企画書_v2.md)."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from backend.crew_adapter import CrewAdapter
from backend.mcp_server import handle_mcp_call
from backend.store import ForemanStore
from backend.supervisor import ForemanSupervisor


def run_verification() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        db_file = str(Path(tmpdir) / "test_foreman.db")
        os.environ["GHOST_FOREMAN_DATA_DIR"] = tmpdir

        store = ForemanStore(db_path=db_file)
        store.seed_defaults_if_empty()
        adapter = CrewAdapter(store)
        supervisor = ForemanSupervisor(store, adapter)

        print("=== [1] 18個のセッション識別＆Managed Slots / 外部MCP権限制約の検証 ===")
        slots = adapter.list_slots()
        assert len(slots) == 18, f"Expected 18 seeded slots, got {len(slots)}"
        managed_hist = adapter.get_slot_history("slot-01")
        external_hist = adapter.get_slot_history("slot-17")
        assert managed_hist["access"] == "full_managed_access"
        assert external_hist["access"] == "restricted_external_session"
        print(f"OK: 18 slots active. slot-01={managed_hist['access']}, slot-17={external_hist['access']}")

        print("\n=== [2] 既知の確認が人間を呼ばず根拠引用付きで自動解決する検証 ===")
        q_known = supervisor.receive_agent_question(
            slot_id="slot-01",
            raw_question="セーブデータのタイムスタンプはUNIX秒とISO8601のどちらでJSONに保存しますか？",
            question_id="q-test-known-01",
        )
        assert q_known["status"] == "auto_resolved", f"Expected auto_resolved, got {q_known['status']}"
        assert q_known["policy_id_applied"] == "pol-game-01"
        # Verify idempotency (re-sending same question_id does not duplicate execution)
        q_dup = supervisor.receive_agent_question(
            slot_id="slot-01",
            raw_question="セーブデータのタイムスタンプはUNIX秒とISO8601のどちらでJSONに保存しますか？",
            question_id="q-test-known-01",
        )
        assert q_dup.get("deduplicated") is True
        print(f"OK: Auto-resolved via {q_known['policy_id_applied']} and deduplicated on replay.")

        print("\n=== [3] 未決事項の事前逆質問 → 人間からの再質問 → 選択的記憶（恒久ルール昇格）＆一括回答のスコープ隔離検証 ===")
        q_unk1 = supervisor.receive_agent_question(
            slot_id="slot-02",
            raw_question="アイテムインベントリの検索キャッシュにJSONとSQLiteのどちらを使いますか？",
            question_id="q-test-unk-01",
        )
        assert q_unk1["status"] == "needs_human"
        assert q_unk1["probe_count"] == 1
        assert len(q_unk1["options"]) >= 2

        # Another pending question in the SAME project (proj-game) and one in a DIFFERENT project (proj-budget)
        q_unk_same_proj = supervisor.receive_agent_question(
            slot_id="slot-03",
            raw_question="ステージ2のリプレイログキャッシュもJSONかSQLiteか迷っています",
            question_id="q-test-unk-02",
        )
        q_unk_other_proj = supervisor.receive_agent_question(
            slot_id="slot-08",
            raw_question="入力フォームのアニメーションイージングはeaseOutかspringのどちらにしますか？",
            question_id="q-test-unk-03",
        )
        assert q_unk_same_proj["status"] == "needs_human"
        assert q_unk_other_proj["status"] == "needs_human"

        # Human asks Ghost Foreman a follow-up question first ("JSONとSQLiteの違いは？")
        q_inquired = supervisor.ask_ghost_about_question(
            question_id="q-test-unk-01",
            human_inquiry="JSONとSQLiteの違いは？今回ならどちらが便利？",
            re_probe_agent=True,
        )
        assert any(p["role"] == "ghost_explanation" for p in q_inquired["probe_history"])

        # Human resolves q-test-unk-01 with permanent_policy + batch_apply_same_project=True
        q_resolved = supervisor.resolve_question_by_human(
            question_id="q-test-unk-01",
            answer_text="キャッシュ・検索層はすべて SQLite テーブルで統一する。",
            memory_mode="permanent_policy",
            policy_scope="project",
            policy_title="キャッシュ・検索層のSQLite統一規約",
            policy_keywords=["キャッシュ", "SQLite", "インベントリ"],
            batch_apply_same_project=True,
        )
        assert q_resolved["status"] == "human_resolved"
        assert q_resolved["promoted_policy_id"].startswith("pol-")
        assert "q-test-unk-02" in q_resolved["batch_resolved_ids"]

        # Verify unrelated project (proj-budget: q-test-unk-03) was NOT touched by batch reply!
        q_other_after = supervisor.get_question("q-test-unk-03")
        assert q_other_after["status"] == "needs_human", "Batch reply leaked to another project!"
        print("OK: Reverse-probe, human follow-up inquiry, selective memory promotion, and project-scoped batch reply verified.")

        print("\n=== [4] 確定仕様に反する提案の保留（Spec Violation Guard）検証 ===")
        q_spec_viol = supervisor.receive_agent_question(
            slot_id="slot-07",
            raw_question="金額計算を四捨五入に変えて仕様変更してよいか？",
            proposes_spec_change=True,
        )
        assert q_spec_viol["status"] == "held_spec_violation"
        print(f"OK: Locked specification violation held ({q_spec_viol['policy_id_applied']}).")

        print("\n=== [5] 無料API枠上限到達時に許可なく有料APIへ切り替わらない検証 ===")
        with store._conn() as conn:
            conn.execute("UPDATE provider_budgets SET free_quota_used = free_quota_limit WHERE provider_id = 'gemini-free'")
        route_after_exhaust = supervisor.route_supervisor_llm("triage")
        assert route_after_exhaust["allowed"] is True
        assert route_after_exhaust["provider_id"] == "kiro-bot"
        assert route_after_exhaust.get("switched_from") == "gemini-free"

        paid_attempt = supervisor.route_supervisor_llm("triage", require_paid=True)
        assert paid_attempt["allowed"] is False
        print(f"OK: Free-tier exhaustion safely routed to {route_after_exhaust['provider_id']} and blocked unauthorized paid API.")

        print("\n=== [6] AI会議室（独立案出し→相互批評→幽霊の整理）＆採用案のみタスク化検証 ===")
        mtg = supervisor.run_brainstorm_meeting(
            project_id="proj-game",
            topic="雨のステージで足場が滑る仕掛けの案",
        )
        assert mtg["status"] == "awaiting_human_adoption"
        assert len(mtg["rounds"]) == 2
        adopt_res = supervisor.adopt_meeting_option(mtg["id"], "adopt_hybrid", target_slot_id="slot-03")
        assert adopt_res["action"] == "scheduled_to_slot"
        slot3 = adapter.get_slot("slot-03")
        assert "雨のステージで足場が滑る仕掛けの案" in slot3["next_task"]
        print("OK: AI Brainstorming Room & human adoption scheduling verified.")

        print("\n=== [7] PC操作権（Desktop Lease）の貸出・人間への即時返却＆全停止操作検証 ===")
        lease_ai = supervisor.control_desktop_lease("grant_to_ai", slot_id="slot-05")
        assert lease_ai["holder_type"] == "ai_slot"
        lease_human = supervisor.control_desktop_lease("reclaim_for_human", slot_id="slot-05")
        assert lease_human["holder_type"] == "human"
        adapter.stop_control("all")
        assert all(s["status"] == "stopped" for s in adapter.list_slots())
        adapter.stop_control("resume_all")
        print("OK: Desktop lease grant/reclaim and emergency stop verified.")

        print("\n=== [8] 再起動後の永続状態（未処理質問・記憶・企画）復元検証 ===")
        store2 = ForemanStore(db_path=db_file)
        adapter2 = CrewAdapter(store2)
        supervisor2 = ForemanSupervisor(store2, adapter2)
        pending_after_restart = supervisor2.list_questions(status="needs_human")
        assert any(q["id"] == "q-test-unk-03" for q in pending_after_restart)
        policies_after_restart = supervisor2.list_policies(project_id="proj-game")
        assert any(p["id"] == q_resolved["promoted_policy_id"] for p in policies_after_restart)
        print("OK: State persistence across restart verified.")

        print("\nALL 8 ACCEPTANCE TEST SUITES PASSED SUCCESSFULLY!")


if __name__ == "__main__":
    run_verification()
