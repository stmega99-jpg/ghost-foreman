"""The Kiro Crew dashboard's app SDK only lets a screen call paths the manifest declares (a path prefix match). The
screen reads and writes the app's OWN routes (/api/apps/ghost-foreman/...), so those must be declared, as every
other app does; without them the dashboard page shows "not permitted to access /api/apps/ghost-foreman/dashboard".
"""

from __future__ import annotations

import json
import os
import re
import sys
import unittest

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, ROOT)

BASE = "/api/apps/ghost-foreman"


def host_allows(declared, path):
    """The host SDK's rule (kiro_crew static bundle: eW/tW), restated: exact, prefix + '/', or a trailing '*'."""
    for entry in declared:
        e = entry.strip()
        if not e:
            continue
        if e.endswith("/*"):
            stem = e[:-2]
            if path == stem or path.startswith(stem + "/"):
                return True
        elif e.endswith("*"):
            if path.startswith(e[:-1]):
                return True
        elif path == e or path.startswith(e + "/"):
            return True
    return False


class Manifest(unittest.TestCase):
    def setUp(self):
        with open(os.path.join(ROOT, "app.json"), encoding="utf-8") as f:
            self.app = json.load(f)
        with open(os.path.join(ROOT, "ui", "dist", "index.mjs"), encoding="utf-8") as f:
            self.ui = f.read()

    def test_every_path_the_screen_calls_is_declared(self):
        declared = self.app["permissions"]["api"]
        used = {"/dashboard"} | set(re.findall(r'call\(\s*"(?:GET|POST)"\s*,\s*"(/[A-Za-z0-9_/\-]+)', self.ui))
        self.assertIn("/meetings", used)
        self.assertIn("/stop", used)
        for rel in sorted(used):
            self.assertTrue(host_allows(declared, BASE + rel), f"{BASE + rel} is not covered by permissions.api")

    def test_the_rule_would_have_caught_the_original_manifest(self):
        old = ["/api/slots", "/api/chat/slots", "/api/approvals", "/api/sessions", "/api/sessions/usage", "/api/agents", "/api/crons", "/api/status"]
        self.assertFalse(host_allows(old, BASE + "/dashboard"))
        self.assertTrue(host_allows(old + [BASE, BASE + "/*"], BASE + "/dashboard"))

    def test_only_its_own_namespace_was_added(self):
        extra = [p for p in self.app["permissions"]["api"] if p.startswith(BASE)]
        self.assertEqual(sorted(extra), [BASE, BASE + "/*"])
        self.assertFalse(host_allows(self.app["permissions"]["api"], "/api/apps/another-app/dashboard"))
        self.assertFalse(host_allows(self.app["permissions"]["api"], "/api/spawn"))


if __name__ == "__main__":
    unittest.main()
