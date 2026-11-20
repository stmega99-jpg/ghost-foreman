"""The person can add, rename, archive and re-open their own projects. Nothing is ever deleted."""
from __future__ import annotations
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from backend import routes  # noqa: E402
from backend.store import ForemanStore  # noqa: E402


class Projects(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = ForemanStore(os.path.join(self.tmp.name, "gf.db"))
        self.store.seed_defaults_if_empty()

    def api(self, path, body):
        with mock.patch("backend.hooks.get_runtime", return_value=(self.store, None, None)):
            return routes.dispatch_api_request("POST", path, body)

    def names(self):
        with self.store._conn() as conn:
            return {r["name"]: r["status"] for r in conn.execute("SELECT name, status FROM projects")}

    def test_a_project_can_be_added_with_a_generated_id(self):
        status, p = self.api("/projects", {"name": "  家計簿アプリ ", "description": "毎月の支出を記録する"})
        self.assertEqual(status, 200)
        self.assertEqual((p["name"], p["description"], p["status"]), ("家計簿アプリ", "毎月の支出を記録する", "active"))
        self.assertRegex(p["id"], r"^proj-[0-9a-f]{8}$")
        self.assertEqual(self.names()["家計簿アプリ"], "active")

    def test_the_caller_cannot_choose_the_id(self):
        _, p = self.api("/projects", {"name": "YouTubeチャンネル運営", "id": "proj-game"})
        self.assertNotEqual(p["id"], "proj-game")

    def test_bad_names_are_refused(self):
        for body in ({}, {"name": ""}, {"name": "   "}, {"name": "x" * 81}, {"name": "ok", "description": "y" * 301}):
            with self.assertRaises(ValueError, msg=str(body)[:40]):
                self.api("/projects", body)

    def test_two_active_projects_cannot_share_a_name(self):
        self.api("/projects", {"name": "オンラインショップ開業"})
        with self.assertRaises(ValueError):
            self.api("/projects", {"name": "オンラインショップ開業"})

    def test_rename_and_describe(self):
        _, p = self.api("/projects", {"name": "恋愛小説"})
        _, q = self.api("/projects/update", {"project_id": p["id"], "name": "恋愛小説の執筆", "description": "長編"})
        self.assertEqual((q["id"], q["name"], q["description"]), (p["id"], "恋愛小説の執筆", "長編"))
        _, r = self.api("/projects/update", {"project_id": p["id"], "description": "短編"})
        self.assertEqual((r["name"], r["description"]), ("恋愛小説の執筆", "短編"), "fields not given are kept")

    def test_archive_and_reopen_keep_everything(self):
        with self.store._conn() as conn:
            before = conn.execute("SELECT COUNT(*) c FROM policies WHERE project_id = 'proj-game'").fetchone()["c"]
        _, p = self.api("/projects/update", {"project_id": "proj-game", "status": "archived"})
        self.assertEqual(p["status"], "archived")
        with self.store._conn() as conn:
            after = conn.execute("SELECT COUNT(*) c FROM policies WHERE project_id = 'proj-game'").fetchone()["c"]
            still_there = conn.execute("SELECT COUNT(*) c FROM projects WHERE id = 'proj-game'").fetchone()["c"]
        self.assertEqual((after, still_there), (before, 1), "archiving deletes nothing")
        _, p = self.api("/projects/update", {"project_id": "proj-game", "status": "active"})
        self.assertEqual(p["status"], "active")

    def test_bad_updates_are_refused(self):
        for body in ({"project_id": "proj-nope", "name": "x"}, {"project_id": "proj-game", "status": "deleted"},
                     {"project_id": "proj-game", "name": ""}):
            with self.assertRaises(ValueError, msg=str(body)):
                self.api("/projects/update", body)

    def test_reopening_cannot_create_a_name_clash(self):
        _, a = self.api("/projects", {"name": "家計簿アプリ"})
        self.api("/projects/update", {"project_id": a["id"], "status": "archived"})
        self.api("/projects", {"name": "家計簿アプリ"})  # allowed: the first one is archived
        with self.assertRaises(ValueError):
            self.api("/projects/update", {"project_id": a["id"], "status": "active"})

    def test_there_is_no_delete_route(self):
        paths = {r.path for r in routes.register_routes()}
        self.assertIn("/projects", paths)
        self.assertIn("/projects/update", paths)
        self.assertFalse(any("delete" in p for p in paths))


if __name__ == "__main__":
    unittest.main()
