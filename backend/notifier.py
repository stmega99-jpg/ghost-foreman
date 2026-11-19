"""Human notifications (Spec F): decide WHEN to ping the human, deliver through Kiro Crew's own notification bus.

Delivery (PWA / Web Push to the iPhone, the in-app bell) is the host's job: this module only calls
``POST /api/notifications/push`` on channels declared in app.json. Ghost Foreman adds the policy on top:

- resident (在宅): do not interrupt; the item is only shown in the app.
- away (離席): push as soon as a decision is needed; items of one project share a ``group_key`` so the phone
  collapses them, and each question is notified at most once.
- sleep (おやすみ): hold everything; at ``quiet_until`` send ONE digest. Nothing is dropped.

Every decision is written to ``notifications_log`` (sent / held / digested / failed / not_sent) so what the human
was or was not told is auditable. A notification failure never affects the question flow.
"""

from __future__ import annotations

import json
import logging
import threading
import time
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional

from .store import ForemanStore, _now_iso

logger = logging.getLogger("ghost-foreman.notifier")

CHANNEL_DECISION = "decision-needed"
CHANNEL_DIGEST = "digest"
# Opens Ghost Foreman's own phone page (not the Kiro Crew dashboard).
APP_PAGE = "/api/apps/ghost-foreman/m/"
DIGEST_CHECK_SECS = 30.0
NOTIFY_STATUSES = ("needs_human", "needs_human_approval", "held_spec_violation")

Pusher = Callable[[str, str, Optional[Dict[str, Any]]], Any]


def _clip(text: str, n: int) -> str:
    text = " ".join(str(text or "").split())
    return text if len(text) <= n else text[: n - 1] + "…"


