"""Notification policy tests (Spec F): resident / away / sleep, de-duplication, digest, failure isolation.

The host bus is replaced by a recording fake; delivery to a real iPhone is verified manually (see the PR).
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from backend.notifier import Notifier  # noqa: E402
from backend.store import ForemanStore  # noqa: E402


class FakeLive:
    def __init__(self, fail=False):
        self.sent, self.fail = [], fail

    def _http(self, method, path, body=None):
        if self.fail:
            raise RuntimeError("bus unavailable")
        self.sent.append((method, path, body))
        return {"ok": True}


class FakeAdapter:
    def __init__(self, live):
        self.live = live


class Clock:
    def __init__(self, now):
        self.now = now

    def __call__(self):
        return self.now


def make(mode="away", live=True, fail=False, now=datetime(2026, 11, 18, 22, 0, 0), **extra):
    store = ForemanStore(db_path=os.path.join(tempfile.mkdtemp(), "n.db"))
    store.seed_defaults_if_empty()
    state = store.get_state("foreman_mode", {})
    state.update({"mode": mode, "quiet_until": "07:30"})
    state.update(extra)
    store.set_state("foreman_mode", state)
    fake = FakeLive(fail=fail) if live else None
    clock = Clock(now)
    return Notifier(store, FakeAdapter(fake), clock), store, fake, clock


def add_question(store, qid="q-1", status="needs_human", project="proj-foreman", text="保存形式はどちらにしますか？"):
    with store._conn() as c:
        c.execute(
            "INSERT INTO questions (id, project_id, slot_id, kind, raw_question, status, created_at, updated_at) VALUES (?, ?, 'slot-01', 'natural_question', ?, ?, 't', 't')",
            (qid, project, text, status),
        )


def deliveries(store):
    with store._conn() as c:
        return [(r["question_id"], r["delivery"]) for r in c.execute("SELECT * FROM notifications_log ORDER BY id").fetchall()]


class AwayMode(unittest.TestCase):
    def test_pushes_once_with_group_key_and_deep_link(self):
        n, store, live, _ = make("away")
        add_question(store)
        self.assertEqual(n.decision_needed("q-1"), "sent")
        _, path, body = live.sent[0]
        self.assertEqual(path, "/api/notifications/push")
        self.assertEqual((body["channel"], body["priority"], body["group_key"]), ("decision-needed", "default", "gf-proj-foreman"))
        self.assertIn("q=q-1", body["url"])
        self.assertEqual(n.decision_needed("q-1"), "duplicate_suppressed")
        self.assertEqual(len(live.sent), 1, "the same question must not notify twice")

    def test_spec_violation_is_critical(self):
        n, store, live, _ = make("away")
        add_question(store, status="held_spec_violation")
        n.decision_needed("q-1")
        self.assertEqual(live.sent[0][2]["priority"], "critical")

    def test_resolved_or_unknown_questions_do_not_notify(self):
        n, store, live, _ = make("away")
        add_question(store, status="auto_resolved")
        self.assertEqual(n.decision_needed("q-1"), "not_needed")
        self.assertEqual(n.decision_needed("nope"), "not_needed")
        self.assertEqual(live.sent, [])

    def test_failure_is_logged_not_raised(self):
        n, store, _, _ = make("away", fail=True)
        add_question(store)
        self.assertEqual(n.decision_needed("q-1"), "failed")
        self.assertEqual(deliveries(store), [("q-1", "failed")])

    def test_simulated_mode_does_not_pretend_to_send(self):
        n, store, _, _ = make("away", live=False)
        add_question(store)
        self.assertEqual(n.decision_needed("q-1"), "not_sent")


class ResidentMode(unittest.TestCase):
    def test_no_interruption_but_recorded(self):
        n, store, live, _ = make("resident")
        add_question(store)
        self.assertEqual(n.decision_needed("q-1"), "held_resident")
        self.assertEqual(live.sent, [])
        self.assertEqual(deliveries(store), [("q-1", "held_resident")])


class SleepMode(unittest.TestCase):
    def test_hold_overnight_then_one_digest(self):
        n, store, live, clock = make("sleep", sleep_started_at="2026-11-18T22:00:00")
        add_question(store, "q-1")
        add_question(store, "q-2", text="別の確認")
        self.assertEqual(n.decision_needed("q-1"), "held")
        self.assertEqual(n.decision_needed("q-2"), "held")
        self.assertEqual(live.sent, [])
        clock.now = datetime(2026, 11, 19, 3, 0, 0)
        self.assertIsNone(n.send_digest_if_due(), "not due before quiet_until")
        clock.now = datetime(2026, 11, 19, 7, 30, 1)
        self.assertEqual(n.send_digest_if_due(), 2)
        self.assertEqual(len(live.sent), 1)
        self.assertEqual(live.sent[0][2]["channel"], "digest")
        self.assertIn("2件", live.sent[0][2]["body"])
        self.assertEqual(n.send_digest_if_due(), 0, "the digest is sent once")
        self.assertEqual(len(live.sent), 1)

    def test_resolved_items_are_not_in_the_digest(self):
        n, store, live, clock = make("sleep", sleep_started_at="2026-11-18T22:00:00")
        add_question(store, "q-1")
        n.decision_needed("q-1")
        with store._conn() as c:
            c.execute("UPDATE questions SET status = 'human_resolved' WHERE id = 'q-1'")
        clock.now = datetime(2026, 11, 19, 8, 0, 0)
        self.assertEqual(n.send_digest_if_due(), 0)
        self.assertEqual(live.sent, [])

    def test_after_the_window_new_questions_are_pushed_again(self):
        n, store, live, clock = make("sleep", sleep_started_at="2026-11-18T22:00:00", now=datetime(2026, 11, 19, 9, 0, 0))
        add_question(store, "q-9")
        self.assertEqual(n.decision_needed("q-9"), "sent")


if __name__ == "__main__":
    unittest.main()
