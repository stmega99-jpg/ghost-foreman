"""Kiro Crew Gateway Adapter with Managed Slot Ownership & MCP Consultation Fallback.

Addresses Section 6.1 of Ghost Foreman v2.0:
- Because Kiro Crew enforces session isolation on reading arbitrary external session histories,
  Ghost Foreman creates and owns its own Managed Slots via `/api/chat/slots` (`createSlot`),
  giving it full permission to call `getSlotHistory`, `sendMessage`, and `/api/chat/slots/{id}/context`.
- External sessions created outside Ghost Foreman can also consult Ghost Foreman via the MCP bridge (`foreman_ask`).
- Automatically detects if the live Kiro Crew Gateway (`kirocrew-client` / `~/.kiro/crew/apps/ghost-foreman/.app_secret`)
  is reachable, and falls back to the local SQLite-backed Managed Slot simulator with explicit mode labeling.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional

from .store import ForemanStore, _now_iso


class CrewAdapter:
    """Kiro Crew adapter. Slots backed by a real Gateway slot carry a non-empty ``live_key``.

    ``gateway_mode`` is ``live_gateway`` only while a ``LiveGateway`` is bound (the app is
    running inside a Gateway). Individual slots without a ``live_key`` are simulated and are
    labelled ``simulated`` so the UI never presents them as real sessions.
    """

    def __init__(self, store: ForemanStore) -> None:
        self.store = store
        self.app_name = "ghost-foreman"
        self.live: Optional[Any] = None

    @property
    def gateway_mode(self) -> str:
        return "live_gateway" if self.live is not None else "simulated_gateway"

    def bind_live(self, live: Any) -> None:
        self.live = live

    def reattach_live_slots(self) -> List[str]:
        """After a Gateway restart, re-acquire the real slots recorded in the DB. Returns failures."""
        failed: List[str] = []
        if self.live is None:
            return failed
        with self.store._conn() as conn:
            rows = conn.execute("SELECT id, project_id, live_key FROM managed_slots WHERE live_key != ''").fetchall()
        for r in rows:
            try:
                self.live.call(self.live.acquire(r["live_key"], r["project_id"]))
            except Exception as exc:  # noqa: BLE001
                failed.append(f"{r['id']}: {exc}")
        return failed

    def _present(self, row: Any) -> Dict[str, Any]:
        item = dict(row)
        item["history"] = json.loads(item.pop("history_json", "[]"))
        item["context"] = json.loads(item.pop("context_json", "[]"))
        live_key = item.get("live_key", "")
        item["is_live"] = bool(live_key and self.live is not None)
        item["gateway_mode"] = "live_gateway" if item["is_live"] else "simulated"
        if item["is_live"]:
            try:
                item["history"] = self.live.history(live_key)
                item["live"] = self.live.describe(live_key)
            except Exception as exc:  # slot vanished from the Gateway
                item["live_error"] = str(exc)
        return item
    def list_slots(self, project_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """List Ghost Foreman managed slots (live Gateway slots and simulated ones, labelled)."""
        with self.store._conn() as conn:
            if project_id:
                rows = conn.execute(
                    "SELECT * FROM managed_slots WHERE project_id = ? ORDER BY id ASC", (project_id,)
                ).fetchall()
            else:
                rows = conn.execute("SELECT * FROM managed_slots ORDER BY id ASC").fetchall()
        return [self._present(r) for r in rows]

    def get_slot(self, slot_id: str) -> Optional[Dict[str, Any]]:
        with self.store._conn() as conn:
            row = conn.execute("SELECT * FROM managed_slots WHERE id = ?", (slot_id,)).fetchone()
        return self._present(row) if row else None

    def create_managed_slot(
        self,
        project_id: str,
        name: str,
        backend: str,
        role: str,
        current_task: str,
        next_task: str = "",
        worktree_branch: str = "",
        live: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """Create a Ghost Foreman managed slot.

        When bound to a Gateway (``live`` unset or True) a real app-owned Kiro Crew slot is
        acquired. ``live=False`` (or no Gateway) creates a simulated slot, labelled as such.
        """
        use_live = self.live is not None if live is None else bool(live)
        if use_live and self.live is None:
            raise RuntimeError("live slot requested but no Gateway is bound")
        with self.store._conn() as conn:
            count = conn.execute("SELECT COUNT(*) AS c FROM managed_slots").fetchone()["c"]
            slot_id = f"slot-{count + 1:02d}"
        live_key = ""
        if use_live:
            key = f"gf-{project_id}-{slot_id}"
            self.live.call(self.live.acquire(key, project_id, agent=""))
            live_key = key
        branch = worktree_branch or f"feat/{project_id}-{slot_id}"
        now = _now_iso()
        initial_history = [
            {
                "role": "system",
                "text": f"[Managed Slot Created by Ghost Foreman] agent={backend} role={role} branch={branch}",
                "ts": now,
            }
        ]
        with self.store._conn() as conn:
            conn.execute(
                """
                INSERT INTO managed_slots
                (id, project_id, name, backend, role, ownership, status, current_task, waiting_reason,
                 next_task, worktree_branch, history_json, context_json, updated_at, live_key)
                VALUES (?, ?, ?, ?, ?, 'managed', 'working', ?, '', ?, ?, ?, '[]', ?, ?)
                """,
                (slot_id, project_id, name, backend, role, current_task, next_task, branch,
                 json.dumps(initial_history, ensure_ascii=False), now, live_key),
            )
        if live_key:
            intro = (
                f"あなたは Ghost Foreman の管理スロット {slot_id}（案件: {project_id} / 役割: {role}）です。\n"
                f"最初の仕事: {current_task}\n\n"
                "ルール: 設計・仕様・方針で判断に迷ったら、人間へ直接尋ねず、foreman_ask ツール"
                f"（slot_id=\"{slot_id}\"）で現場監督（Ghost Foreman）に質問してください。"
                "回答が返るまで、その判断に依存しない作業を進めてください。"
                "現場監督の回答が確定ルールに基づく場合はそれに従ってください。"
            )
            self.send_message(slot_id, intro, sender="ghost_foreman", resume_work=True)
        return self.get_slot(slot_id)  # type: ignore[return-value]

    def get_slot_history(self, slot_id: str, limit: int = 50) -> Dict[str, Any]:
        """Retrieve message history for a Managed Slot, enforcing ownership checks."""
        slot = self.get_slot(slot_id)
        if not slot:
            raise ValueError(f"Unknown slot_id: {slot_id}")
        if slot["ownership"] != "managed":
            return {
                "slot_id": slot_id,
                "ownership": slot["ownership"],
                "access": "restricted_external_session",
                "note": "外部起動セッションのため直接履歴取得は制限されています。MCP相談窓口 (foreman_ask) 経由の質問のみ受信します。",
                "messages": slot["history"][-limit:],
            }
        return {
            "slot_id": slot_id,
            "ownership": "managed",
            "access": "full_managed_access",
            "gateway_mode": slot["gateway_mode"],
            "messages": slot["history"][-limit:],
        }

    def send_message(self, slot_id: str, message: str, sender: str = "ghost_foreman", resume_work: bool = True) -> Dict[str, Any]:
        """Send a reply or reverse-probe to a slot.

        Live slot: the message is delivered to the real Gateway session. No reply is fabricated;
        the agent's actual answer shows up in the slot's real history.
        Simulated slot: the message is appended to the local log only (no assistant reply is invented).
        """
        slot = self.get_slot(slot_id)
        if not slot:
            raise ValueError(f"Unknown slot_id: {slot_id}")
        now = _now_iso()
        delivery = "simulated_not_delivered"
        if slot.get("is_live"):
            delivery = self.live.call(self.live.send(slot["live_key"], message))
        else:
            with self.store._conn() as conn:
                row = conn.execute("SELECT history_json FROM managed_slots WHERE id = ?", (slot_id,)).fetchone()
                history = json.loads(row["history_json"])
                history.append({"role": sender, "text": message, "ts": now, "simulated": True})
                conn.execute(
                    "UPDATE managed_slots SET history_json = ? WHERE id = ?",
                    (json.dumps(history, ensure_ascii=False), slot_id),
                )
        new_status = "working" if resume_work else slot["status"]
        new_waiting = "" if resume_work else slot["waiting_reason"]
        with self.store._conn() as conn:
            conn.execute(
                "UPDATE managed_slots SET status = ?, waiting_reason = ?, updated_at = ? WHERE id = ?",
                (new_status, new_waiting, now, slot_id),
            )
        result = self.get_slot(slot_id)  # type: ignore[assignment]
        result["delivery"] = delivery  # type: ignore[index]
        return result  # type: ignore[return-value]
    def inject_slot_context(self, slot_id: str, policy_title: str, policy_rule: str) -> Dict[str, Any]:
        """Inject selective memory / updated policy into a slot's context (`/api/chat/slots/{slotId}/context`)."""
        slot = self.get_slot(slot_id)
        if not slot:
            raise ValueError(f"Unknown slot_id: {slot_id}")

        ctx = slot["context"]
        now = _now_iso()
        ctx.append({"title": policy_title, "rule": policy_rule, "injected_at": now})
        with self.store._conn() as conn:
            conn.execute(
                "UPDATE managed_slots SET context_json = ?, updated_at = ? WHERE id = ?",
                (json.dumps(ctx, ensure_ascii=False), now, slot_id),
            )
        return self.get_slot(slot_id)  # type: ignore[return-value]

    def stop_control(self, scope: str, target_id: str = "") -> Dict[str, Any]:
        """Stop work by slot, project, or all (Spec B & F emergency stop)."""
        now = _now_iso()
        with self.store._conn() as conn:
            if scope == "slot" and target_id:
                conn.execute(
                    "UPDATE managed_slots SET status = 'stopped', waiting_reason = '人間による個別停止操作', updated_at = ? WHERE id = ?",
                    (now, target_id),
                )
            elif scope == "project" and target_id:
                conn.execute(
                    "UPDATE managed_slots SET status = 'stopped', waiting_reason = '人間によるプロジェクト一括停止', updated_at = ? WHERE project_id = ?",
                    (now, target_id),
                )
            elif scope == "all":
                conn.execute(
                    "UPDATE managed_slots SET status = 'stopped', waiting_reason = '人間による全エージェント緊急停止', updated_at = ?",
                    (now,),
                )
            elif scope == "resume_all":
                conn.execute(
                    "UPDATE managed_slots SET status = 'working', waiting_reason = '', updated_at = ? WHERE status = 'stopped'",
                    (now,),
                )
        return {"ok": True, "scope": scope, "target_id": target_id, "updated_at": now}
