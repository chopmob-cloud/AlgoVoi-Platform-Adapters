"""
Output sanitisation for tool responses.

Two things happen before any response returns to the LLM:

  1. Sensitive keys are redacted — ``mnemonic``, ``private_key``, ``secret``,
     ``api_key``, ``webhook_secret``, ``authorization``, ``access_token``,
     ``refresh_token``, ``bearer_token``, ``password``.
     (The *checkout* ``token`` returned by ``create_payment_link`` is NOT in
     the list — it's a short opaque ID the caller needs, not a credential.)

  2. String fields are truncated to :data:`MAX_STR` to defend against
     prompt-injection payloads embedded in attacker-controlled blockchain
     data (transaction memos, NFT metadata, labels).  See §4.4 of
     ALGOVOI_MCP.md.
"""

from __future__ import annotations

from typing import Any

MAX_STR = 512

SENSITIVE_KEYS: frozenset[str] = frozenset(
    {
        "mnemonic",
        "private_key",
        "privatekey",
        "secret",
        "api_key",
        "apikey",
        "password",
        "passwd",
        "authorization",
        "auth",
        "webhook_secret",
        "webhooksecret",
        "access_token",
        "refresh_token",
        "bearer_token",
        # Env-var names too, in case something forwards them
        "algovoi_api_key",
        "algovoi_webhook_secret",
    }
)

_REDACTED = "[REDACTED]"


def scrub(obj: Any) -> Any:
    """
    Recursively sanitise ``obj`` for safe inclusion in tool responses.

    - Dict keys matched (case-insensitive, exact match) against
      :data:`SENSITIVE_KEYS` have their values replaced with ``"[REDACTED]"``.
    - String values longer than :data:`MAX_STR` are truncated with a visible
      ``"... [truncated N chars]"`` suffix.
    - Lists and nested dicts are walked recursively.
    - All other types pass through unchanged.
    """
    if isinstance(obj, dict):
        out: dict[Any, Any] = {}
        for k, v in obj.items():
            if isinstance(k, str) and k.lower() in SENSITIVE_KEYS:
                out[k] = _REDACTED
            else:
                out[k] = scrub(v)
        return out
    if isinstance(obj, list):
        return [scrub(x) for x in obj]
    if isinstance(obj, tuple):
        return tuple(scrub(x) for x in obj)
    if isinstance(obj, str) and len(obj) > MAX_STR:
        return obj[:MAX_STR] + f"... [truncated {len(obj) - MAX_STR} chars]"
    return obj