class Notifier:
    def __init__(self, store: ForemanStore, adapter: Any, clock: Callable[[], datetime] = datetime.now) -> None:
        self.store = store
        self.adapter = adapter
        self._clock = clock
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

    # ------------------------------------------------------------------ transport
    def _push(self, payload: Dict[str, Any]) -> Any:
        live = getattr(self.adapter, "live", None)
        if live is None:
            raise RuntimeError("no Gateway bound (simulated mode): nothing can be delivered")
        return live._http("POST", "/api/notifications/push", payload)

    # ------------------------------------------------------------------ mode logic
    def _mode(self) -> Dict[str, Any]:
        return self.store.get_state("foreman_mode", {}) or {}

    def quiet_window_end(self) -> Optional[datetime]:
        """End of the current sleep window = the first quiet_until (HH:MM) after sleep started. None if not asleep."""
        mode = self._mode()
        if mode.get("mode") != "sleep":
            return None
        started = mode.get("sleep_started_at")
        try:
            start = datetime.fromisoformat(started) if started else self._clock()
            hh, mm = (int(x) for x in str(mode.get("quiet_until", "07:30")).split(":"))
        except (TypeError, ValueError):
            return None
        end = start.replace(hour=hh, minute=mm, second=0, microsecond=0)
        if end <= start:
            end += timedelta(days=1)
        return end

    def _log(self, question_id: str, kind: str, title: str, body: str, delivery: str, detail: str = "") -> None:
        with self.store._conn() as conn:
            conn.execute(
                "INSERT INTO notifications_log (ts, question_id, kind, title, body, delivery, detail) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (_now_iso(), question_id, kind, title, body, delivery, detail[:300]),
            )

    def _already_logged(self, question_id: str, kind: str) -> bool:
        with self.store._conn() as conn:
            row = conn.execute(
                "SELECT 1 FROM notifications_log WHERE question_id = ? AND kind = ? AND delivery IN ('sent', 'held', 'digested', 'held_resident')",
                (question_id, kind),
            ).fetchone()
        return row is not None

    # ------------------------------------------------------------------ public API
    def decision_needed(self, question_id: str) -> str:
        """Called when a question needs the human. Returns the delivery outcome (also written to the log)."""
        try:
            with self._lock:
                return self._decision_needed(question_id)
        except Exception as exc:  # noqa: BLE001 - must never break the question flow
            logger.warning("notification failed for %s: %s", question_id, exc)
            self._log(question_id, "decision", "", "", "failed", str(exc))
            return "failed"

    def _decision_needed(self, question_id: str) -> str:
        with self.store._conn() as conn:
            q = conn.execute("SELECT * FROM questions WHERE id = ?", (question_id,)).fetchone()
            if not q or q["status"] not in NOTIFY_STATUSES:
                return "not_needed"
            project = conn.execute("SELECT name FROM projects WHERE id = ?", (q["project_id"],)).fetchone()
            pending = conn.execute(
                "SELECT COUNT(*) AS c FROM questions WHERE project_id = ? AND status IN ('needs_human','needs_human_approval','held_spec_violation')",
                (q["project_id"],),
            ).fetchone()["c"]
        if self._already_logged(question_id, "decision"):
            return "duplicate_suppressed"
        name = project["name"] if project else q["project_id"]
        title = f"👻 判断待ち: {_clip(name, 30)}"
        body = _clip(q["raw_question"], 90) + (f"（この案件で{pending}件待ち）" if pending > 1 else "")
        if getattr(self.adapter, "live", None) is None:
            self._log(question_id, "decision", title, body, "not_sent", "模擬モード: Gateway未接続のため通知は送信しません")
            return "not_sent"
        mode = self._mode().get("mode", "away")
        if mode == "resident":
            self._log(question_id, "decision", title, body, "held_resident", "常駐モード: 通知せず画面にのみ表示")
            return "held_resident"
        end = self.quiet_window_end()
        if mode == "sleep" and end is not None and self._clock() < end:
            self._log(question_id, "decision", title, body, "held", f"おやすみモード: {end.strftime('%H:%M')} にまとめて報告")
            return "held"
        priority = "critical" if q["status"] == "held_spec_violation" else "default"
        try:
            result = self._push(
                {
                    "channel": CHANNEL_DECISION,
                    "title": title,
                    "body": body,
                    "priority": priority,
                    "group_key": f"gf-{q['project_id']}",
                    "url": f"{APP_PAGE}?q={question_id}",
                    "meta": {"question_id": question_id, "project_id": q["project_id"]},
                }
            )
        except Exception as exc:  # noqa: BLE001
            self._log(question_id, "decision", title, body, "failed", str(exc))
            return "failed"
        self._log(question_id, "decision", title, body, "sent", json.dumps(result, ensure_ascii=False)[:250] if result else "")
        return "sent"

    def send_test(self) -> Dict[str, Any]:
        """A harmless test push the human asked for. Ignores the mode, never touches a question."""
        title, body = "👻 Ghost Foreman テスト通知", "このメッセージが届けば、iPhoneへの通知は成功です。タップするとアプリが開きます。"
        try:
            result = self._push({"channel": CHANNEL_DECISION, "title": title, "body": body, "priority": "default", "group_key": "gf-test", "url": APP_PAGE})
        except Exception as exc:  # noqa: BLE001
            self._log("*", "test", title, body, "failed", str(exc))
            return {"ok": False, "error": str(exc)}
        self._log("*", "test", title, body, "sent", json.dumps(result, ensure_ascii=False)[:250] if result else "")
        return {"ok": True, "result": result}

    # ------------------------------------------------------------------ sleep digest
    def send_digest_if_due(self) -> Optional[int]:
        """After the sleep window ends, send one digest for everything that was held. Returns the item count."""
        with self._lock:
            mode = self._mode()
            end = self.quiet_window_end()
            if mode.get("mode") != "sleep" or end is None or self._clock() < end:
                return None
            with self.store._conn() as conn:
                held = [r["question_id"] for r in conn.execute("SELECT question_id FROM notifications_log WHERE delivery = 'held' AND kind = 'decision'").fetchall()]
                open_ids = [
                    r["id"]
                    for r in conn.execute("SELECT id FROM questions WHERE status IN ('needs_human','needs_human_approval','held_spec_violation')").fetchall()
                    if r["id"] in held
                ]
            if not open_ids:
                return 0
            title = "☀️ おはようございます: 判断待ちのまとめ"
            body = f"夜のあいだに判断待ちが{len(open_ids)}件あります。アプリを開いて確認してください。"
            try:
                self._push({"channel": CHANNEL_DIGEST, "title": title, "body": body, "priority": "default", "group_key": "gf-digest", "url": APP_PAGE})
            except Exception as exc:  # noqa: BLE001
                self._log("*", "digest", title, body, "failed", str(exc))
                return None
            for qid in open_ids:
                self._log(qid, "decision", title, body, "digested", "朝のまとめとして送信")
            with self.store._conn() as conn:
                conn.execute("UPDATE notifications_log SET delivery = 'held_done' WHERE delivery = 'held' AND question_id IN (%s)" % ",".join("?" * len(open_ids)), open_ids)
            self._log("*", "digest", title, body, "sent", f"{len(open_ids)} items")
            return len(open_ids)

    def start(self) -> None:
        if self._thread is not None:
            return

        def loop() -> None:
            while not self._stop.wait(DIGEST_CHECK_SECS):
                try:
                    self.send_digest_if_due()
                except Exception:  # noqa: BLE001
                    logger.debug("digest check failed", exc_info=True)

        self._thread = threading.Thread(target=loop, daemon=True, name="foreman-digest")
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def recent(self, limit: int = 20) -> List[Dict[str, Any]]:
        with self.store._conn() as conn:
            return [dict(r) for r in conn.execute("SELECT * FROM notifications_log ORDER BY id DESC LIMIT ?", (limit,)).fetchall()]
