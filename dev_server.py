"""Standalone HTTP server for Ghost Foreman (`python dev_server.py`).

It serves the demo page (``demo/index.html``): the same screen as the real app, running on made-up sample data in
the browser (``demo/engine.mjs``). The page makes no requests of its own, so this server only hands out static files.
The Python backend with simulated slots is still reachable under ``/api/...`` for API checks (it is not used by the demo).
"""
from __future__ import annotations
import json
import mimetypes
import os
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

from backend.routes import dispatch_api_request

ROOT = Path(__file__).resolve().parent
# Only these folders are served as files (the demo page and the screen code and React it loads).
STATIC_DIRS = ("demo", "ui")
DEMO_PAGE = "/demo/index.html"
_TYPES = {".mjs": "text/javascript; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".html": "text/html; charset=utf-8",
          ".json": "application/json; charset=utf-8", ".png": "image/png"}


def resolve_static(url_path: str) -> Path | None:
    """The file for *url_path* if it is inside demo/ or ui/ (no ``..`` escapes), else None."""
    rel = unquote(url_path).lstrip("/")
    if not rel or rel.split("/")[0] not in STATIC_DIRS:
        return None
    target = (ROOT / rel).resolve()
    allowed = [(ROOT / d).resolve() for d in STATIC_DIRS]
    if not any(target == a or a in target.parents for a in allowed) or not target.is_file():
        return None
    return target


class ForemanHTTPHandler(BaseHTTPRequestHandler):
    def _send_json(self, status: int, data: dict) -> None:
        raw = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _send_file(self, path: Path) -> None:
        raw = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", _TYPES.get(path.suffix) or mimetypes.guess_type(str(path))[0] or "application/octet-stream")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path in ("/", "/apps/ghost-foreman", "/index.html"):
            self.send_response(302)
            self.send_header("Location", DEMO_PAGE)
            self.end_headers()
            return
        static = resolve_static(parsed.path)
        if static is not None:
            self._send_file(static)
            return
        if parsed.path.startswith("/api/"):
            status, data = dispatch_api_request("GET", parsed.path)
            self._send_json(status, data)
            return
        self._send_json(404, {"error": f"Not found: {parsed.path}", "code": "not_found"})

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        length = int(self.headers.get("Content-Length", "0"))
        raw_body = self.rfile.read(length).decode("utf-8") if length > 0 else "{}"
        try:
            body = json.loads(raw_body) if raw_body else {}
        except Exception:
            body = {}
        status, data = dispatch_api_request("POST", parsed.path, body)
        self._send_json(status, data)

    def log_message(self, format: str, *args: object) -> None:
        return


def main() -> None:
    port = int(os.environ.get("PORT", "8765"))
    server = HTTPServer(("127.0.0.1", port), ForemanHTTPHandler)
    print(f"Ghost Foreman demo listening on http://127.0.0.1:{port}{DEMO_PAGE}")
    server.serve_forever()


if __name__ == "__main__":
    main()