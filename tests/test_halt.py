"""After an emergency stop NOTHING restarts work until a human resumes (and resuming replays nothing).

A recording fake stands in for the live Gateway so we can assert that no message is ever delivered while stopped.
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from backend.crew_adapter import CrewAdapter  # noqa: E402
from backend.halt import EmergencyStopped, HaltState  # noqa: E402
from backend.store import ForemanStore  # noqa: E402
from backend.supervisor import ForemanSupervisor  # noqa: E402


class FakeLive:
    """Just enough of LiveGateway; records every delivery / stop / watch."""

    def __init__(self):
        self.sent, self.stopped, self.watched, self.halt_check = [], [], [], None

    def call(self, value):
        return value

    def acquire(self, key, project_id, agent="", model=""):
        return {"live_key": key}

    def send(self, key, text):
        self.sent.append((key, text))
        return "turn"

    def history(self, key, limit=50):
        return []

    def describe(self, key):
        return {"live_key": key, "running": False, "queue_depth": 0, "message_count": 0}

    def delete(self, key):
        return None

    def stop_slot(self, key):
        self.stopped.append(key)

    def watch_reply(self, key, marker, cb, timeout=0):
        self.watched.append((key, marker))


def make():
    store = ForemanStore(db_path=os.path.join(tempfile.mkdtemp(), "h.db"))
    store.seed_defaults_if_empty()
    adapter = CrewAdapter(store)
    live = FakeLive()
    adapter.bind_live(live)
    sup = ForemanSupervisor(store, adapter)

    def boom(*a, **k):
        raise AssertionError("the judge must not be consulted while stopped")

    sup.llm.complete = boom
    a = adapter.create_managed_slot("proj-foreman", "worker-a", "kiro", "実装", "task A", live=True, send_intro=False)
    b = adapter.create_managed_slot("proj-other", "worker-b", "kiro", "実装", "task B", live=True, send_intro=False)
    live.sent.clear()
    return store, adapter, live, sup, a["id"], b["id"]


class StopThenNothingRestarts(unittest.TestCase):
    def test_stop_all_interrupts_real_sessions_and_blocks_every_delivery(self):
        store, adapter, live, sup, a, b = make()
        res = adapter.stop_control("all")
        self.assertEqual(sorted(res["live_stopped"]), sorted([a, b]))
        self.assertTrue(res["halt"]["active"])
        with self.assertRaises(EmergencyStopped):
            adapter.send_message(a, "continue please")
        with self.assertRaises(EmergencyStopped):
            adapter.create_managed_slot("proj-foreman", "new", "kiro", "x", "y", live=True, send_intro=False)
        self.assertEqual(live.sent, [], "no message may reach a real session while stopped")

    def test_question_during_stop_is_recorded_only(self):
        store, adapter, live, sup, a, b = make()
        adapter.stop_control("all")
        q = sup.receive_agent_question(a, "保存形式はJSONでよいですか？")
        self.assertEqual(q["status"], "held_emergency_stop")
        self.assertIn("再開しないでください", q["instruction"])
        self.assertEqual(live.sent, [])  # not answered, not probed
        self.assertEqual(live.watched, [])
        self.assertEqual(sup.notifier.recent(), [], "no notification while stopped")
        again = sup.receive_agent_question(a, "保存形式はJSONでよいですか？")
        self.assertEqual(again["id"], q["id"], "a repeated ask collapses into the same held ticket")

    def test_resume_releases_to_human_and_never_auto_answers(self):
        store, adapter, live, sup, a, b = make()
        adapter.stop_control("all")
        q = sup.receive_agent_question(a, "保存形式はJSONでよいですか？")
        adapter.stop_control("resume_all")
        self.assertFalse(adapter.halt.snapshot()["active"])
        released = sup.release_held_questions()
        self.assertEqual(released, [q["id"]])
        self.assertEqual(sup.get_question(q["id"])["status"], "needs_human")
        self.assertEqual(live.sent, [], "resuming must not replay or auto-answer anything by itself")
        self.assertEqual(adapter.get_slot(a)["status"], "idle", "resumed slots are idle, not 'working'")

    def test_human_answer_while_stopped_changes_nothing(self):
        store, adapter, live, sup, a, b = make()
        adapter.stop_control("all")
        q = sup.receive_agent_question(a, "どちらにしますか？")
        with self.assertRaises(EmergencyStopped):
            sup.resolve_question_by_human(q["id"], "Aにする")
        self.assertEqual(sup.get_question(q["id"])["status"], "held_emergency_stop")
        self.assertEqual(live.sent, [])

    def test_meetings_and_adoption_are_blocked_without_side_effects(self):
        store, adapter, live, sup, a, b = make()
        with store._conn() as c:
            c.execute(
                "INSERT INTO meetings (id, project_id, topic, participants_json, rounds_json, summary_json, status, created_at) VALUES ('m1','proj-foreman','t','[]','[]',?, 'awaiting_human_adoption','t')",
                ('{"options_for_human":[{"id":"o1","label":"L","detail":"D"}],"live":true}',),
            )
        adapter.stop_control("all")
        with self.assertRaises(EmergencyStopped):
            sup.run_brainstorm_meeting("proj-foreman", "topic")
        with self.assertRaises(EmergencyStopped):
            sup.adopt_meeting_option("m1", "o1", a)
        with store._conn() as c:
            status = c.execute("SELECT status FROM meetings WHERE id='m1'").fetchone()["status"]
            next_task = c.execute("SELECT next_task FROM managed_slots WHERE id=?", (a,)).fetchone()["next_task"]
        self.assertEqual(status, "awaiting_human_adoption", "a refused adoption must not change the meeting")
        self.assertNotIn("会議採用案", next_task)
        self.assertEqual(live.sent, [])

    def test_foreman_tool_auto_approval_is_off_while_stopped(self):
        store, adapter, live, sup, a, b = make()
        key = adapter.get_slot(a)["live_key"]
        self.assertFalse(live.halt_check(key))
        adapter.stop_control("slot", a)
        self.assertTrue(live.halt_check(key))
        self.assertFalse(live.halt_check(adapter.get_slot(b)["live_key"]))


class Scope(unittest.TestCase):
    def test_slot_stop_leaves_other_slots_running(self):
        store, adapter, live, sup, a, b = make()
        adapter.stop_control("slot", a)
        with self.assertRaises(EmergencyStopped):
            adapter.send_message(a, "x")
        adapter.send_message(b, "still fine", resume_work=False)
        self.assertEqual(len(live.sent), 1)

    def test_project_stop_and_scoped_resume(self):
        store, adapter, live, sup, a, b = make()
        adapter.stop_control("project", "proj-foreman")
        with self.assertRaises(EmergencyStopped):
            adapter.send_message(a, "x")
        adapter.send_message(b, "other project is fine", resume_work=False)
        adapter.stop_control("resume_project", "proj-foreman")
        adapter.send_message(a, "now allowed", resume_work=False)

    def test_resuming_one_hold_does_not_lift_another(self):
        store, adapter, live, sup, a, b = make()
        adapter.stop_control("all")
        adapter.stop_control("resume_slot", a)  # the global hold still applies
        with self.assertRaises(EmergencyStopped):
            adapter.send_message(a, "x")


class Persistence(unittest.TestCase):
    def test_hold_survives_a_restart_and_is_audited(self):
        store, adapter, live, sup, a, b = make()
        adapter.stop_control("all")
        reopened = HaltState(ForemanStore(db_path=store.db_path))  # a new process reading the same database
        self.assertTrue(reopened.snapshot()["all"])
        adapter.stop_control("resume_all")
        with store._conn() as c:
            actions = [r["action_type"] for r in c.execute("SELECT action_type FROM decisions_audit WHERE actor='human' ORDER BY created_at").fetchall()]
        self.assertIn("emergency_stop", actions)
        self.assertIn("resume_permission", actions)


if __name__ == "__main__":
    unittest.main()
