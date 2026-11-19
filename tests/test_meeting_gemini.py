"""Gemini (official API free tier) as an AI-meeting participant, with the human's permission asked PER MEETING.

The real LlmRouter is used with a fake Gemini client, so the free-tier guard (cooldown after a 429, no Kiro fallback,
no paid API, usage records) is exercised as in production. Kiro and Claude Code / Codex are the fakes of test_meeting.
"""

from __future__ import annotations

import json
import os
import sys
import threading
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.dirname(__file__))

from backend import meeting as meeting_mod  # noqa: E402
from backend.gemini import GeminiQuotaExhausted, GeminiResult  # noqa: E402
from backend.llm_router import GEMINI_ID, LlmRouter, LlmUnavailable  # noqa: E402
from backend.meeting import GEMINI_CONSENT_REQUIRED, MeetingEngine  # noqa: E402
from test_meeting import answer_for, make, wait  # noqa: E402


class FakeGemini:
    """Stands in for GeminiClient (the HTTP layer). Records every prompt it was sent."""

    def __init__(self, key=True, quota_after=None, block=None):
        self.key, self.quota_after, self.block = key, quota_after, block
        self.prompts, self.systems, self.max_tokens = [], [], []

    def has_key(self):
        return self.key

    def generate(self, prompt, system="", json_mode=False, max_output_tokens=1024):
        self.prompts.append(prompt)
        self.systems.append(system)
        self.max_tokens.append(max_output_tokens)
        if self.block is not None:
            self.block.wait(10)
        if self.quota_after is not None and len(self.prompts) > self.quota_after:
            raise GeminiQuotaExhausted("gemini-2.5-flash-lite: quota", 120.0)
        return GeminiResult(answer_for(prompt, "gemini"), "gemini-2.5-flash-lite", 40, 12)


def setup(gemini=None):
    store, adapter, live, ext, _ = make()
    fake = gemini or FakeGemini()
    router = LlmRouter(store, adapter, gemini=fake)
    engine = MeetingEngine(store, adapter, external=ext, gemini=router)
    return store, adapter, live, ext, fake, router, engine


WITH_GEMINI = [
    {"perspective": "設計の視点", "harness": "claude"},
    {"perspective": "市場の視点", "harness": "gemini"},
    {"perspective": "体験の視点", "harness": "kiro"},
]


def meeting_count(store):
    with store._conn() as c:
        return c.execute("SELECT COUNT(*) FROM meetings").fetchone()[0]


