"""
AlgoVoi MPP AI Adapter

Payment-gate any OpenAI (or OpenAI-compatible) API using the IETF MPP protocol
(draft-ryan-httpauth-payment) — paid in USDC on Algorand, VOI, Hedera, or Stellar.

Usage:
    from mpp_algovoi import AlgoVoiMppAI

    gate = AlgoVoiMppAI(
        openai_key        = "sk-...",
        algovoi_key       = "algv_...",
        tenant_id         = "your-tenant-uuid",
        payout_address    = "YOUR_ALGORAND_ADDRESS",
        networks          = ["algorand_mainnet"],   # snake_case MPP keys
        amount_microunits = 10000,                  # 0.01 USDC per call
        resource_id       = "ai-chat",
    )

    # Flask
    @app.route("/ai/chat", methods=["POST"])
    def chat():
        result = gate.check(dict(request.headers))
        if result.requires_payment:
            return result.as_flask_response()
        # result.receipt.payer, .amount, .tx_id available
        return jsonify({"content": gate.complete(request.json["messages"])})

    # FastAPI
    @app.post("/ai/chat")
    async def chat(req: Request):
        result = gate.check(dict(req.headers))
        if result.requires_payment:
            status, headers, body_bytes = result.as_wsgi_response()
            return Response(body_bytes, status_code=402, headers=dict(headers))
        return {"content": gate.complete((await req.json())["messages"])}

Networks (snake_case for MPP):
    "algorand_mainnet"  USDC  (ASA 31566704)
    "voi_mainnet"       aUSDC (ARC200 302190)
    "hedera_mainnet"    USDC  (HTS 0.0.456858)
    "stellar_mainnet"   USDC  (Circle)

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

class MppAiResult:
    """
    Wraps MppResult with AI-specific convenience.

    Attributes:
        requires_payment: True if client must pay before proceeding
        receipt:          MppReceipt on success — .payer, .tx_id, .amount, .method
        error:            Error string if verification failed
    """

    def __init__(self, inner: Any):
        self._inner = inner
        self.requires_payment: bool = inner.requires_payment
        self.receipt = getattr(inner, "receipt", None)
        self.error: Optional[str] = getattr(inner, "error", None)

    def as_flask_response(self) -> tuple:
        if hasattr(self._inner, "as_flask_response"):
            return self._inner.as_flask_response()
        # MppResult only has as_wsgi_response — convert to Flask tuple
        if hasattr(self._inner, "as_wsgi_response"):
            _, wsgi_headers, body_bytes = self._inner.as_wsgi_response()
            headers = dict(wsgi_headers)
            return body_bytes.decode(), 402, headers
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

class AlgoVoiMppAI:
    """
    MPP payment-gated wrapper for OpenAI (and compatible) APIs.

    Uses the IETF MPP protocol (WWW-Authenticate: Payment challenge)
    with AlgoVoi on-chain verification across all 4 supported chains.
    """

    def __init__(
        self,
        openai_key:        str,
        algovoi_key:       str,
        tenant_id:         str,
        payout_address:    str,
        networks:          Optional[list[str]] = None,
        amount_microunits: int  = 10000,
        resource_id:       str  = "ai-chat",
        realm:             str  = "AI Access",
        model:             str  = "gpt-4o",
        base_url:          Optional[str] = None,
    ):
        """
        Args:
            openai_key:        OpenAI (or compatible) API key
            algovoi_key:       AlgoVoi API key (algv_...)
            tenant_id:         AlgoVoi tenant UUID
            payout_address:    On-chain address to receive payments
            networks:          MPP network keys — snake_case e.g. ["algorand_mainnet"]
                               (default: ["algorand_mainnet"])
            amount_microunits: Price per call in USDC microunits (10000 = 0.01 USDC)
            resource_id:       MPP resource identifier shown in challenges
            realm:             Human-readable protection space name
            model:             Default AI model (e.g. "gpt-4o", "mistral-large-latest")
            base_url:          Override API base URL for OpenAI-compatible providers
        """
        _add_path("mpp-adapter")
        from mpp import MppGate  # type: ignore

        self._openai_key = openai_key
        self._model      = model
        self._base_url   = base_url
        self._gate = MppGate(
            api_base          = _API_BASE,
            api_key           = algovoi_key,
            tenant_id         = tenant_id,
            resource_id       = resource_id,
            amount_microunits = amount_microunits,
            networks          = networks or ["algorand_mainnet"],
            realm             = realm,
            payout_address    = payout_address,
        )

    # ── Payment check ─────────────────────────────────────────────────────────

    def check(self, headers: dict) -> MppAiResult:
        """
        Check a request for valid MPP payment credentials.

        Returns MppAiResult. If result.requires_payment is True, return
        result.as_flask_response() or result.as_wsgi_response() immediately.
        On success, result.receipt has payer, tx_id, amount, method.
        """
        return MppAiResult(self._gate.check(headers))

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
        Flask route handler — checks MPP payment then calls AI.

        Usage:
            @app.route("/ai/chat", methods=["POST"])
            def chat():
                return gate.flask_guard()
        """
        from flask import request, jsonify, Response  # type: ignore

        body   = request.get_json(silent=True) or {}
        result = self.check(dict(request.headers))
        if result.requires_payment:
            flask_body, status, headers = result.as_flask_response()
            return Response(flask_body, status=status, headers=headers, mimetype="application/json")
        messages = body.get(messages_key, [])
        content  = self.complete(messages, model=model, **kwargs)
        return jsonify({"content": content})
