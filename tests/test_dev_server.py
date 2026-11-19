"""dev_server.py hands out the demo page and its files, and nothing else from the disk."""
from __future__ import annotations
import http.client
import os
import sys
import threading
import unittest
from http.server import HTTPServer

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import dev_server  # noqa: E402


class DevServer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = HTTPServer(("127.0.0.1", 0), dev_server.ForemanHTTPHandler)
        cls.port = cls.server.server_address[1]
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def get(self, path):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        conn.request("GET", path)
        res = conn.getresponse()
        body = res.read()
        conn.close()
        return res.status, dict(res.getheaders()), body

    def test_the_root_goes_to_the_demo_page(self):
        for p in ("/", "/apps/ghost-foreman", "/index.html"):
            status, headers, _ = self.get(p)
            self.assertEqual((status, headers.get("Location")), (302, "/demo/index.html"), p)

    def test_the_demo_page_and_its_files_are_served(self):
        status, headers, body = self.get("/demo/index.html")
        self.assertEqual(status, 200)
        self.assertIn("connect-src 'none'", body.decode("utf-8"))
        for p, kind in (("/demo/engine.mjs", "javascript"), ("/demo/sdk.mjs", "javascript"), ("/ui/dist/index.mjs", "javascript"), ("/ui/m/vendor/react.mjs", "javascript")):
            status, headers, _ = self.get(p)
            self.assertEqual(status, 200, p)
            self.assertIn(kind, headers.get("Content-Type", ""), p)

    def test_other_files_are_not_served(self):
        for p in ("/backend/store.py", "/data", "/README.md", "/dev_server.py", "/.git/config", "/demo/../README.md", "/demo/%2e%2e/README.md", "/ui/..%2fREADME.md", "/demo/nope.js"):
            status, _, _ = self.get(p)
            self.assertEqual(status, 404, p)

    def test_the_simulated_api_still_answers(self):
        status, _, body = self.get("/api/apps/ghost-foreman/dashboard")
        self.assertEqual(status, 200)
        self.assertIn(b"simulated_gateway", body)


if __name__ == "__main__":
    unittest.main()