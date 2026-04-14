"""
AlgoVoi OpenAI Adapter

Payment-gate any OpenAI (or OpenAI-compatible) API using x402, MPP, or AP2
— paid in USDC on Algorand, VOI, Hedera, or Stellar.

Usage:
    from openai_algovoi import AlgoVoiOpenAI

    gate = AlgoVoiOpenAI(
        openai_key        = "sk-...",
        algovoi_key       = "algv_...",
        tenant_id         = "your-tenant-uuid",
        payout_address    = "YOUR_ALGORAND_ADDRESS",
        protocol          = "x402",              # "x402" | "mpp" | "ap2"
        network           = "algorand-mainnet",  # see NETWORKS below
        amount_microunits = 10000,               # 0.01 USDC per call
    )

    # Flask
    @app.route("/ai/chat", methods=["POST"])
    def chat():
        result = gate.check(request.headers, request.json)
        if result.requires_payment:
            return result.as_flask_response()
        return jsonify(gate.complete(request.json["messages"]))

    # FastAPI
    @app.post("/ai/chat")
    async def chat(req: Request):
        body = await req.json()
        result = gate.check(dict(req.headers), body)
        if result.requires_payment:
            status, headers, body_bytes = result.as_wsgi_response()
            return Response(body_bytes, status_code=402, headers=dict(headers))
        return {"content": gate.complete(body["messages"])}

Networks:
    "algorand-mainnet"  USDC  (ASA 31566704)
    "voi-mainnet"       aUSDC (ARC200 302190)
    "hedera-mainnet"    USDC  (HTS 0.0.456858)
    "stellar-mainnet"   USDC  (Circle)

OpenAI-compatible APIs (pass base_url=):
    OpenAI      https://api.openai.com/v1        (default)
    Mistral     https://api.mistral.ai/v1
    Together    https://api.together.xyz/v1
    Groq        https://api.groq.com/openai/v1
    Perplexity  https://api.perplexity.ai

AlgoVoi docs: https://github.com/chopmob-cloud/AlgoVoi-Platform-Adapters
Licensed under the Business Source License 1.1 — see LICENSE for details.

Version: 1.0.0
"""

from __future__ import annotations

import base64
import json
import os
import ssl
import sys
import time
from typing import Any, Optional
from urllib.error import URLError
from urllib.request import Request, urlopen

__version__ = "1.0.0"

_API_BASE = "https://api1.ilovechicken.co.uk"

# Canonical network keys accepted by this adapter
NETWORKS = [
    "algorand-mainnet",
    "voi-mainnet",
    "hedera-mainnet",
    "stellar-mainnet",
]

PROTOCOLS = ["x402", "mpp", "ap2"]

# CAIP-2 identifiers for x402 header
_CAIP2 = {
    "algorand-mainnet": "algorand:mainnet",
    "voi-mainnet":      "voi:mainnet",
    "hedera-mainnet":   "hedera:mainnet",
    "stellar-mainnet":  "stellar:pubnet",
}

# Chain-native USDC asset IDs for x402 header
_ASSET_ID = {
    "algorand-mainnet": "31566704",
    "voi-mainnet":      "302190",
    "hedera-mainnet":   "0.0.456858",
    "stellar-mainnet":  "USDC:GA5ZSEJYB37JRC5AVCIA5MOP4RHTM335X2KGX3IHOJAPP5RE34K4KZVN",
}

# snake_case network keys used by MppGate
_SNAKE = {
    "algorand-mainnet": "algorand_mainnet",
    "voi-mainnet":      "voi_mainnet",
    "hedera-mainnet":   "hedera_mainnet",
    "stellar-mainnet":  "stellar_mainnet",
}

# Path to the adapters root (platform-adapters/)
_ADAPTERS_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _add_path(subdir: str) -> None:
    p = os.path.join(_ADAPTERS_ROOT, subdir)
    if p not in sys.path:
        sys.path.insert(0, p)


# ── Shared result ─────────────────────────────────────────────────────────────