class PerMeetingPermission(unittest.TestCase):
    def test_gemini_takes_part_when_this_meeting_allows_it(self):
        store, adapter, live, ext, fake, router, engine = setup()
        m = wait(engine, engine.start("proj-foreman", "議題", WITH_GEMINI, synthesizer_harness="kiro", allow_unpublished_to_gemini=True)["id"])
        self.assertEqual(m["status"], "awaiting_human_adoption", m["summary"].get("note"))
        g = m["summary"]["participants_detail"][1]
        self.assertEqual((g["harness"], g["runtime"], g["ran_on"], g["model"], g["verified"]),
                         ("gemini", "gemini_api", "gemini", "gemini-2.5-flash-lite", True))
        self.assertEqual(g["runtime_label"], "Kiro Crew 外で実行（Gemini API 無料枠）")
        self.assertTrue(m["summary"]["outside_kiro_crew"])
        consent = m["summary"]["gemini_consent"]
        self.assertEqual((consent["asked"], consent["allowed"], consent["scope"]), (True, True, "この会議のみ"))
        self.assertTrue(consent["decided_at"])
        self.assertEqual(len(fake.prompts), 3, "participation check, ideas, critique")
        self.assertIn("gemini proposal", json.dumps(m["rounds"][1], ensure_ascii=False))
        self.assertTrue(all(s == meeting_mod.GEMINI_SYSTEM for s in fake.systems))
        self.assertTrue(all(t == meeting_mod.GEMINI_MAX_OUTPUT_TOKENS for t in fake.max_tokens))
        with store._conn() as c:
            rows = [dict(r) for r in c.execute("SELECT * FROM llm_usage WHERE provider_id = ?", (GEMINI_ID,)).fetchall()]
        self.assertEqual([r["task"] for r in rows], ["meeting:pre", "meeting:r1", "meeting:r2"])
        self.assertTrue(all(r["cost_usd"] is None for r in rows), "billing stays unconfirmed, never $0")

    def test_without_permission_nothing_is_created_or_sent(self):
        store, adapter, live, ext, fake, router, engine = setup()
        for answer in (False, None, "true", 1, "yes"):
            with self.assertRaises(ValueError) as cm:
                engine.start("proj-foreman", "議題", WITH_GEMINI, synthesizer_harness="kiro", allow_unpublished_to_gemini=answer)
            self.assertEqual(str(cm.exception), GEMINI_CONSENT_REQUIRED)
        self.assertEqual(fake.prompts, [], "nothing was sent to Gemini")
        self.assertEqual(ext.calls, [], "no other AI was started either")
        self.assertEqual(live.agent_of, {}, "no Kiro slot was created")
        self.assertEqual(meeting_count(store), 0)

    def test_gemini_as_organiser_also_needs_permission(self):
        store, adapter, live, ext, fake, router, engine = setup()
        parts = [{"perspective": "a", "harness": "kiro"}, {"perspective": "b", "harness": "codex"}]
        with self.assertRaises(ValueError):
            engine.start("proj-foreman", "議題", parts, synthesizer_harness="gemini")
        m = wait(engine, engine.start("proj-foreman", "議題", parts, synthesizer_harness="gemini", allow_unpublished_to_gemini=True)["id"])
        self.assertEqual(m["status"], "awaiting_human_adoption", m["summary"].get("note"))
        self.assertEqual(m["summary"]["synthesizer"]["ran_on"], "gemini")
        self.assertEqual(m["summary"]["consensus"], "合意")

    def test_permission_is_per_meeting_and_the_global_switch_is_untouched(self):
        store, adapter, live, ext, fake, router, engine = setup()
        before = dict(store.get_state("foreman_mode", {}) or {})
        self.assertFalse(router.allow_confidential_to_free_tier())
        first = wait(engine, engine.start("proj-foreman", "議題1", WITH_GEMINI, synthesizer_harness="kiro", allow_unpublished_to_gemini=True)["id"])
        self.assertEqual(first["status"], "awaiting_human_adoption")
        self.assertEqual(dict(store.get_state("foreman_mode", {}) or {}), before, "the global free-tier switch is not changed")
        self.assertFalse(router.allow_confidential_to_free_tier())
        self.assertEqual(engine._gemini_allowed, {}, "the permission ended with the meeting")
        sent = len(fake.prompts)
        with self.assertRaises(ValueError):  # the next meeting is asked again
            engine.start("proj-foreman", "議題2", WITH_GEMINI, synthesizer_harness="kiro")
        self.assertEqual(len(fake.prompts), sent)

    def test_a_meeting_without_gemini_records_no_permission(self):
        store, adapter, live, ext, fake, router, engine = setup()
        parts = [{"perspective": "a", "harness": "kiro"}, {"perspective": "b", "harness": "claude"}]
        m = wait(engine, engine.start("proj-foreman", "議題", parts, synthesizer_harness="kiro", allow_unpublished_to_gemini=True)["id"])
        self.assertEqual((m["summary"]["gemini_consent"]["asked"], m["summary"]["gemini_consent"]["allowed"]), (False, False))
        self.assertEqual(fake.prompts, [])

    def test_a_running_meeting_without_permission_never_calls_gemini(self):
        # Defence in depth: even if a Gemini job reached _ask_all for a meeting with no permission, it is refused.
        store, adapter, live, ext, fake, router, engine = setup()
        out, done = {}, threading.Event()
        engine._ask_gemini("mtg-x", "proj-foreman", "r1", "secret", out, done)
        self.assertTrue(done.is_set())
        self.assertIsNone(out["reply"])
        self.assertEqual(fake.prompts, [])


