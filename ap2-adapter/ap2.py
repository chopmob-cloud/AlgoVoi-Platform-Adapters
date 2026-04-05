"""
AlgoVoi AP2 (Agent Payment Protocol v2) Server Adapter

Drop-in middleware for accepting AP2 payment mandates from AI agents.
AP2 uses ed25519 signed credentials — no on-chain transaction required
at the point of purchase. Settlement happens asynchronously.

Spec: Google Agent Payments Protocol (AP2)

Works with Flask, Django, FastAPI, or any WSGI/ASGI framework.
Zero pip dependencies — uses only the Python standard library.

Usage:
    from ap2 import Ap2Gate

    gate = Ap2Gate(
        merchant_id='shop42',
        api_base='https://api1.ilovechicken.co.uk',
        api_key='algv_...',
        tenant_id='uuid',
    )

    # Flask
    @app.route('/api/resource', methods=['POST'])
    def resource():
        result = gate.check(request.headers, request.get_json())
        if result.requires_payment:
            return result.as_flask_response()
        # Access granted — result.mandate has payer details
        return jsonify(data="premium content")

Version: 1.0.0
"""

from __future__ import annotations

import json
import ssl
import time
from base64 import b64decode, b64encode
from typing import Any, Callable, Optional
from urllib.request import Request, urlopen
from urllib.error import URLError

__version__ = "1.0.0"


class Ap2PaymentRequest:
    """An AP2 payment request to present to the agent."""

    def __init__(
        self,
        merchant_id: str,
        amount_usd: float,
        currency: str,
        items: list[dict],
        networks: list[str],
        expires_seconds: int = 600,
    ):
        self.merchant_id = merchant_id
        self.amount_usd = amount_usd
        self.currency = currency
        self.items = items
        self.networks = networks
        self.expires_at = time.time() + expires_seconds
        self.request_id = f"ap2_{int(time.time())}_{id(self) % 10000}"

    def as_dict(self) -> dict:
        return {
            "protocol": "ap2",
            "version": "1",
            "merchant_id": self.merchant_id,
            "request_id": self.request_id,
            "amount": {
                "value": str(self.amount_usd),
                "currency": self.currency,
            },
            "items": self.items,
            "networks": self.networks,
            "signing": "ed25519",
            "expires_at": int(self.expires_at),
        }

    def as_header(self) -> str:
        return b64encode(json.dumps(self.as_dict()).encode()).decode()


class Ap2Mandate:
    """A verified AP2 payment mandate from an agent."""

    def __init__(
        self,
        payer_address: str,
        merchant_id: str,
        amount: float,
        currency: str,
        signature: str,
        network: str,
        verified_at: float = 0,
    ):
        self.payer_address = payer_address
        self.merchant_id = merchant_id
        self.amount = amount
        self.currency = currency
        self.signature = signature
        self.network = network
        self.verified_at = verified_at or time.time()


class Ap2Result:
    """Result of checking a request for AP2 credentials."""

    def __init__(
        self,
        requires_payment: bool,
        payment_request: Optional[Ap2PaymentRequest] = None,
        mandate: Optional[Ap2Mandate] = None,
        error: Optional[str] = None,
    ):
        self.requires_payment = requires_payment
        self.payment_request = payment_request
        self.mandate = mandate
        self.error = error

    def as_flask_response(self) -> tuple:
        """Return a Flask-compatible (body, status, headers) tuple."""
        if not self.requires_payment:
            return {}, 200, {}

        body = {
            "error": "Payment Required",
            "protocol": "ap2",
            "detail": self.error or "This endpoint requires an AP2 payment mandate.",
        }
        if self.payment_request:
            body["payment_request"] = self.payment_request.as_dict()

        headers = {"Content-Type": "application/json"}
        if self.payment_request:
            headers["X-AP2-Payment-Request"] = self.payment_request.as_header()

        return json.dumps(body), 402, headers

    def as_wsgi_response(self) -> tuple[str, list[tuple[str, str]], bytes]:
        """Return a WSGI-compatible (status, headers, body) tuple."""
        body_str, status_code, header_dict = self.as_flask_response()
        headers = list(header_dict.items())
        return f"{status_code} Payment Required", headers, body_str.encode() if isinstance(body_str, str) else json.dumps(body_str).encode()


