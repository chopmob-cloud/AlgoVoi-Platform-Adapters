"""
AlgoVoi Mistral Adapter

Payment-gate the Mistral API (native mistralai SDK) using x402, MPP, or AP2
— paid in USDC on Algorand, VOI, Hedera, or Stellar.

Usage:
    from mistral_algovoi import AlgoVoiMistral

    gate = AlgoVoiMistral(
        mistral_key       = "...",                   # Mistral API key
        algovoi_key       = "algv_...",
        tenant_id         = "your-tenant-uuid",
        payout_address    = "YOUR_ALGORAND_ADDRESS",
        protocol          = "mpp",                   # "mpp" | "ap2" | "x402"
        network           = "algorand-mainnet",
        amount_microunits = 10000,                   # 0.01 USDC per call
        model             = "mistral-large-latest",  # default
    )

    # Flask
    @app.route("/ai/chat", methods=["POST"])
    def chat():
        result = gate.check(dict(request.headers), request.get_json())
        if result.requires_payment:
            return result.as_flask_response()
        return jsonify({"content": gate.complete(request.json["messages"])})

    # FastAPI
    @app.post("/ai/chat")
    async def chat(req: Request):
        body = await req.json()
        result = gate.check(dict(req.headers), body)
        if result.requires_payment:
            status, headers, body_bytes = result.as_wsgi_response()
            return Response(body_bytes, status_code=402, headers=dict(headers))
        return {"content": gate.complete(body["messages"])}

Messages (OpenAI format — Mistral accepts dicts natively):
    [
        {"role": "system",    "content": "You are a helpful assistant."},
        {"role": "user",      "content": "Hello"},
        {"role": "assistant", "content": "Hi!"},
        {"role": "user",      "content": "What can you do?"},
    ]

Models:
    mistral-large-latest    (flagship — default)
    mistral-medium-latest   (balanced)
    mistral-small-latest    (fastest / cheapest)
    codestral-latest        (code-specialised)
    open-mistral-nemo       (open-weight, 12B)
    pixtral-large-latest    (vision-capable)

Networks:
    "algorand-mainnet"  USDC  (ASA 31566704)
    "voi-mainnet"       aUSDC (ARC200 302190)
    "hedera-mainnet"    USDC  (HTS 0.0.456858)
    "stellar-mainnet"   USDC  (Circle)

AlgoVoi docs: https://github.com/chopmob-cloud/AlgoVoi-Platform-Adapters
Licensed under the Business Source License 1.1 — see LICENSE for details.

Version: 1.1.0
"""

from __future__ import annotations

import os
import sys
import json
import threading
from typing import Any, Optional

__version__ = "1.1.0"

_API_BASE = "https://api1.ilovechicken.co.uk"

NETWORKS = [
    "algorand-mainnet",
    "voi-mainnet",
    "hedera-mainnet",
    "stellar-mainnet",
    "base-mainnet",
    "solana-mainnet",
    "tempo-mainnet",
]

PROTOCOLS = ["x402", "mpp", "ap2"]

_SNAKE = {
    "algorand-mainnet": "algorand_mainnet",
    "voi-mainnet":      "voi_mainnet",
    "hedera-mainnet":   "hedera_mainnet",
    "stellar-mainnet":  "stellar_mainnet",
    "base-mainnet":     "base_mainnet",
    "solana-mainnet":   "solana_mainnet",
    "tempo-mainnet":    "tempo_mainnet",
}

_ADAPTERS_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _add_path(subdir: str) -> None:
    p = os.path.join(_ADAPTERS_ROOT, subdir)
    if p not in sys.path:
        sys.path.insert(0, p)


# ── Result wrapper ────────────────────────────────────────────────────────────

