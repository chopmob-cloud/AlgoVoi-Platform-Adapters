"""
AlgoVoi x402 AI Agents Payment Adapter

Implements the x402 open standard for machine-to-machine payments over HTTP.
When an AI agent hits a paywall, the server responds HTTP 402 with an
X-PAYMENT-REQUIRED header (base64 JSON) describing what to pay. The agent
submits an on-chain transaction (USDC on Algorand or aUSDC on VOI), then
retries with an X-PAYMENT header containing base64 proof (signature/tx_id).
The AlgoVoi facilitator verifies on-chain and grants access.

x402 is co-developed by Coinbase, Cloudflare, Google, Stripe, AWS, Circle,
Anthropic, and Vercel. AlgoVoi implements x402 natively on Algorand, VOI,
Stellar, and Hedera.

Conforms to x402 spec v1 (accepts array, x402Version integer, CAIP-2 network
IDs, string microunit amounts, payload.signature proof format).

Works with Flask, Django, FastAPI, or any WSGI framework.
Zero pip dependencies — uses only the Python standard library.

x402 spec: https://www.x402.org
AlgoVoi docs: https://github.com/chopmob-cloud/AlgoVoi-Platform-Adapters

Version: 2.0.0
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import ssl
from typing import Any, Optional
from urllib.parse import quote
from urllib.request import Request, urlopen
from urllib.error import URLError

__version__ = "2.0.0"

HOSTED_NETWORKS = {"algorand_mainnet", "voi_mainnet", "hedera_mainnet", "stellar_mainnet"}

CHAIN_LABELS = {
    "algorand_mainnet": "USDC on Algorand",
    "voi_mainnet": "aUSDC on VOI",
    "hedera_mainnet": "USDC on Hedera",
    "stellar_mainnet": "USDC on Stellar",
}

# CAIP-2 style network identifiers (namespace:reference)
NETWORK_CAIP2 = {
    "algorand_mainnet": "algorand:mainnet",
    "voi_mainnet": "voi:mainnet",
    "stellar_mainnet": "stellar:pubnet",
    "hedera_mainnet": "hedera:mainnet",
}

# Chain-native asset identifiers for USDC per network
NETWORK_ASSET = {
    "algorand_mainnet": "31566704",
    "voi_mainnet": "302190",
    "stellar_mainnet": "USDC:GA5ZSEJYB37JRC5AVCIA5MOP4RHTM335X2KGX3IHOJAPP5RE34K4KZVN",
    "hedera_mainnet": "0.0.456858",
}

USDC_DECIMALS = 6

# x402 header names
HEADER_PAYMENT_REQUIRED = "X-PAYMENT-REQUIRED"
HEADER_PAYMENT = "X-PAYMENT"
HTTP_402 = 402


class X402AgentAlgoVoi:
    """
    x402 AI Agent payment adapter for AlgoVoi.

    Handles the full x402 HTTP 402 payment flow:
      - Generating payment requirements (X-PAYMENT-REQUIRED headers)
      - Verifying payment proofs (X-PAYMENT headers)
      - Flask middleware for gating protected routes
      - AlgoVoi payment link creation as a fallback flow
    """

    def __init__(
        self,
        api_base: str = "https://api1.ilovechicken.co.uk",
        api_key: str = "",
        tenant_id: str = "",
        webhook_secret: str = "",
        default_network: str = "algorand_mainnet",
        base_currency: str = "USD",
        payout_address: str = "",
        timeout: int = 30,
    ):
        self.api_base = api_base.rstrip("/")
        self.api_key = api_key
        self.tenant_id = tenant_id
        self.webhook_secret = webhook_secret
        self.default_network = default_network
        self.base_currency = base_currency
        self.payout_address = payout_address
        self.timeout = timeout
        self._ssl = ssl.create_default_context()

    # ── x402 Payment Requirements ────────────────────────────────────────

    def create_payment_requirement(
        self,
        amount: float,
        currency: Optional[str] = None,
        network: Optional[str] = None,
        resource_path: str = "/",
        resource_description: str = "",
        expires_in: int = 300,
    ) -> dict:
        """
        Build an x402 v1 spec-compliant payment requirement descriptor.

        This is the structure that gets base64-encoded and sent as the
        X-PAYMENT-REQUIRED header value when responding with HTTP 402.

        Args:
            amount:               Payment amount in USDC (e.g. 0.01 for 1 cent)
            currency:             Unused — kept for backward-compat call sites
            network:              Target network key (defaults to default_network)
            resource_path:        URL path of the protected resource
            resource_description: Human-readable description of the resource
            expires_in:           maxTimeoutSeconds for the payment (default 300)

        Returns:
            dict with the full x402 requirement, including a base64-encoded
            header_value ready for use in X-PAYMENT-REQUIRED
        """
        if not network or network not in HOSTED_NETWORKS:
            network = self.default_network

        microunits = str(int(round(amount * 10 ** USDC_DECIMALS)))
        description = resource_description or f"AlgoVoi: {resource_path}"

        requirement = {
            "x402Version": 1,
            "accepts": [
                {
                    "scheme": "exact",
                    "network": NETWORK_CAIP2.get(network, network),
                    "amount": microunits,
                    "asset": NETWORK_ASSET.get(network, ""),
                    "payTo": self.payout_address,
                    "maxTimeoutSeconds": expires_in,
                    "extra": {
                        "name": "USDC",
                        "decimals": USDC_DECIMALS,
                        "description": description,
                    },
                }
            ],
            "resource": {
                "url": resource_path,
                "description": description,
            },
        }

        header_value = base64.b64encode(json.dumps(requirement).encode()).decode()
        requirement["header_value"] = header_value
        return requirement

    def decode_payment_requirement(self, header_value: str) -> Optional[dict]:
        """
        Decode a base64-encoded X-PAYMENT-REQUIRED header value.

        Args:
            header_value: Raw value from the X-PAYMENT-REQUIRED header

        Returns:
            Parsed dict, or None on decode / JSON failure
        """
        if not header_value:
            return None
        try:
            decoded = base64.b64decode(header_value.encode())
            return json.loads(decoded)
        except (ValueError, json.JSONDecodeError, Exception):
            return None

    # ── Webhook Verification ─────────────────────────────────────────────

    def verify_webhook(self, raw_body: bytes, signature: str) -> Optional[dict]:
        """
        Verify an AlgoVoi webhook using HMAC-SHA256.

        Args:
            raw_body:  Raw POST body as bytes
            signature: Signature header value

        Returns:
            Parsed payload dict, or None if verification fails
        """
        if not self.webhook_secret:
            return None

        expected = hmac.new(
            self.webhook_secret.encode(),
            raw_body,
            hashlib.sha256,
        ).hexdigest()

        if not hmac.compare_digest(expected, signature):
            return None

        try:
            return json.loads(raw_body)
        except json.JSONDecodeError:
            return None

    # ── Payment Link (Fallback / Non-Agent Flow) ─────────────────────────

    def create_payment_link(
        self,
        amount: float,
        currency: Optional[str] = None,
        network: Optional[str] = None,
        label: str = "",
        redirect_url: str = "",
    ) -> Optional[dict]:
        """
        Create an AlgoVoi hosted checkout link.

        Used as a fallback when the client is a human browser rather than
        an autonomous agent, or when a hosted checkout UX is preferred.

        Args:
            amount:       Payment amount
            currency:     ISO currency code (defaults to base_currency)
            network:      Preferred network (defaults to default_network)
            label:        Payment label shown to payer
            redirect_url: Return URL after payment (optional)

        Returns:
            dict with checkout_url and token, or None on failure
        """
        if not network or network not in HOSTED_NETWORKS:
            network = self.default_network
        if not currency:
            currency = self.base_currency
        if not label:
            label = "AlgoVoi x402 Payment"

        payload: dict[str, Any] = {
            "amount": round(amount, 2),
            "currency": currency.upper(),
            "label": label,
            "preferred_network": network,
        }
        if redirect_url:
            payload["redirect_url"] = redirect_url
            payload["expires_in_seconds"] = 3600

        resp = self._post("/v1/payment-links", payload)
        if not resp or not resp.get("checkout_url"):
            return None

        return {
            "checkout_url": resp["checkout_url"],
            "token": resp.get("token", ""),
        }

    # ── x402 Payment Verification ────────────────────────────────────────

    def verify_x402_payment(self, header_value: str) -> tuple:
        """
        Verify an x402 payment proof from the X-PAYMENT header.

        Decodes the base64 JSON proof and calls the AlgoVoi API to confirm
        the on-chain transaction was successful.

        Args:
            header_value: Raw value from the X-PAYMENT header

        Returns:
            (True, tx_id) if payment is confirmed, (False, None) otherwise
        """
        if not header_value:
            return (False, None)

        try:
            decoded = base64.b64decode(header_value.encode())
            proof = json.loads(decoded)
        except (ValueError, json.JSONDecodeError, Exception):
            return (False, None)

        # Spec format: payload.signature; legacy fallback: payload.tx_id or root tx_id
        payload_obj = proof.get("payload") or {}
        tx_id = (
            payload_obj.get("signature")
            or payload_obj.get("tx_id")
            or proof.get("tx_id")
            or ""
        )
        if not tx_id:
            return (False, None)

        if self.verify_payment(tx_id):
            return (True, tx_id)
        return (False, None)

    def verify_payment(self, token: str) -> bool:
        """
        Check if a payment / transaction has been confirmed on-chain.

        Args:
            token: AlgoVoi checkout token or on-chain tx_id

        Returns:
            True only if the API confirms payment is complete
        """
        if not token:
            return False
        tx_id = token
        if len(tx_id) > 200:
            return False

        url = f"{self.api_base}/checkout/{quote(token, safe='')}/status"
        if not url.startswith("https://"):
            return False
        try:
            req = Request(url, method="GET")
            with urlopen(req, timeout=15, context=self._ssl) as resp:  # nosec B310
                if resp.status != 200:
                    return False
                data = json.loads(resp.read())
                return data.get("status") in ("paid", "completed", "confirmed")
        except (URLError, json.JSONDecodeError, OSError):
            return False

    # ── Flask Middleware ─────────────────────────────────────────────────

    def flask_x402_middleware(self, protected_routes: list, amount_map: dict):
        """
        Returns a Flask before_request function that gates protected routes.

        For each route in amount_map, the middleware:
          1. Checks for an X-PAYMENT header — if valid, allows the request through
          2. If missing or invalid, returns HTTP 402 with X-PAYMENT-REQUIRED header

        Usage:
            app.before_request(adapter.flask_x402_middleware(
                protected_routes=["/api/inference"],
                amount_map={
                    "/api/inference": {
                        "amount": 0.001,
                        "currency": "USD",
                        "network": "algorand_mainnet",
                    }
                }
            ))

        Args:
            protected_routes: List of route path strings to protect
            amount_map:       Dict mapping route paths to payment config dicts

        Returns:
            A callable suitable for use with Flask's before_request
        """
        adapter = self

        def before_request():
            from flask import request, Response

            path = request.path
            if path not in protected_routes and path not in amount_map:
                return None  # not a protected route, allow through

            cfg = amount_map.get(path, {})
            amount = cfg.get("amount", 0)
            currency = cfg.get("currency", adapter.base_currency)
            network = cfg.get("network", adapter.default_network)

            # Check for existing payment proof
            payment_header = request.headers.get(HEADER_PAYMENT, "")
            if payment_header:
                ok, _ = adapter.verify_x402_payment(payment_header)
                if ok:
                    return None  # payment verified, allow through

            # No valid payment — issue 402
            pr = adapter.build_payment_required_response(amount, currency, network, path)
            resp = Response(
                json.dumps({"error": "Payment required", "x402": True}),
                status=402,
                mimetype="application/json",
            )
            resp.headers[pr["header_name"]] = pr["header_value"]
            return resp

        return before_request

    # ── Agent Helpers ────────────────────────────────────────────────────

    def handle_agent_payment(self, request_path: str, payment_header: str) -> bool:
        """
        Helper: given a resource path and X-PAYMENT header value, verify payment.

        Args:
            request_path:   Path of the resource being requested
            payment_header: Raw value of the X-PAYMENT header

        Returns:
            True if payment is valid and verified, False otherwise
        """
        if not payment_header:
            return False
        ok, _ = self.verify_x402_payment(payment_header)
        return ok

    def build_payment_required_response(
        self,
        amount: float,
        currency: Optional[str] = None,
        network: Optional[str] = None,
        resource_path: str = "/",
    ) -> dict:
        """
        Build the full HTTP 402 response descriptor.

        Args:
            amount:        Payment amount
            currency:      ISO currency code (defaults to base_currency)
            network:       Target network (defaults to default_network)
            resource_path: URL path of the protected resource

        Returns:
            dict with status_code (402), header_name, and header_value
        """
        req = self.create_payment_requirement(
            amount=amount,
            currency=currency,
            network=network,
            resource_path=resource_path,
        )
        return {
            "status_code": HTTP_402,
            "header_name": HEADER_PAYMENT_REQUIRED,
            "header_value": req["header_value"],
        }

    # ── Internal ─────────────────────────────────────────────────────────

    def _post(self, path: str, data: dict) -> Optional[dict]:
        if not self.api_base.startswith("https://"):
            return None
        body = json.dumps(data).encode()
        req = Request(
            f"{self.api_base}{path}",
            data=body,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
                "X-Tenant-Id": self.tenant_id,
            },
        )
        try:
            with urlopen(req, timeout=self.timeout, context=self._ssl) as resp:  # nosec B310
                if resp.status < 200 or resp.status >= 300:
                    return None
                return json.loads(resp.read())
        except (URLError, json.JSONDecodeError, OSError):
            return None

    def _get(self, path: str) -> Optional[dict]:
        req = Request(
            f"{self.api_base}{path}",
            method="GET",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "X-Tenant-Id": self.tenant_id,
            },
        )
        try:
            with urlopen(req, timeout=self.timeout, context=self._ssl) as resp:  # nosec B310
                if resp.status < 200 or resp.status >= 300:
                    return None
                return json.loads(resp.read())
        except (URLError, json.JSONDecodeError, OSError):
            return None
