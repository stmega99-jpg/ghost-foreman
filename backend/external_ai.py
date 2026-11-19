"""Claude Code / Codex as AI-meeting participants, started directly by Ghost Foreman (OUTSIDE Kiro Crew).

Why this exists: Kiro Crew 0.12.2 gives an app no way to start a run on a chosen harness (the spawn API refuses app
tokens; the app spawn SDK has no harness argument). Brainstorming across different AIs is a core feature, so - by the
owner's decision recorded in the plan (企画書 2章 / 3章D) - meetings, and ONLY meetings, may start the two CLIs directly.
Development work and progress management keep using Kiro Crew's own features.

What this module guarantees, because Kiro Crew's own guards do not apply out here:

* Text in, text out. Every tool is switched off by the CLI's own options, AND the event stream is watched: the first
  sign of a tool (Claude: a non-empty tool list or a ``tool_use`` block; Codex: any item that is not a message) kills
  the process and the run fails as a violation.
* No metered API. Claude must report ``apiKeySource: none`` (subscription sign-in) and Codex must be signed in with
  ChatGPT; otherwise the run is refused (steering rule 5). API keys are never passed: the child gets an allowlisted
  environment only.
* Emergency stop: every child is tracked and killed (whole process tree) by ``kill_all``; the meeting stop and the
  global stop both call it, and a stop in force refuses new starts.
* Memory: a start waits until enough RAM is free and at most ``MAX_CONCURRENT`` CLIs run at once.
* Record: every run is written to ``external_runs`` (CLI, version, model, time, outcome, token counts) and to
  ``llm_usage`` with the cost marked unconfirmed. The prompt itself is stored only as a hash.
* Isolation: each run starts in an empty folder, keeps no session on disk, and loads no user config / MCP / hooks.
"""

from __future__ import annotations

import ctypes
import hashlib
import json
import logging
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from .store import ForemanStore, _now_iso

logger = logging.getLogger("ghost-foreman.external")

RUNTIME = "external_cli"  # shown to the human as "Kiro Crew 外で実行"
MAX_CONCURRENT = 2
MIN_FREE_GB = 1.5
MEMORY_WAIT_SECS = 600.0
RUN_TIMEOUT_SECS = 300.0
STATUS_CACHE_SECS = 300.0
MAX_PROMPT_CHARS = 60_000
MAX_REPLY_CHARS = 20_000

# Environment the CLIs get. Nothing else is inherited (no API keys, no tokens, no app secrets).
_ENV_ALLOW = [
    "PATH", "PATHEXT", "SYSTEMROOT", "SYSTEMDRIVE", "WINDIR", "COMSPEC", "TEMP", "TMP", "USERPROFILE", "HOMEDRIVE",
    "HOMEPATH", "HOME", "APPDATA", "LOCALAPPDATA", "PROGRAMDATA", "PROGRAMFILES", "PROGRAMFILES(X86)", "PROGRAMW6432",
    "USERNAME", "USER", "LOGNAME", "OS", "NUMBER_OF_PROCESSORS", "PROCESSOR_ARCHITECTURE", "LANG", "LC_ALL", "TZ",
    "CLAUDE_CONFIG_DIR", "CODEX_HOME", "HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY", "SSL_CERT_FILE", "NODE_EXTRA_CA_CERTS",
]

# Codex features that could act on the machine or the network. All switched off for meeting runs.
_CODEX_DISABLE = [
    "shell_tool", "unified_exec", "apps", "browser_use", "browser_use_external", "computer_use", "image_generation",
    "multi_agent", "plugins", "hooks", "view_image", "sleep_tool", "tool_suggest", "goals", "in_app_browser",
    "skill_mcp_dependency_install", "code_mode_host", "remote_plugin",
]
# Codex items that are only text. Anything else (command, file change, MCP/collab tool call, web search ...) is a tool.
_CODEX_TEXT_ITEMS = {"agent_message", "reasoning", "error"}

LABELS = {"claude": "Claude Code", "codex": "Codex"}