class Ap2Gate:
    """AP2 payment gate — checks requests for valid AP2 mandates."""

    NETWORKS = {
        "algorand_mainnet": "algorand-mainnet",
        "voi_mainnet": "voi-mainnet",
        "hedera_mainnet": "hedera-mainnet",
        "stellar_mainnet": "stellar-mainnet",
    }

    def __init__(
        self,
        merchant_id: str,
        api_base: str,
        api_key: str,
        tenant_id: str,
        amount_usd: float = 1.00,
        currency: str = "USD",
        networks: Optional[list[str]] = None,
        items: Optional[list[dict]] = None,
    ):
        self.merchant_id = merchant_id
        self.api_base = api_base.rstrip("/")
        self.api_key = api_key
        self.tenant_id = tenant_id
        self.amount_usd = amount_usd
        self.currency = currency
        self.networks = networks or ["algorand_mainnet", "voi_mainnet"]
        self.items = items or [{"label": "API Access", "amount": str(amount_usd)}]
        self._ssl_ctx = ssl.create_default_context()

    def check(self, headers: dict[str, str], body: Optional[dict] = None) -> Ap2Result:
        """
        Check a request for AP2 payment credentials.

        Args:
            headers: Request headers
            body:    Parsed JSON body (may contain ap2_mandate)

        Returns:
            Ap2Result — check .requires_payment to decide whether to gate
        """
        h = {k.lower(): v for k, v in headers.items()}

        # Look for AP2 mandate in header or body
        mandate_raw = h.get("x-ap2-mandate", "")
        if not mandate_raw and body and isinstance(body, dict):
            mandate_raw = body.get("ap2_mandate", "")

        if not mandate_raw:
            return Ap2Result(
                requires_payment=True,
                payment_request=self._build_request(),
            )

        # Parse mandate
        try:
            if mandate_raw.startswith("{"):
                mandate_data = json.loads(mandate_raw)
            else:
                mandate_data = json.loads(b64decode(mandate_raw))
        except (json.JSONDecodeError, Exception):
            return Ap2Result(
                requires_payment=True,
                payment_request=self._build_request(),
                error="Invalid AP2 mandate encoding",
            )

        payer = mandate_data.get("payer_address", "")
        sig = mandate_data.get("signature", "")
        network = mandate_data.get("network", "algorand-mainnet")
        amount = float(mandate_data.get("amount", {}).get("value", 0))
        merchant = mandate_data.get("merchant_id", "")

        # Validate merchant_id matches
        if merchant != self.merchant_id:
            return Ap2Result(
                requires_payment=True,
                payment_request=self._build_request(),
                error="Merchant ID mismatch",
            )

        if not payer or not sig:
            return Ap2Result(
                requires_payment=True,
                payment_request=self._build_request(),
                error="Missing payer_address or signature",
            )

        # Verify with AlgoVoi API
        verified = self._verify_mandate(mandate_data)
        if not verified:
            return Ap2Result(
                requires_payment=True,
                payment_request=self._build_request(),
                error="Mandate verification failed",
            )

        return Ap2Result(
            requires_payment=False,
            mandate=Ap2Mandate(
                payer_address=payer,
                merchant_id=merchant,
                amount=amount,
                currency=mandate_data.get("amount", {}).get("currency", "USD"),
                signature=sig,
                network=network,
            ),
        )

    def _build_request(self) -> Ap2PaymentRequest:
        """Build an AP2 payment request."""
        net_ids = [self.NETWORKS.get(n, n) for n in self.networks]
        return Ap2PaymentRequest(
            merchant_id=self.merchant_id,
            amount_usd=self.amount_usd,
            currency=self.currency,
            items=self.items,
            networks=net_ids,
        )

    def _verify_mandate(self, mandate_data: dict) -> bool:
        """Verify an AP2 mandate with the AlgoVoi API."""
        url = f"{self.api_base}/v1/ap2/verify"
        payload = json.dumps({
            "mandate": mandate_data,
            "merchant_id": self.merchant_id,
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
                    return False
                data = json.loads(resp.read())
                return data.get("verified", False)
        except (URLError, json.JSONDecodeError, OSError):
            return False

    # ── Framework Helpers ────────────────────────────────────────────────

    def flask_guard(self, body: Optional[dict] = None) -> Optional[tuple]:
        """
        Flask route guard. Returns None (proceed) or a 402 response tuple.

        Usage:
            @app.route('/api/premium')
            def premium():
                guard = gate.flask_guard(request.get_json(silent=True))
                if guard:
                    return guard
                return jsonify(data="premium content")
        """
        from flask import request as flask_request  # type: ignore

        result = self.check(dict(flask_request.headers), body)
        if not result.requires_payment:
            return None
        return result.as_flask_response()

    def django_decorator(self, view_func: Callable) -> Callable:
        """
        Django view decorator.

        Usage:
            @gate.django_decorator
            def premium_view(request):
                return JsonResponse({'data': 'premium'})
        """
        from django.http import JsonResponse  # type: ignore
        from functools import wraps

        @wraps(view_func)
        def wrapped(request: Any, *args: Any, **kwargs: Any) -> Any:
            headers = {
                k.replace("HTTP_", "").replace("_", "-").title(): v
                for k, v in request.META.items() if k.startswith("HTTP_")
            }
            try:
                body = json.loads(request.body) if request.body else None
            except json.JSONDecodeError:
                body = None

            result = self.check(headers, body)
            if result.requires_payment:
                resp_body, status, resp_headers = result.as_flask_response()
                resp = JsonResponse(json.loads(resp_body) if isinstance(resp_body, str) else resp_body, status=status)
                for k, v in resp_headers.items():
                    resp[k] = v
                return resp
            return view_func(request, *args, **kwargs)

        return wrapped
