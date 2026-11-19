"""Claude Code / Codex started outside Kiro Crew for AI meetings: text-only enforcement, metered-API refusal,
emergency stop, memory gate, environment scrubbing and the run record. No real CLI is started: a fake process
replays the event streams the real CLIs were observed to produce (Claude 2.1.x stream-json, Codex 0.159 --json).
"""

from __future__ import annotations

import io
import json
import os
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import backend.external_ai as ext  # noqa: E402
from backend.store import ForemanStore  # noqa: E402

CLAUDE_INIT = {"type": "system", "subtype": "init", "tools": [], "mcp_servers": [], "apiKeySource": "none", "model": "claude-opus-4-7"}
CLAUDE_OK = [CLAUDE_INIT,
             {"type": "assistant", "message": {"content": [{"type": "text", "text": "準備OK"}]}},
             {"type": "result", "subtype": "success", "is_error": False, "result": "Claude Code です。準備OK", "usage": {"input_tokens": 12, "output_tokens": 7}}]
CODEX_OK = [{"type": "thread.started", "thread_id": "t"},
            {"type": "item.completed", "item": {"id": "item_0", "type": "error", "message": "Code Mode is unavailable ... fail closed"}},
            {"type": "turn.started"},
            {"type": "item.completed", "item": {"id": "item_1", "type": "agent_message", "text": "Codex です。準備OK"}},
            {"type": "turn.completed", "usage": {"input_tokens": 8396, "output_tokens": 5}}]


class FakeProc:
    def __init__(self, events, hang=False, returncode=0):
        self.pid = 999999
        self.returncode = None
        self._rc = returncode
        self.stdin = io.BytesIO()
        self.stdin.close = lambda: None
        self.stderr = io.BytesIO(b"")
        self._lines = [(json.dumps(e) + "\n").encode() for e in events]
        self._hang = hang
        self.killed = threading.Event()

    @property
    def stdout(self):
        for line in self._lines:
            if self.killed.is_set():
                return
            yield line
        while self._hang and not self.killed.is_set():
            time.sleep(0.01)

    def poll(self):
        return self.returncode

    def wait(self, timeout=None):
        self.returncode = -9 if self.killed.is_set() else self._rc
        return self.returncode

    def kill(self):
        self.killed.set()


class Harness:
    def __init__(self, events_by_harness, free_gb=8.0, status=None, hang=False):
        self.events, self.hang, self.free_gb = events_by_harness, hang, free_gb
        self.started, self.killed = [], []
        store = ForemanStore(db_path=os.path.join(tempfile.mkdtemp(), "e.db"))
        store.seed_defaults_if_empty()
        self.halted = False
        self.store = store
        self.runner = ext.ExternalAIRunner(
            store, rooms_dir=Path(tempfile.mkdtemp()), is_halted=lambda pid: self.halted,
            resolver=lambda h: [f"/bin/{h}"], memory=lambda: self.free_gb, popen=self.popen, killer=self.kill,
        )
        st = status or {}
        self.runner.status = lambda h, refresh=False: {"id": h, "label": ext.LABELS[h], "runtime": ext.RUNTIME, "available": st.get(h, True),
                                                       "reason": "" if st.get(h, True) else "未ログイン", "auth": "subscription", "version": "x"}

    def popen(self, cmd, **kw):
        harness = "claude" if "claude" in cmd[0] else "codex"
        self.started.append((cmd, kw))
        return FakeProc(self.events[harness], hang=self.hang)

    def kill(self, proc):
        self.killed.append(proc)
        proc.kill()