class MistralAiResult:
    """
    Unified payment check result for all three protocols.

    Attributes:
        requires_payment: True if caller must pay before proceeding
        receipt:          MppReceipt on MPP success (.payer, .tx_id, .amount)
        mandate:          Ap2Mandate on AP2 success (.payer_address, .network, .tx_id)
        error:            Error string if verification failed
    """

    def __init__(self, inner: Any):
        self._inner = inner
        self.requires_payment: bool = inner.requires_payment
        self.receipt  = getattr(inner, "receipt",  None)
        self.mandate  = getattr(inner, "mandate",  None)
        self.error: Optional[str] = getattr(inner, "error", None)

    def as_flask_response(self) -> tuple:
        if hasattr(self._inner, "as_flask_response"):
            return self._inner.as_flask_response()
        if hasattr(self._inner, "as_wsgi_response"):
            _, wsgi_headers, body_bytes = self._inner.as_wsgi_response()
            return body_bytes.decode(), 402, dict(wsgi_headers)
        body = json.dumps({"error": "Payment Required", "detail": self.error or ""})
        return body, 402, {"Content-Type": "application/json"}

    def as_wsgi_response(self) -> tuple[str, list, bytes]:
        if hasattr(self._inner, "as_wsgi_response"):
            return self._inner.as_wsgi_response()
        body = json.dumps({"error": "Payment Required", "detail": self.error or ""}).encode()
        return "402 Payment Required", [("Content-Type", "application/json")], body


# ── Gate factory ──────────────────────────────────────────────────────────────

def _build_gate(
    protocol: str,
    algovoi_key: str,
    tenant_id: str,
    payout_address: str,
    network: str,
    amount_microunits: int,
    resource_id: str,
) -> Any:
    if network not in NETWORKS:
        raise ValueError(f"network must be one of {NETWORKS} — got {network!r}")
    if protocol not in PROTOCOLS:
        raise ValueError(f"protocol must be one of {PROTOCOLS} — got {protocol!r}")

    if protocol == "x402":
        _add_path("ai-adapters/openai")
        from openai_algovoi import _X402Gate  # type: ignore
        return _X402Gate(
            api_base=_API_BASE, api_key=algovoi_key, tenant_id=tenant_id,
            payout_address=payout_address, network=network,
            amount_microunits=amount_microunits,
        )

    if protocol == "mpp":
        _add_path("mpp-adapter")
        from mpp import MppGate  # type: ignore
        return MppGate(
            api_base=_API_BASE, api_key=algovoi_key, tenant_id=tenant_id,
            resource_id=resource_id, payout_address=payout_address,
            networks=[_SNAKE[network]], amount_microunits=amount_microunits,
        )

    if protocol == "ap2":
        _add_path("ap2-adapter")
        from ap2 import Ap2Gate  # type: ignore
        return Ap2Gate(
            merchant_id=tenant_id, api_base=_API_BASE, api_key=algovoi_key,
            tenant_id=tenant_id, payout_address=payout_address,
            networks=[network], amount_microunits=amount_microunits,
        )


# ── Main adapter ──────────────────────────────────────────────────────────────

