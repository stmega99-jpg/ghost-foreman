"""AI meeting room (Spec D): independent ideas -> mutual critique -> Ghost synthesis, on real agents.

Each participant is a real Ghost Foreman-owned Kiro Crew slot. Nothing is scripted: every proposal, critique
and the final synthesis is the actual answer read back from a live session. Only the human adopting an option
turns a result into work (consultation never implements anything by itself).

The meeting runs in a background thread; its row in ``meetings`` is updated after every round so the
dashboard shows progress (status ``running`` -> ``awaiting_human_adoption`` / ``failed``).
"""

from __future__ import annotations

import json
import threading
import uuid
from typing import Any, Dict, List, Optional, Tuple

from .store import ForemanStore, _now_iso

DEFAULT_PERSPECTIVES = [
    "設計・世界観との整合性の視点",
    "実装工数・リスクの視点",
    "プレイヤー体験・面白さの視点",
]
MAX_PARTICIPANTS = 5
ROUND_TIMEOUT_SECS = 240.0

_NO_TOOLS = "ツールの実行やファイル操作はせず、考えだけで答えてください。"


def extract_json(text: str) -> Optional[Dict[str, Any]]:
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        data = json.loads(text[start : end + 1])
    except ValueError:
        return None
    return data if isinstance(data, dict) else None


def _s(value: Any, limit: int = 1200) -> str:
    return str(value if value is not None else "").strip()[:limit]


def _fmt_list(value: Any) -> str:
    if isinstance(value, list):
        return " / ".join(_s(v, 200) for v in value if v)
    return _s(value, 300)