class FreeTierGuard(unittest.TestCase):
    def test_quota_exhausted_means_no_answer_and_no_substitute(self):
        store, adapter, live, ext, fake, router, engine = setup(FakeGemini(quota_after=0))
        m = wait(engine, engine.start("proj-foreman", "議題", WITH_GEMINI, synthesizer_harness="kiro", allow_unpublished_to_gemini=True)["id"])
        self.assertEqual(m["status"], "failed")
        self.assertIn("有料APIには切り替えません", m["summary"]["note"])
        g = m["summary"]["participants_detail"][1]
        self.assertFalse(g["verified"])
        self.assertNotEqual(g["ran_on"], "kiro", "Kiro did not answer in Gemini's place")
        self.assertEqual(len(live.last), 2, "only the Kiro participant and the organiser were asked")
        # The cooldown is now in force: the next meeting is refused before anything is sent.
        sent = len(fake.prompts)
        with self.assertRaises(ValueError) as cm:
            engine.start("proj-foreman", "議題", WITH_GEMINI, synthesizer_harness="kiro", allow_unpublished_to_gemini=True)
        self.assertIn("待機中", str(cm.exception))
        self.assertEqual(len(fake.prompts), sent)

    def test_no_key_is_reported_as_unavailable(self):
        store, adapter, live, ext, fake, router, engine = setup(FakeGemini(key=False))
        row = [r for r in engine.available_harnesses()["harnesses"] if r["id"] == "gemini"][0]
        self.assertFalse(row["available"])
        self.assertIn("GEMINI_API_KEY", row["reason"])
        self.assertTrue(row["needs_consent"])
        with self.assertRaises(ValueError):
            engine.start("proj-foreman", "議題", WITH_GEMINI, synthesizer_harness="kiro", allow_unpublished_to_gemini=True)

    def test_gemini_only_requires_permission_and_never_falls_back(self):
        store, adapter, live, ext, fake, router, engine = setup(FakeGemini(quota_after=0))
        with self.assertRaises(LlmUnavailable):
            router.gemini_only("t", "x", unpublished_allowed=False)
        self.assertEqual(fake.prompts, [])
        with mock.patch.object(router, "_ask_kiro", side_effect=AssertionError("must not fall back to Kiro")):
            with self.assertRaises(LlmUnavailable) as cm:
                router.gemini_only("t", "x", unpublished_allowed=True)
        self.assertIn("有料APIには切り替えません", str(cm.exception))


class EmergencyStop(unittest.TestCase):
    def test_answer_arriving_after_a_stop_is_thrown_away(self):
        gate = threading.Event()
        store, adapter, live, ext, fake, router, engine = setup(FakeGemini(block=gate))
        mid = engine.start("proj-foreman", "議題", WITH_GEMINI, synthesizer_harness="kiro", allow_unpublished_to_gemini=True)["id"]
        for _ in range(200):
            if fake.prompts:
                break
            threading.Event().wait(0.01)
        self.assertEqual(len(fake.prompts), 1, "the participation check is in flight")
        adapter.stop_control("all")
        gate.set()  # the HTTP answer arrives after the stop
        m = wait(engine, mid)
        self.assertEqual(m["status"], "failed")
        self.assertIn("緊急停止", m["summary"]["note"])
        self.assertNotIn("gemini です", json.dumps(m["rounds"], ensure_ascii=False), "the late answer is not used")
        self.assertEqual(len(fake.prompts), 1, "nothing more was sent")

    def test_no_request_is_sent_while_a_stop_is_in_force(self):
        store, adapter, live, ext, fake, router, engine = setup()
        engine._gemini_allowed["mtg-y"] = True
        adapter.halt.engage("all")
        out, done = {}, threading.Event()
        engine._ask_gemini("mtg-y", "proj-foreman", "r1", "x", out, done)
        self.assertIn("緊急停止中", out["error"])
        self.assertEqual(fake.prompts, [])


class Route(unittest.TestCase):
    def test_only_a_literal_true_in_the_request_counts_as_permission(self):
        from backend import routes

        seen = []

        class Sup:
            def run_brainstorm_meeting(self, **kw):
                seen.append(kw["allow_unpublished_to_gemini"])
                return {"id": "m"}

        for value, expected in ((True, True), ("true", False), (1, False), (None, False)):
            body = {"topic": "t", "participants": [], "allow_unpublished_to_gemini": value}
            with mock.patch("backend.hooks.get_runtime", return_value=(None, None, Sup())):
                routes.dispatch_api_request("POST", "/meetings", body)
            self.assertEqual(seen[-1], expected, value)
        with mock.patch("backend.hooks.get_runtime", return_value=(None, None, Sup())):
            routes.dispatch_api_request("POST", "/meetings", {"topic": "t"})
        self.assertFalse(seen[-1], "missing means not allowed")


if __name__ == "__main__":
    unittest.main()
