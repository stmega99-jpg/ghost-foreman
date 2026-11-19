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
from backend.gemini import GeminiClient, GeminiQuotaExhausted, GeminiResult, GeminiStopped  # noqa: E402
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

    def generate(self, prompt, system="", json_mode=False, max_output_tokens=1024, should_stop=None):
        if should_stop is not None and should_stop():
            raise GeminiStopped("緊急停止中のため Gemini API に送信しませんでした")
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


MODELS = {"models": [{"name": f"models/{n}", "supportedGenerationMethods": ["generateContent"]}
                     for n in ("gemini-2.5-flash-lite", "gemini-2.0-flash-lite", "gemini-2.5-flash")]}


class Transport:
    """The HTTP layer under the REAL GeminiClient. Every model answers 503 (busy), so the client moves on to the next
    model, unless *on_post* (run while the first request is "in flight") stops it."""

    def __init__(self, on_post=None):
        self.requests, self.on_post = [], on_post

    def __call__(self, method, url, headers, body, timeout):
        self.requests.append((method, url.rsplit("/", 1)[-1]))
        if method == "GET":
            return 200, MODELS
        if self.on_post is not None and len([r for r in self.requests if r[0] == "POST"]) == 1:
            self.on_post()
        return 503, {"error": {"message": "overloaded"}}

    def posts(self):
        return [u for m, u in self.requests if m == "POST"]


class NoRetryOnAnotherModelAfterAStop(unittest.TestCase):
    def test_without_a_stop_check_the_client_does_try_the_next_models(self):
        # Shows what the check prevents: on 503 the client sends the same text to the next model.
        t = Transport()
        with self.assertRaises(Exception):
            GeminiClient(key_loader=lambda: "k", transport=t).generate("x")
        self.assertEqual(len(t.posts()), 3)

    def test_a_stop_during_the_first_request_means_no_other_model_is_asked(self):
        stopped = {"v": False}
        t = Transport(on_post=lambda: stopped.update(v=True))
        with self.assertRaises(GeminiStopped):
            GeminiClient(key_loader=lambda: "k", transport=t).generate("x", should_stop=lambda: stopped["v"])
        self.assertEqual(t.posts(), ["gemini-2.5-flash-lite:generateContent"], "only the request already in flight")

    def test_nothing_is_sent_when_stopped_before_the_first_request(self):
        t = Transport()
        with self.assertRaises(GeminiStopped):
            GeminiClient(key_loader=lambda: "k", transport=t).generate("x", should_stop=lambda: True)
        self.assertEqual(t.requests, [], "not even the model list")

    def test_in_a_meeting_a_stop_while_gemini_answers_ends_all_requests(self):
        holder = {}
        t = Transport(on_post=lambda: holder["adapter"].stop_control("all"))
        client = GeminiClient(key_loader=lambda: "k", transport=t)
        store, adapter, live, ext, _fake, router, engine = setup()
        router.gemini = client
        holder["adapter"] = adapter
        m = wait(engine, engine.start("proj-foreman", "議題", WITH_GEMINI, synthesizer_harness="kiro", allow_unpublished_to_gemini=True)["id"])
        self.assertEqual(m["status"], "failed")
        self.assertIn("緊急停止", m["summary"]["note"])
        self.assertEqual(len(t.posts()), 1, "after the stop no other model received the meeting's text")
        self.assertEqual(store.get_state("gemini_cooldown_until", 0.0) or 0.0, 0.0, "a stop is not a quota problem")
        with store._conn() as c:
            status = c.execute("SELECT status FROM provider_budgets WHERE provider_id = ?", (GEMINI_ID,)).fetchone()
        self.assertNotEqual(status and status["status"], "key_rejected", "a stop does not mark the key as rejected")


