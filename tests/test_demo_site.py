"""The published demo site contains only what the demo page needs, and works on its own."""
from __future__ import annotations
import os
import re
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))
import build_demo_site  # noqa: E402

EXPECTED = [".nojekyll", "demo/engine.mjs", "demo/index.html", "demo/sdk.mjs", "index.html", "ui/dist/index.mjs", "ui/m/vendor/react.mjs"]


class DemoSite(unittest.TestCase):
    def build(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        out = Path(tmp.name) / "site"
        return out, build_demo_site.build(out)

    def test_only_the_listed_files_are_published(self):
        _, files = self.build()
        self.assertEqual(files, EXPECTED)

    def test_nothing_private_can_be_published(self):
        _, files = self.build()
        for name in files:
            self.assertFalse(re.match(r"(backend|data|tests|agents|skills|docs|scripts|\.kiro|\.github)/", name), name)
            self.assertFalse(name.endswith((".py", ".db", ".md", ".json", ".ps1")), name)

    def test_the_demo_page_finds_everything_it_loads_inside_the_site(self):
        out, files = self.build()
        page = (out / "demo" / "index.html").read_text(encoding="utf-8")
        wanted = re.findall(r'"(?:react|react-dom/client|@kirocrew/app-sdk)":\s*"([^"]+)"', page) + re.findall(r'import\("(\.[^"]+)"\)', page)
        self.assertGreaterEqual(len(wanted), 4)
        for rel in wanted:
            self.assertTrue(rel.startswith("."), f"an absolute path would break a project site: {rel}")
            target = os.path.normpath(os.path.join("demo", rel)).replace("\\", "/")
            self.assertIn(target, files, rel)
        sdk = (out / "demo" / "sdk.mjs").read_text(encoding="utf-8")
        for rel in re.findall(r'from "(\./[^"]+)"', sdk):
            self.assertIn(os.path.normpath(os.path.join("demo", rel)).replace("\\", "/"), files, rel)

    def test_the_page_cannot_open_connections(self):
        out, _ = self.build()
        self.assertIn("connect-src 'none'", (out / "demo" / "index.html").read_text(encoding="utf-8"))

    def test_the_workflow_uploads_only_the_built_folder(self):
        wf = (Path(__file__).resolve().parent.parent / ".github" / "workflows" / "pages.yml").read_text(encoding="utf-8")
        self.assertIn("python scripts/build_demo_site.py _site", wf)
        self.assertIn("path: _site", wf)
        self.assertNotRegex(wf, r"path:\s*(\.|/)\s*$")


if __name__ == "__main__":
    unittest.main()