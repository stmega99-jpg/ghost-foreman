"""In-process bridge to the real Kiro Crew Gateway (live managed slots).

Ghost Foreman runs inside the Gateway process, so it reaches real chat slots through the
host's own app-facing entry points instead of a simulator:

- ``kiro_crew.apps.worker_slots.acquire_worker_slot``: create / adopt an app-owned slot.
- ``kiro_crew.dashboard.session_deliver.deliver`` with an ``app`` origin: send a message
  into the slot (queued if the slot is mid-turn).
- ``slot.messages``: the slot's real transcript.

All coroutines run on the Gateway event loop. The rest of the backend is synchronous and is
called from worker threads (``asyncio.to_thread``), so ``call`` hops back onto the loop.

Nothing here fabricates a reply: whatever an agent answers is read back from the real slot.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("ghost-foreman.live")

APP_NAME = "ghost-foreman"
WORKER_SLOT_LIMIT = 20
DEFAULT_AGENT = "kirocrew"
CALL_TIMEOUT_SECS = 60.0
# Only Ghost Foreman's own consultation tools are auto-approved on its slots (via the host's
# sessionApproval route). Every other tool request is left for the human.
# (Host pattern trust cannot cover MCP calls that carry arguments, so approval is explicit per call.)
FOREMAN_TOOLS = [
    "@ghost-foreman:ghost-foreman-mcp/foreman_ask",
    "@ghost-foreman:ghost-foreman-mcp/foreman_get_policies",
    "@ghost-foreman:ghost-foreman-mcp/foreman_report_status",
]
APPROVAL_POLL_SECS = 2.0
TOKEN_CACHE_SECS = 240.0  # app tokens expire after 300s


class LiveGatewayError(RuntimeError):
    pass


class LiveGateway:
    def __init__(self, ctx: Any, loop: asyncio.AbstractEventLoop) -> None:
        self.ctx = ctx
        self.loop = loop
        self.state = self._resolve_state(ctx)
        self.workspaces_root = Path(ctx.data_dir) / "workspaces"
        self.leases: Dict[str, Any] = {}
        from kiro_crew.apps.worker_slots import set_worker_slot_limit

        set_worker_slot_limit(APP_NAME, WORKER_SLOT_LIMIT)
        self._token = ""
        self._token_ts = 0.0
        self.approved_count = 0
        self._approval_future = asyncio.run_coroutine_threadsafe(self._approval_loop(), loop)

    @staticmethod
    def _resolve_state(ctx: Any) -> Any:
        http_app = getattr(ctx, "http_app", None)
        state = http_app["state"] if http_app is not None else None
        if state is None:
            raise LiveGatewayError("Gateway DashboardState unavailable (ctx.http_app['state'])")
        return state

    # -- thread -> loop hop -------------------------------------------------
    def call(self, coro: Any, timeout: float = CALL_TIMEOUT_SECS) -> Any:
        """Run *coro* on the Gateway loop from a worker thread and return its result."""
        try:
            running = asyncio.get_running_loop()
        except RuntimeError:
            running = None
        if running is self.loop:
            raise LiveGatewayError("LiveGateway.call must be used from a worker thread")
        return asyncio.run_coroutine_threadsafe(coro, self.loop).result(timeout)

    # -- slots --------------------------------------------------------------
    async def acquire(self, key: str, project_id: str, agent: str = "", model: str = "") -> Dict[str, Any]:
        from kiro_crew.apps.worker_slots import acquire_worker_slot

        workdir = self.workspaces_root / project_id
        workdir.mkdir(parents=True, exist_ok=True)
        lease = await acquire_worker_slot(
            self.state,
            APP_NAME,
            key,
            project=str(workdir),
            agent=agent or DEFAULT_AGENT,
            model=model,
        )
        self.leases[lease.key] = lease
        return self.describe(lease.key)

    def _slot(self, key: str) -> Any:
        lease = self.leases.get(key)
        if lease is not None and not lease.released:
            return lease.slot
        slot = self.state.get_slot(key)
        if slot is None:
            raise LiveGatewayError(f"unknown live slot: {key}")
        return slot

    def describe(self, key: str) -> Dict[str, Any]:
        slot = self._slot(key)
        return {
            "live_key": slot.key,
            "running": bool(getattr(slot, "running", False)),
            "queue_depth": int(getattr(slot, "queue_depth", 0) or 0),
            "message_count": len(slot.messages),
        }

    async def send(self, key: str, text: str) -> str:
        from kiro_crew.dashboard import session_deliver

        slot = self._slot(key)
        from kiro_crew.dashboard import session_control

        outcome = await session_deliver.deliver(
            self.state,
            slot,
            text,
            session_deliver.app(APP_NAME),
            admission=session_control.containment_meta(self.state, slot),
        )
        if outcome == session_deliver.QUEUE_FULL:
            raise LiveGatewayError("slot queue is full")
        if outcome == session_deliver.NOT_DELIVERED:
            raise LiveGatewayError("slot is closed; message not delivered")
        return str(outcome)

    def history(self, key: str, limit: int = 50) -> List[Dict[str, Any]]:
        slot = self._slot(key)
        rows = list(slot.messages)[-limit:]
        out: List[Dict[str, Any]] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            out.append(
                {
                    "role": row.get("role") or row.get("kind") or "",
                    "text": row.get("text") or row.get("content") or "",
                    "ts": row.get("ts") or row.get("timestamp") or "",
                }
            )
        return out

    # -- foreman tool approvals --------------------------------------------
    def _http(self, method: str, path: str, body: Optional[Dict[str, Any]] = None) -> Any:
        """Call the Gateway as this app. App tokens live 300s, so refresh early and retry once on 401/403."""
        port = os.environ.get("KIROCREW_PORT", "5476")
        base = os.environ.get("KIROCREW_GATEWAY_URL", f"http://127.0.0.1:{port}").rstrip("/")
        for attempt in (0, 1):
            now = time.time()
            if attempt == 1 or not self._token or now - self._token_ts > TOKEN_CACHE_SECS:
                secret = (Path.home() / ".kiro" / "crew" / "apps" / APP_NAME / ".app_secret").read_text(encoding="utf-8").strip()
                req = urllib.request.Request(
                    f"{base}/api/apps/{APP_NAME}/token", data=b"{}", method="POST",
                    headers={"Content-Type": "application/json", "X-App-Secret": secret},
                )
                with urllib.request.urlopen(req, timeout=10) as resp:
                    self._token = json.loads(resp.read().decode("utf-8"))["token"]
                self._token_ts = now
            sep = "&" if "?" in path else "?"
            url = f"{base}{path}{sep}{urllib.parse.urlencode({'token': self._token})}"
            data = json.dumps(body).encode("utf-8") if body is not None else None
            req = urllib.request.Request(url, data=data, method=method, headers={"Content-Type": "application/json"})
            try:
                with urllib.request.urlopen(req, timeout=15) as resp:
                    return json.loads(resp.read().decode("utf-8") or "null")
            except urllib.error.HTTPError as exc:
                if exc.code in (401, 403) and attempt == 0:
                    continue
                raise
        raise RuntimeError("unreachable")
    def _approve_foreman_tools_once(self) -> int:
        done = 0
        for key in list(self.leases):
            slot = self.state.get_slot(key)
            if slot is None or not getattr(slot, "_approval_futures", None):
                continue
            listing = self._http("GET", "/api/chat/slots")
            info = next((s.get("pending_approval_info") for s in listing if s.get("key") == key and s.get("pending_approval")), None)
            if not info or info.get("tool") not in FOREMAN_TOOLS:
                continue  # not ours: leave it for the human
            self._http(
                "POST",
                f"/api/chat/slots/{urllib.parse.quote(key)}/approve",
                {"action": "approved", "request_id": info.get("request_id", ""), "request_mid": info.get("request_mid", ""), "origin": info.get("origin", "native")},
            )
            logger.info("auto-approved %s on %s", info.get("tool"), key)
            done += 1
        return done

    async def _approval_loop(self) -> None:
        while True:
            await asyncio.sleep(APPROVAL_POLL_SECS)
            if not self.leases:
                continue
            try:
                self.approved_count += await asyncio.to_thread(self._approve_foreman_tools_once)
            except Exception:  # noqa: BLE001 - keep polling
                logger.debug("approval poll failed", exc_info=True)

    # -- reply watching -----------------------------------------------------
    @staticmethod
    def _row_text(row: Dict[str, Any]) -> str:
        return str(row.get("content") or row.get("text") or "")

    def watch_reply(self, key: str, marker: str, callback: Any, timeout: float = 300.0) -> None:
        """Watch a live slot for the agent's answer to the message containing *marker*.

        When the turn that followed the marker row is done, ``callback(reply_text, error)`` is called
        in a worker thread. ``reply_text`` is None when the agent produced no answer (``error`` says why).
        Fire-and-forget; safe to call from a worker thread.
        """
        asyncio.run_coroutine_threadsafe(self._watch(key, marker, callback, timeout), self.loop)

    async def _watch(self, key: str, marker: str, callback: Any, timeout: float) -> None:
        deadline = self.loop.time() + timeout
        reply: Optional[str] = None
        error = "timeout"
        while self.loop.time() < deadline:
            await asyncio.sleep(2)
            try:
                rows = [r for r in self._slot(key).messages if isinstance(r, dict)]
            except Exception as exc:  # noqa: BLE001
                error = f"slot unavailable: {exc}"
                break
            start = next((i for i, r in enumerate(rows) if marker in self._row_text(r)), None)
            if start is None:
                continue
            tail = rows[start + 1 :]
            if any(r.get("role") == "done" for r in tail):
                answer = "\n".join(self._row_text(r) for r in tail if r.get("role") == "assistant").strip()
                errors = "\n".join(self._row_text(r) for r in tail if r.get("role") == "error").strip()
                reply, error = (answer or None), (errors or ("" if answer else "empty reply"))
                break
        try:
            await asyncio.to_thread(callback, reply, error)
        except Exception:  # noqa: BLE001
            logger.exception("watch_reply callback failed for %s", key)

    async def stop(self, key: str) -> None:
        lease = self.leases.pop(key, None)
        if lease is not None and not lease.released:
            await lease.release()

    def stop_slot(self, key: str) -> None:
        """Interrupt whatever the real session is doing (Gateway's own stop route). Worker-thread safe."""
        self._http("POST", f"/api/chat/slots/{urllib.parse.quote(key)}/stop", {})

    async def delete(self, key: str) -> None:
        """Release the lease and remove the slot from the Gateway (best effort)."""
        await self.stop(key)
        try:
            await asyncio.to_thread(self._http, "DELETE", f"/api/chat/slots/{urllib.parse.quote(key)}")
        except Exception:  # noqa: BLE001
            logger.debug("gateway slot delete failed for %s", key, exc_info=True)

    async def release_all(self) -> None:
        self._approval_future.cancel()
        for key in list(self.leases):
            try:
                await self.stop(key)
            except Exception:  # noqa: BLE001 - shutdown must not raise
                logger.exception("release failed for %s", key)
