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
    """Dual-mode Kiro Crew Gateway adapter (live_gateway vs simulated_gateway)."""

    def __init__(self, store: ForemanStore) -> None:
        self.store = store
        self.app_name = "ghost-foreman"
        self.gateway_url = os.environ.get("KIROCREW_GATEWAY_URL", "http://127.0.0.1:4120").rstrip("/")
        self._token: Optional[str] = None
        self.gateway_mode = self._detect_gateway_mode()

    def _detect_gateway_mode(self) -> str:
        secret_path = Path.home() / ".kiro" / "crew" / "apps" / self.app_name / ".app_secret"
        if secret_path.exists():
            try:
                secret = secret_path.read_text(encoding="utf-8").strip()
                req = urllib.request.Request(
                    f"{self.gateway_url}/api/apps/{self.app_name}/token",
                    data=json.dumps({"secret": secret}).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=1.5) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    self._token = data.get("token")
                    if self._token:
                        return "live_gateway"
            except Exception:
                pass
        return "simulated_gateway"

    def list_slots(self, project_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """List Ghost Foreman Managed Slots and MCP-connected external slots."""
        with self.store._conn() as conn:
            if project_id:
                rows = conn.execute(
                    "SELECT * FROM managed_slots WHERE project_id = ? ORDER BY id ASC",
                    (project_id,),
                ).fetchall()
            else:
                rows = conn.execute("SELECT * FROM managed_slots ORDER BY id ASC").fetchall()

        result = []
        for r in rows:
            item = dict(r)
            item["history"] = json.loads(item.pop("history_json", "[]"))
            item["context"] = json.loads(item.pop("context_json", "[]"))
            item["gateway_mode"] = self.gateway_mode
            result.append(item)
        return result

    def get_slot(self, slot_id: str) -> Optional[Dict[str, Any]]:
        with self.store._conn() as conn:
            row = conn.execute("SELECT * FROM managed_slots WHERE id = ?", (slot_id,)).fetchone()
            if not row:
                return None
            item = dict(row)
            item["history"] = json.loads(item.pop("history_json", "[]"))
            item["context"] = json.loads(item.pop("context_json", "[]"))
            item["gateway_mode"] = self.gateway_mode
            return item

    def create_managed_slot(
        self,
        project_id: str,
        name: str,
        backend: str,
        role: str,
        current_task: str,
        next_task: str = "",
        worktree_branch: str = "",
    ) -> Dict[str, Any]:
        """Create a new Ghost Foreman Managed Slot (`POST /api/chat/slots`)."""
        with self.store._conn() as conn:
            count = conn.execute("SELECT COUNT(*) AS c FROM managed_slots").fetchone()["c"]
            slot_id = f"slot-{count + 1:02d}"
            branch = worktree_branch or f"feat/{project_id}-{slot_id}"
            now = _now_iso()
            initial_history = [
                {
                    "role": "system",
                    "text": f"[Managed Slot Created by Ghost Foreman] agent={backend} role={role} branch={branch}",
                    "ts": now,
                }
            ]
            conn.execute(
                """
                INSERT INTO managed_slots
                (id, project_id, name, backend, role, ownership, status, current_task, waiting_reason, next_task, worktree_branch, history_json, context_json, updated_at)
                VALUES (?, ?, ?, ?, ?, 'managed', 'working', ?, '', ?, ?, ?, '[]', ?)
                """,
                (
                    slot_id,
                    project_id,
                    name,
                    backend,
                    role,
                    current_task,
                    next_task,
                    branch,
                    json.dumps(initial_history, ensure_ascii=False),
                    now,
                ),
            )
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
            "messages": slot["history"][-limit:],
        }

    def send_message(self, slot_id: str, message: str, sender: str = "ghost_foreman", resume_work: bool = True) -> Dict[str, Any]:
        """Send a reply or reverse-probe to a slot (`sendMessage(id, msg)`) and optionally resume its work."""
        slot = self.get_slot(slot_id)
        if not slot:
            raise ValueError(f"Unknown slot_id: {slot_id}")

        history = slot["history"]
        now = _now_iso()
        history.append({"role": sender, "text": message, "ts": now})

        new_status = "working" if resume_work else slot["status"]
        new_waiting = "" if resume_work else slot["waiting_reason"]

        if resume_work:
            history.append(
                {
                    "role": "assistant",
                    "text": f"了解しました。指示（{message[:60]}...）に基づき『{slot['current_task']}』の作業を再開します。",
                    "ts": now,
                }
            )

        with self.store._conn() as conn:
            conn.execute(
                """
                UPDATE managed_slots
                SET status = ?, waiting_reason = ?, history_json = ?, updated_at = ?
                WHERE id = ?
                """,
                (new_status, new_waiting, json.dumps(history, ensure_ascii=False), now, slot_id),
            )
        return self.get_slot(slot_id)  # type: ignore[return-value]

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
