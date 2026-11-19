"""AI meeting room with DIFFERENT AIs: Kiro in a Kiro Crew slot, Claude Code / Codex outside Kiro Crew.

A fake Gateway answers the Kiro slot and a fake external runner answers for the CLIs, so the whole three-round flow
runs in a unit test. The tests prove which runtime each participant used, that unavailable AIs are refused before
anything starts, that a participant that cannot answer stops the meeting, and that an emergency stop cancels both kinds.
"""

from __future__ import annotations

import json
import os
import re
import sys
import tempfile
import threading
import time
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from backend import meeting as meeting_mod  # noqa: E402
from backend.crew_adapter import CrewAdapter  # noqa: E402
from backend.meeting import MEETING_AGENT, MeetingEngine  # noqa: E402
from backend.store import ForemanStore  # noqa: E402


def answer_for(prompt: str, who: str) -> str:
    if "参加確認" in prompt or "participation check" in prompt:
        return f"{who} です。準備OK"
    if "独立して具体案" in prompt:
        return json.dumps({"title": f"{who}の案", "proposal": f"{who} proposal", "pros": ["p"], "risks": ["r"]})
    if "他案の問題点" in prompt:
        return json.dumps({"critique": f"{who} critique", "improved_proposal": f"{who} improved"})
    return json.dumps({"consensus": "合意", "conflict_points": "対立", "unresolved": "未決", "options": [{"id": "opt1", "label": "案1", "detail": "内容"}]})


class FakeLive:
    """Kiro Crew slots for Kiro participants."""

    def __init__(self, hold=False):
        self.agent_of, self.last, self.halt_check, self.hold, self.deleted = {}, {}, None, hold, []

    def call(self, v):
        return v

    def acquire(self, key, project_id, agent="", model=""):
        self.agent_of[key] = agent
        return {"live_key": key}

    def send(self, key, text):
        self.last[key] = text
        return "turn"

    def history(self, key, limit=50):
        return []

    def describe(self, key):
        return {"live_key": key, "running": False, "queue_depth": 0, "message_count": 0}

    def delete(self, key):
        self.deleted.append(key)

    def stop_slot(self, key):
        return 0

    def watch_reply(self, key, marker, cb, timeout=0):
        if self.hold:
            return
        threading.Thread(target=cb, args=(answer_for(self.last[key], "kiro"), "")).start()


class FakeExternal:
    """Claude Code / Codex outside Kiro Crew."""

    def __init__(self, unavailable=(), broken=(), hold=False):
        self.calls, self.killed, self.unavailable, self.broken, self.hold = [], [], set(unavailable), set(broken), hold
        self._stop = threading.Event()

    def status(self, h, refresh=False):
        ok = h not in self.unavailable
        return {"id": h, "label": {"claude": "Claude Code", "codex": "Codex"}[h], "runtime": "external_cli", "available": ok,
                "reason": "" if ok else "Claude Code にログインしていません"}

    def run(self, h, prompt, meeting_id="", project_id="", tag="", timeout=0):
        self.calls.append((h, tag))
        if self.hold:
            self._stop.wait(5)
            return {"reply": None, "error": "緊急停止により終了しました", "ran_on": h, "run_id": "r", "model": ""}
        if h in self.broken:
            return {"reply": None, "error": "Not logged in", "ran_on": h, "run_id": "r", "model": ""}
        return {"reply": answer_for(prompt, h), "error": "", "ran_on": h, "run_id": f"ext-{len(self.calls)}", "model": f"{h}-model"}

    def kill_all(self, project_id=None):
        self.killed.append(project_id)
        self._stop.set()
        return ["r"]


def make(live=None, external=None):
    store = ForemanStore(db_path=os.path.join(tempfile.mkdtemp(), "m.db"))
    store.seed_defaults_if_empty()
    adapter = CrewAdapter(store)
    live = live or FakeLive()
    adapter.bind_live(live)
    external = external or FakeExternal()
    adapter.stop_callbacks.append(lambda scope, target: external.kill_all(None if scope == "all" else target))
    return store, adapter, live, external, MeetingEngine(store, adapter, external=external)


def wait(engine, mid, secs=20):
    for t in threading.enumerate():
        if t.name == f"meeting-{mid}":
            t.join(secs)
    return engine.get(mid)


PARTS = [
    {"perspective": "設計の視点", "harness": "claude"},
    {"perspective": "実装工数の視点", "harness": "codex"},
    {"perspective": "プレイヤー体験の視点", "harness": "kiro"},
]


