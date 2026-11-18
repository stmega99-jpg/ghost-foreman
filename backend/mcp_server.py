"""MCP Consultation Server (`backend.mcp_server`) for external sessions.

Allows sessions started outside Ghost Foreman's Managed Slots to consult Ghost Foreman
(`foreman_ask`, `foreman_report_status`, `foreman_get_policies`) without requiring Ghost Foreman
to bypass Kiro Crew's cross-session history isolation.
"""

from __future__ import annotations

import json
import sys
from typing import Any, Dict

from .hooks import get_runtime


def handle_mcp_call(tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    store, adapter, supervisor = get_runtime()
    if tool_name == "foreman_get_policies":
        return {"policies": supervisor.list_policies(project_id=arguments.get("project_id"))}
    if tool_name == "foreman_ask":
        return supervisor.receive_agent_question(
            slot_id=arguments.get("slot_id", "slot-17"),
            raw_question=arguments["question"],
            kind="natural_question",
            options=arguments.get("options"),
            proposes_spec_change=bool(arguments.get("proposes_spec_change", False)),
        )
    if tool_name == "foreman_report_status":
        slot_id = arguments.get("slot_id", "slot-17")
        msg = arguments.get("status_message", "")
        return adapter.send_message(slot_id, f"[MCP Status Report] {msg}", sender="external_mcp_agent", resume_work=True)
    return {"error": f"Unknown tool: {tool_name}"}


def main() -> None:
    """Minimal JSON-RPC stdio loop for MCP tool invocations."""
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
            req_id = req.get("id")
            method = req.get("method", "")
            params = req.get("params", {})
            if method == "tools/list":
                res = {
                    "tools": [
                        {"name": "foreman_ask", "description": "Consult Ghost Foreman on a design/spec question"},
                        {"name": "foreman_get_policies", "description": "Fetch active project policies and selective memory"},
                        {"name": "foreman_report_status", "description": "Report task progress from an external session"},
                    ]
                }
            elif method == "tools/call":
                res = {"content": [{"type": "text", "text": json.dumps(handle_mcp_call(params.get("name", ""), params.get("arguments", {})), ensure_ascii=False)}]}
            else:
                res = {"ok": True}
            sys.stdout.write(json.dumps({"jsonrpc": "2.0", "id": req_id, "result": res}, ensure_ascii=False) + "\n")
            sys.stdout.flush()
        except Exception as exc:
            sys.stdout.write(json.dumps({"jsonrpc": "2.0", "id": None, "error": {"code": -32000, "message": str(exc)}}) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