class ExternalRunRefused(RuntimeError):
    pass


def free_memory_gb() -> Optional[float]:
    """Available physical memory, or None if it cannot be read."""
    try:
        if sys.platform == "win32":
            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong), ("ullTotalPhys", ctypes.c_ulonglong),
                            ("ullAvailPhys", ctypes.c_ulonglong), ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                            ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong), ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]

            st = MEMORYSTATUSEX()
            st.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(st)):
                return st.ullAvailPhys / 1024**3
            return None
        with open("/proc/meminfo", encoding="ascii") as f:
            for line in f:
                if line.startswith("MemAvailable:"):
                    return int(line.split()[1]) / 1024**2
    except Exception:  # noqa: BLE001
        return None
    return None


def child_env() -> Dict[str, str]:
    return {k: os.environ[k] for k in _ENV_ALLOW if k in os.environ}


def _npm_dir() -> Optional[Path]:
    appdata = os.environ.get("APPDATA")
    return Path(appdata) / "npm" if appdata else None


def resolve_command(harness: str) -> Optional[List[str]]:
    """The real executable to start (never a .cmd/.ps1 shim, so no shell ever parses an argument)."""
    npm = _npm_dir()
    if harness == "claude":
        if npm:
            exe = npm / "node_modules" / "@anthropic-ai" / "claude-code" / "bin" / "claude.exe"
            if exe.is_file():
                return [str(exe)]
        found = shutil.which("claude")
        if found and not found.lower().endswith((".cmd", ".bat", ".ps1")):
            return [found]
        return None
    if harness == "codex":
        if npm:
            js = npm / "node_modules" / "@openai" / "codex" / "bin" / "codex.js"
            node = shutil.which("node")
            if js.is_file() and node:
                return [node, str(js)]
        found = shutil.which("codex")
        if found and not found.lower().endswith((".cmd", ".bat", ".ps1")):
            return [found]
        return None
    return None


def kill_tree(proc: subprocess.Popen) -> None:
    if proc.poll() is not None:
        return
    try:
        if sys.platform == "win32":
            subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True, timeout=20)
        else:
            os.killpg(proc.pid, signal.SIGKILL)
    except Exception:  # noqa: BLE001
        pass
    try:
        proc.kill()
    except Exception:  # noqa: BLE001
        pass