class Meeting(unittest.TestCase):
    def test_three_different_ais_take_part_and_where_they_ran_is_recorded(self):
        store, adapter, live, ext, engine = make()
        m = wait(engine, engine.start("proj-foreman", "議題", PARTS, synthesizer_harness="kiro")["id"])
        self.assertEqual(m["status"], "awaiting_human_adoption", m["summary"].get("note"))
        self.assertEqual(sorted(ext.calls), sorted([("claude", "pre"), ("codex", "pre"), ("claude", "r1"), ("codex", "r1"), ("claude", "r2"), ("codex", "r2")]))
        self.assertEqual(sorted(live.agent_of.values()), [MEETING_AGENT, MEETING_AGENT], "Kiro participant + organiser use the tool-less agent")
        detail = m["summary"]["participants_detail"]
        self.assertEqual([(p["harness"], p["runtime"], p["ran_on"], p["verified"]) for p in detail],
                         [("claude", "external_cli", "claude", True), ("codex", "external_cli", "codex", True), ("kiro", "kiro_crew", "kiro", True)])
        self.assertEqual([p["runtime_label"] for p in detail], ["Kiro Crew 外で実行", "Kiro Crew 外で実行", "Kiro Crew で実行"])
        self.assertTrue(m["summary"]["outside_kiro_crew"])
        self.assertIn("［Kiro Crew 外で実行・claude-model］", json.dumps(m["rounds"][0], ensure_ascii=False))
        self.assertIn("codex proposal", json.dumps(m["rounds"][1], ensure_ascii=False))
        self.assertEqual(m["summary"]["consensus"], "合意")
        self.assertEqual(len(live.deleted), 2, "Kiro meeting slots are removed afterwards")

    def test_unavailable_ai_is_refused_before_anything_starts(self):
        store, adapter, live, ext, engine = make(external=FakeExternal(unavailable={"claude"}))
        with self.assertRaises(ValueError) as ctx:
            engine.start("proj-foreman", "議題", PARTS)
        self.assertIn("ログインしていません", str(ctx.exception))
        self.assertEqual(ext.calls, [])
        self.assertEqual(live.agent_of, {})

    def test_a_participant_that_cannot_answer_stops_the_meeting_after_the_check(self):
        store, adapter, live, ext, engine = make(external=FakeExternal(broken={"codex"}))
        m = wait(engine, engine.start("proj-foreman", "議題", PARTS)["id"])
        self.assertEqual(m["status"], "failed")
        self.assertIn("参加できないAI", m["summary"]["note"])
        self.assertEqual(len(m["rounds"]), 1, "no idea round")
        self.assertNotIn(("claude", "r1"), ext.calls)
        self.assertEqual(len(live.deleted), 2, "slots cleaned up")

    def test_emergency_stop_cancels_kiro_and_outside_participants(self):
        ext = FakeExternal(hold=True)
        store, adapter, live, ext, engine = make(live=FakeLive(hold=True), external=ext)
        mid = engine.start("proj-foreman", "議題", PARTS)["id"]
        for _ in range(300):
            if len(ext.calls) >= 2:
                break
            time.sleep(0.01)
        res = adapter.stop_control("all")
        m = wait(engine, mid)
        self.assertEqual(m["status"], "failed")
        self.assertIn("中止", m["summary"]["note"])
        self.assertIn(None, ext.killed)
        self.assertIn("stopped_outside_kiro_crew", res)
        with self.assertRaises(Exception):
            engine.start("proj-foreman", "after stop", PARTS)

    def test_harness_list_says_where_each_ai_runs(self):
        store, adapter, live, ext, engine = make(external=FakeExternal(unavailable={"codex"}))
        rows = {r["id"]: r for r in engine.available_harnesses()["harnesses"]}
        self.assertEqual((rows["kiro"]["runtime_label"], rows["kiro"]["available"]), ("Kiro Crew で実行", True))
        self.assertEqual((rows["claude"]["runtime_label"], rows["claude"]["available"]), ("Kiro Crew 外で実行", True))
        self.assertFalse(rows["codex"]["available"])

    def test_participant_validation(self):
        self.assertEqual(MeetingEngine.normalize_participants(["a", "b"]), [{"perspective": "a", "harness": "kiro"}, {"perspective": "b", "harness": "kiro"}])
        self.assertEqual(MeetingEngine.normalize_participants([{"perspective": "a", "harness": "kas"}, "b"])[0]["harness"], "kiro")
        for bad in (["only one"], [str(i) for i in range(6)], [{"perspective": "a", "harness": "grok"}, "b"], [{"perspective": "a", "harness": "../x"}, "b"]):
            with self.assertRaises(ValueError):
                MeetingEngine.normalize_participants(bad)

    def test_leftover_meeting_slots_are_removed_after_a_restart(self):
        store, adapter, live, ext, engine = make()
        s = adapter.create_managed_slot("proj-foreman", "会議A", "kiro", "会議参加者", "t", live=True, send_intro=False, agent=MEETING_AGENT)
        engine.recover_interrupted()
        self.assertIsNone(adapter.get_slot(s["id"]))


