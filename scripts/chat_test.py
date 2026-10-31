#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Part 491: CLI helper to send a prompt to /api/agent/stream and print SSE events.
Usage: python scripts/chat_test.py "What is 123 * 456?"
"""
import sys
import os
import json
import argparse
from pathlib import Path

# Load .env
env_path = Path(__file__).parent.parent / ".env"
if env_path.exists():
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ[k.strip()] = v.strip()

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from fastapi.testclient import TestClient
from sunnyware.main import app


def main():
    parser = argparse.ArgumentParser(description="Test /api/agent/stream")
    parser.add_argument("prompt", help="Prompt to send")
    parser.add_argument("--session", default="cli-test", help="Session ID")
    args = parser.parse_args()

    print("Prompt: %s" % args.prompt)
    print("Session: %s\n" % args.session)

    with TestClient(app) as client:
        with client.stream("POST", "/api/agent/stream", json={
            "input": args.prompt,
            "session_id": args.session,
        }) as resp:
            if resp.status_code != 200:
                print("HTTP %s: %s" % (resp.status_code, resp.read().decode()[:300]))
                sys.exit(1)

            for line in resp.iter_lines():
                if not line:
                    continue
                if isinstance(line, bytes):
                    line = line.decode("utf-8", errors="replace")
                if not line.startswith("data:"):
                    continue
                payload = line[5:].strip()
                if not payload:
                    continue
                try:
                    data = json.loads(payload)
                except json.JSONDecodeError:
                    continue
                typ = data.get("type", "")
                if typ == "tool_call":
                    print("  [tool_call] %s(%s)" % (data.get("tool"), data.get("args")))
                elif typ == "tool_result":
                    print("  [tool_result] %s -> %s" % (data.get("tool"), str(data.get("result"))[:100]))
                elif typ == "answer":
                    print("  [answer] %s" % data.get("content", "")[:200])
                elif typ == "error":
                    print("  [error] %s" % data.get("error"))


if __name__ == "__main__":
    main()