class ExternalAIRunner:
    def __init__(self, store: ForemanStore, rooms_dir: Optional[Path] = None, is_halted: Optional[Callable[[Optional[str]], bool]] = None,
                 resolver: Callable[[str], Optional[List[str]]] = resolve_command, memory: Callable[[], Optional[float]] = free_memory_gb,
                 popen: Callable[..., Any] = subprocess.Popen, killer: Callable[[Any], None] = kill_tree) -> None:
        self.store = store
        self.rooms_dir = rooms_dir or Path(tempfile.gettempdir()) / "ghost-foreman-meeting-rooms"
        self.is_halted = is_halted or (lambda project_id: False)
        self._resolve = resolver
        self._memory = memory
        self._popen = popen
        self._kill = killer
        self._lock = threading.Lock()
        self._procs: Dict[str, Dict[str, Any]] = {}  # run_id -> {"proc", "project_id"}
        self._status_cache: Dict[str, tuple] = {}
        self._ensure_table()

    def _ensure_table(self) -> None:
        with self.store._conn() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS external_runs (
                    id TEXT PRIMARY KEY, meeting_id TEXT NOT NULL DEFAULT '', project_id TEXT NOT NULL DEFAULT '',
                    tag TEXT NOT NULL DEFAULT '', harness TEXT NOT NULL, runtime TEXT NOT NULL DEFAULT 'external_cli',
                    command TEXT NOT NULL DEFAULT '', cli_version TEXT NOT NULL DEFAULT '', model TEXT NOT NULL DEFAULT '',
                    auth TEXT NOT NULL DEFAULT '', status TEXT NOT NULL, error TEXT NOT NULL DEFAULT '',
                    started_at TEXT NOT NULL, ended_at TEXT NOT NULL DEFAULT '', duration_ms INTEGER NOT NULL DEFAULT 0,
                    prompt_sha256 TEXT NOT NULL DEFAULT '', prompt_chars INTEGER NOT NULL DEFAULT 0, reply_chars INTEGER NOT NULL DEFAULT 0,
                    input_tokens INTEGER NOT NULL DEFAULT 0, output_tokens INTEGER NOT NULL DEFAULT 0,
                    free_gb_at_start REAL, pid INTEGER NOT NULL DEFAULT 0
                )
                """
            )

    # ------------------------------------------------------------------ availability
    def status(self, harness: str, refresh: bool = False) -> Dict[str, Any]:
        """Can this PC run *harness* for a meeting right now? Cached for a few minutes (each check starts the CLI)."""
        cached = self._status_cache.get(harness)
        if cached and not refresh and time.time() - cached[0] < STATUS_CACHE_SECS:
            return cached[1]
        out = {"id": harness, "label": LABELS.get(harness, harness), "runtime": RUNTIME, "available": False, "reason": "", "auth": "", "version": ""}
        cmd = self._resolve(harness)
        if not cmd:
            out["reason"] = f"{out['label']} がこのPCに見つかりません"
        else:
            try:
                out.update(self._check_auth(harness, cmd))
            except Exception as exc:  # noqa: BLE001
                out["reason"] = f"状態を確認できませんでした: {exc}"
        self._status_cache[harness] = (time.time(), out)
        return out

    def _quick(self, cmd: List[str], *args: str) -> str:
        p = subprocess.run(cmd + list(args), capture_output=True, env=child_env(), timeout=60, cwd=str(self._room("status")))
        return (p.stdout + p.stderr).decode("utf-8", "replace")

    def _check_auth(self, harness: str, cmd: List[str]) -> Dict[str, Any]:
        version = self._quick(cmd, "--version").strip().splitlines()[:1]
        res: Dict[str, Any] = {"version": version[0][:60] if version else ""}
        if harness == "claude":
            text = self._quick(cmd, "auth", "status")
            try:
                data = json.loads(text[text.find("{"): text.rfind("}") + 1])
            except ValueError:
                data = {}
            method = str(data.get("authMethod", ""))
            res["auth"] = method or "unknown"
            if not data.get("loggedIn"):
                res["reason"] = "Claude Code にログインしていません（PCで `claude` を起動して /login してください）"
            elif "api" in method.lower() and "key" in method.lower():
                res["reason"] = "Claude Code が API キー（従量課金）でログインしているため使いません"
            else:
                res["available"] = True
        else:
            text = self._quick(cmd, "login", "status")
            res["auth"] = text.strip().splitlines()[-1][:80] if text.strip() else "unknown"
            if "chatgpt" in text.lower():
                res["available"] = True
            elif "api key" in text.lower():
                res["reason"] = "Codex が API キー（従量課金）でログインしているため使いません"
            else:
                res["reason"] = "Codex にログインしていません（PCで `codex login` を実行してください）"
        return res

    # ------------------------------------------------------------------ stop
    def kill_all(self, project_id: Optional[str] = None) -> List[str]:
        """Emergency stop: kill every running CLI (or one project's). Returns the run ids."""
        # Marked under the lock, so a run that is still being started (``proc`` not set yet) sees the mark when it
        # registers its process and kills it itself. See ``run`` for the other half.
        with self._lock:
            targets = [(rid, info) for rid, info in self._procs.items() if project_id is None or info["project_id"] == project_id]
            for _, info in targets:
                info["killed"] = "緊急停止"
            procs = [info["proc"] for _, info in targets if info["proc"] is not None]
        for proc in procs:
            self._kill(proc)
        return [rid for rid, _ in targets]

    def running(self) -> int:
        with self._lock:
            return len(self._procs)

    # ------------------------------------------------------------------ run
    def _room(self, name: str) -> Path:
        room = self.rooms_dir / name
        room.mkdir(parents=True, exist_ok=True)
        return room

    def _wait_for_capacity(self, run_id: str, project_id: str, deadline: float) -> Optional[float]:
        """Wait for room, then RESERVE it: the run is tracked (``proc`` None) before its process exists.

        Counting and reserving under one lock keeps parallel starts within ``MAX_CONCURRENT``, and the reservation
        is what lets ``kill_all`` reach a run whose process is still being created.
        """
        while True:
            if self.is_halted(project_id):
                raise ExternalRunRefused("緊急停止中のため起動しません")
            free = self._memory()
            with self._lock:
                if len(self._procs) < MAX_CONCURRENT and (free is None or free >= MIN_FREE_GB):
                    self._procs[run_id] = {"proc": None, "project_id": project_id, "killed": ""}
                    return free
            if time.monotonic() > deadline:
                raise ExternalRunRefused(
                    f"メモリが足りないため起動できませんでした（空き {free:.1f}GB／必要 {MIN_FREE_GB}GB）" if free is not None and free < MIN_FREE_GB
                    else "同時に起動できる数の上限に達したまま空きませんでした"
                )
            time.sleep(2.0)

    def _command(self, harness: str, base: List[str], room: Path) -> List[str]:
        if harness == "claude":
            return base + ["-p", "--output-format", "stream-json", "--verbose", "--tools", "", "--strict-mcp-config",
                           "--mcp-config", '{"mcpServers":{}}', "--setting-sources", "project", "--disable-slash-commands",
                           "--no-session-persistence", "--permission-mode", "dontAsk"]
        args = base + ["exec", "--json", "--ephemeral", "--skip-git-repo-check", "--ignore-user-config", "--ignore-rules",
                       "--sandbox", "read-only", "-C", str(room), "-c", 'web_search="disabled"', "-c", 'approval_policy="never"']
        for f in _CODEX_DISABLE:
            args += ["--disable", f]
        return args + ["-"]

    def run(self, harness: str, prompt: str, *, meeting_id: str = "", project_id: str = "", tag: str = "",
            timeout: float = RUN_TIMEOUT_SECS) -> Dict[str, Any]:
        """Run one prompt; never raises. Returns {reply, error, ran_on, runtime, run_id, model, violation}."""
        run_id = f"ext-{uuid.uuid4().hex[:12]}"
        result: Dict[str, Any] = {"reply": None, "error": "", "ran_on": harness, "runtime": RUNTIME, "run_id": run_id, "model": "", "violation": ""}
        prompt = prompt[:MAX_PROMPT_CHARS]
        started = time.monotonic()
        row = {"id": run_id, "meeting_id": meeting_id, "project_id": project_id, "tag": tag, "harness": harness, "status": "starting",
               "started_at": _now_iso(), "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(), "prompt_chars": len(prompt)}
        self._write(row)
        try:
            st = self.status(harness)
            row["cli_version"], row["auth"] = st.get("version", ""), st.get("auth", "")
            if not st["available"]:
                raise ExternalRunRefused(st["reason"] or f"{LABELS.get(harness, harness)} は使えません")
            row["free_gb_at_start"] = self._wait_for_capacity(run_id, project_id, time.monotonic() + MEMORY_WAIT_SECS)
            room: Optional[Path] = None
            try:  # from here the run is reserved in self._procs; every exit below releases it
                info = self._procs[run_id]
                room = self._room(run_id)
                cmd = self._command(harness, self._resolve(harness) or [], room)
                row["command"] = Path(cmd[0]).name + (" " + Path(cmd[1]).name if len(cmd) > 1 and cmd[1].endswith(".js") else "")
                kwargs: Dict[str, Any] = {"stdin": subprocess.PIPE, "stdout": subprocess.PIPE, "stderr": subprocess.PIPE, "cwd": str(room), "env": child_env()}
                if sys.platform == "win32":
                    kwargs["creationflags"] = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) | getattr(subprocess, "CREATE_NO_WINDOW", 0)
                else:
                    kwargs["start_new_session"] = True
                # Last check before creating the process: a stop that has landed since the capacity check starts nothing.
                with self._lock:
                    stopped = bool(info["killed"])
                if stopped or self.is_halted(project_id):
                    raise ExternalRunRefused("緊急停止中のため起動しません")
                proc = self._popen(cmd, **kwargs)
                # A stop can land while the process is being created. kill_all marks the reservation under this lock
                # and the stop sets its hold before calling kill_all, so after this block either kill_all sees the
                # process, or this run sees the mark or the hold and kills the process itself. Nothing in between.
                with self._lock:
                    info["proc"] = proc
                    stop_now = bool(info["killed"])
                if not stop_now and self.is_halted(project_id):
                    stop_now = True
                if stop_now:
                    info["killed"] = info["killed"] or "緊急停止"
                    self._kill(proc)
                    try:
                        proc.wait(timeout=30)
                    except Exception:  # noqa: BLE001 - kill_tree already forced it; this only reaps
                        pass
                row["pid"], row["status"] = getattr(proc, "pid", 0), "running"
                self._write(row)
                if not stop_now:
                    self._feed_and_watch(harness, proc, prompt, result, timeout, info)
            finally:
                with self._lock:
                    self._procs.pop(run_id, None)
                if room is not None:
                    shutil.rmtree(room, ignore_errors=True)
            if info["killed"]:
                result["reply"] = None
                result["error"] = result["error"] or f"{info['killed']}により終了しました"
        except ExternalRunRefused as exc:
            result["error"] = str(exc)
        except Exception as exc:  # noqa: BLE001
            logger.exception("external run failed")
            result["error"] = f"起動できませんでした: {exc}"
        row.update(
            status="violation" if result["violation"] else ("ok" if result["reply"] is not None and not result["error"] else "failed"),
            error=(result["violation"] or result["error"])[:400], ended_at=_now_iso(), duration_ms=int((time.monotonic() - started) * 1000),
            model=result.get("model", "")[:80], reply_chars=len(result["reply"] or ""),
            input_tokens=result.get("input_tokens", 0), output_tokens=result.get("output_tokens", 0),
        )
        self._write(row)
        self._record_usage(harness, row)
        return result

    def _feed_and_watch(self, harness: str, proc: Any, prompt: str, result: Dict[str, Any], timeout: float, info: Dict[str, Any]) -> None:
        def feed() -> None:
            try:
                proc.stdin.write(prompt.encode("utf-8"))
                proc.stdin.close()
            except Exception:  # noqa: BLE001
                pass

        threading.Thread(target=feed, daemon=True).start()
        def on_timeout() -> None:
            info["killed"] = f"{int(timeout)}秒のタイムアウト"
            self._kill(proc)

        timer = threading.Timer(timeout, on_timeout)
        timer.daemon = True
        timer.start()
        texts: List[str] = []
        try:
            for raw in proc.stdout:
                line = raw.decode("utf-8", "replace").strip()
                if not line:
                    continue
                try:
                    ev = json.loads(line)
                except ValueError:
                    continue
                violation = self._claude_event(ev, result, texts) if harness == "claude" else self._codex_event(ev, result, texts)
                if violation:
                    result["violation"] = violation
                    result["error"] = violation
                    result["reply"] = None
                    self._kill(proc)
                    break
            proc.wait(timeout=30)
        finally:
            timer.cancel()
        if result["violation"] or info["killed"]:
            return
        if result["reply"] is None and not result["error"]:
            if harness == "codex" and texts:
                result["reply"] = texts[-1][:MAX_REPLY_CHARS]
            else:
                err = proc.stderr.read().decode("utf-8", "replace")[-300:] if proc.stderr else ""
                result["error"] = f"返答がありませんでした（終了コード {proc.returncode}）{(': ' + err.strip()) if err.strip() else ''}"

    @staticmethod
    def _claude_event(ev: Dict[str, Any], result: Dict[str, Any], texts: List[str]) -> str:
        t = ev.get("type")
        if t == "system" and ev.get("subtype") == "init":
            result["model"] = str(ev.get("model", ""))
            if ev.get("tools"):
                return "ツールが有効な状態で起動したため停止しました: " + ", ".join(map(str, ev["tools"]))[:200]
            if ev.get("mcp_servers"):
                return "外部ツール(MCP)が読み込まれたため停止しました"
            if str(ev.get("apiKeySource", "none")) != "none":
                return f"API キー（従量課金, {ev.get('apiKeySource')}）で動こうとしたため停止しました"
        elif t == "assistant":
            for block in (ev.get("message") or {}).get("content") or []:
                if isinstance(block, dict) and block.get("type") in ("tool_use", "server_tool_use", "mcp_tool_use"):
                    return f"ツールを使おうとしたため停止しました（{block.get('name', '?')}）"
        elif t == "result":
            usage = ev.get("usage") or {}
            result["input_tokens"] = int(usage.get("input_tokens", 0) or 0)
            result["output_tokens"] = int(usage.get("output_tokens", 0) or 0)
            text = str(ev.get("result") or "")
            if ev.get("is_error"):
                result["error"] = text[:300] or "Claude Code がエラーを返しました"
            else:
                result["reply"] = text[:MAX_REPLY_CHARS]
        return ""

    @staticmethod
    def _codex_event(ev: Dict[str, Any], result: Dict[str, Any], texts: List[str]) -> str:
        t = str(ev.get("type", ""))
        item = ev.get("item") if isinstance(ev.get("item"), dict) else None
        if item is not None:
            kind = str(item.get("type", ""))
            if kind not in _CODEX_TEXT_ITEMS:
                return f"ツールを使おうとしたため停止しました（{kind}）"
            if kind == "agent_message" and t == "item.completed":
                texts.append(str(item.get("text", "")))
        elif t == "turn.completed":
            usage = ev.get("usage") or {}
            result["input_tokens"] = int(usage.get("input_tokens", 0) or 0)
            result["output_tokens"] = int(usage.get("output_tokens", 0) or 0)
            if texts:
                result["reply"] = texts[-1][:MAX_REPLY_CHARS]
        elif t in ("turn.failed", "error"):
            err = ev.get("error")
            msg = ev.get("message") or (err.get("message") if isinstance(err, dict) else err)
            result["error"] = str(msg or ev)[:300]
        return ""

    # ------------------------------------------------------------------ records
    def _write(self, row: Dict[str, Any]) -> None:
        cols = list(row)
        with self.store._conn() as conn:
            conn.execute(
                f"INSERT INTO external_runs ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))}) "
                f"ON CONFLICT(id) DO UPDATE SET {', '.join(f'{c}=excluded.{c}' for c in cols if c != 'id')}",
                [row[c] for c in cols],
            )

    def _record_usage(self, harness: str, row: Dict[str, Any]) -> None:
        try:
            with self.store._conn() as conn:
                conn.execute(
                    "INSERT INTO llm_usage (ts, provider_id, model, task, input_tokens, output_tokens, cost_usd, cost_basis, ok, note) VALUES (?, ?, ?, ?, ?, ?, NULL, ?, ?, ?)",
                    (_now_iso(), f"{harness}-cli", row.get("model", ""), "meeting", row.get("input_tokens", 0), row.get("output_tokens", 0),
                     "Kiro Crew外で実行 / サブスクリプションのCLI（請求額は未確認）", 1 if row.get("status") == "ok" else 0, (row.get("error") or "")[:200]),
                )
        except Exception:  # noqa: BLE001 - the usage table may not exist in old databases; the run record is primary
            logger.debug("usage record failed", exc_info=True)

    def recent(self, limit: int = 30) -> List[Dict[str, Any]]:
        with self.store._conn() as conn:
            return [dict(r) for r in conn.execute("SELECT * FROM external_runs ORDER BY started_at DESC LIMIT ?", (limit,)).fetchall()]