class SlotKeys(unittest.TestCase):
    def test_a_reused_slot_id_gets_a_new_gateway_key(self):
        store, adapter, live, ext, engine = make()
        first = adapter.create_managed_slot("proj-foreman", "会議A", "kiro", "会議参加者", "t", live=True, send_intro=False)
        adapter.retire_slot(first["id"])
        second = adapter.create_managed_slot("proj-foreman", "会議A", "kiro", "会議参加者", "t", live=True, send_intro=False)
        self.assertEqual(first["id"], second["id"], "the visible slot id is reused")
        self.assertNotEqual(first["live_key"], second["live_key"], "but the Gateway never resumes the old session")


class Language(unittest.TestCase):
    """The screen's language is passed to the meeting, so the AIs answer in it (the program's own keys stay the same)."""

    def run_meeting(self, language):
        store, adapter, live, ext, engine = make()
        sent = []
        real_run, real_send = ext.run, live.send
        ext.run = lambda h, prompt, **kw: (sent.append(prompt), real_run(h, prompt, **kw))[1]
        live.send = lambda key, text: (sent.append(text), real_send(key, text))[1]
        mid = engine.start("proj-foreman", "議題", PARTS, synthesizer_harness="kiro", **({} if language is None else {"language": language}))["id"]
        m = wait(engine, mid)
        return m, sent, engine

    def test_an_english_meeting_asks_every_ai_in_every_round_to_answer_in_english(self):
        m, sent, engine = self.run_meeting("en")
        self.assertEqual(m["status"], "awaiting_human_adoption", m["summary"].get("note"))
        self.assertEqual(m["summary"]["language"], "en")
        self.assertGreaterEqual(len(sent), 10, "participation check, ideas, critique and the summary, for every AI")
        self.assertTrue(all(p.endswith(meeting_mod.ENGLISH_SUFFIX) or meeting_mod.ENGLISH_SUFFIX in p for p in sent))
        checks = [p for p in sent if "participation check" in p]
        self.assertTrue(checks, "the participation check is asked in English")
        self.assertFalse(any(re.search(r"[\u3040-\u30ff\u4e00-\u9fff]", p) for p in checks), "no Japanese in the English check")
        self.assertEqual(engine._language, {}, "nothing is kept after the meeting")

    def test_a_japanese_meeting_is_unchanged(self):
        for language in ("ja", None, "fr", "", "EN ", 1):
            m, sent, engine = self.run_meeting(language)
            if str(language).strip().lower() == "en":
                self.assertEqual(m["summary"]["language"], "en")
                continue
            self.assertEqual(m["summary"]["language"], "ja", language)
            self.assertFalse(any("in English" in p for p in sent), language)


class MeetingAgent(unittest.TestCase):
    def test_meeting_agent_definition_has_no_tools(self):
        root = os.path.join(os.path.dirname(__file__), "..")
        spec = json.load(open(os.path.join(root, "agents", "meeting-participant.json"), encoding="utf-8"))
        app = json.load(open(os.path.join(root, "app.json"), encoding="utf-8"))
        # Kiro Crew starts a Kiro session only after its guide and mate servers advertise a tool,
        # so the participant sees exactly one read-only tool on each (owner's decision, option A).
        # Neither is in allowedTools, so a call still waits for the human's approval.
        self.assertEqual(sorted(spec["tools"]), ["@kirocrew-guide/search_docs", "@kirocrew-mate/find_capabilities"])
        for tool in ("search_docs", "find_capabilities"):
            self.assertIn(tool, app["permissions"]["mcpTools"])
        for tool in ("find_ui", "guide_start", "propose_change", "update_self", "set_model", "save_notes", "request_capabilities"):
            self.assertNotIn(tool, app["permissions"]["mcpTools"])
        self.assertNotIn("mcpServers", spec)
        self.assertNotIn("allowedTools", spec)
        self.assertIn("agents/meeting-participant.json", app["agents"])
        self.assertEqual(MEETING_AGENT, spec["name"], "Kiro Crew resolves app agents by their declared name")
        for perm in ("/api/spawn", "/api/tasks", "/api/acp-backends"):
            self.assertNotIn(perm, app["permissions"]["api"], "no unused permission is requested")


if __name__ == "__main__":
    unittest.main()
