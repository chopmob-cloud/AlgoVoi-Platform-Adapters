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

# Chain indexers for direct on-chain verification (no central API needed)
_INDEXERS = {
    "algorand-mainnet": "https://mainnet-idx.algonode.cloud/v2",
    "voi-mainnet":      "https://mainnet-idx.voi.nodely.dev/v2",
    "hedera-mainnet":   "https://mainnet-public.mirrornode.hedera.com/api/v1",
    "stellar-mainnet":  "https://horizon.stellar.org",
}

# Integer asset IDs for AVM chains (for indexer comparison)
_ASSET_ID_INT = {
    "algorand-mainnet": 31566704,
    "voi-mainnet":      302190,
}

# Stellar USDC issuer
_STELLAR_USDC_ISSUER = "GA5ZSEJYB37JRC5AVCIA5MOP4RHTM335X2KGX3IHOJAPP5RE34K4KZVN"


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
    X-PAYMENT proofs via direct on-chain indexer calls — no central
    verification API required.
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
        self._payout_address = payout_address
        self._network        = network
        self._amount         = amount_microunits
        self._ssl            = ssl.create_default_context()  # nosec B310
        self._caip2          = _CAIP2[network]
        self._asset_id       = _ASSET_ID[network]

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

    def _extract_tx_id(self, proof: str) -> Optional[str]:
        """Extract tx_id from a base64-encoded x402 proof."""
        try:
            obj = json.loads(base64.b64decode(proof + "=="))
        except Exception:
            return None
        payload = obj.get("payload") or {}
        return (
            payload.get("signature")
            or payload.get("tx_id")
            or obj.get("tx_id")
            or obj.get("txId")
        )

    def _verify_avm(self, tx_id: str) -> bool:
        """Verify Algorand or VOI payment via chain indexer."""
        indexer = _INDEXERS.get(self._network)
        if not indexer:
            return False
        try:
            req = Request(
                f"{indexer}/transactions/{tx_id}",
                headers={"Accept": "application/json"},
            )
            with urlopen(req, timeout=15, context=self._ssl) as resp:  # nosec B310
                if resp.status != 200:
                    return False
                data = json.loads(resp.read())
        except (URLError, OSError, json.JSONDecodeError):
            return False

        tx = data.get("transaction", {})
        if not tx.get("confirmed-round"):
            return False
        atx = tx.get("asset-transfer-transaction", {})
        if atx.get("receiver") != self._payout_address:
            return False
        if atx.get("amount", 0) < self._amount:
            return False
        expected_int = _ASSET_ID_INT.get(self._network)
        if expected_int and atx.get("asset-id") != expected_int:
            return False
        return True

    def _verify_hedera(self, tx_id: str) -> bool:
        """Verify Hedera USDC payment via Hedera Mirror Node."""
        base = _INDEXERS.get(self._network)
        if not base:
            return False
        if "@" in tx_id:
            account_part, time_part = tx_id.split("@", 1)
            normalised = f"{account_part}-{time_part.replace('.', '-', 1)}"
        else:
            normalised = tx_id
        try:
            req = Request(
                f"{base}/transactions/{normalised}",
                headers={"Accept": "application/json"},
            )
            with urlopen(req, timeout=15, context=self._ssl) as resp:  # nosec B310
                if resp.status != 200:
                    return False
                data = json.loads(resp.read())
        except (URLError, OSError, json.JSONDecodeError):
            return False

        transactions = data.get("transactions", [])
        if not transactions or transactions[0].get("result") != "SUCCESS":
            return False
        for transfer in transactions[0].get("token_transfers", []):
            if transfer.get("token_id") != "0.0.456858":
                continue
            if (transfer.get("account") == self._payout_address
                    and transfer.get("amount", 0) >= self._amount):
                return True
        return False

    def _verify_stellar(self, tx_id: str) -> bool:
        """Verify Stellar USDC payment via Horizon."""
        base = _INDEXERS.get(self._network)
        if not base:
            return False
        try:
            req = Request(
                f"{base}/transactions/{tx_id}/operations",
                headers={"Accept": "application/json"},
            )
            with urlopen(req, timeout=15, context=self._ssl) as resp:  # nosec B310
                if resp.status != 200:
                    return False
                data = json.loads(resp.read())
        except (URLError, OSError, json.JSONDecodeError):
            return False

        for op in data.get("_embedded", {}).get("records", []):
            if op.get("type") != "payment":
                continue
            if op.get("to") != self._payout_address:
                continue
            if op.get("asset_code") != "USDC":
                continue
            if op.get("asset_issuer") != _STELLAR_USDC_ISSUER:
                continue
            try:
                amount_microunits = int(float(op.get("amount", "0")) * 1_000_000)
            except (ValueError, TypeError):
                continue
            if amount_microunits >= self._amount:
                return True
        return False

    def _verify_on_chain(self, tx_id: str) -> bool:
        """Route to the correct chain verifier."""
        if "algorand" in self._network or "voi" in self._network:
            return self._verify_avm(tx_id)
        if "hedera" in self._network:
            return self._verify_hedera(tx_id)
        if "stellar" in self._network:
            return self._verify_stellar(tx_id)
        return False

    def check(self, headers: dict, body: Optional[dict] = None) -> _X402Result:
        h = {k.lower(): v for k, v in headers.items()}
        proof = h.get("x-payment") or h.get("x-payment-signature")

        if not proof:
            return _X402Result(
                requires_payment=True,
                headers_402={"X-PAYMENT-REQUIRED": self._payment_required_header()},
            )

        tx_id = self._extract_tx_id(proof)
        if not tx_id:
            return _X402Result(
                requires_payment=True,
                headers_402={"X-PAYMENT-REQUIRED": self._payment_required_header()},
                error="Invalid payment proof — could not extract transaction ID",
            )

        if self._verify_on_chain(tx_id):
            return _X402Result(requires_payment=False)

        return _X402Result(
            requires_payment=True,
            headers_402={"X-PAYMENT-REQUIRED": self._payment_required_header()},
            error="Payment verification failed — transaction not confirmed or amount incorrect",
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
        )  # api_base/api_key/tenant_id retained for future hosted-verify option

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
