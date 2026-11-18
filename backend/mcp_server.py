"""Ghost Foreman MCP consultation server (stdio, spawned per agent session).

Runs as a separate process, so it never touches Ghost Foreman's database directly. Every tool call is
forwarded over HTTP to the app routes inside the running Kiro Crew Gateway
(``/api/apps/ghost-foreman/...``), authenticated with the app secret -> short-lived token exchange.

Tools:
- foreman_ask: ask for a decision. Returns the Foreman's answer, or an escalation ticket.
- foreman_get_policies: list active project rules.
- foreman_report_status: report progress.
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, Optional

APP_NAME = "ghost-foreman"
SERVER_VERSION = "0.3.0"
HTTP_TIMEOUT = 30

TOOLS = [
    {
        "name": "foreman_ask",
        "description": (
            "Ask the Ghost Foreman (site supervisor) for a decision instead of waiting for the human. "
            "Use it for design/spec questions and choices. The Foreman answers from the project's confirmed "
            "rules when it can, otherwise it escalates to the human and delivers the answer to your session later."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "slot_id": {"type": "string", "description": "Your Ghost Foreman slot id (given in your first message)."},
                "question": {"type": "string", "description": "The question, with enough background to decide."},
                "options": {
                    "type": "array",
                    "description": "Optional candidate choices.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "string"},
                            "label": {"type": "string"},
                            "impact": {"type": "string"},
                        },
                    },
                },
                "proposes_spec_change": {"type": "boolean", "description": "True if you propose changing a confirmed spec."},
            },
            "required": ["slot_id", "question"],
        },
    },
    {
        "name": "foreman_get_policies",
        "description": "List the active confirmed rules (policies) that apply to a project.",
        "inputSchema": {
            "type": "object",
            "properties": {"project_id": {"type": "string"}},
        },
    },
    {
        "name": "foreman_report_status",
        "description": "Report task progress or completion to the Ghost Foreman.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "slot_id": {"type": "string"},
                "status_message": {"type": "string"},
            },
            "required": ["slot_id", "status_message"],
        },
    },
]


class GatewayClient:
    """Minimal authenticated client for this app's routes on the local Gateway."""

    def __init__(self) -> None:
        port = os.environ.get("KIROCREW_PORT", "5476")
        self.base = os.environ.get("KIROCREW_GATEWAY_URL", f"http://127.0.0.1:{port}").rstrip("/")
        self._token: Optional[str] = None
        self._token_ts = 0.0

    def _secret(self) -> str:
        path = Path.home() / ".kiro" / "crew" / "apps" / APP_NAME / ".app_secret"
        return path.read_text(encoding="utf-8").strip()

    def _auth(self, force: bool = False) -> str:
        if self._token and not force and time.time() - self._token_ts < 600:
            return self._token
        req = urllib.request.Request(
            f"{self.base}/api/apps/{APP_NAME}/token",
            data=b"{}",
            headers={"Content-Type": "application/json", "X-App-Secret": self._secret()},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as resp:
            self._token = json.loads(resp.read().decode("utf-8"))["token"]
        self._token_ts = time.time()
        return self._token

    def request(self, method: str, rel_path: str, body: Optional[Dict[str, Any]] = None, query: Optional[Dict[str, str]] = None) -> Any:
        for attempt in (0, 1):
            params = dict(query or {})
            params["token"] = self._auth(force=attempt == 1)
            url = f"{self.base}/api/apps/{APP_NAME}{rel_path}?{urllib.parse.urlencode(params)}"
            data = json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None
            req = urllib.request.Request(url, data=data, method=method, headers={"Content-Type": "application/json; charset=utf-8"})
            try:
                with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as resp:
                    return json.loads(resp.read().decode("utf-8"))
            except urllib.error.HTTPError as exc:
                if exc.code in (401, 403) and attempt == 0:
                    continue
                raise RuntimeError(f"Ghost Foreman API {exc.code}: {exc.read().decode('utf-8', 'replace')[:300]}") from exc
        raise RuntimeError("unreachable")


_CLIENT: Optional[GatewayClient] = None


def _client() -> GatewayClient:
    global _CLIENT
    if _CLIENT is None:
        _CLIENT = GatewayClient()
    return _CLIENT


def handle_mcp_call(tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    c = _client()
    if tool_name == "foreman_get_policies":
        q = {"project_id": arguments["project_id"]} if arguments.get("project_id") else None
        return c.request("GET", "/policies", query=q)
    if tool_name == "foreman_ask":
        return c.request(
            "POST",
            "/questions",
            {
                "slot_id": arguments["slot_id"],
                "raw_question": arguments["question"],
                "kind": "natural_question",
                "options": arguments.get("options"),
                "proposes_spec_change": bool(arguments.get("proposes_spec_change", False)),
            },
        )
    if tool_name == "foreman_report_status":
        return c.request("POST", "/slots/report", {"slot_id": arguments["slot_id"], "status_message": arguments["status_message"]})
    raise ValueError(f"Unknown tool: {tool_name}")


def _reply(req_id: Any, result: Any = None, error: Optional[Dict[str, Any]] = None) -> None:
    msg: Dict[str, Any] = {"jsonrpc": "2.0", "id": req_id}
    if error is not None:
        msg["error"] = error
    else:
        msg["result"] = result
    sys.stdout.write(json.dumps(msg, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def handle_request(req: Dict[str, Any]) -> None:
    req_id = req.get("id")
    method = req.get("method", "")
    params = req.get("params") or {}
    if req_id is None:  # notification (e.g. notifications/initialized): no response
        return
    if method == "initialize":
        _reply(
            req_id,
            {
                "protocolVersion": params.get("protocolVersion", "2024-11-05"),
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "ghost-foreman-mcp", "version": SERVER_VERSION},
            },
        )
    elif method == "ping":
        _reply(req_id, {})
    elif method == "tools/list":
        _reply(req_id, {"tools": TOOLS})
    elif method == "tools/call":
        try:
            out = handle_mcp_call(params.get("name", ""), params.get("arguments") or {})
            _reply(req_id, {"content": [{"type": "text", "text": json.dumps(out, ensure_ascii=False)}], "isError": False})
        except Exception as exc:  # tool failure is reported in-band so the agent can react
            _reply(req_id, {"content": [{"type": "text", "text": f"Ghost Foreman error: {exc}"}], "isError": True})
    else:
        _reply(req_id, error={"code": -32601, "message": f"Method not found: {method}"})


def main() -> None:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            handle_request(json.loads(line))
        except Exception as exc:  # malformed input must not kill the server
            sys.stderr.write(f"ghost-foreman-mcp: {exc}\n")
            sys.stderr.flush()


if __name__ == "__main__":
    main()