class AlgoVoiMistral:
    """
    Payment-gated wrapper for the Mistral API.

    Supports x402, MPP, and AP2 payment protocols across
    Algorand, VOI, Hedera, and Stellar.

    Uses the official mistralai SDK (mistralai>=2.0.0).
    Install: pip install mistralai
    """

    def __init__(
        self,
        mistral_key:       str,
        algovoi_key:       str,
        tenant_id:         str,
        payout_address:    str,
        protocol:          str = "mpp",
        network:           str = "algorand-mainnet",
        amount_microunits: int = 10000,
        model:             str = "mistral-large-latest",
        resource_id:       str = "ai-chat",
    ):
        """
        Args:
            mistral_key:       Mistral API key
            algovoi_key:       AlgoVoi API key (algv_...)
            tenant_id:         AlgoVoi tenant UUID
            payout_address:    On-chain address to receive payments
            protocol:          Payment protocol — "mpp", "ap2", or "x402"
            network:           Chain — "algorand-mainnet", "voi-mainnet",
                               "hedera-mainnet", or "stellar-mainnet"
            amount_microunits: Price per call in USDC microunits (10000 = 0.01 USDC)
            model:             Mistral model ID (default: mistral-large-latest)
            resource_id:       Resource identifier used in MPP challenges
        """
        self._mistral_key    = mistral_key
        self._model          = model
        self._mistral_client = None   # Lazy-init on first complete() call
        self._client_lock    = threading.Lock()   # Guards _ensure_client against double-construct
        self._gate           = _build_gate(
            protocol, algovoi_key, tenant_id, payout_address,
            network, amount_microunits, resource_id,
        )

    # ── Client lifecycle ─────────────────────────────────────────────────────

    def _ensure_client(self):
        """
        Lazy-create a persistent mistralai.Mistral client. The SDK manages
        an httpx connection pool internally; reusing the client across
        complete() calls avoids the per-request socket setup.

        Thread-safe via double-checked locking — two concurrent first-calls
        can't double-construct the client.
        """
        if self._mistral_client is not None:
            return self._mistral_client
        with self._client_lock:
            if self._mistral_client is None:
                try:
                    # Public entry point per mistralai>=2.0.0 docs.
                    from mistralai.client import Mistral             # type: ignore
                except ImportError:
                    raise ImportError(
                        "The mistralai package is required: pip install mistralai"
                    )
                self._mistral_client = Mistral(api_key=self._mistral_key)
            return self._mistral_client

    def close(self) -> None:
        """
        Release the underlying httpx connection pool. Safe to call
        multiple times; exceptions from the client's close() are
        swallowed (best-effort cleanup).
        """
        with self._client_lock:
            if self._mistral_client is not None:
                try:
                    # Mistral supports the context-manager protocol, which
                    # closes the httpx transport on __exit__.
                    self._mistral_client.__exit__(None, None, None)
                except Exception:
                    pass
                self._mistral_client = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()
        return False

    # ── Payment check ─────────────────────────────────────────────────────────

    def check(self, headers: dict, body: Optional[dict] = None) -> MistralAiResult:
        """
        Check a request for valid payment credentials.

        Returns MistralAiResult. If result.requires_payment is True, return
        result.as_flask_response() or result.as_wsgi_response() immediately.
        """
        try:
            inner = self._gate.check(headers, body)
        except TypeError:
            inner = self._gate.check(headers)
        return MistralAiResult(inner)

    # ── AI completion ─────────────────────────────────────────────────────────

    def complete(
        self,
        messages: list[dict],
        model: Optional[str] = None,
        **kwargs: Any,
    ) -> str:
        """
        Call the Mistral API and return the response text.

        Args:
            messages:   OpenAI-format message list. Mistral accepts dicts
                        with role ∈ {"system", "user", "assistant"} directly.
                        Recognised roles: system / user / assistant. Unknown
                        roles (e.g. "tool", "function") are silently skipped —
                        we don't map them to user because that would corrupt
                        the conversation shape. This matches the Bedrock /
                        xAI pattern.
            model:      Override the default model
            **kwargs:   Additional keyword arguments forwarded to
                        client.chat.complete() (e.g. temperature, max_tokens,
                        response_format, tools).

        Returns:
            The assistant's reply as a plain string.
        """
        client = self._ensure_client()

        # Filter messages to only known roles — Mistral's typed-message
        # validation would reject unknown roles anyway, but we want the
        # silent-skip behaviour for consistency with the other adapters.
        mistral_messages = []
        for msg in messages:
            role    = msg.get("role") or "user"   # missing role → user
            content = msg.get("content", "")
            if role in ("system", "user", "assistant"):
                mistral_messages.append({"role": role, "content": content})
            # else: unknown role, skip silently.

        resp = client.chat.complete(
            model=model or self._model,
            messages=mistral_messages,
            **kwargs,
        )
        # Response shape: resp.choices[0].message.content
        return str(resp.choices[0].message.content)

    # ── Flask convenience ─────────────────────────────────────────────────────

    def flask_guard(
        self,
        messages_key: str = "messages",
        model: Optional[str] = None,
        **kwargs: Any,
    ):
        """
        Flask route handler — checks payment then calls Mistral.

        Usage:
            @app.route("/ai/chat", methods=["POST"])
            def chat():
                return gate.flask_guard()
        """
        from flask import request, jsonify, Response  # type: ignore

        body   = request.get_json(silent=True) or {}
        result = self.check(dict(request.headers), body)
        if result.requires_payment:
            flask_body, status, headers = result.as_flask_response()
            return Response(flask_body, status=status, headers=headers, mimetype="application/json")
        messages = body.get(messages_key, [])
        content  = self.complete(messages, model=model, **kwargs)
        return jsonify({"content": content})
