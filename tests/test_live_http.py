"""LiveGateway._http must survive app-token expiry (tokens live 300 s): refresh early and retry once on 401/403."""

from __future__ import annotations

import io
import json
import os
import sys
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import backend.live_gateway as lg  # noqa: E402


class FakeResp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class TokenHandling(unittest.TestCase):
    def setUp(self):
        home = Path(tempfile.mkdtemp())
        secret_dir = home / ".kiro" / "crew" / "apps" / "ghost-foreman"
        secret_dir.mkdir(parents=True)
        (secret_dir / ".app_secret").write_text("s3cret", encoding="utf-8")
        p = mock.patch.object(lg.Path, "home", return_value=home)
        p.start()
        self.addCleanup(p.stop)
        self.live = object.__new__(lg.LiveGateway)
        self.live._token, self.live._token_ts = "", 0.0

    def run_http(self, behaviour):
        issued = []

        def fake_urlopen(req, timeout=None):
            url = req.full_url if hasattr(req, "full_url") else req
            if url.endswith("/token"):
                issued.append(f"tok{len(issued) + 1}")
                return FakeResp(json.dumps({"token": issued[-1]}).encode())
            return behaviour(url, issued)

        with mock.patch.object(lg.urllib.request, "urlopen", fake_urlopen):
            return self.live._http("GET", "/api/x"), issued

    def test_403_with_a_stale_token_refreshes_once_and_succeeds(self):
        def behaviour(url, issued):
            if "token=tok1" not in url:  # only the freshly issued token is accepted
                raise urllib.error.HTTPError(url, 403, "Forbidden", {}, io.BytesIO(b"{}"))
            return FakeResp(b'{"ok": true}')

        self.live._token, self.live._token_ts = "tok0-expired", __import__("time").time()  # looks fresh, is dead
        result, issued = self.run_http(behaviour)
        self.assertEqual(result, {"ok": True})
        self.assertEqual(len(issued), 1)  # one refresh after the 403

    def test_persistent_403_is_raised_not_retried_forever(self):
        def behaviour(url, issued):
            raise urllib.error.HTTPError(url, 403, "Forbidden", {}, io.BytesIO(b"{}"))

        with self.assertRaises(urllib.error.HTTPError):
            self.run_http(behaviour)

    def test_cache_window_is_shorter_than_token_lifetime(self):
        self.assertLess(lg.TOKEN_CACHE_SECS, 300)


class StopDoesNotLeaveAutoRestart(unittest.TestCase):
    def test_queue_is_emptied_before_and_after_the_stop_call(self):
        live = object.__new__(lg.LiveGateway)
        calls = []
        queues = [[{"id": "q1"}, {"id": "q2"}], [{"id": "q3"}]]  # what is queued before the stop / appears right after

        def fake_http(method, path, body=None):
            calls.append((method, path))
            if method == "GET":
                return {"queue": queues.pop(0)}
            return {"ok": True}

        live._http = fake_http
        cancelled = live.stop_slot("gf-x")
        self.assertEqual(cancelled, 3)
        order = [(m, p.rsplit("/", 1)[-1]) for m, p in calls]
        stop_at = order.index(("POST", "stop"))
        self.assertEqual([c for c in order[:stop_at] if c[0] == "DELETE"], [("DELETE", "q1"), ("DELETE", "q2")], "queue emptied BEFORE the stop")
        self.assertEqual([c for c in order[stop_at + 1 :] if c[0] == "DELETE"], [("DELETE", "q3")], "and again AFTER it")


if __name__ == "__main__":
    unittest.main()
