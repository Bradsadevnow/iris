"""Talking to the local model.

Targets an OpenAI-compatible model server on :1234 (e.g. LM Studio). From inside
a rootless podman container the host is reachable as host.containers.internal; on
the host it's localhost. Both are covered by the default below plus the
IRIS_LM_BASE override.
"""
from __future__ import annotations

import json
import os
import urllib.request

BASE = os.environ.get("IRIS_LM_BASE", "http://localhost:1234").rstrip("/")
MODEL = os.environ.get("IRIS_LM_MODEL", "google/gemma-4-e4b")


def chat(messages: list[dict], temperature: float = 0.7, max_tokens: int = 1024) -> str:
    body = json.dumps({
        "model": MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }).encode()
    req = urllib.request.Request(
        BASE + "/v1/chat/completions", data=body,
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as r:
        d = json.loads(r.read())
    return d["choices"][0]["message"]["content"]
