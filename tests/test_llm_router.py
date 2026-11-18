"""Unit tests for the Gemini client / provider router failure paths (no network, no real key).

Run: python -m unittest discover -s tests -v   (from the repository root)
These cover paths that cannot be provoked safely on the real API (free-tier exhaustion) with an injected transport.
Real-API behaviour is verified separately against the live Gateway and recorded in the PR.
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from backend.crew_adapter import CrewAdapter  # noqa: E402
from backend.gemini import GeminiClient, rank_models, retry_delay_secs  # noqa: E402
from backend.llm_router import LlmRouter, LlmUnavailable  # noqa: E402
from backend.news import UnsafeUrl, validate_public_url  # noqa: E402
from backend.store import ForemanStore  # noqa: E402

KEY = "test-key-should-never-leak"


def make_router(transport, allow_confidential=False):
    tmp = tempfile.mkdtemp()
    store = ForemanStore(db_path=os.path.join(tmp, "t.db"))
    store.seed_defaults_if_empty()
    mode = store.get_state("foreman_mode", {})
    mode["allow_unpublished_to_free_tier"] = allow_confidential
    store.set_state("foreman_mode", mode)
    adapter = CrewAdapter(store)  # no live Gateway -> no Kiro fallback
    return LlmRouter(store, adapter, GeminiClient(key_loader=lambda: KEY, transport=transport)), store


def ok_body(text="{}"):
    return {"candidates": [{"content": {"parts": [{"text": text}]}}], "usageMetadata": {"promptTokenCount": 7, "candidatesTokenCount": 3}}


MODELS = {"models": [{"name": "models/gemini-3.5-flash-lite", "supportedGenerationMethods": ["generateContent"]},
                     {"name": "models/gemini-2.5-flash", "supportedGenerationMethods": ["generateContent"]}]}


class Recorder:
    def __init__(self, generate):
        self.generate, self.calls = generate, []

    def __call__(self, method, url, headers, body, timeout):
        self.calls.append((method, url, dict(headers)))
        if method == "GET":
            return 200, MODELS
        return self.generate(url)


class ModelRanking(unittest.TestCase):
    def test_lite_first_newest_first_and_stable_only(self):
        names = ["gemini-2.5-flash", "gemini-3.5-flash-lite", "gemini-3.8-flash", "gemini-3.1-flash-lite", "gemini-3.1-flash-image", "gemini-flash-latest", "gemini-3-flash-preview"]
        self.assertEqual(rank_models(names), ["gemini-3.5-flash-lite", "gemini-3.1-flash-lite", "gemini-3.8-flash", "gemini-2.5-flash"])

    def test_retry_delay_parsed(self):
        self.assertEqual(retry_delay_secs({"error": {"details": [{"retryDelay": "42s"}]}}), 42.0)


class Routing(unittest.TestCase):
    def test_confidential_text_is_not_sent_to_free_tier_by_default(self):
        rec = Recorder(lambda url: (200, ok_body()))
        router, _ = make_router(rec, allow_confidential=False)
        with self.assertRaises(LlmUnavailable) as ctx:
            router.complete("t", "secret design", confidential=True)
        self.assertEqual([c for c in rec.calls if c[0] == "POST"], [], "no request may leave when not permitted")
        self.assertIn("未許可", str(ctx.exception))

    def test_public_task_uses_gemini_and_key_only_in_header(self):
        rec = Recorder(lambda url: (200, ok_body("hello")))
        router, store = make_router(rec)
        res = router.complete("news", "public text", confidential=False)
        self.assertEqual((res.provider_id, res.text, res.input_tokens, res.output_tokens), ("gemini-free", "hello", 7, 3))
        for _, url, headers in rec.calls:
            self.assertNotIn(KEY, url)
            self.assertEqual(headers["x-goog-api-key"], KEY)
        self.assertEqual(router.usage_summary()["totals"][0]["calls"], 1)

    def test_quota_exhaustion_switches_never_to_paid_and_cools_down(self):
        rec = Recorder(lambda url: (429, {"error": {"message": "quota", "details": [{"retryDelay": "120s"}]}}))
        router, store = make_router(rec)
        with self.assertRaises(LlmUnavailable) as ctx:  # no Kiro Gateway in the unit test -> hold
            router.complete("news", "x", confidential=False)
        self.assertIn("有料APIには切り替えません", str(ctx.exception))
        post_calls = [c for c in rec.calls if c[0] == "POST"]
        self.assertEqual(len(post_calls), 1, "429 must not be retried on other models")
        with store._conn() as conn:
            status = conn.execute("SELECT status FROM provider_budgets WHERE provider_id='gemini-free'").fetchone()["status"]
        self.assertEqual(status, "quota_exhausted_switched")
        # while cooling down, Gemini is not even contacted
        before = len(rec.calls)
        with self.assertRaises(LlmUnavailable):
            router.complete("news", "x", confidential=False)
        self.assertEqual(len(rec.calls), before)

    def test_overloaded_model_falls_through_to_next_model(self):
        seen = []

        def gen(url):
            seen.append(url)
            return (503, {"error": {"message": "busy"}}) if "3.5-flash-lite" in url else (200, ok_body("from fallback model"))

        router, _ = make_router(Recorder(gen))
        res = router.complete("news", "x", confidential=False)
        self.assertEqual(res.model, "gemini-2.5-flash")
        self.assertEqual(len(seen), 2)

    def test_rejected_key_is_reported_and_not_retried(self):
        rec = Recorder(lambda url: (403, {"error": {"message": f"bad {KEY}"}}))
        router, _ = make_router(rec)
        with self.assertRaises(LlmUnavailable) as ctx:
            router.complete("news", "x", confidential=False)
        self.assertNotIn(KEY, str(ctx.exception))


class SsrfGuard(unittest.TestCase):
    def test_non_public_and_odd_urls_rejected(self):
        for url in ("http://127.0.0.1/", "http://localhost:5476/x", "http://169.254.169.254/latest/", "http://10.0.0.5/", "file:///etc/passwd", "ftp://example.com/", "http://user:pw@example.com/"):
            with self.subTest(url=url), self.assertRaises(UnsafeUrl):
                validate_public_url(url)


if __name__ == "__main__":
    unittest.main()
