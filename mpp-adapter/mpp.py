"""
AlgoVoi MPP (Machine Payments Protocol) Server Adapter

Drop-in middleware for gating APIs behind MPP payment challenges.
When a request lacks valid payment credentials, responds with
WWW-Authenticate: Payment header. When credentials are present,
verifies the on-chain transaction via the AlgoVoi facilitator.

Works with Flask, Django, FastAPI, or any WSGI/ASGI framework.
Zero pip dependencies — uses only the Python standard library.

Spec: https://paymentauth.org / https://mpp.dev

Usage:
    from mpp import MppGate

    gate = MppGate(
        api_base='https://api1.ilovechicken.co.uk',
        api_key='algv_...',
        tenant_id='uuid',
        resource_id='my-api',
    )

    # Flask
    @app.before_request
    def check_payment():
        return gate.flask_guard()

    # Or manual check
    result = gate.check(request_headers)
    if result.requires_payment:
        return result.challenge_response()

Version: 1.0.0
"""

from __future__ import annotations

import json
import ssl
import time
from base64 import b64decode, b64encode
from typing import Any, Callable, Optional
from urllib.parse import quote
from urllib.request import Request, urlopen
from urllib.error import URLError

__version__ = "1.0.0"


class MppChallenge:
    """A payment challenge to return to the client."""

    def __init__(self, realm: str, accepts: list[dict], resource_id: str):
        self.realm = realm
        self.accepts = accepts
        self.resource_id = resource_id

    def www_authenticate_header(self) -> str:
        """Build the WWW-Authenticate: Payment header value."""
        payload = {
            "realm": self.realm,
            "accepts": self.accepts,
            "resource": self.resource_id,
            "version": "1",
        }
        encoded = b64encode(json.dumps(payload).encode()).decode()
        return f'Payment realm="{self.realm}", challenge="{encoded}"'

    def as_402_headers(self) -> dict[str, str]:
        """Return headers for a 402 response."""
        return {
            "WWW-Authenticate": self.www_authenticate_header(),
            "X-Payment-Required": b64encode(json.dumps({
                "accepts": self.accepts,
                "resource": self.resource_id,
            }).encode()).decode(),
        }


class MppReceipt:
    """A verified payment receipt."""

    def __init__(self, tx_id: str, payer: str, network: str, amount: int, receipt_jwt: str = ""):
        self.tx_id = tx_id
        self.payer = payer
        self.network = network
        self.amount = amount
        self.receipt_jwt = receipt_jwt
        self.verified_at = time.time()


class MppResult:
    """Result of checking a request for MPP credentials."""

    def __init__(
        self,
        requires_payment: bool,
        challenge: Optional[MppChallenge] = None,
        receipt: Optional[MppReceipt] = None,
        error: Optional[str] = None,
    ):
        self.requires_payment = requires_payment
        self.challenge = challenge
        self.receipt = receipt
        self.error = error


