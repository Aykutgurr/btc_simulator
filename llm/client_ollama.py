# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import os
import urllib.request
from typing import Any, Dict, List, Optional, Tuple


def _env(name: str, default: str) -> str:
    v = os.environ.get(name)
    return v.strip() if isinstance(v, str) and v.strip() else default


class OllamaClient:
    """
    Minimal Ollama chat client.
    API: POST {base_url}/api/chat
    """

    def __init__(self):
        self.base_url = _env("LLM_BASE_URL", "http://localhost:11434").rstrip("/")
        self.model = _env("LLM_MODEL", "qwen2.5:7b-instruct")
        self.temperature = float(_env("LLM_TEMPERATURE", "0.2"))
        self.max_tokens = int(_env("LLM_MAX_TOKENS", "2000"))

    def chat(self, messages: List[Dict[str, str]], *, system: Optional[str] = None) -> Tuple[str, Dict[str, Any]]:
        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": ([] if system is None else [{"role": "system", "content": system}]) + messages,
            "stream": False,
            "options": {
                "temperature": self.temperature,
                # Ollama uses num_predict; keep it bounded
                "num_predict": self.max_tokens,
            },
        }
        req = urllib.request.Request(
            f"{self.base_url}/api/chat",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=120) as resp:
            raw = resp.read().decode("utf-8")
        data = json.loads(raw)
        content = ""
        try:
            content = data.get("message", {}).get("content", "") or ""
        except Exception:
            content = ""
        return content, data