class TextOnly(unittest.TestCase):
    def test_claude_answer_is_returned_with_model_and_tokens(self):
        h = Harness({"claude": CLAUDE_OK})
        r = h.runner.run("claude", "hello", meeting_id="m1", project_id="p")
        self.assertEqual((r["reply"], r["error"], r["model"], r["runtime"]), ("Claude Code です。準備OK", "", "claude-opus-4-7", "external_cli"))
        cmd, kw = h.started[0]
        for flag in ("--tools", "--strict-mcp-config", "--no-session-persistence", "--disable-slash-commands"):
            self.assertIn(flag, cmd)
        self.assertEqual(cmd[cmd.index("--tools") + 1], "", "all built-in tools off")
        self.assertNotIn("hello", " ".join(cmd), "the prompt goes through stdin, never the command line")

    def test_codex_answer_and_its_tool_switches(self):
        h = Harness({"codex": CODEX_OK})
        r = h.runner.run("codex", "hello")
        self.assertEqual((r["reply"], r["error"]), ("Codex です。準備OK", ""))
        cmd, _ = h.started[0]
        for feature in ("shell_tool", "unified_exec", "browser_use", "computer_use", "multi_agent", "apps", "plugins", "hooks"):
            self.assertIn(feature, cmd)
        for flag in ("--ignore-user-config", "--ephemeral", "--json"):
            self.assertIn(flag, cmd)
        self.assertEqual(cmd[cmd.index("--sandbox") + 1], "read-only")

    def test_claude_tool_use_kills_the_process(self):
        events = [CLAUDE_INIT, {"type": "assistant", "message": {"content": [{"type": "tool_use", "name": "Bash", "input": {}}]}}]
        h = Harness({"claude": events}, hang=True)
        r = h.runner.run("claude", "x")
        self.assertIsNone(r["reply"])
        self.assertIn("ツールを使おうとした", r["violation"])
        self.assertEqual(len(h.killed), 1)

    def test_claude_started_with_tools_is_refused(self):
        h = Harness({"claude": [{**CLAUDE_INIT, "tools": ["Bash", "Read"]}]}, hang=True)
        r = h.runner.run("claude", "x")
        self.assertIn("ツールが有効", r["violation"])
        self.assertEqual(len(h.killed), 1)

    def test_codex_command_execution_kills_the_process(self):
        events = CODEX_OK[:3] + [{"type": "item.started", "item": {"id": "i", "type": "command_execution", "command": "type C:\\secret"}}]
        h = Harness({"codex": events}, hang=True)
        r = h.runner.run("codex", "x")
        self.assertIn("command_execution", r["violation"])
        self.assertIsNone(r["reply"])
        self.assertEqual(len(h.killed), 1)
        rec = h.runner.recent()[0]
        self.assertEqual(rec["status"], "violation")


class NoMeteredApi(unittest.TestCase):
    def test_claude_on_an_api_key_is_stopped_before_answering(self):
        h = Harness({"claude": [{**CLAUDE_INIT, "apiKeySource": "ANTHROPIC_API_KEY"}] + CLAUDE_OK[1:]}, hang=True)
        r = h.runner.run("claude", "x")
        self.assertIn("API キー", r["violation"])
        self.assertIsNone(r["reply"])

    def test_unavailable_harness_is_not_started(self):
        h = Harness({"claude": CLAUDE_OK}, status={"claude": False})
        r = h.runner.run("claude", "x")
        self.assertIn("未ログイン", r["error"])
        self.assertEqual(h.started, [])

    def test_environment_carries_no_keys_or_tokens(self):
        h = Harness({"claude": CLAUDE_OK})
        with mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-x", "OPENAI_API_KEY": "sk-y", "GEMINI_API_KEY": "g", "GITHUB_TOKEN": "t"}):
            h.runner.run("claude", "x")
        env = h.started[0][1]["env"]
        for k in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GEMINI_API_KEY", "GITHUB_TOKEN"):
            self.assertNotIn(k, env)

    def test_auth_check_reads_the_cli_answers(self):
        h = Harness({})
        runner = ext.ExternalAIRunner(h.store, rooms_dir=Path(tempfile.mkdtemp()), resolver=lambda x: ["/bin/x"])
        answers = {("auth", "status"): '{"loggedIn": true, "authMethod": "claude.ai"}', ("--version",): "2.1.143 (Claude Code)", ("login", "status"): "Logged in using ChatGPT"}
        runner._quick = lambda cmd, *a: answers[a]
        self.assertTrue(runner.status("claude", refresh=True)["available"])
        self.assertTrue(runner.status("codex", refresh=True)["available"])
        answers[("auth", "status")] = '{"loggedIn": true, "authMethod": "api_key"}'
        answers[("login", "status")] = "Logged in using an API key"
        self.assertIn("従量課金", runner.status("claude", refresh=True)["reason"])
        self.assertIn("従量課金", runner.status("codex", refresh=True)["reason"])
        answers[("auth", "status")] = '{"loggedIn": false, "authMethod": "none"}'
        self.assertIn("ログインしていません", runner.status("claude", refresh=True)["reason"])