class MppGate:
    """MPP payment gate — checks requests for valid payment credentials."""

    NETWORKS = {
        "algorand_mainnet": {"asset_id": 31566704, "ticker": "USDC", "network": "algorand-mainnet"},
        "voi_mainnet":      {"asset_id": 302190,   "ticker": "aUSDC", "network": "voi-mainnet"},
    }

    def __init__(
        self,
        api_base: str,
        api_key: str,
        tenant_id: str,
        resource_id: str,
        amount_microunits: int = 1000000,
        networks: Optional[list[str]] = None,
        realm: str = "API Access",
        payout_address: str = "",
    ):
        self.api_base = api_base.rstrip("/")
        self.api_key = api_key
        self.tenant_id = tenant_id
        self.resource_id = resource_id
        self.amount_microunits = amount_microunits
        self.networks = networks or ["algorand_mainnet"]
        self.realm = realm
        self.payout_address = payout_address
        self._ssl_ctx = ssl.create_default_context()

    def check(self, headers: dict[str, str]) -> MppResult:
        """
        Check a request for MPP payment credentials.

        Args:
            headers: Request headers (case-insensitive keys)

        Returns:
            MppResult — check .requires_payment to decide whether to gate
        """
        # Normalize header keys
        h = {k.lower(): v for k, v in headers.items()}

        # Look for Authorization: Payment or X-Payment header
        auth = h.get("authorization", "")
        payment_proof = h.get("x-payment", "")

        credential = None
        if auth.lower().startswith("payment "):
            credential = auth[8:].strip()
        elif payment_proof:
            credential = payment_proof.strip()

        if not credential:
            return MppResult(
                requires_payment=True,
                challenge=self._build_challenge(),
            )

        # Parse and verify credential
        try:
            decoded = json.loads(b64decode(credential))
        except (json.JSONDecodeError, Exception):
            return MppResult(requires_payment=True, challenge=self._build_challenge(), error="Invalid credential encoding")

        tx_id = decoded.get("payload", {}).get("txId", "") or decoded.get("tx_id", "")
        payer = decoded.get("payload", {}).get("payer", "") or decoded.get("payer", "")
        network = decoded.get("network", "algorand-mainnet")

        if not tx_id or len(tx_id) > 200:
            return MppResult(requires_payment=True, challenge=self._build_challenge(), error="Missing or invalid txId")

        # Verify with AlgoVoi facilitator
        receipt = self._verify_payment(tx_id, network)
        if not receipt:
            return MppResult(requires_payment=True, challenge=self._build_challenge(), error="Payment verification failed")

        return MppResult(requires_payment=False, receipt=receipt)

    def _build_challenge(self) -> MppChallenge:
        """Build an MPP challenge with all configured networks."""
        accepts = []
        for net_key in self.networks:
            cfg = self.NETWORKS.get(net_key)
            if not cfg:
                continue
            accepts.append({
                "network": cfg["network"],
                "maxAmountRequired": str(self.amount_microunits),
                "asset": str(cfg["asset_id"]),
                "payTo": self.payout_address,
            })
        return MppChallenge(realm=self.realm, accepts=accepts, resource_id=self.resource_id)

    def _verify_payment(self, tx_id: str, network: str) -> Optional[MppReceipt]:
        """Verify a payment transaction with the AlgoVoi API."""
        url = f"{self.api_base}/v1/verify"
        payload = json.dumps({
            "tx_id": tx_id,
            "network": network,
            "resource_id": self.resource_id,
            "tenant_id": self.tenant_id,
        }).encode()

        req = Request(url, data=payload, method="POST", headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
            "X-Tenant-Id": self.tenant_id,
        })
        try:
            with urlopen(req, timeout=30, context=self._ssl_ctx) as resp:
                if resp.status != 200:
                    return None
                data = json.loads(resp.read())
                if not data.get("verified"):
                    return None
                return MppReceipt(
                    tx_id=tx_id,
                    payer=data.get("payer", ""),
                    network=network,
                    amount=data.get("amount", 0),
                    receipt_jwt=data.get("receipt", ""),
                )
        except (URLError, json.JSONDecodeError, OSError):
            return None

    # ── Framework Helpers ────────────────────────────────────────────────

    def flask_guard(self) -> Optional[tuple]:
        """
        Flask before_request guard. Returns None (proceed) or a 402 response.

        Usage:
            @app.before_request
            def check_payment():
                return gate.flask_guard()
        """
        from flask import request, jsonify, make_response  # type: ignore

        result = self.check(dict(request.headers))
        if not result.requires_payment:
            return None

        resp = make_response(jsonify({
            "error": "Payment Required",
            "detail": result.error or "This endpoint requires payment via MPP.",
            "resource": self.resource_id,
        }), 402)
        for k, v in result.challenge.as_402_headers().items():
            resp.headers[k] = v
        return resp

    def django_middleware(self, get_response: Callable) -> Callable:
        """
        Django middleware factory.

        Usage in settings.py MIDDLEWARE:
            'yourapp.middleware.mpp_middleware'

        In yourapp/middleware.py:
            from mpp import MppGate
            gate = MppGate(...)
            mpp_middleware = gate.django_middleware
        """
        from django.http import JsonResponse  # type: ignore

        def middleware(request: Any) -> Any:
            headers = {k.replace("HTTP_", "").replace("_", "-").title(): v
                       for k, v in request.META.items() if k.startswith("HTTP_")}
            result = self.check(headers)
            if result.requires_payment:
                resp = JsonResponse({
                    "error": "Payment Required",
                    "detail": result.error or "This endpoint requires payment via MPP.",
                }, status=402)
                for k, v in result.challenge.as_402_headers().items():
                    resp[k] = v
                return resp
            return get_response(request)

        return middleware

    def wsgi_guard(self, environ: dict) -> Optional[tuple[str, list[tuple[str, str]], bytes]]:
        """
        WSGI guard. Returns None (proceed) or (status, headers, body) tuple.

        Usage:
            result = gate.wsgi_guard(environ)
            if result:
                status, headers, body = result
                start_response(status, headers)
                return [body]
        """
        headers = {}
        for key, value in environ.items():
            if key.startswith("HTTP_"):
                name = key[5:].replace("_", "-").title()
                headers[name] = value

        result = self.check(headers)
        if not result.requires_payment:
            return None

        resp_headers = [("Content-Type", "application/json")]
        for k, v in result.challenge.as_402_headers().items():
            resp_headers.append((k, v))

        body = json.dumps({
            "error": "Payment Required",
            "detail": result.error or "This endpoint requires payment via MPP.",
        }).encode()

        return "402 Payment Required", resp_headers, body
