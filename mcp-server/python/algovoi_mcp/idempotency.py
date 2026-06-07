"""
In-memory TTL cache for idempotency keys.

For an stdio-local MCP server the cache lives inside the Python process —
good enough to dedupe retries inside a single Claude Desktop / Cursor
session.  §6.4 of ALGOVOI_MCP.md mandates ``idempotency_key`` handling on
payment-execution tools; we apply it to ``create_payment_link`` since that
is the only outbound-writing tool we expose.
"""

from __future__ import annotations

from threading import Lock
from time import monotonic
from typing import Any, Optional

_DEFAULT_TTL_SECONDS = 24 * 60 * 60  # 24 h
_MAX_ENTRIES          = 1_000


class IdempotencyCache:
    """
    Thread-safe (``threading.Lock``) mapping from idempotency key → cached
    result, with a per-entry TTL.  Opportunistic sweep runs when the cache
    grows past :data:`_MAX_ENTRIES` — avoids an unbounded background task
    on what is meant to be a short-lived stdio subprocess.
    """

    def __init__(self, ttl_seconds: int = _DEFAULT_TTL_SECONDS) -> None:
        self._ttl    = int(ttl_seconds)
        self._store: dict[str, tuple[float, Any]] = {}
        self._lock   = Lock()

    def get(self, key: str) -> Optional[Any]:
        """Return the cached value for *key*, or ``None`` if absent/expired."""
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            expiry, value = entry
            if monotonic() > expiry:
                self._store.pop(key, None)
                return None
            return value

    def set(self, key: str, value: Any) -> None:
        """Store *value* under *key* with the configured TTL."""
        with self._lock:
            self._store[key] = (monotonic() + self._ttl, value)
            if len(self._store) > _MAX_ENTRIES:
                self._sweep_locked()

    def _sweep_locked(self) -> None:
        """Drop all expired entries — must be called with the lock held."""
        now = monotonic()
        expired = [k for k, (exp, _) in self._store.items() if now > exp]
        for k in expired:
            self._store.pop(k, None)

    def __len__(self) -> int:
        with self._lock:
            return len(self._store)