class StopMemoryRecord(unittest.TestCase):
    def test_kill_all_stops_a_running_cli(self):
        h = Harness({"claude": [CLAUDE_INIT]}, hang=True)
        out = {}
        t = threading.Thread(target=lambda: out.update(h.runner.run("claude", "x", project_id="p")), daemon=True)
        t.start()
        for _ in range(300):
            if h.runner.running():
                break
            time.sleep(0.01)
        self.assertEqual(len(h.runner.kill_all("p")), 1)
        t.join(5)
        self.assertIsNone(out["reply"])
        self.assertIn("緊急停止", out["error"])

    def test_no_start_while_a_stop_is_in_force(self):
        h = Harness({"claude": CLAUDE_OK})
        h.halted = True
        r = h.runner.run("claude", "x")
        self.assertIn("緊急停止中", r["error"])
        self.assertEqual(h.started, [])

    def test_waits_for_memory_then_gives_up_with_the_reason(self):
        h = Harness({"claude": CLAUDE_OK}, free_gb=0.4)
        with mock.patch.object(ext, "MEMORY_WAIT_SECS", 0.05):
            r = h.runner.run("claude", "x")
        self.assertIn("メモリが足りない", r["error"])
        self.assertEqual(h.started, [])

    def test_timeout_kills_and_reports(self):
        h = Harness({"codex": CODEX_OK[:2]}, hang=True)
        r = h.runner.run("codex", "x", timeout=0.2)
        self.assertIsNone(r["reply"])
        self.assertIn("タイムアウト", r["error"])

    def test_every_run_is_recorded_without_the_prompt_text(self):
        h = Harness({"claude": CLAUDE_OK})
        h.runner.run("claude", "secret plan text", meeting_id="m9", project_id="p", tag="pre")
        rec = h.runner.recent()[0]
        self.assertEqual((rec["meeting_id"], rec["harness"], rec["runtime"], rec["status"], rec["model"]), ("m9", "claude", "external_cli", "ok", "claude-opus-4-7"))
        self.assertEqual((rec["input_tokens"], rec["output_tokens"]), (12, 7))
        self.assertNotIn("secret plan text", json.dumps(rec, ensure_ascii=False))
        with h.store._conn() as c:
            u = dict(c.execute("SELECT * FROM llm_usage WHERE provider_id='claude-cli'").fetchone())
        self.assertIsNone(u["cost_usd"], "billing is unconfirmed, never shown as 0")
        self.assertIn("Kiro Crew外", u["cost_basis"])


