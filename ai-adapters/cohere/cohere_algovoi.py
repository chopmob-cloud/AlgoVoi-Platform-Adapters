"""
AlgoVoi Cohere Adapter

Payment-gate the Cohere API using x402, MPP, or AP2
— paid in USDC on Algorand, VOI, Hedera, or Stellar.

Usage:
    from cohere_algovoi import AlgoVoiCohere

    gate = AlgoVoiCohere(
        cohere_key        = "...",
        algovoi_key       = "algv_...",
        tenant_id         = "your-tenant-uuid",
        payout_address    = "YOUR_ALGORAND_ADDRESS",
        protocol          = "mpp",               # "mpp" | "ap2" | "x402"
        network           = "algorand-mainnet",
        amount_microunits = 10000,               # 0.01 USDC per call
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

Messages (OpenAI format — system role supported natively):
    [
        {"role": "system",    "content": "You are a helpful assistant."},
        {"role": "user",      "content": "Hello"},
        {"role": "assistant", "content": "Hi!"},
        {"role": "user",      "content": "What can you do?"},
    ]

Models:
    command-r-plus-08-2024   (most capable, default)
    command-r-08-2024        (balanced)
    command-r7b-12-2024      (fastest / lightest)

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

class CohereAiResult:
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

class AlgoVoiCohere:
    """
    Payment-gated wrapper for the Cohere API.

    Supports x402, MPP, and AP2 payment protocols across
    Algorand, VOI, Hedera, and Stellar.

    Uses Cohere ClientV2 (cohere>=5.0.0).
    Install: pip install cohere
    """

    def __init__(
        self,
        cohere_key:        str,
        algovoi_key:       str,
        tenant_id:         str,
        payout_address:    str,
        protocol:          str = "mpp",
        network:           str = "algorand-mainnet",
        amount_microunits: int = 10000,
        model:             str = "command-r-plus-08-2024",
        resource_id:       str = "ai-chat",
    ):
        """
        Args:
            cohere_key:        Cohere API key
            algovoi_key:       AlgoVoi API key (algv_...)
            tenant_id:         AlgoVoi tenant UUID
            payout_address:    On-chain address to receive payments
            protocol:          Payment protocol — "mpp", "ap2", or "x402"
            network:           Chain — "algorand-mainnet", "voi-mainnet",
                               "hedera-mainnet", or "stellar-mainnet"
            amount_microunits: Price per call in USDC microunits (10000 = 0.01 USDC)
            model:             Cohere model ID (default: command-r-plus-08-2024)
            resource_id:       Resource identifier used in MPP challenges
        """
        self._cohere_key = cohere_key
        self._model      = model
        self._gate       = _build_gate(
            protocol, algovoi_key, tenant_id, payout_address,
            network, amount_microunits, resource_id,
        )

    # ── Payment check ─────────────────────────────────────────────────────────

    def check(self, headers: dict, body: Optional[dict] = None) -> CohereAiResult:
        """
        Check a request for valid payment credentials.

        Returns CohereAiResult. If result.requires_payment is True, return
        result.as_flask_response() or result.as_wsgi_response() immediately.
        """
        try:
            inner = self._gate.check(headers, body)
        except TypeError:
            inner = self._gate.check(headers)
        return CohereAiResult(inner)

    # ── AI completion ─────────────────────────────────────────────────────────

    def complete(
        self,
        messages: list[dict],
        model: Optional[str] = None,
        **kwargs: Any,
    ) -> str:
        """
        Call the Cohere API and return the response text.

        Args:
            messages:   OpenAI-format message list. System role is passed natively
                        in the messages array — no extraction or remapping needed.
                        [{"role": "system", "content": "..."}, {"role": "user", "content": "..."}]
            model:      Override the default model
            **kwargs:   Additional keyword arguments forwarded to client.chat()

        Returns:
            The assistant's reply as a plain string.
        """
        try:
            import cohere  # type: ignore
        except ImportError:
            raise ImportError(
                "The cohere package is required: pip install cohere"
            )

        client = cohere.ClientV2(api_key=self._cohere_key)

        resp = client.chat(
            model=model or self._model,
            messages=messages,
            **kwargs,
        )
        return resp.message.content[0].text

    # ── Flask convenience ─────────────────────────────────────────────────────

    def flask_guard(
        self,
        messages_key: str = "messages",
        model: Optional[str] = None,
        **kwargs: Any,
    ):
        """
        Flask route handler — checks payment then calls Cohere.

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
