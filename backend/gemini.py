"""Gemini API client (official Google AI Studio API, user's own key).

- The key is read from the Kiro Crew secret vault (name ``GEMINI_API_KEY``) at call time, sent only in the
  ``x-goog-api-key`` header, never put in a URL or logged, and scrubbed from error text.
- The model is chosen from the live model list (names change and old ones are retired), cheapest first
  (``-flash-lite`` then ``-flash``, newest stable versions first). 503 / timeouts / 404 move on to the next model.
- HTTP 429 (free-tier quota) is NOT retried on another model: it raises ``GeminiQuotaExhausted`` so the router can
  switch provider. Nothing here can enable billing; a key from a project with billing attached would be charged by
  Google, which this code cannot detect, so the README tells the user to use an AI Studio free-tier key.
"""

from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
SECRET_NAME = "GEMINI_API_KEY"
REQUEST_TIMEOUT_SECS = 40
MODEL_LIST_TTL_SECS = 3600
MAX_MODELS_PER_CALL = 4

Transport = Callable[[str, str, Dict[str, str], Optional[Dict[str, Any]], float], Tuple[int, Dict[str, Any]]]


class GeminiError(RuntimeError):
    pass


class GeminiNoKey(GeminiError):
    """No usable key is configured."""


class GeminiAuthError(GeminiError):
    """The key was rejected (do not retry)."""


class GeminiQuotaExhausted(GeminiError):
    def __init__(self, message: str, retry_after_secs: Optional[float] = None) -> None:
        super().__init__(message)
        self.retry_after_secs = retry_after_secs


class GeminiUnavailable(GeminiError):
    """All candidate models failed with transient errors."""


class GeminiStopped(GeminiError):
    """The caller's stop check said stop: no (further) request was sent."""


@dataclass
class GeminiResult:
    text: str
    model: str
    input_tokens: int
    output_tokens: int


def _default_transport(method: str, url: str, headers: Dict[str, str], body: Optional[Dict[str, Any]], timeout: float) -> Tuple[int, Dict[str, Any]]:
    req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8") if body is not None else None, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as exc:
        try:
            return exc.code, json.loads(exc.read().decode("utf-8") or "{}")
        except ValueError:
            return exc.code, {}
    except Exception as exc:  # noqa: BLE001 - timeouts / DNS: reported as status -1
        return -1, {"error": {"message": type(exc).__name__}}


def vault_key_loader() -> Optional[str]:
    """Read the key from the Kiro Crew vault; fall back to the environment for local development."""
    try:
        from kiro_crew.secrets.vault import SecretVault

        secret = SecretVault(Path.home() / ".kiro" / "crew").get(SECRET_NAME)
        if secret is not None:
            value = secret.reveal().strip()
            if value:
                return value
    except Exception:  # noqa: BLE001 - vault unavailable (e.g. dev server): try env
        pass
    return os.environ.get(SECRET_NAME, "").strip() or None


_STABLE = re.compile(r"gemini-(\d+)(?:\.(\d+))?-flash(-lite)?")


def rank_models(names: List[str]) -> List[str]:
    """Stable flash models, cheapest tier first (lite), newest version first within a tier."""
    scored = []
    for n in names:
        m = _STABLE.fullmatch(n)
        if m:
            tier = 0 if m.group(3) else 1
            scored.append((tier, -int(m.group(1)), -int(m.group(2) or 0), n))
    return [n for *_, n in sorted(scored)]


def retry_delay_secs(error_body: Dict[str, Any]) -> Optional[float]:
    for detail in (error_body.get("error", {}) or {}).get("details", []) or []:
        delay = detail.get("retryDelay") if isinstance(detail, dict) else None
        if isinstance(delay, str) and delay.endswith("s"):
            try:
                return float(delay[:-1])
            except ValueError:
                return None
    return None


class GeminiClient:
    def __init__(self, key_loader: Callable[[], Optional[str]] = vault_key_loader, transport: Transport = _default_transport) -> None:
        self._key_loader = key_loader
        self._transport = transport
        self._models: List[str] = []
        self._models_ts = 0.0

    # -- helpers -----------------------------------------------------------
    def has_key(self) -> bool:
        try:
            return bool(self._key_loader())
        except Exception:  # noqa: BLE001
            return False

    def _call(self, method: str, path: str, body: Optional[Dict[str, Any]], key: str,
              should_stop: Optional[Callable[[], bool]] = None) -> Tuple[int, Dict[str, Any]]:
        # Checked before EVERY request, so a stop that lands while one model is answering means the next model (or
        # the model list) is never asked. A request already in flight cannot be recalled; its answer is the
        # caller's to discard.
        if should_stop is not None and should_stop():
            raise GeminiStopped("緊急停止中のため Gemini API に送信しませんでした")
        headers = {"x-goog-api-key": key, "Content-Type": "application/json"}
        return self._transport(method, f"{BASE_URL}{path}", headers, body, REQUEST_TIMEOUT_SECS)

    def _candidates(self, key: str, should_stop: Optional[Callable[[], bool]] = None) -> List[str]:
        if not self._models or time.time() - self._models_ts > MODEL_LIST_TTL_SECS:
            status, data = self._call("GET", "/models?pageSize=200", None, key, should_stop)
            if status == 200:
                names = [m["name"].replace("models/", "") for m in data.get("models", []) if "generateContent" in m.get("supportedGenerationMethods", [])]
                self._models, self._models_ts = rank_models(names), time.time()
            elif status in (400, 401, 403):
                raise GeminiAuthError(f"Gemini rejected the key (HTTP {status})")
            elif status == 429:
                raise GeminiQuotaExhausted("Gemini quota exhausted while listing models", retry_delay_secs(data))
        return self._models[:MAX_MODELS_PER_CALL]

    # -- main API ----------------------------------------------------------
    def generate(self, prompt: str, system: str = "", json_mode: bool = False, max_output_tokens: int = 1024,
                 should_stop: Optional[Callable[[], bool]] = None) -> GeminiResult:
        """*should_stop* is asked before each request (model list and every model tried); when it returns True no
        further request is sent and ``GeminiStopped`` is raised."""
        key = self._key_loader()
        if not key:
            raise GeminiNoKey("GEMINI_API_KEY is not registered in the Kiro Crew vault")
        body: Dict[str, Any] = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"maxOutputTokens": max_output_tokens, "temperature": 0.2},
        }
        if system:
            body["systemInstruction"] = {"parts": [{"text": system}]}
        if json_mode:
            body["generationConfig"]["responseMimeType"] = "application/json"
        last = "no candidate model"
        for model in self._candidates(key, should_stop):
            status, data = self._call("POST", f"/models/{model}:generateContent", body, key, should_stop)
            if status == 200:
                cand = (data.get("candidates") or [{}])[0]
                text = "".join(p.get("text", "") for p in (cand.get("content") or {}).get("parts", []))
                if not text.strip():
                    last = f"{model}: empty answer ({cand.get('finishReason', '?')})"
                    continue
                usage = data.get("usageMetadata") or {}
                return GeminiResult(text, model, int(usage.get("promptTokenCount", 0)), int(usage.get("candidatesTokenCount", 0)))
            message = str((data.get("error") or {}).get("message", ""))[:160].replace(key, "***")
            if status == 429:
                raise GeminiQuotaExhausted(f"{model}: {message}", retry_delay_secs(data))
            if status in (401, 403) or (status == 400 and "API key" in message):
                raise GeminiAuthError(f"Gemini rejected the key (HTTP {status})")
            last = f"{model}: HTTP {status} {message}"
        raise GeminiUnavailable(last)