class StopRacesWithStart(unittest.TestCase):
    """An emergency stop that lands while a CLI is being started must still stop it.

    The stop sets the hold first and then calls ``kill_all`` (crew_adapter.stop_control). The dangerous window is
    between the start's last hold check and the moment the new process is tracked: ``kill_all`` cannot see it yet.
    """

    def _stop_during_popen(self, set_hold: bool, call_kill_all: bool):
        h = Harness({"claude": [CLAUDE_INIT] + CLAUDE_OK[1:]}, hang=True)
        real_popen = h.popen

        def popen(cmd, **kw):
            # The stop arrives while the OS is creating the process.
            if set_hold:
                h.halted = True
            if call_kill_all:
                h.runner.kill_all("p")
            return real_popen(cmd, **kw)

        h.runner._popen = popen
        out = {}
        t = threading.Thread(target=lambda: out.update(h.runner.run("claude", "x", project_id="p")), daemon=True)
        t.start()
        t.join(5)
        self.assertFalse(t.is_alive(), "the run must end instead of running on after the stop")
        return h, out

    def test_stop_during_process_creation_kills_the_new_process(self):
        h, out = self._stop_during_popen(set_hold=True, call_kill_all=True)
        self.assertEqual(len(h.killed), 1, "the process started during the stop is killed")
        self.assertIsNone(out["reply"])
        self.assertIn("緊急停止", out["error"])
        self.assertEqual(h.runner.recent()[0]["status"], "failed")

    def test_hold_alone_during_process_creation_kills_it(self):
        # The hold is set but kill_all has not run yet (or already ran before the process existed).
        h, out = self._stop_during_popen(set_hold=True, call_kill_all=False)
        self.assertEqual(len(h.killed), 1)
        self.assertIn("緊急停止", out["error"])

    def test_kill_all_alone_during_process_creation_kills_it(self):
        # A meeting abort calls kill_all for its project; a start already past its checks must not escape it.
        h, out = self._stop_during_popen(set_hold=False, call_kill_all=True)
        self.assertEqual(len(h.killed), 1)
        self.assertIn("緊急停止", out["error"])

    def test_stop_after_capacity_check_starts_nothing(self):
        h = Harness({"claude": CLAUDE_OK})
        real_room = h.runner._room

        def room(name):
            h.halted = True  # the stop lands after the capacity check, before the process is created
            h.runner.kill_all("p")
            return real_room(name)

        h.runner._room = room
        r = h.runner.run("claude", "x", project_id="p")
        self.assertEqual(h.started, [], "no process is created once the stop is in force")
        self.assertIn("緊急停止", r["error"])

    def test_concurrent_starts_never_exceed_the_limit(self):
        h = Harness({"claude": [CLAUDE_INIT]}, hang=True)
        alive, peak, lock = [0], [0], threading.Lock()
        real_popen = h.popen

        def popen(cmd, **kw):
            time.sleep(0.05)  # widen the check-then-start window
            with lock:
                alive[0] += 1
                peak[0] = max(peak[0], alive[0])
            return real_popen(cmd, **kw)

        def kill(proc):
            with lock:
                alive[0] -= 1
            proc.kill()

        h.runner._popen, h.runner._kill = popen, kill
        threads = [threading.Thread(target=h.runner.run, args=("claude", "x"), kwargs={"project_id": "p"}, daemon=True) for _ in range(6)]
        with mock.patch.object(ext, "MEMORY_WAIT_SECS", 1.0):
            for t in threads:
                t.start()
            time.sleep(0.6)
            h.halted = True
            h.runner.kill_all()
            for t in threads:
                t.join(10)
        self.assertLessEqual(peak[0], ext.MAX_CONCURRENT)
        self.assertEqual(h.runner.running(), 0)

    def test_randomised_stop_timing_never_leaves_a_process_running(self):
        import random

        rng = random.Random(7)
        for _ in range(40):
            h = Harness({"claude": [CLAUDE_INIT]}, hang=True)
            procs, real_popen = [], h.popen

            def popen(cmd, **kw):
                time.sleep(rng.uniform(0, 0.02))
                p = real_popen(cmd, **kw)
                procs.append(p)
                return p

            h.runner._popen = popen
            out = {}
            t = threading.Thread(target=lambda: out.update(h.runner.run("claude", "x", project_id="p")), daemon=True)
            t.start()
            time.sleep(rng.uniform(0, 0.03))
            h.halted = True
            h.runner.kill_all("p")
            t.join(5)
            self.assertFalse(t.is_alive())
            self.assertTrue(all(p.killed.is_set() for p in procs), "every process that was created is killed")
            self.assertIsNone(out.get("reply"))


if __name__ == "__main__":
    unittest.main()