class MeetingEngine:
    def __init__(self, store: ForemanStore, adapter: Any) -> None:
        self.store = store
        self.adapter = adapter

    # ------------------------------------------------------------------ public
    def start(self, project_id: str, topic: str, perspectives: Optional[List[str]] = None) -> Dict[str, Any]:
        labels = [p for p in (perspectives or DEFAULT_PERSPECTIVES) if isinstance(p, str) and p.strip()][:MAX_PARTICIPANTS]
        if len(labels) < 2:
            raise ValueError("a meeting needs at least 2 participants")
        meeting_id = f"mtg-{uuid.uuid4().hex[:8]}"
        speakers = [f"参加者{chr(65 + i)}（{lab}）" for i, lab in enumerate(labels)]
        summary = {"note": "実エージェントによる会議を実行中です。人間が採用ボタンを押すまで制作には移しません（仕様D）。", "live": True}
        with self.store._conn() as conn:
            conn.execute(
                "INSERT INTO meetings (id, project_id, topic, participants_json, rounds_json, summary_json, status, created_at)"
                " VALUES (?, ?, ?, ?, '[]', ?, 'running', ?)",
                (meeting_id, project_id, topic, json.dumps(speakers, ensure_ascii=False), json.dumps(summary, ensure_ascii=False), _now_iso()),
            )
        threading.Thread(target=self._run, args=(meeting_id, project_id, topic, labels, speakers), daemon=True, name=f"meeting-{meeting_id}").start()
        return self.get(meeting_id)

    def get(self, meeting_id: str) -> Dict[str, Any]:
        with self.store._conn() as conn:
            row = conn.execute("SELECT * FROM meetings WHERE id = ?", (meeting_id,)).fetchone()
        if not row:
            raise ValueError(f"Unknown meeting_id: {meeting_id}")
        d = dict(row)
        d["participants"] = json.loads(d.pop("participants_json", "[]"))
        d["rounds"] = json.loads(d.pop("rounds_json", "[]"))
        d["summary"] = json.loads(d.pop("summary_json", "{}"))
        return d

    def recover_interrupted(self) -> int:
        """After a restart, a 'running' meeting has no thread any more: mark it failed, keep what it produced."""
        with self.store._conn() as conn:
            ids = [r["id"] for r in conn.execute("SELECT id FROM meetings WHERE status = 'running'").fetchall()]
        for mid in ids:
            self._finish(mid, "failed", {"note": "Gateway再起動により会議が中断されました。途中までの発言は保存されています。"}, merge=True)
        return len(ids)

    # ------------------------------------------------------------------ internals
    def _save_rounds(self, meeting_id: str, rounds: List[Dict[str, Any]]) -> None:
        with self.store._conn() as conn:
            conn.execute("UPDATE meetings SET rounds_json = ? WHERE id = ?", (json.dumps(rounds, ensure_ascii=False), meeting_id))

    def _finish(self, meeting_id: str, status: str, summary: Dict[str, Any], merge: bool = False) -> None:
        with self.store._conn() as conn:
            if merge:
                row = conn.execute("SELECT summary_json FROM meetings WHERE id = ?", (meeting_id,)).fetchone()
                base = json.loads(row["summary_json"] or "{}") if row else {}
                base.update(summary)
                summary = base
            conn.execute("UPDATE meetings SET status = ?, summary_json = ? WHERE id = ?", (status, json.dumps(summary, ensure_ascii=False), meeting_id))

    def _ask_all(self, meeting_id: str, tag: str, jobs: List[Tuple[Dict[str, Any], str]]) -> List[Tuple[Optional[str], str]]:
        """Send one prompt per slot in parallel; return each slot's real (reply, error)."""
        live = self.adapter.live
        results: List[Tuple[Optional[str], str]] = [(None, "not sent")] * len(jobs)
        events = [threading.Event() for _ in jobs]

        def make_cb(i: int):
            def _cb(reply: Optional[str], err: str) -> None:
                results[i] = (reply, err)
                events[i].set()

            return _cb

        for i, (slot, prompt) in enumerate(jobs):
            marker = f"[mtg:{meeting_id}:{tag}:{i}]"
            try:
                self.adapter.send_message(slot["id"], f"{marker}\n{prompt}", sender="ghost_foreman_meeting", resume_work=False)
                live.watch_reply(slot["live_key"], marker, make_cb(i), timeout=ROUND_TIMEOUT_SECS)
            except Exception as exc:  # noqa: BLE001
                results[i] = (None, f"send failed: {exc}")
                events[i].set()
        for ev in events:
            ev.wait(ROUND_TIMEOUT_SECS + 30)
        return results

    def _run(self, meeting_id: str, project_id: str, topic: str, labels: List[str], speakers: List[str]) -> None:
        slot_ids: List[str] = []
        try:
            for i, label in enumerate(labels):
                slot = self.adapter.create_managed_slot(
                    project_id, f"会議{chr(65 + i)}", "kiro", "会議参加者", f"AI会議: {topic}", live=True, send_intro=False
                )
                slot_ids.append(slot["id"])
            ghost = self.adapter.create_managed_slot(project_id, "会議・幽霊(整理役)", "kiro", "議事整理", f"AI会議の整理: {topic}", live=True, send_intro=False)
            slot_ids.append(ghost["id"])
            parts = [self.adapter.get_slot(sid) for sid in slot_ids[:-1]]
            rounds: List[Dict[str, Any]] = []

            # Round 1: independent ideation (participants cannot see each other)
            r1_jobs = [
                (
                    p,
                    f"あなたはAI会議の「{speakers[i]}」です。議題: {topic}\n"
                    f"他の参加者の案は見えません。あなたの視点（{labels[i]}）から、独立して具体案を1つ出してください。{_NO_TOOLS}\n"
                    '次のJSONだけを返してください: {"title":"案の名前","proposal":"150字以内の具体案","pros":["利点"],"risks":["リスク"]}',
                )
                for i, p in enumerate(parts)
            ]
            r1 = self._ask_all(meeting_id, "r1", r1_jobs)
            proposals: List[Dict[str, Any]] = []
            entries = []
            for i, (reply, err) in enumerate(r1):
                data = extract_json(reply or "") or {}
                text = (
                    f"【{_s(data.get('title'), 80)}】{_s(data.get('proposal'))}"
                    f"（利点: {_fmt_list(data.get('pros'))} / リスク: {_fmt_list(data.get('risks'))}）"
                    if data.get("proposal")
                    else (_s(reply, 1500) or f"（返答なし: {err}）")
                )
                proposals.append({"speaker": speakers[i], "text": text, "ok": bool(reply)})
                entries.append({"speaker": speakers[i], "proposal": text, "live": True})
            rounds.append({"phase": "1. 独立案出し (Independent Ideation)", "entries": entries})
            self._save_rounds(meeting_id, rounds)
            if not any(p["ok"] for p in proposals):
                raise RuntimeError("参加者から案が得られませんでした")

            # Round 2: mutual critique and refinement
            def others(i: int) -> str:
                return "\n".join(f"- {p['speaker']}: {p['text']}" for j, p in enumerate(proposals) if j != i and p["ok"])

            r2_jobs = [
                (
                    p,
                    f"AI会議の議題: {topic}\nあなたは「{speakers[i]}」です。あなたの案: {proposals[i]['text']}\n他の参加者の案:\n{others(i)}\n\n"
                    f"他案の問題点を指摘し、全体を踏まえてあなたの案を改善してください。{_NO_TOOLS}\n"
                    '次のJSONだけを返してください: {"critique":"他案への批評（200字以内）","improved_proposal":"改善した自案（150字以内）"}',
                )
                for i, p in enumerate(parts)
                if proposals[i]["ok"]
            ]
            active = [i for i, p in enumerate(proposals) if p["ok"]]
            r2 = self._ask_all(meeting_id, "r2", r2_jobs)
            critiques: List[Dict[str, Any]] = []
            entries = []
            for idx, (reply, err) in zip(active, r2):
                data = extract_json(reply or "") or {}
                text = (
                    f"批評: {_s(data.get('critique'), 600)} → 改善案: {_s(data.get('improved_proposal'), 600)}"
                    if data.get("critique") or data.get("improved_proposal")
                    else (_s(reply, 1500) or f"（返答なし: {err}）")
                )
                critiques.append({"speaker": speakers[idx], "text": text, "ok": bool(reply)})
                entries.append({"speaker": speakers[idx], "critique": text, "live": True})
            rounds.append({"phase": "2. 相互批評・改善 (Mutual Critique & Refinement)", "entries": entries})
            self._save_rounds(meeting_id, rounds)

            # Round 3: Ghost synthesis (by a separate real session that did not take part)
            transcript = "\n".join(
                [f"[独立案] {p['speaker']}: {p['text']}" for p in proposals] + [f"[批評・改善] {c['speaker']}: {c['text']}" for c in critiques]
            )
            ghost_slot = self.adapter.get_slot(slot_ids[-1])
            r3 = self._ask_all(
                meeting_id,
                "r3",
                [
                    (
                        ghost_slot,
                        f"あなたは現場監督「幽霊」として、AI会議の論点整理を行います。議題: {topic}\n会議の記録:\n{transcript}\n\n"
                        f"合意点・対立点・未決事項を整理し、人間が採用を選べる選択肢（最大4つ）にまとめてください。"
                        f"各選択肢のdetailは、その選択肢だけを読んで実装担当が作業できるよう単独で完結させ、他の選択肢のIDや番号を参照しないこと。{_NO_TOOLS}\n"
                        '次のJSONだけを返してください: {"consensus":"合意点","conflict_points":"対立点とそれぞれの根拠","unresolved":"未決事項",'
                        '"options":[{"id":"opt1","label":"選択肢の名前","detail":"採用した場合に作る内容と影響"}]}',
                    )
                ],
            )
            reply, err = r3[0]
            data = extract_json(reply or "") or {}
            options = []
            for k, o in enumerate(data.get("options") or []):
                if isinstance(o, dict) and o.get("label"):
                    options.append({"id": _s(o.get("id") or f"opt{k + 1}", 40), "label": _s(o["label"], 120), "detail": _s(o.get("detail"), 800)})
            options.append({"id": "hold_as_idea", "label": "まだ制作には移さず、アイデア帳に議事録として保存のみ行う", "detail": ""})
            if data.get("consensus") or data.get("conflict_points"):
                summary = {
                    "consensus": _s(data.get("consensus"), 1500),
                    "conflict_points": _s(data.get("conflict_points"), 1500),
                    "unresolved": _s(data.get("unresolved"), 1000),
                    "options_for_human": options,
                    "note": "実エージェントによる会議の結果です。人間が採用ボタンを押すまで勝手に実装タスクへは移しません（仕様D準拠）。",
                    "live": True,
                }
            else:
                summary = {
                    "consensus": "幽霊の論点整理を得られませんでした。各ラウンドの発言をご確認ください。",
                    "conflict_points": _s(reply, 800) or f"（返答なし: {err}）",
                    "options_for_human": options[-1:],
                    "note": "整理役の返答が構造化されていませんでした。採用は保存のみ可能です。",
                    "live": True,
                }
            self._finish(meeting_id, "awaiting_human_adoption", summary)
        except Exception as exc:  # noqa: BLE001
            self._finish(meeting_id, "failed", {"note": f"会議が失敗しました: {exc}"}, merge=True)
        finally:
            for sid in slot_ids:
                try:
                    self.adapter.retire_slot(sid)
                except Exception:  # noqa: BLE001
                    pass
