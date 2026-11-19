"""Kiro Crew App routes (`backend.routes:register_routes`) and core API dispatcher.

Conforms strictly to Kiro Crew 0.12.2 `RouteRegistry.register_app_routes(app_name, app_dir, hook_path, ctx)`:
- `register_routes(ctx: AppContext) -> list[ForemanRoute]` returns a list of route objects
  with `.method`, `.path` (relative to `/api/apps/ghost-foreman`), and `.handler(request, ctx)`.
- Performs no heavy DB/network I/O inside `register_routes()`.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, List, Tuple

from .halt import EmergencyStopped
from .store import _now_iso as _now


# Files served as Ghost Foreman's own phone page (see ui/m/). Fixed allowlist: no path is ever built from the request.
_APP_ROOT = Path(__file__).resolve().parent.parent
_HTML = "text/html; charset=utf-8"
_JS = "application/javascript; charset=utf-8"
_STATIC_FILES: Dict[str, Tuple[str, str]] = {
    "/m": ("ui/m/index.html", _HTML),
    "/m/": ("ui/m/index.html", _HTML),
    "/m/sdk.mjs": ("ui/m/sdk.mjs", _JS),
    "/m/app.mjs": ("ui/dist/index.mjs", _JS),  # the same React UI the dashboard loads
    "/m/sw.js": ("ui/m/sw.js", _JS),  # scope = /api/apps/ghost-foreman/m/ (its own directory)
}


def _static_handler(rel_path: str) -> Callable[[Any, Any], Awaitable[Any]]:
    filename, content_type = _STATIC_FILES[rel_path]

    async def _handler(request: Any, app_ctx: Any = None) -> Any:
        from aiohttp import web

        data = await asyncio.to_thread((_APP_ROOT / filename).read_bytes)
        return web.Response(body=data, headers={"Content-Type": content_type, "Cache-Control": "no-store"})

    return _handler


@dataclass
class ForemanRoute:
    """Structural match for `kiro_crew.apps.route_registry.AppRoute` (`_route_fields`)."""

    method: str
    path: str
    handler: Callable[[Any, Any], Awaitable[Any]]


def dispatch_api_request(method: str, path: str, body: Dict[str, Any] | None = None) -> Tuple[int, Dict[str, Any]]:
    """Framework-agnostic API dispatcher used by both Kiro Crew Gateway routes and the local dev server."""
    from .hooks import get_runtime

    store, adapter, supervisor = get_runtime()
    payload = body or {}

    # Normalize path so both `/dashboard` (RouteRegistry relative) and `/api/apps/ghost-foreman/dashboard` work
    rel_path = path
    for prefix in ("/api/apps/ghost-foreman", "/api"):
        if rel_path.startswith(prefix):
            rel_path = rel_path[len(prefix) :] or "/"
            break

    if method == "GET" and rel_path == "/dashboard":
        with store._conn() as conn:
            projects = [dict(r) for r in conn.execute("SELECT * FROM projects ORDER BY priority ASC").fetchall()]
            budgets = [dict(r) for r in conn.execute("SELECT * FROM provider_budgets").fetchall()]
            audits = [dict(r) for r in conn.execute("SELECT * FROM decisions_audit ORDER BY created_at DESC LIMIT 30").fetchall()]
            ideas = [dict(r) for r in conn.execute("SELECT * FROM ideas ORDER BY created_at DESC").fetchall()]
            news = [dict(r) for r in conn.execute("SELECT * FROM news_items ORDER BY created_at DESC").fetchall()]
            meetings_raw = conn.execute("SELECT * FROM meetings ORDER BY created_at DESC").fetchall()
            lease_row = dict(conn.execute("SELECT * FROM desktop_leases WHERE device_id = 'main-workstation'").fetchone())
            lease_row["queue"] = json.loads(lease_row.pop("queue_json", "[]"))

        meetings = []
        for m in meetings_raw:
            md = dict(m)
            md["participants"] = json.loads(md.pop("participants_json", "[]"))
            md["rounds"] = json.loads(md.pop("rounds_json", "[]"))
            md["summary"] = json.loads(md.pop("summary_json", "{}"))
            meetings.append(md)

        slots = adapter.list_slots()
        questions = supervisor.list_questions()
        policies = supervisor.list_policies()
        mode_state = store.get_state("foreman_mode", {})
        mode_state["gateway_mode"] = adapter.gateway_mode

        return 200, {
            "app": "ghost-foreman",
            "version": "0.2.0",
            "mode_state": mode_state,
            "projects": projects,
            "slots": slots,
            "questions": questions,
            "policies": policies,
            "budgets": budgets,
            "audits": audits,
            "meetings": meetings,
            "ideas": ideas,
            "news": news,
            "desktop_lease": lease_row,
            "usage": supervisor.llm.usage_summary(),
            "halt": adapter.halt.snapshot(),
            "external_runs": supervisor.external.recent(20),
            "notifications": supervisor.notifier.recent(20),
        }

    if method == "POST" and rel_path == "/questions":
        q = supervisor.receive_agent_question(
            slot_id=payload.get("slot_id", "slot-01"),
            raw_question=payload["raw_question"],
            kind=payload.get("kind", "natural_question"),
            question_id=payload.get("question_id"),
            options=payload.get("options"),
            proposes_spec_change=bool(payload.get("proposes_spec_change", False)),
            conflict_with_slot=payload.get("conflict_with_slot", ""),
        )
        return 200, q

    if method == "POST" and rel_path == "/questions/inquire":
        q = supervisor.ask_ghost_about_question(
            question_id=payload["question_id"],
            human_inquiry=payload["human_inquiry"],
            re_probe_agent=bool(payload.get("re_probe_agent", True)),
        )
        return 200, q

    if method == "POST" and rel_path == "/questions/resolve":
        q = supervisor.resolve_question_by_human(
            question_id=payload["question_id"],
            answer_text=payload["answer_text"],
            memory_mode=payload.get("memory_mode", "one_time"),
            policy_scope=payload.get("policy_scope", "project"),
            policy_title=payload.get("policy_title", ""),
            policy_keywords=payload.get("policy_keywords"),
            batch_apply_same_project=bool(payload.get("batch_apply_same_project", False)),
        )
        return 200, q

    if method == "POST" and rel_path == "/meetings":
        mtg = supervisor.run_brainstorm_meeting(
            project_id=payload.get("project_id", "proj-game"),
            topic=payload["topic"],
            participants=payload.get("participants"),
            synthesizer_harness=payload.get("synthesizer_harness", ""),
            # Only a literal true counts as the human's permission for this meeting ("yes", 1, "true" do not).
            allow_unpublished_to_gemini=payload.get("allow_unpublished_to_gemini") is True,
        )
        return 200, mtg

    if method == "POST" and rel_path == "/meetings/adopt":
        res = supervisor.adopt_meeting_option(
            meeting_id=payload["meeting_id"],
            option_id=payload["option_id"],
            target_slot_id=payload.get("target_slot_id", "slot-03"),
        )
        return 200, res

    if method == "POST" and rel_path == "/slots":
        slot = adapter.create_managed_slot(
            project_id=payload.get("project_id", "proj-game"),
            name=payload["name"],
            backend=payload.get("backend", "claude-code"),
            role=payload.get("role", "実装担当"),
            current_task=payload["current_task"],
            next_task=payload.get("next_task", ""),
            worktree_branch=payload.get("worktree_branch", ""),
        )
        return 200, slot

    if method == "GET" and rel_path == "/policies":
        return 200, {"policies": supervisor.list_policies(project_id=payload.get("project_id") or None)}

    if method == "POST" and rel_path == "/slots/report":
        # Record only: the report comes FROM the agent, so it must not be echoed back into its session.
        with store._conn() as conn:
            conn.execute(
                "UPDATE managed_slots SET waiting_reason = ?, updated_at = ? WHERE id = ? AND status != 'stopped'",
                (f"報告: {str(payload['status_message'])[:300]}", _now(), payload["slot_id"]),
            )
        return 200, adapter.get_slot(payload["slot_id"]) or {"error": "unknown slot"}

    if method == "POST" and rel_path == "/slots/send":
        res = adapter.send_message(
            slot_id=payload["slot_id"],
            message=payload["message"],
            sender=payload.get("sender", "human_via_foreman"),
            resume_work=bool(payload.get("resume_work", True)),
        )
        return 200, res

    if method == "GET" and rel_path.startswith("/slots/history"):
        slot_id = payload.get("slot_id") or (rel_path.split("?slot_id=", 1)[1] if "?slot_id=" in rel_path else "")
        return 200, adapter.get_slot_history(slot_id, limit=int(payload.get("limit", 50)))
    if method == "GET" and rel_path == "/usage":
        return 200, supervisor.llm.usage_summary()

    if method == "POST" and rel_path == "/news/summarize":
        try:
            item = supervisor.news.summarize_url(
                project_id=payload.get("project_id", "proj-foreman"),
                url=payload["url"],
                reason=payload.get("reason", ""),
                category=payload.get("category", "ニュース"),
            )
        except Exception as exc:  # fetch / safety / LLM failures are reported, not hidden
            from .news import UnsafeUrl

            code = "unsafe_url" if isinstance(exc, UnsafeUrl) else "news_failed"
            return 422, {"error": f"{type(exc).__name__}: {exc}", "code": code}
        return 200, item

    if method == "GET" and rel_path == "/meetings/harnesses":
        # AIs (Kiro Crew harnesses) a meeting participant can run on: Claude Code / Codex / Kiro ...
        listing = supervisor.meetings.available_harnesses(refresh=str(payload.get("refresh", "")) == "1")
        listing.update({"max_participants": 5, "min_participants": 2})
        return 200, listing

    if method == "GET" and rel_path == "/meetings/external-runs":
        # Record of every Claude Code / Codex run started outside Kiro Crew for meetings.
        return 200, {"runs": supervisor.external.recent(int(payload.get("limit", 30)))}

    if method == "GET" and rel_path == "/m/ping":
        # Cheap "am I signed in?" check for the phone page (the Gateway answers 401/403 before this if not).
        return 200, {"ok": True}

    if method == "POST" and rel_path == "/notify/test":
        # The human asked for a test push (the phone app's button): sent regardless of mode, and logged.
        return 200, supervisor.notifier.send_test()

    if method == "POST" and rel_path == "/stop":
        res = adapter.stop_control(
            scope=payload.get("scope", "all"),
            target_id=payload.get("target_id", ""),
        )
        if str(payload.get("scope", "")).startswith("resume"):
            res["released_questions"] = supervisor.release_held_questions()
        return 200, res

    if method == "POST" and rel_path == "/mode":
        mode_state = store.get_state("foreman_mode", {})
        new_mode = payload.get("mode", mode_state.get("mode", "away"))
        if new_mode == "sleep" and mode_state.get("mode") != "sleep":
            from datetime import datetime as _dt

            mode_state["sleep_started_at"] = _dt.now().isoformat(timespec="seconds")
        if new_mode != "sleep":
            mode_state.pop("sleep_started_at", None)
        mode_state["mode"] = new_mode
        if "quiet_until" in payload:
            mode_state["quiet_until"] = payload["quiet_until"]
        if "allow_unpublished_to_free_tier" in payload:
            # Human-owned privacy switch (Spec C): may unpublished project text be sent to the Gemini free tier?
            mode_state["allow_unpublished_to_free_tier"] = bool(payload["allow_unpublished_to_free_tier"])
        store.set_state("foreman_mode", mode_state)
        return 200, mode_state

    if method == "POST" and rel_path == "/desktop-lease":
        res = supervisor.control_desktop_lease(
            action=payload.get("action", "reclaim_for_human"),
            slot_id=payload.get("slot_id", "slot-05"),
        )
        return 200, res

    return 404, {"error": f"Unknown endpoint: {method} {path}", "code": "not_found"}


def register_routes(ctx: Any = None) -> List[ForemanRoute]:
    """Return list of route objects for Kiro Crew's `RouteRegistry.register_app_routes`."""

    def _make_handler(rel_path: str) -> Callable[[Any, Any], Awaitable[Any]]:
        async def _handler(request: Any, app_ctx: Any = None) -> Any:
            from aiohttp import web

            body = None
            if request.method == "GET":
                body = dict(request.query)
            if request.method in ("POST", "PUT", "PATCH"):
                try:
                    body = await request.json()
                except Exception:
                    body = {}
            try:
                status, data = await asyncio.to_thread(dispatch_api_request, request.method, rel_path, body)
            except EmergencyStopped as exc:
                return web.json_response({"error": str(exc), "code": "emergency_stop"}, status=409)
            except (KeyError, ValueError, TypeError) as exc:
                # Bad input or an unknown id is the caller's error, not a server fault.
                return web.json_response({"error": f"{type(exc).__name__}: {exc}", "code": "bad_request"}, status=400)
            return web.json_response(data, status=status)

        return _handler

    route_specs = [
        ("GET", "/dashboard"),
        ("POST", "/questions"),
        ("POST", "/questions/inquire"),
        ("POST", "/questions/resolve"),
        ("POST", "/meetings"),
        ("POST", "/meetings/adopt"),
        ("POST", "/slots"),
        ("GET", "/policies"),
        ("POST", "/slots/report"),
        ("POST", "/slots/send"),
        ("GET", "/slots/history"),
        ("GET", "/usage"),
        ("POST", "/news/summarize"),
        ("GET", "/meetings/harnesses"),
        ("GET", "/meetings/external-runs"),
        ("GET", "/m/ping"),
        ("POST", "/notify/test"),
        ("POST", "/stop"),
        ("POST", "/mode"),
        ("POST", "/desktop-lease"),
    ]
    routes = [ForemanRoute(method=m, path=p, handler=_make_handler(p)) for m, p in route_specs]
    routes += [ForemanRoute(method="GET", path=p, handler=_static_handler(p)) for p in _STATIC_FILES]
    return routes