class _Result:
    """Unified payment check result — wraps protocol-specific results."""

    def __init__(self, requires_payment: bool, inner: Any = None, error: Optional[str] = None):
        self.requires_payment = requires_payment
        self._inner = inner
        self.error = error

    def as_flask_response(self) -> tuple:
        """Return Flask-compatible (body, status, headers) tuple."""
        if self._inner is not None and hasattr(self._inner, "as_flask_response"):
            return self._inner.as_flask_response()
        body = json.dumps({"error": "Payment Required", "detail": self.error or ""})
        return body, 402, {"Content-Type": "application/json"}

    def as_wsgi_response(self) -> tuple[str, list, bytes]:
        """Return WSGI-compatible (status_str, headers_list, body_bytes) tuple."""
        if self._inner is not None and hasattr(self._inner, "as_wsgi_response"):
            return self._inner.as_wsgi_response()
        body = json.dumps({"error": "Payment Required", "detail": self.error or ""}).encode()
        return "402 Payment Required", [("Content-Type", "application/json")], body


# ── Inline x402 gate ──────────────────────────────────────────────────────────

class _X402Result:
    """Result for the inline x402 gate."""

    def __init__(self, requires_payment: bool, headers_402: Optional[dict] = None, error: Optional[str] = None):
        self.requires_payment = requires_payment
        self._headers = headers_402 or {}
        self.error = error

    def as_flask_response(self) -> tuple:
        body = json.dumps({
            "error": "Payment Required",
            "detail": self.error or "This endpoint requires an x402 payment.",
        })
        return body, 402, {**self._headers, "Content-Type": "application/json"}

    def as_wsgi_response(self) -> tuple[str, list, bytes]:
        body_str, _, header_dict = self.as_flask_response()
        return "402 Payment Required", list(header_dict.items()), body_str.encode()


class _X402Gate:
    """
    Minimal x402 server gate.

    Issues X-PAYMENT-REQUIRED challenges (spec v1) and verifies
    X-PAYMENT proofs via the AlgoVoi verify endpoint.
    """

    def __init__(
        self,
        api_base: str,
        api_key: str,
        tenant_id: str,
        payout_address: str,
        network: str,
        amount_microunits: int,
    ):
        self._api_base      = api_base.rstrip("/")
        self._api_key       = api_key
        self._tenant_id     = tenant_id
        self._payout_address = payout_address
        self._network       = network
        self._amount        = amount_microunits
        self._ssl           = ssl.create_default_context()  # nosec B310
        self._caip2         = _CAIP2[network]
        self._asset_id      = _ASSET_ID[network]

    def _payment_required_header(self) -> str:
        payload = {
            "x402Version": 1,
            "accepts": [{
                "network":            self._caip2,
                "asset":              self._asset_id,
                "amount":             str(self._amount),
                "payTo":              self._payout_address,
                "maxTimeoutSeconds":  300,
                "extra":              {},
            }],
        }
        return base64.b64encode(json.dumps(payload).encode()).decode()

    def check(self, headers: dict, body: Optional[dict] = None) -> _X402Result:
        h = {k.lower(): v for k, v in headers.items()}
        proof = h.get("x-payment") or h.get("x-payment-signature")

        if not proof:
            return _X402Result(
                requires_payment=True,
                headers_402={"X-PAYMENT-REQUIRED": self._payment_required_header()},
            )

        # Verify proof via AlgoVoi
        try:
            req_body = json.dumps({
                "x402Version": 1,
                "proof": proof,
                "network": self._caip2,
                "asset": self._asset_id,
                "amount": str(self._amount),
                "payTo": self._payout_address,
                "tenantId": self._tenant_id,
            }).encode()
            req = Request(
                f"{self._api_base}/x402/verify",
                data=req_body,
                headers={
                    "Content-Type": "application/json",
                    "X-API-Key": self._api_key,
                },
                method="POST",
            )
            with urlopen(req, timeout=15, context=self._ssl) as resp:
                result = json.loads(resp.read())
            if result.get("verified") or result.get("success"):
                return _X402Result(requires_payment=False)
            return _X402Result(
                requires_payment=True,
                headers_402={"X-PAYMENT-REQUIRED": self._payment_required_header()},
                error=result.get("error", "Payment verification failed"),
            )
        except (URLError, OSError, json.JSONDecodeError) as exc:
            return _X402Result(
                requires_payment=True,
                headers_402={"X-PAYMENT-REQUIRED": self._payment_required_header()},
                error=f"Verification error: {exc}",
            )


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
        return _X402Gate(
            api_base=_API_BASE,
            api_key=algovoi_key,
            tenant_id=tenant_id,
            payout_address=payout_address,
            network=network,
            amount_microunits=amount_microunits,
        )

    if protocol == "mpp":
        _add_path("mpp-adapter")
        from mpp import MppGate  # type: ignore
        return MppGate(
            api_base=_API_BASE,
            api_key=algovoi_key,
            tenant_id=tenant_id,
            resource_id=resource_id,
            payout_address=payout_address,
            networks=[_SNAKE[network]],
            amount_microunits=amount_microunits,
        )

    if protocol == "ap2":
        _add_path("ap2-adapter")
        from ap2 import Ap2Gate  # type: ignore
        return Ap2Gate(
            merchant_id=tenant_id,
            api_base=_API_BASE,
            api_key=algovoi_key,
            tenant_id=tenant_id,
            payout_address=payout_address,
            networks=[network],
            amount_microunits=amount_microunits,
        )


