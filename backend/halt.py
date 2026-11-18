"""Emergency-stop state: after a human presses stop, NOTHING restarts work until a human gives permission.

Stopping sets a persistent hold (``kv_state['emergency_halt']``, so it survives a Gateway restart) on the whole
installation, one project or one slot. While a hold applies:

- no message is delivered to a real session (auto-replies, reverse-probes, orders from an adopted meeting,
  judge calls, and also direct sends: the human resumes first, then sends),
- no new real slot or meeting is created,
- ``foreman_*`` tool calls are not auto-approved,
- an incoming question is recorded as ``held_emergency_stop`` and is neither judged nor answered.

Only an explicit resume (``/stop`` with ``resume_*``) lifts a hold. Resuming does not replay or auto-answer anything
that arrived during the hold: those questions go to the human as ``needs_human``.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .store import ForemanStore, _now_iso

KEY = "emergency_halt"


class EmergencyStopped(RuntimeError):
    """Raised when something tries to start or continue work while a hold applies."""

    code = "emergency_stop"


def _empty() -> Dict[str, Any]:
    return {"all": False, "projects": [], "slots": [], "since": "", "reason": ""}


class HaltState:
    def __init__(self, store: ForemanStore) -> None:
        self.store = store

    # -- reading -----------------------------------------------------------
    def snapshot(self) -> Dict[str, Any]:
        data = _empty()
        data.update(self.store.get_state(KEY, {}) or {})
        data["active"] = bool(data["all"] or data["projects"] or data["slots"])
        return data

    def is_halted(self, slot_id: Optional[str] = None, project_id: Optional[str] = None) -> bool:
        s = self.snapshot()
        if s["all"]:
            return True
        if project_id and project_id in s["projects"]:
            return True
        return bool(slot_id and slot_id in s["slots"])

    def halted_for_slot_row(self, slot: Dict[str, Any]) -> bool:
        return self.is_halted(slot_id=slot.get("id"), project_id=slot.get("project_id"))

    def ensure_running(self, slot: Optional[Dict[str, Any]] = None, project_id: Optional[str] = None) -> None:
        sid = slot.get("id") if slot else None
        pid = project_id or (slot.get("project_id") if slot else None)
        if self.is_halted(slot_id=sid, project_id=pid):
            raise EmergencyStopped("緊急停止中です。人間が再開を許可するまで、自動で作業の発注・送信・再開は行いません。")

    # -- changing ----------------------------------------------------------
    def engage(self, scope: str, target_id: str = "", reason: str = "人間による緊急停止") -> Dict[str, Any]:
        s = self.snapshot()
        if scope == "all":
            s["all"] = True
        elif scope == "project" and target_id:
            s["projects"] = sorted(set(s["projects"]) | {target_id})
        elif scope == "slot" and target_id:
            s["slots"] = sorted(set(s["slots"]) | {target_id})
        else:
            raise ValueError(f"cannot stop scope={scope!r} target={target_id!r}")
        s["since"] = s["since"] or _now_iso()
        s["reason"] = reason
        self._save(s)
        return self.snapshot()

    def release(self, scope: str, target_id: str = "") -> Dict[str, Any]:
        s = self.snapshot()
        if scope in ("resume_all", "all"):
            s = _empty()
        elif scope == "resume_project" and target_id:
            s["projects"] = [p for p in s["projects"] if p != target_id]
        elif scope == "resume_slot" and target_id:
            s["slots"] = [x for x in s["slots"] if x != target_id]
        else:
            raise ValueError(f"cannot resume scope={scope!r} target={target_id!r}")
        if not (s["all"] or s["projects"] or s["slots"]):
            s = _empty()
        self._save(s)
        return self.snapshot()

    def _save(self, s: Dict[str, Any]) -> None:
        s = {k: s[k] for k in ("all", "projects", "slots", "since", "reason")}
        self.store.set_state(KEY, s)

    # -- audit ---------------------------------------------------------------
    def audit(self, action: str, scope: str, target_id: str, detail: str) -> None:
        import uuid

        with self.store._conn() as conn:
            conn.execute(
                "INSERT INTO decisions_audit (id, question_id, project_id, slot_id, actor, action_type, raw_question, answer_sent, rationale, created_at)"
                " VALUES (?, '-', ?, ?, 'human', ?, ?, '', ?, ?)",
                (f"aud-{uuid.uuid4().hex[:8]}", target_id if scope in ("project", "resume_project") else "*", target_id if scope in ("slot", "resume_slot") else "*", action, f"{scope} {target_id}".strip(), detail, _now_iso()),
            )

    def held_slot_ids(self) -> List[str]:
        return list(self.snapshot()["slots"])
