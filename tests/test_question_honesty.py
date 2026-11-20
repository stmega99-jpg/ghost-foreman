"""When the asking AI gives its own options, they are shown as they are: no probe ran, so no made-up recommendation."""
from __future__ import annotations
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from backend.crew_adapter import CrewAdapter  # noqa: E402
from backend.store import ForemanStore  # noqa: E402
from backend.supervisor import ForemanSupervisor  # noqa: E402


class AgentOptions(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        store = ForemanStore(os.path.join(self.tmp.name, "gf.db"))
        store.seed_defaults_if_empty()
        self.sup = ForemanSupervisor(store, CrewAdapter(store))

    def test_options_from_the_ai_get_no_ghost_recommendation(self):
        q = self.sup.receive_agent_question(
            slot_id="slot-01", raw_question="Should next week's video go out on Tuesday or Thursday?",
            options=[{"id": "tue", "label": "Tuesday", "impact": "earlier"}, {"id": "thu", "label": "Thursday", "impact": "later"}])
        self.assertEqual(q["status"], "needs_human")
        self.assertEqual((q["recommendation"], q["recommendation_reason"]), ("", ""))
        self.assertEqual([o["id"] for o in q["options"]], ["tue", "thu"])
        self.assertIn("担当AIが示した選択肢", q["context_summary"])
        self.assertNotIn("逆質問し", q["context_summary"], "no probe ran, so the text must not say one did")
        self.assertEqual(q["probe_count"], 0)


class JudgeLanguage(unittest.TestCase):
    """The judge's reason is shown to the person, so an English question gets an English prompt."""
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        store = ForemanStore(os.path.join(self.tmp.name, "gf.db"))
        store.seed_defaults_if_empty()
        self.sup = ForemanSupervisor(store, CrewAdapter(store))
        self.prompts = []

        class Res:
            text = '{"policy_id": null, "confidence": 0.1, "reason": "x"}'
            provider_id, model, switched_from = "fake", "fake", ""

        def complete(task, prompt, system, **kw):
            self.prompts.append(prompt)
            return Res()

        self.sup.llm.complete = complete

    def judge(self, question):
        self.sup._judge_policy("proj-shop", question, {"is_live": True})
        return self.prompts[-1]

    def test_an_english_question_gets_an_english_prompt(self):
        p = self.judge("Should prices be shown with tax included?")
        self.assertIn("Confirmed rules:", p)
        self.assertIn("in English", p)
        self.assertNotIn("確定ルール:", p)

    def test_a_japanese_question_keeps_the_japanese_prompt(self):
        p = self.judge("価格は税込みで表示しますか？")
        self.assertIn("確定ルール:", p)


if __name__ == "__main__":
    unittest.main()
