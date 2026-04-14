"""
AlgoVoi AP2 AI Adapter

Payment-gate any OpenAI (or OpenAI-compatible) API using AP2 v0.1
(CartMandate / PaymentMandate + AlgoVoi crypto-algo extension)
— paid in USDC on Algorand or VOI.

Usage:
    from ap2_algovoi import AlgoVoiAp2AI

    gate = AlgoVoiAp2AI(
        openai_key        = "sk-...",
        algovoi_key       = "algv_...",
        tenant_id         = "your-tenant-uuid",
        payout_address    = "YOUR_ALGORAND_ADDRESS",
        networks          = ["algorand-mainnet", "voi-mainnet"],
        amount_microunits = 10000,                  # 0.01 USDC per call
    )

    # Flask
    @app.route("/ai/chat", methods=["POST"])
    def chat():
        body   = request.get_json(silent=True) or {}
        result = gate.check(dict(request.headers), body)
        if result.requires_payment:
            return result.as_flask_response()
        # result.mandate.payer_address, .network, .tx_id available
        return jsonify({"content": gate.complete(body["messages"])})

    # FastAPI
    @app.post("/ai/chat")
    async def chat(req: Request):
        body   = await req.json()
        result = gate.check(dict(req.headers), body)
        if result.requires_payment:
            status, headers, body_bytes = result.as_wsgi_response()
            return Response(body_bytes, status_code=402, headers=dict(headers))
        return {"content": gate.complete(body["messages"])}

Networks (hyphenated AP2 keys):
    "algorand-mainnet"  USDC  (ASA 31566704)
    "voi-mainnet"       aUSDC (ARC200 302190)

Extension URI: https://api1.ilovechicken.co.uk/ap2/extensions/crypto-algo/v1

AlgoVoi docs: https://github.com/chopmob-cloud/AlgoVoi-Platform-Adapters
Licensed under the Business Source License 1.1 — see LICENSE for details.

Version: 1.0.0
"""

from __future__ import annotations

import os
import sys
from typing import Any, Optional

__version__ = "1.0.0"

_API_BASE = "https://api1.ilovechicken.co.uk"

# Path to the adapters root (platform-adapters/)
_ADAPTERS_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _add_path(subdir: str) -> None:
    p = os.path.join(_ADAPTERS_ROOT, subdir)
    if p not in sys.path:
        sys.path.insert(0, p)


# ── Result wrapper ────────────────────────────────────────────────────────────

class Ap2AiResult:
    """
    Wraps Ap2Result with AI-specific convenience.

    Attributes:
        requires_payment: True if client must pay before proceeding
        mandate:          Ap2Mandate on success — .payer_address, .network, .tx_id
        error:            Error string if verification failed
    """

    def __init__(self, inner: Any):
        self._inner = inner
        self.requires_payment: bool = inner.requires_payment
        self.mandate = getattr(inner, "mandate", None)
        self.error: Optional[str] = getattr(inner, "error", None)

    def as_flask_response(self) -> tuple:
        if hasattr(self._inner, "as_flask_response"):
            return self._inner.as_flask_response()
        import json
        body = json.dumps({"error": "Payment Required", "detail": self.error or ""})
        return body, 402, {"Content-Type": "application/json"}

    def as_wsgi_response(self) -> tuple[str, list, bytes]:
        if hasattr(self._inner, "as_wsgi_response"):
            return self._inner.as_wsgi_response()
        import json
        body = json.dumps({"error": "Payment Required", "detail": self.error or ""}).encode()
        return "402 Payment Required", [("Content-Type", "application/json")], body


# ── Main adapter ──────────────────────────────────────────────────────────────

class AlgoVoiAp2AI:
    """
    AP2 payment-gated wrapper for OpenAI (and compatible) APIs.

    Implements AP2 v0.1 CartMandate / PaymentMandate with the AlgoVoi
    crypto-algo extension for on-chain USDC payments on Algorand and VOI.
    """

    def __init__(
        self,
        openai_key:        str,
        algovoi_key:       str,
        tenant_id:         str,
        payout_address:    str,
        networks:          Optional[list[str]] = None,
        amount_microunits: int  = 10000,
        model:             str  = "gpt-4o",
        base_url:          Optional[str] = None,
        expires_seconds:   int  = 600,
    ):
        """
        Args:
            openai_key:        OpenAI (or compatible) API key
            algovoi_key:       AlgoVoi API key (algv_...)
            tenant_id:         AlgoVoi tenant UUID (used as merchant_id)
            payout_address:    On-chain address to receive payments
            networks:          AP2 network keys — hyphenated e.g. ["algorand-mainnet"]
                               (default: ["algorand-mainnet", "voi-mainnet"])
            amount_microunits: Price per call in USDC microunits (10000 = 0.01 USDC)
            model:             Default AI model (e.g. "gpt-4o", "mistral-large-latest")
            base_url:          Override API base URL for OpenAI-compatible providers
            expires_seconds:   CartMandate TTL in seconds (default: 600)
        """
        _add_path("ap2-adapter")
        from ap2 import Ap2Gate  # type: ignore

        self._openai_key = openai_key
        self._model      = model
        self._base_url   = base_url
        self._gate = Ap2Gate(
            merchant_id       = tenant_id,
            api_base          = _API_BASE,
            api_key           = algovoi_key,
            tenant_id         = tenant_id,
            amount_microunits = amount_microunits,
            networks          = networks or ["algorand-mainnet", "voi-mainnet"],
            payout_address    = payout_address,
            expires_seconds   = expires_seconds,
        )

    # ── Payment check ─────────────────────────────────────────────────────────

    def check(self, headers: dict, body: Optional[dict] = None) -> Ap2AiResult:
        """
        Check a request for a valid AP2 PaymentMandate.

        Returns Ap2AiResult. If result.requires_payment is True, return
        result.as_flask_response() or result.as_wsgi_response() immediately.
        On success, result.mandate has payer_address, network, tx_id.
        """
        return Ap2AiResult(self._gate.check(headers, body))

    # ── AI completion ─────────────────────────────────────────────────────────

    def complete(
        self,
        messages: list[dict],
        model: Optional[str] = None,
        **kwargs: Any,
    ) -> str:
        """
        Call the AI API and return the response text.

        Args:
            messages: OpenAI-format message list
            model:    Override the default model
            **kwargs: Additional openai.chat.completions.create() params

        Returns:
            The assistant's reply as a plain string.
        """
        try:
            from openai import OpenAI as _OpenAI  # type: ignore
        except ImportError:
            raise ImportError("The openai package is required: pip install openai")

        client = _OpenAI(api_key=self._openai_key, base_url=self._base_url)
        resp = client.chat.completions.create(
            model    = model or self._model,
            messages = messages,
            **kwargs,
        )
        return resp.choices[0].message.content

    # ── Flask convenience ─────────────────────────────────────────────────────

    def flask_guard(
        self,
        messages_key: str = "messages",
        model: Optional[str] = None,
        **kwargs: Any,
    ):
        """
        Flask route handler — checks AP2 payment then calls AI.

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
