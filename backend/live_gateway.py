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
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("ghost-foreman.live")

APP_NAME = "ghost-foreman"
WORKER_SLOT_LIMIT = 20
DEFAULT_AGENT = "kirocrew"
CALL_TIMEOUT_SECS = 60.0


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

    async def stop(self, key: str) -> None:
        lease = self.leases.pop(key, None)
        if lease is not None and not lease.released:
            await lease.release()

    async def release_all(self) -> None:
        for key in list(self.leases):
            try:
                await self.stop(key)
            except Exception:  # noqa: BLE001 - shutdown must not raise
                logger.exception("release failed for %s", key)
