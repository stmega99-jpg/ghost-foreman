"""Standalone HTTP server for Ghost Foreman UI & API verification (`python dev_server.py`)."""

from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlparse

from backend.routes import dispatch_api_request

UI_FILE = Path(__file__).resolve().parent / "ui" / "index.html"


class ForemanHTTPHandler(BaseHTTPRequestHandler):
    def _send_json(self, status: int, data: dict) -> None:
        raw = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path in ("/", "/apps/ghost-foreman", "/index.html"):
            html = UI_FILE.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(html)))
            self.end_headers()
            self.wfile.write(html)
            return

        status, data = dispatch_api_request("GET", parsed.path)
        self._send_json(status, data)

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
    print(f"Ghost Foreman Dev Server listening on http://127.0.0.1:{port}/apps/ghost-foreman")
    server.serve_forever()


if __name__ == "__main__":
    main()
