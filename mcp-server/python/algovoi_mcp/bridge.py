"""
Cross-Claude-session bridge — file-based message-passing between collaborating
Claude sessions on the same machine (or any host with shared filesystem).

Storage layout::

    ~/.algovoi-bridge/<channel>.jsonl

Each line is a single JSON message::

    {"id": "<26-char ulid>", "ts": "<ISO-8601-utc>", "from": "<agent>", "body": "<text>"}

Append-only — never rewrites, never deletes. A simple file lock (advisory)
keeps two writers from interleaving on the same line.

Channel names are validated by the Pydantic schema before reaching here, so
we can trust them as filesystem-safe.
"""

from __future__ import annotations

import json
import os
import secrets
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


_BRIDGE_DIR_ENV = "ALGOVOI_BRIDGE_DIR"
_DEFAULT_DIR    = Path.home() / ".algovoi-bridge"


def _bridge_dir() -> Path:
    """Resolved storage directory — env override first, then ~/.algovoi-bridge."""
    raw = os.environ.get(_BRIDGE_DIR_ENV)
    p = Path(raw) if raw else _DEFAULT_DIR
    p.mkdir(parents=True, exist_ok=True)
    return p


def _channel_path(channel: str) -> Path:
    return _bridge_dir() / f"{channel}.jsonl"


def _new_id() -> str:
    """26-char monotonic id: 13 ms + 13 random hex.  Sortable by time."""
    ms  = int(time.time() * 1000)
    rnd = secrets.token_hex(7)[:13]   # 13 hex chars = ~52 bits of entropy
    return f"{ms:013d}-{rnd}"


def send(channel: str, body: str, from_agent: Optional[str] = None) -> dict:
    """Append a message to the channel. Returns the stored record."""
    rec = {
        "id":   _new_id(),
        "ts":   datetime.now(timezone.utc).isoformat(),
        "from": from_agent or "",
        "body": body,
    }
    line = json.dumps(rec, ensure_ascii=False, separators=(",", ":")) + "\n"
    path = _channel_path(channel)

    # Append atomically (single write() call, line < pipe buf so it lands intact)
    with path.open("a", encoding="utf-8") as f:
        f.write(line)
        f.flush()

    return {
        "id":      rec["id"],
        "ts":      rec["ts"],
        "channel": channel,
        "from":    rec["from"],
        "stored":  str(path),
    }


def read(channel: str, since: Optional[str] = None, limit: int = 50) -> dict:
    """Read messages from the channel.

    - If ``since`` is empty/None: return the last ``limit`` messages.
    - If ``since`` is a message id: return all messages strictly after that id,
      capped at ``limit``.
    """
    path = _channel_path(channel)
    if not path.exists():
        return {"messages": [], "next_since": "", "channel": channel, "exhausted": True}

    msgs: list[dict] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                msgs.append(json.loads(line))
            except json.JSONDecodeError:
                continue  # skip malformed lines, don't crash

    if since:
        # Tail: keep only messages with id > since (lexicographic sort = chronological)
        msgs = [m for m in msgs if m.get("id", "") > since]
    else:
        # No watermark: return the most recent batch
        msgs = msgs[-limit:]

    truncated = len(msgs) > limit
    msgs      = msgs[:limit]

    return {
        "messages":  msgs,
        "next_since": msgs[-1]["id"] if msgs else (since or ""),
        "channel":   channel,
        "exhausted": not truncated,
    }


def wait(channel: str, since: Optional[str] = None, timeout_seconds: int = 30) -> dict:
    """Long-poll: block until at least one new message appears, or timeout.

    Returns the same shape as ``read()``. ``messages`` is empty iff the timeout
    expired before any new message was written.
    """
    deadline = time.monotonic() + timeout_seconds
    poll_interval = 0.5

    while True:
        result = read(channel, since=since, limit=50)
        if result["messages"]:
            return result
        if time.monotonic() >= deadline:
            return result  # empty messages = timed out
        time.sleep(poll_interval)
