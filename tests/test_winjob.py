"""Windows Job Object containment for CLIs started outside Kiro Crew. Real processes, real Win32 calls.

Each test starts a small Python program in place of Claude Code / Codex. The program starts child processes (as
codex.js starts the Codex binary) and writes every PID it creates to a folder, so the test can check afterwards that
no process is left running.
"""

from __future__ import annotations

import ctypes
import os
import subprocess
import sys
import tempfile
import textwrap
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import backend.external_ai as ext  # noqa: E402
from backend import winjob  # noqa: E402
from backend.store import ForemanStore  # noqa: E402

FLAGS = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) | getattr(subprocess, "CREATE_NO_WINDOW", 0)


def alive(pid: int) -> bool:
    k32 = ctypes.windll.kernel32
    h = k32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
    if not h:
        return False
    code = ctypes.c_ulong()
    ok = k32.GetExitCodeProcess(h, ctypes.byref(code))
    k32.CloseHandle(h)
    return bool(ok) and code.value == 259  # STILL_ACTIVE


# A child that sleeps. Writes its own PID first.
CHILD = "import os,sys,time; open(os.path.join(sys.argv[1], f'{os.getpid()}.pid'),'w').close(); time.sleep(60)"

PROGRAMS = {
    # Starts one child, then waits.
    "one_child": """
        p = start_child()
        time.sleep(60)
    """,
    # Starts children without pause, so some are always being created when the stop lands.
    "spawner": """
        while True:
            start_child()
            time.sleep(0.005)
    """,
    # Starts a child, waits until the child has registered its PID, then exits, leaving the child running.
    "leaves_child": """
        p = start_child()
        end = time.time() + 30
        while not os.path.exists(os.path.join(OUT, f"{p.pid}.pid")) and time.time() < end:
            time.sleep(0.02)
    """,
    # Tries to start a child outside the job.
    "breakaway": """
        try:
            subprocess.Popen([sys.executable, "-c", CHILD, OUT], creationflags=0x01000000)  # CREATE_BREAKAWAY_FROM_JOB
            open(os.path.join(OUT, "breakaway.ok"), "w").close()
        except OSError as exc:
            open(os.path.join(OUT, "breakaway.refused"), "w").write(str(exc))
        start_child()
        time.sleep(60)
    """,
}


