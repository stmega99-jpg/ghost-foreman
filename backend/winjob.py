"""Windows Job Objects: stop a CLI together with EVERY process it started, with no window to escape.

``taskkill /T`` walks the process tree at the moment it runs, so a child that is being created at that instant can
be missed and live on. A Job Object closes that gap:

* The CLI is created SUSPENDED, put into a new job, and only then resumed. It cannot run a single instruction, so it
  cannot start a child, before it is inside the job. Every process it starts later joins the job automatically
  (this job grants no breakaway).
* Stopping is ``TerminateJobObject``: one call ends every process in the job, including one created a moment ago.
* The job is created with ``KILL_ON_JOB_CLOSE``. Closing its handle when the run ends (``release``) ends anything
  the CLI left behind, and if the Gateway process itself dies Windows closes the handle and does the same.

If any step fails the process is terminated and the start is refused: a CLI is never run without this protection.
Only documented Win32 APIs are used (kernel32: job objects, Toolhelp32 thread snapshot, ResumeThread).
"""

from __future__ import annotations

import ctypes
import subprocess
import sys
import threading
from ctypes import wintypes
from typing import Any, List

IS_WINDOWS = sys.platform == "win32"

CREATE_SUSPENDED = 0x00000004
JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000
JOB_OBJECT_EXTENDED_LIMIT_INFORMATION_CLASS = 9
PROCESS_SET_QUOTA = 0x0100
PROCESS_TERMINATE = 0x0001
THREAD_SUSPEND_RESUME = 0x0002
TH32CS_SNAPTHREAD = 0x00000004
INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value

_ATTR = "_gf_job"  # the job handle, kept on the Popen object for kill / release


class JobSetupFailed(RuntimeError):
    pass