class SelfReport(unittest.TestCase):
    """What an AI called itself vs. the AI that was actually called. Replies are the real ones seen on 2026-11-19."""

    def test_real_replies(self):
        from backend.meeting import check_self_report as c

        self.assertEqual(c("claude", "Claude (Anthropic) — claude-sonnet-4-6  準備OK")["status"], "ok")
        self.assertEqual(c("codex", "OpenAI Codex 準備OK")["status"], "ok")
        self.assertEqual(c("kiro", "私は Kiro Crew 上で動く Kiro です（モデルは「Auto」で、具体名は不明です）。 準備OK")["status"], "ok")
        g = c("gemini", "私はGoogleのClaudeではありません、Anthropic社が開発したAIアシスタント、Claudeです。準備OK")
        self.assertEqual((g["status"], g["names"]), ("other_name", ["Claude"]))
        self.assertIn("実際に答えたのは Gemini", g["note"])

    def test_other_cases(self):
        from backend.meeting import check_self_report as c

        self.assertEqual(c("gemini", "Google の Gemini です。準備OK")["status"], "ok")
        self.assertEqual(c("gemini", "ジェミニです。準備OK")["status"], "ok")
        self.assertEqual(c("gemini", "AIアシスタントです。準備OK")["status"], "no_own_name")
        self.assertEqual(c("kiro", "Kiro です。中身は Claude Sonnet です。準備OK")["status"], "ok", "Kiro may run a Claude model")
        self.assertEqual(c("claude", "I am ChatGPT by OpenAI. 準備OK")["status"], "other_name")
        self.assertEqual(c("codex", "Gemini です")["names"], ["Gemini"])

    def test_gemini_is_told_its_own_name(self):
        self.assertIn("You are Gemini", meeting_mod.GEMINI_SYSTEM)
        self.assertIn("Google", meeting_mod.GEMINI_SYSTEM)

    def test_a_wrong_self_introduction_is_flagged_but_does_not_change_who_answered(self):
        class ClaimsClaude(FakeGemini):
            def generate(self, prompt, **kw):
                res = super().generate(prompt, **kw)
                if "参加確認" in prompt or "participation check" in prompt:
                    res.text = "Anthropic社が開発したAIアシスタント、Claudeです。準備OK"
                return res

        store, adapter, live, ext, fake, router, engine = setup(ClaimsClaude())
        m = wait(engine, engine.start("proj-foreman", "議題", WITH_GEMINI, synthesizer_harness="kiro", allow_unpublished_to_gemini=True)["id"])
        self.assertEqual(m["status"], "awaiting_human_adoption", "the meeting goes on")
        g = m["summary"]["participants_detail"][1]
        self.assertTrue(g["verified"], "who answered comes from the call, not the text")
        self.assertEqual(g["ran_on"], "gemini")
        self.assertEqual(g["self_report_check"]["status"], "other_name")
        self.assertTrue(m["summary"]["self_report_mismatch"])
        self.assertIn("⚠️ 自己紹介に別のAIの名前（Claude）", json.dumps(m["rounds"][0], ensure_ascii=False))
        others = [p for i, p in enumerate(m["summary"]["participants_detail"]) if i != 1]
        self.assertTrue(all(p["self_report_check"]["status"] == "ok" for p in others))


class Route(unittest.TestCase):
    def test_only_a_literal_true_in_the_request_counts_as_permission(self):
        from backend import routes

        seen, langs = [], []

        class Sup:
            def run_brainstorm_meeting(self, **kw):
                seen.append(kw["allow_unpublished_to_gemini"])
                langs.append(kw["language"])
                return {"id": "m"}

        for value, expected in ((True, True), ("true", False), (1, False), (None, False)):
            body = {"topic": "t", "participants": [], "allow_unpublished_to_gemini": value}
            with mock.patch("backend.hooks.get_runtime", return_value=(None, None, Sup())):
                routes.dispatch_api_request("POST", "/meetings", body)
            self.assertEqual(seen[-1], expected, value)
        with mock.patch("backend.hooks.get_runtime", return_value=(None, None, Sup())):
            routes.dispatch_api_request("POST", "/meetings", {"topic": "t"})
        self.assertFalse(seen[-1], "missing means not allowed")
        self.assertEqual(langs[-1], "ja", "no language sent means Japanese")
        with mock.patch("backend.hooks.get_runtime", return_value=(None, None, Sup())):
            routes.dispatch_api_request("POST", "/meetings", {"topic": "t", "language": "en"})
        self.assertEqual(langs[-1], "en")


if __name__ == "__main__":
    unittest.main()