@unittest.skipUnless(sys.platform == "win32", "Job Objects are Windows-only")
class _ProcessTest(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.out = self.dir / "pids"
        self.out.mkdir()
        self.started = []

    def tearDown(self):
        for pid in self.pids():  # never leave stray processes behind, even when a test fails
            if alive(pid):
                subprocess.run(["taskkill", "/PID", str(pid), "/F"], capture_output=True)

    def program(self, name: str) -> list:
        body = textwrap.dedent(PROGRAMS[name])
        src = (
            "import os, subprocess, sys, time\n"
            f"OUT = {str(self.out)!r}\nCHILD = {CHILD!r}\n"
            "open(os.path.join(OUT, f'{os.getpid()}.pid'), 'w').close()\n"
            "def start_child():\n    return subprocess.Popen([sys.executable, '-c', CHILD, OUT])\n" + body
        )
        path = self.dir / f"{name}.py"
        path.write_text(src, encoding="utf-8")
        return [sys.executable, str(path)]

    def pids(self) -> list:
        return [int(p.stem) for p in self.out.glob("*.pid")] if self.out.exists() else []

    def start(self, name: str) -> subprocess.Popen:
        proc = winjob.popen_contained(self.program(name), stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                      stderr=subprocess.PIPE, creationflags=FLAGS)
        self.started.append(proc)
        return proc

    def wait_for(self, cond, secs=15.0):
        end = time.monotonic() + secs
        while time.monotonic() < end:
            if cond():
                return True
            time.sleep(0.05)
        return False

    def assert_none_alive(self):
        time.sleep(0.3)
        left = [p for p in self.pids() if alive(p)]
        self.assertEqual(left, [], f"processes still running: {left}")


@unittest.skipUnless(sys.platform == "win32", "Job Objects are Windows-only")
class JobContainment(_ProcessTest):
    def test_the_cli_runs_after_being_resumed_inside_its_job(self):
        proc = self.start("one_child")
        self.assertTrue(winjob.has_job(proc))
        self.assertTrue(self.wait_for(lambda: len(self.pids()) >= 2), "the resumed CLI ran and started its child")
        ext.kill_tree(proc)
        proc.wait(10)
        winjob.release(proc)
        self.assert_none_alive()

    def test_stop_ends_children_that_are_being_created_at_that_moment(self):
        proc = self.start("spawner")
        self.assertTrue(self.wait_for(lambda: len(self.pids()) >= 15))
        ext.kill_tree(proc)
        proc.wait(10)
        seen = len(self.pids())
        self.assert_none_alive()
        self.assertGreaterEqual(seen, 15)
        winjob.release(proc)

    def test_a_child_cannot_leave_the_job(self):
        proc = self.start("breakaway")
        self.assertTrue(self.wait_for(lambda: (self.out / "breakaway.refused").exists() or (self.out / "breakaway.ok").exists()))
        self.assertTrue((self.out / "breakaway.refused").exists(), "starting a process outside the job is refused")
        ext.kill_tree(proc)
        proc.wait(10)
        winjob.release(proc)
        self.assert_none_alive()

    def test_ending_the_run_ends_a_child_the_cli_left_behind(self):
        proc = self.start("leaves_child")
        proc.wait(30)  # the CLI itself has exited normally, after its child registered
        self.assertEqual(len(self.pids()), 2)
        left_child = [p for p in self.pids() if alive(p)]
        self.assertTrue(left_child, "a child outlived the CLI")
        winjob.release(proc)  # what run() does when the run ends
        self.assert_none_alive()

    def test_kill_after_the_cli_exited_still_ends_its_child(self):
        proc = self.start("leaves_child")
        proc.wait(30)
        self.assertTrue(any(alive(p) for p in self.pids()), "the child outlived the CLI")
        ext.kill_tree(proc)  # an emergency stop that arrives after the CLI itself ended
        self.assert_none_alive()
        winjob.release(proc)

    def test_a_failed_setup_refuses_the_start_and_leaves_nothing_running(self):
        made = []
        real_popen = subprocess.Popen

        def popen(*a, **kw):
            p = real_popen(*a, **kw)
            made.append(p)
            return p

        with mock.patch.object(winjob, "_assign", side_effect=winjob.JobSetupFailed("AssignProcessToJobObject failed")), \
                mock.patch.object(winjob.subprocess, "Popen", popen):
            with self.assertRaises(winjob.JobSetupFailed):
                winjob.popen_contained(self.program("one_child"), stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                       stderr=subprocess.PIPE, creationflags=FLAGS)
        self.assertEqual(len(made), 1)
        self.assertFalse(alive(made[0].pid), "the suspended process is not left behind")
        self.assertEqual(self.pids(), [], "it never ran: it was still suspended")

    def test_release_and_terminate_on_the_same_process_from_two_threads(self):
        for _ in range(20):
            proc = self.start("one_child")
            self.wait_for(lambda: len(self.pids()) >= 1, 5)
            t = threading.Thread(target=winjob.release, args=(proc,))
            t.start()
            winjob.terminate(proc)  # must not use a handle that release() already closed
            t.join(5)
            proc.wait(10)
        self.assert_none_alive()


@unittest.skipUnless(sys.platform == "win32", "Job Objects are Windows-only")
class RunnerUsesTheJob(_ProcessTest):
    """The same guarantees through ExternalAIRunner.run, the path a meeting takes."""

    def runner(self, name: str, halted: dict):
        store = ForemanStore(db_path=str(self.dir / "r.db"))
        store.seed_defaults_if_empty()
        prog = self.program(name)
        r = ext.ExternalAIRunner(store, rooms_dir=self.dir / "rooms", is_halted=lambda pid: halted["v"],
                                 resolver=lambda h: prog, memory=lambda: 8.0)  # default popen and killer: the real ones
        r.status = lambda h, refresh=False: {"available": True, "version": "test", "auth": "test", "reason": ""}
        r._command = lambda harness, base, room: base  # the test program takes no CLI flags
        return r

    def test_emergency_stop_during_a_run_ends_everything(self):
        halted = {"v": False}
        r = self.runner("spawner", halted)
        out = {}
        t = threading.Thread(target=lambda: out.update(r.run("codex", "x", project_id="p", timeout=60)), daemon=True)
        t.start()
        self.assertTrue(self.wait_for(lambda: len(self.pids()) >= 10))
        halted["v"] = True
        r.kill_all(None)
        t.join(30)
        self.assertFalse(t.is_alive())
        self.assertIn("緊急停止", out["error"])
        self.assert_none_alive()

    def test_a_normal_end_leaves_nothing_behind(self):
        r = self.runner("leaves_child", {"v": False})
        started = time.monotonic()
        out = r.run("codex", "x", project_id="p", timeout=60)
        self.assertLess(time.monotonic() - started, 30, "the run ends when the CLI ends, not at its timeout")
        self.assertIsNone(out["reply"], "the test program prints no answer")
        self.assertEqual(len(self.pids()), 2, "the CLI and the child it left behind both ran")
        self.assert_none_alive()


if __name__ == "__main__":
    unittest.main()