if IS_WINDOWS:
    class _IO_COUNTERS(ctypes.Structure):
        _fields_ = [(n, ctypes.c_ulonglong) for n in ("ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
                                                      "ReadTransferCount", "WriteTransferCount", "OtherTransferCount")]

    class _BASIC_LIMIT(ctypes.Structure):
        _fields_ = [("PerProcessUserTimeLimit", ctypes.c_longlong), ("PerJobUserTimeLimit", ctypes.c_longlong),
                    ("LimitFlags", wintypes.DWORD), ("MinimumWorkingSetSize", ctypes.c_size_t),
                    ("MaximumWorkingSetSize", ctypes.c_size_t), ("ActiveProcessLimit", wintypes.DWORD),
                    ("Affinity", ctypes.c_size_t), ("PriorityClass", wintypes.DWORD), ("SchedulingClass", wintypes.DWORD)]

    class _EXTENDED_LIMIT(ctypes.Structure):
        _fields_ = [("BasicLimitInformation", _BASIC_LIMIT), ("IoInfo", _IO_COUNTERS),
                    ("ProcessMemoryLimit", ctypes.c_size_t), ("JobMemoryLimit", ctypes.c_size_t),
                    ("PeakProcessMemoryUsed", ctypes.c_size_t), ("PeakJobMemoryUsed", ctypes.c_size_t)]

    class _THREADENTRY32(ctypes.Structure):
        _fields_ = [("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD), ("th32ThreadID", wintypes.DWORD),
                    ("th32OwnerProcessID", wintypes.DWORD), ("tpBasePri", wintypes.LONG), ("tpDeltaPri", wintypes.LONG),
                    ("dwFlags", wintypes.DWORD)]

    _k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    _k32.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
    _k32.CreateJobObjectW.restype = wintypes.HANDLE
    _k32.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
    _k32.SetInformationJobObject.restype = wintypes.BOOL
    _k32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    _k32.AssignProcessToJobObject.restype = wintypes.BOOL
    _k32.TerminateJobObject.argtypes = [wintypes.HANDLE, wintypes.UINT]
    _k32.TerminateJobObject.restype = wintypes.BOOL
    _k32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    _k32.OpenProcess.restype = wintypes.HANDLE
    _k32.OpenThread.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    _k32.OpenThread.restype = wintypes.HANDLE
    _k32.ResumeThread.argtypes = [wintypes.HANDLE]
    _k32.ResumeThread.restype = wintypes.DWORD
    _k32.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
    _k32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    _k32.Thread32First.argtypes = [wintypes.HANDLE, ctypes.POINTER(_THREADENTRY32)]
    _k32.Thread32First.restype = wintypes.BOOL
    _k32.Thread32Next.argtypes = [wintypes.HANDLE, ctypes.POINTER(_THREADENTRY32)]
    _k32.Thread32Next.restype = wintypes.BOOL
    _k32.CloseHandle.argtypes = [wintypes.HANDLE]
    _k32.CloseHandle.restype = wintypes.BOOL


def _err(what: str) -> JobSetupFailed:
    return JobSetupFailed(f"{what} failed (WinError {ctypes.get_last_error()})")


def _new_job() -> int:
    job = _k32.CreateJobObjectW(None, None)
    if not job:
        raise _err("CreateJobObject")
    info = _EXTENDED_LIMIT()
    info.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
    if not _k32.SetInformationJobObject(job, JOB_OBJECT_EXTENDED_LIMIT_INFORMATION_CLASS, ctypes.byref(info), ctypes.sizeof(info)):
        e = _err("SetInformationJobObject")
        _k32.CloseHandle(job)
        raise e
    return job


def _assign(job: int, pid: int) -> None:
    h = _k32.OpenProcess(PROCESS_SET_QUOTA | PROCESS_TERMINATE, False, pid)
    if not h:
        raise _err("OpenProcess")
    try:
        if not _k32.AssignProcessToJobObject(job, h):
            raise _err("AssignProcessToJobObject")
    finally:
        _k32.CloseHandle(h)


def _thread_ids(pid: int) -> List[int]:
    snap = _k32.CreateToolhelp32Snapshot(TH32CS_SNAPTHREAD, 0)
    if not snap or snap == INVALID_HANDLE_VALUE:
        raise _err("CreateToolhelp32Snapshot")
    try:
        entry = _THREADENTRY32()
        entry.dwSize = ctypes.sizeof(entry)
        ids: List[int] = []
        ok = _k32.Thread32First(snap, ctypes.byref(entry))
        while ok:
            if entry.th32OwnerProcessID == pid:
                ids.append(entry.th32ThreadID)
            ok = _k32.Thread32Next(snap, ctypes.byref(entry))
        return ids
    finally:
        _k32.CloseHandle(snap)


def _resume(pid: int) -> None:
    resumed = 0
    for tid in _thread_ids(pid):
        h = _k32.OpenThread(THREAD_SUSPEND_RESUME, False, tid)
        if not h:
            continue
        try:
            if _k32.ResumeThread(h) != 0xFFFFFFFF:
                resumed += 1
        finally:
            _k32.CloseHandle(h)
    if not resumed:
        raise _err("ResumeThread")


def popen_contained(cmd: List[str], **kwargs: Any) -> subprocess.Popen:
    """``subprocess.Popen`` that runs *cmd* inside its own kill-on-close Job Object (Windows).

    Elsewhere it is plain ``Popen``; the caller already starts a new session there and kills the process group.
    """
    if not IS_WINDOWS:
        return subprocess.Popen(cmd, **kwargs)
    kwargs["creationflags"] = kwargs.get("creationflags", 0) | CREATE_SUSPENDED
    proc = subprocess.Popen(cmd, **kwargs)
    job = None
    try:
        job = _new_job()
        _assign(job, proc.pid)
        setattr(proc, _ATTR, job)
        _resume(proc.pid)
        return proc
    except BaseException:
        # Never leave a suspended or unprotected process behind.
        if job:
            _k32.TerminateJobObject(job, 1)
            _k32.CloseHandle(job)
            setattr(proc, _ATTR, None)
        try:
            proc.kill()
            proc.wait(timeout=10)
        except Exception:  # noqa: BLE001
            pass
        raise


# terminate() (an emergency stop, on its own thread) and release() (the run ending) can race. Both hold this lock,
# so a handle is never used after it was closed: Windows reuses handle values, and a stale one could name another
# run's job.
_HANDLE_LOCK = threading.Lock()


def has_job(proc: Any) -> bool:
    return bool(getattr(proc, _ATTR, None))


def terminate(proc: Any) -> bool:
    """End every process in *proc*'s job. False when it has no job (the caller falls back to its own kill)."""
    with _HANDLE_LOCK:
        job = getattr(proc, _ATTR, None)
        if not job:
            return False
        return bool(_k32.TerminateJobObject(job, 1))


def release(proc: Any) -> None:
    """Close the job handle. KILL_ON_JOB_CLOSE ends any process the CLI left running."""
    with _HANDLE_LOCK:
        job = getattr(proc, _ATTR, None)
        if job:
            setattr(proc, _ATTR, None)
            _k32.CloseHandle(job)
