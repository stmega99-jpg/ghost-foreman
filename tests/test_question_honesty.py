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


if __name__ == "__main__":
    unittest.main()