# ── Main adapter ──────────────────────────────────────────────────────────────

class AlgoVoiOpenAI:
    """
    Payment-gated wrapper for OpenAI (and compatible) APIs.

    Supports x402, MPP, and AP2 payment protocols across
    Algorand, VOI, Hedera, and Stellar.
    """

    def __init__(
        self,
        openai_key:        str,
        algovoi_key:       str,
        tenant_id:         str,
        payout_address:    str,
        protocol:          str = "x402",
        network:           str = "algorand-mainnet",
        amount_microunits: int = 10000,
        model:             str = "gpt-4o",
        base_url:          Optional[str] = None,
        resource_id:       str = "ai-chat",
    ):
        """
        Args:
            openai_key:        OpenAI (or compatible) API key
            algovoi_key:       AlgoVoi API key  (algv_...)
            tenant_id:         AlgoVoi tenant UUID
            payout_address:    On-chain address to receive payments
            protocol:          Payment protocol — "x402", "mpp", or "ap2"
            network:           Chain — "algorand-mainnet", "voi-mainnet",
                               "hedera-mainnet", or "stellar-mainnet"
            amount_microunits: Price per call in USDC microunits (10000 = 0.01 USDC)
            model:             Default AI model (e.g. "gpt-4o", "mistral-large-latest")
            base_url:          Override API base URL for OpenAI-compatible providers
            resource_id:       Resource identifier used in MPP challenges
        """
        self._openai_key = openai_key
        self._model      = model
        self._base_url   = base_url
        self._gate       = _build_gate(
            protocol, algovoi_key, tenant_id, payout_address,
            network, amount_microunits, resource_id,
        )

    # ── Payment check ─────────────────────────────────────────────────────────

    def check(self, headers: dict, body: Optional[dict] = None) -> _Result:
        """
        Check a request for valid payment credentials.

        Returns a _Result. If result.requires_payment is True, return
        result.as_flask_response() or result.as_wsgi_response() immediately.
        """
        inner = self._gate.check(headers, body)
        return _Result(
            requires_payment=inner.requires_payment,
            inner=inner,
            error=getattr(inner, "error", None),
        )

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
                      [{"role": "user", "content": "Hello"}]
            model:    Override the default model
            **kwargs: Any additional openai.chat.completions.create() params

        Returns:
            The assistant's reply as a plain string.
        """
        try:
            from openai import OpenAI as _OpenAI  # type: ignore
        except ImportError:
            raise ImportError(
                "The openai package is required: pip install openai"
            )

        client = _OpenAI(api_key=self._openai_key, base_url=self._base_url)
        resp = client.chat.completions.create(
            model=model or self._model,
            messages=messages,
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
        Flask route handler — checks payment then calls AI.

        Usage:
            @app.route("/ai/chat", methods=["POST"])
            def chat():
                return gate.flask_guard()
        """
        from flask import request, jsonify  # type: ignore

        body = request.get_json(silent=True) or {}
        result = self.check(dict(request.headers), body)
        if result.requires_payment:
            flask_body, status, headers = result.as_flask_response()
            from flask import Response
            return Response(
                flask_body,
                status=status,
                headers=headers,
                mimetype="application/json",
            )
        messages = body.get(messages_key, [])
        content  = self.complete(messages, model=model, **kwargs)
        return jsonify({"content": content})
