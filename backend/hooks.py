"""Kiro Crew App lifecycle hooks (`backend.hooks:on_startup` and `backend.hooks:on_shutdown`).

Conforms to Kiro Crew 0.12.2 `LifecycleDispatcher` ABI:
- `async def on_startup(ctx: AppContext) -> None`
- `async def on_shutdown(ctx: AppContext) -> None`
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from .crew_adapter import CrewAdapter
from .store import ForemanStore
from .supervisor import ForemanSupervisor

_STORE: ForemanStore | None = None
_ADAPTER: CrewAdapter | None = None
_SUPERVISOR: ForemanSupervisor | None = None
_CTX: Any = None
_LIVE: Any = None


def get_runtime(data_dir: Path | None = None) -> tuple[ForemanStore, CrewAdapter, ForemanSupervisor]:
    global _STORE, _ADAPTER, _SUPERVISOR
    if _STORE is None:
        if data_dir is not None:
            data_dir.mkdir(parents=True, exist_ok=True)
            db_path = str(data_dir / "ghost_foreman.db")
        else:
            db_path = None
        _STORE = ForemanStore(db_path=db_path)
        _STORE.seed_defaults_if_empty()
    if _ADAPTER is None:
        _ADAPTER = CrewAdapter(_STORE)
    if _SUPERVISOR is None:
        _SUPERVISOR = ForemanSupervisor(_STORE, _ADAPTER)
    return _STORE, _ADAPTER, _SUPERVISOR


async def on_startup(ctx: Any = None) -> None:
    """Invoked asynchronously by Kiro Crew Gateway when Ghost Foreman is enabled or starts."""
    global _CTX
    _CTX = ctx
    data_dir = Path(ctx.data_dir) if ctx is not None and hasattr(ctx, "data_dir") else None
    loop = asyncio.get_running_loop()

    def _init() -> None:
        global _LIVE
        store, adapter, _ = get_runtime(data_dir=data_dir)
        try:
            from .live_gateway import LiveGateway

            _LIVE = LiveGateway(ctx, loop)
            adapter.bind_live(_LIVE)
        except Exception as exc:  # outside a Gateway or state unavailable: stay simulated, and say so
            _LIVE = None
            log = getattr(ctx, "logger", None)
            if log is not None:
                log.warning("ghost-foreman: live Gateway bridge unavailable (%s); running simulated", exc)
        if _LIVE is not None:
            adapter.reattach_live_slots()
            sup = get_runtime()[2]
            sup.recover_probes()
            sup.meetings.recover_interrupted()
            sup.notifier.start()
        mode_state = store.get_state("foreman_mode", {})
        mode_state["gateway_mode"] = adapter.gateway_mode
        store.set_state("foreman_mode", mode_state)

    await asyncio.to_thread(_init)


async def on_shutdown(ctx: Any = None) -> None:
    """Invoked asynchronously by Kiro Crew Gateway when Ghost Foreman is disabled or stopped."""
    global _LIVE
    if _SUPERVISOR is not None:
        _SUPERVISOR.notifier.stop()
    if _LIVE is not None:
        await _LIVE.release_all()
        _LIVE = None
