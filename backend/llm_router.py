"""Provider router for Ghost Foreman's own reasoning (Spec C).

Order: Gemini free tier -> Kiro Crew session ("judge" slot, included in the user's plan) -> hold.
There is deliberately NO code path to a metered paid API: a switch to one would need an explicit human
permission and budget, and none is implemented. Confidential project text is not sent to the Gemini free tier
unless the human enabled ``allow_unpublished_to_free_tier`` (free-tier inputs may be used by the provider).

Every call is recorded in ``llm_usage`` (tokens measured by the provider; cost basis stated), and the
``provider_budgets`` rows shown on the dashboard are updated from real calls.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from .gemini import (
    GeminiAuthError,
    GeminiClient,
    GeminiNoKey,
    GeminiQuotaExhausted,
    GeminiStopped,
    GeminiUnavailable,
)
from .store import ForemanStore, _now_iso

GEMINI_ID = "gemini-free"
KIRO_ID = "kiro-bot"
DEFAULT_COOLDOWN_SECS = 1800.0
MAX_COOLDOWN_SECS = 24 * 3600.0
KIRO_JUDGE_TIMEOUT_SECS = 150.0
JUDGE_PROJECT = "ghost-foreman-internal"


class LlmUnavailable(RuntimeError):
    """No allowed provider could answer (the caller should hold / escalate to the human)."""


@dataclass
class LlmResult:
    text: str
    provider_id: str
    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: Optional[float]  # None = unconfirmed. No provider here exposes a billed amount, so it is never 0.0.
    note: str
    switched_from: str = ""


class LlmRouter:
    def __init__(self, store: ForemanStore, adapter: Any, gemini: Optional[GeminiClient] = None, clock: Callable[[], float] = time.time) -> None:
        self.store = store
        self.adapter = adapter
        self.gemini = gemini or GeminiClient()
        self._clock = clock
        self._lock = threading.Lock()

    # ------------------------------------------------------------ settings / state
    def allow_confidential_to_free_tier(self) -> bool:
        return bool((self.store.get_state("foreman_mode", {}) or {}).get("allow_unpublished_to_free_tier", False))

    def _cooldown_until(self) -> float:
        return float(self.store.get_state("gemini_cooldown_until", 0.0) or 0.0)

    def _set_status(self, provider_id: str, status: str) -> None:
        with self.store._conn() as conn:
            conn.execute("UPDATE provider_budgets SET status = ? WHERE provider_id = ?", (status, provider_id))

    def _bump_quota(self, provider_id: str) -> None:
        today = datetime.now().strftime("%Y-%m-%d")
        with self.store._conn() as conn:
            if self.store.get_state(f"quota_day:{provider_id}", "") != today:
                conn.execute("UPDATE provider_budgets SET free_quota_used = 0 WHERE provider_id = ?", (provider_id,))
            conn.execute("UPDATE provider_budgets SET free_quota_used = free_quota_used + 1 WHERE provider_id = ?", (provider_id,))
        self.store.set_state(f"quota_day:{provider_id}", today)

    def _soft_limit_reached(self, provider_id: str) -> bool:
        today = datetime.now().strftime("%Y-%m-%d")
        with self.store._conn() as conn:
            row = conn.execute("SELECT free_quota_used, free_quota_limit FROM provider_budgets WHERE provider_id = ?", (provider_id,)).fetchone()
        if not row:
            return False
        used = row["free_quota_used"] if self.store.get_state(f"quota_day:{provider_id}", "") == today else 0
        return used >= row["free_quota_limit"]

    def _record(self, provider_id: str, model: str, task: str, tin: int, tout: int, ok: bool, note: str, basis: str) -> None:
        with self.store._conn() as conn:
            conn.execute(
                "INSERT INTO llm_usage (ts, provider_id, model, task, input_tokens, output_tokens, cost_usd, cost_basis, ok, note) VALUES (?, ?, ?, ?, ?, ?, NULL, ?, ?, ?)",
                (_now_iso(), provider_id, model, task, tin, tout, basis, 1 if ok else 0, note[:300]),
            )

    # ------------------------------------------------------------ Gemini free tier
    def gemini_status(self) -> Dict[str, Any]:
        """Can Gemini take a call right now? Read from local state only: checking costs no API call (and no quota)."""
        if not self.gemini.has_key():
            return {"available": False, "reason": "GEMINI_API_KEY が Kiro Crew に登録されていません（設定 → Secrets）"}
        until = self._cooldown_until()
        if self._clock() < until:
            return {"available": False, "reason": f"Gemini 無料枠が上限に達したため待機中です（再開目安 {max(1, int((until - self._clock()) // 60))} 分後）。有料APIには切り替えません"}
        if self._soft_limit_reached(GEMINI_ID):
            return {"available": False, "reason": "Gemini 無料枠の、設定した1日の上限に達しています"}
        return {"available": True, "reason": ""}

    def _try_gemini(self, task: str, prompt: str, system: str, json_mode: bool, max_output_tokens: int, notes: List[str],
                    should_stop: Optional[Callable[[], bool]] = None) -> Optional[LlmResult]:
        """One Gemini free-tier attempt. Returns the result, or None with the reason appended to *notes*.
        *should_stop* is checked before every API request (see GeminiClient._call)."""
        st = self.gemini_status()
        if not st["available"]:
            notes.append("Gemini: " + st["reason"])
            return None
        try:
            kwargs: Dict[str, Any] = {"system": system, "json_mode": json_mode, "max_output_tokens": max_output_tokens}
            if should_stop is not None:
                kwargs["should_stop"] = should_stop
            res = self.gemini.generate(prompt, **kwargs)
            self._bump_quota(GEMINI_ID)
            self._set_status(GEMINI_ID, "available")
            self._record(GEMINI_ID, res.model, task, res.input_tokens, res.output_tokens, True, "ok", "free tier (token counts measured)")
            return LlmResult(res.text, GEMINI_ID, res.model, res.input_tokens, res.output_tokens, None, "Gemini公式無料枠を使用（請求額は未確認）")
        except GeminiQuotaExhausted as exc:
            wait = min(max(exc.retry_after_secs or DEFAULT_COOLDOWN_SECS, 60.0), MAX_COOLDOWN_SECS)
            self.store.set_state("gemini_cooldown_until", self._clock() + wait)
            self._set_status(GEMINI_ID, "quota_exhausted_switched")
            self._record(GEMINI_ID, "", task, 0, 0, False, f"quota exhausted; cooldown {int(wait)}s", "free tier")
            notes.append(f"Gemini無料枠が上限（再開目安 {int(wait // 60)} 分後）。有料APIには切り替えません")
        except (GeminiAuthError, GeminiNoKey) as exc:
            self._set_status(GEMINI_ID, "key_rejected")
            self._record(GEMINI_ID, "", task, 0, 0, False, str(exc), "free tier")
            notes.append(f"Gemini: {exc}")
        except GeminiStopped as exc:
            # A stop, not a provider problem: no cooldown, and the key is not marked as rejected.
            self._record(GEMINI_ID, "", task, 0, 0, False, "emergency stop: no further request sent", "free tier")
            notes.append(str(exc))
        except GeminiUnavailable as exc:
            self._record(GEMINI_ID, "", task, 0, 0, False, str(exc), "free tier")
            notes.append(f"Gemini一時利用不可: {exc}")
        return None

    def gemini_only(self, task: str, prompt: str, *, unpublished_allowed: bool, system: str = "", json_mode: bool = False,
                    max_output_tokens: int = 1024, should_stop: Optional[Callable[[], bool]] = None) -> LlmResult:
        """Gemini free tier and NOTHING else: no Kiro fallback, no paid API. For a meeting participant named "Gemini".

        *unpublished_allowed* is the caller's own, explicit permission for THIS text (an AI meeting asks the human per
        meeting). It is required, and the global ``allow_unpublished_to_free_tier`` switch is neither read nor changed.
        Raises ``LlmUnavailable`` with the reason when Gemini cannot answer.
        """
        if unpublished_allowed is not True:
            raise LlmUnavailable("未公開の制作情報を Gemini 無料枠に送る許可がありません")
        notes: List[str] = []
        res = self._try_gemini(task, prompt, system, json_mode, max_output_tokens, notes, should_stop=should_stop)
        if res is None:
            raise LlmUnavailable("; ".join(notes) or "Gemini が回答できませんでした")
        return res

    # ------------------------------------------------------------ main entry
    def complete(self, task: str, prompt: str, system: str = "", json_mode: bool = False, confidential: bool = True, scope: str = "global") -> LlmResult:
        notes: List[str] = []
        switched_from = ""

        if not self.gemini.has_key():
            notes.append("Gemini: キー未登録")
        elif confidential and not self.allow_confidential_to_free_tier():
            notes.append("Gemini無料枠: 制作内容を含むため未許可のためスキップ（設定 allow_unpublished_to_free_tier）")
        else:
            res = self._try_gemini(task, prompt, system, json_mode, 1024, notes)
            if res is not None:
                return res
            switched_from = GEMINI_ID

        # Fallback: a real Kiro Crew session (included in the user's plan; token cost not exposed -> "unknown")
        if getattr(self.adapter, "live", None) is not None:
            try:
                text = self._ask_kiro(prompt, system, scope)
                self._record(KIRO_ID, "kiro-session", task, 0, 0, True, "; ".join(notes)[:200], "included in plan (usage not exposed: unknown)")
                return LlmResult(text, KIRO_ID, "kiro-session", 0, 0, None, "Kiro Crew 標準枠の実セッションで判定。" + " ".join(notes), switched_from)
            except Exception as exc:  # noqa: BLE001
                notes.append(f"Kiro判定: {exc}")
        raise LlmUnavailable("; ".join(notes) or "no provider available")

    # ------------------------------------------------------------ Kiro fallback
    def _judge_slot(self, scope: str) -> Dict[str, Any]:
        name = f"幽霊・判定係({scope})"
        with self.store._conn() as conn:
            row = conn.execute("SELECT id FROM managed_slots WHERE name = ? AND live_key != ''", (name,)).fetchone()
        if row:
            slot = self.adapter.get_slot(row["id"])
            if slot and slot.get("is_live") and not slot.get("live_error"):
                return slot
            self.adapter.retire_slot(row["id"])
        return self.adapter.create_managed_slot(JUDGE_PROJECT, name, "kiro", "判定係", f"判定: {scope}", live=True, send_intro=False)

    def _ask_kiro(self, prompt: str, system: str, scope: str) -> str:
        slot = self._judge_slot(scope)
        marker = f"[judge:{int(self._clock() * 1000)}:{threading.get_ident() % 10000}]"
        text = f"{marker}\n{system}\nツールやファイル操作はせず、依頼された形式だけで答えてください。\n\n{prompt}"
        done = threading.Event()
        out: Dict[str, Any] = {}

        def _cb(reply: Optional[str], err: str) -> None:
            out["reply"], out["err"] = reply, err
            done.set()

        self.adapter.send_message(slot["id"], text, sender="ghost_foreman_judge", resume_work=False)
        self.adapter.live.watch_reply(slot["live_key"], marker, _cb, timeout=KIRO_JUDGE_TIMEOUT_SECS)
        if not done.wait(KIRO_JUDGE_TIMEOUT_SECS + 20) or not out.get("reply"):
            raise RuntimeError(f"no answer ({out.get('err') or 'timeout'})")
        return str(out["reply"])

    # ------------------------------------------------------------ reporting
    def usage_summary(self, limit: int = 20) -> Dict[str, Any]:
        with self.store._conn() as conn:
            totals = [dict(r) for r in conn.execute(
                "SELECT provider_id, COUNT(*) AS calls, SUM(ok) AS ok_calls, SUM(input_tokens) AS input_tokens, SUM(output_tokens) AS output_tokens, SUM(cost_usd) AS cost_usd FROM llm_usage GROUP BY provider_id"
            ).fetchall()]
            for t in totals:
                # SUM over only-NULL rows is NULL: keep it NULL and say so, never show it as $0.
                t["cost_display"] = "未確認" if t["cost_usd"] is None else f"${t['cost_usd']:.4f}"
            recent = [dict(r) for r in conn.execute("SELECT * FROM llm_usage ORDER BY id DESC LIMIT ?", (limit,)).fetchall()]
        return {
            "totals": totals,
            "recent": recent,
            "gemini_cooldown_until": self._cooldown_until(),
            "allow_unpublished_to_free_tier": self.allow_confidential_to_free_tier(),
            "actual_billing": "未確認",
            "billing_note": (
                "実際の請求額はAPIから取得できません。Gemini無料枠のみの利用なら通常は発生しませんが、アプリでは確認できないため"
                "「未確認」と表示しています。Google AI Studio / Cloud Billing の請求画面で確認してください。"
                "Kiro の判定は契約枠内で、使用量はホストが公開していません。"
            ),
            "paid_api": "not implemented: no path to a metered paid API exists",
        }
