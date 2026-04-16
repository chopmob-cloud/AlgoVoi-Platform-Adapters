"""
Structured audit logging for every tool invocation.

Implements §10 of ALGOVOI_MCP.md — each call emits a single-line JSON
record to **stderr** (stdout is reserved for the MCP protocol frames).
Raw arguments are hashed, not logged, so secrets that somehow leak into
the argument map (e.g. a webhook_secret passed explicitly) never hit the
log file.

Format::

    {
      "timestamp":   "2026-04-16T18:04:33Z",
      "trace_id":    "a1b2c3d4e5f6",
      "tool_name":   "create_payment_link",
      "args_hash":   "sha256 prefix",
      "status":      "ok" | "error" | "rejected",
      "duration_ms": 42.18,
      "error_code":  "ValidationError"     # only on non-ok
    }
"""

from __future__ import annotations

import hashlib
import json
import secrets
import sys
import time
from typing import Any


def _hash_args(args: Any) -> str:
    """Stable, redacted 16-char SHA-256 prefix of the arguments.

    We serialise with ``sort_keys=True`` so logically identical calls hash
    to the same prefix regardless of dict ordering, and fall back to
    ``str()`` if some value is not JSON-serialisable.
    """
    try:
        payload = json.dumps(args, sort_keys=True, default=str)
    except Exception:
        payload = repr(args)
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def log_call(
    *,
    tool_name:   str,
    args:        Any,
    status:      str,
    duration_ms: float,
    error_code:  str | None = None,
) -> None:
    """
    Emit one audit record to ``sys.stderr``.

    Args:
        tool_name:   MCP tool name, e.g. "create_payment_link".
        args:        The raw argument dict (only the SHA-256 prefix is logged).
        status:      One of ``"ok"``, ``"error"``, ``"rejected"``.
        duration_ms: Wall-clock cost of the tool handler.
        error_code:  Optional short error class name (e.g. ``"ValidationError"``).
    """
    entry = {
        "timestamp":   time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "trace_id":    secrets.token_hex(8),
        "tool_name":   tool_name,
        "args_hash":   _hash_args(args),
        "status":      status,
        "duration_ms": round(float(duration_ms), 2),
    }
    if error_code:
        entry["error_code"] = error_code
    try:
        sys.stderr.write(json.dumps(entry, separators=(",", ":")) + "\n")
        sys.stderr.flush()
    except Exception:
        # Never let audit-log failures block or fail a tool call.
        pass
