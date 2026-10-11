#!/usr/bin/env python3
"""Probe Azure OpenAI endpoint + deployment (no LiveKit). Loads .env from repo root."""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlencode

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
except ImportError:
    pass


def _get(url: str, api_key: str) -> tuple[int, str]:
    req = urllib.request.Request(url, headers={"api-key": api_key}, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return resp.status, resp.read().decode("utf-8", errors="replace")[:2000]
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", errors="replace")[:2000]


def main() -> int:
    endpoint = os.getenv("AZURE_OPENAI_ENDPOINT", "").rstrip("/")
    deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT", "").strip()
    api_key = os.getenv("AZURE_OPENAI_API_KEY", "").strip()

    if not endpoint or not api_key:
        print("Set AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_API_KEY in .env", file=sys.stderr)
        return 1

    print(f"Endpoint: {endpoint}")
    print(f"Deployment (from .env): {deployment or '(not set)'}\n")

    for label, path in [
        ("GA models list", "/openai/v1/models"),
        ("Legacy deployments", "/openai/deployments"),
    ]:
        if "deployments" in path:
            q = urlencode({"api-version": "2024-06-01"})
            url = f"{endpoint}{path}?{q}"
        else:
            url = f"{endpoint}{path}"
        code, body = _get(url, api_key)
        print(f"--- {label} GET {path} -> HTTP {code}")
        if code == 200:
            try:
                data = json.loads(body)
                if "data" in data and isinstance(data["data"], list):
                    ids = [str(x.get("id", x)) for x in data["data"][:20]]
                    print("  ids:", ", ".join(ids) if ids else "(empty)")
                else:
                    print("  ", body[:400])
            except json.JSONDecodeError:
                print("  ", body[:400])
        else:
            print("  ", body[:400])
        print()

    if deployment:
        for api_ver in ("2025-04-01-preview", "2024-10-01-preview"):
            q = urlencode({"api-version": api_ver})
            url = f"{endpoint}/openai/deployments/{deployment}?{q}"
            code, body = _get(url, api_key)
            print(f"--- Deployment lookup ({api_ver}) -> HTTP {code}")
            if code != 200:
                print("  ", body[:300])
            else:
                print("  OK — name matches this resource for preview API.")
            print()

    print("WebSocket paths LiveKit may use:")
    print(f"  GA:     wss://.../openai/v1/realtime?model={deployment or '<deployment>'}")
    print(
        f"  Preview: wss://.../openai/realtime?api-version=2025-04-01-preview&deployment={deployment or '<deployment>'}"
    )
    print(
        "\nIf deployment lookup is 404, fix AZURE_OPENAI_DEPLOYMENT or endpoint "
        "(Foundry → Models + endpoints → same Azure resource)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
