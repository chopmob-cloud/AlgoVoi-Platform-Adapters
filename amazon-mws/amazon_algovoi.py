"""
AlgoVoi Amazon SP-API Payment Adapter

Receives Amazon Selling Partner API (SP-API) ORDER_CHANGE notifications,
creates AlgoVoi payment links, and marks orders as shipped when payment
is confirmed on-chain.

Use cases:
  - B2B / wholesale invoicing — issue crypto payment request to trade buyers
  - Seller fee settlement — settle inter-company invoices in USDC/aUSDC
  - Operator-initiated flows — your backend sends order data to AlgoVoi

Amazon does NOT allow third-party payment at customer checkout.
This adapter handles post-order payment flows only.

Works with Flask, Django, FastAPI, or any WSGI framework.
Zero pip dependencies — uses only the Python standard library.

Version: 1.1.0

AlgoVoi docs: https://github.com/chopmob-cloud/AlgoVoi-Platform-Adapters
Licensed under the Business Source License 1.1 — see LICENSE for details.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import math
import re
import ssl
import time
from typing import Any, Optional
from urllib.parse import quote, urlparse
from urllib.request import Request, urlopen
from urllib.error import URLError

__version__ = "1.1.0"

HOSTED_NETWORKS = {"algorand_mainnet", "voi_mainnet", "hedera_mainnet", "stellar_mainnet"}

CHAIN_LABELS = {
    "algorand_mainnet": "USDC on Algorand",
    "voi_mainnet": "aUSDC on VOI",
    "hedera_mainnet": "USDC on Hedera",
    "stellar_mainnet": "USDC on Stellar",
}

# Hard caps and validation patterns
MAX_WEBHOOK_BODY_BYTES = 64 * 1024     # Amazon order notifications are <2 KB
AMAZON_ORDER_ID_RE     = re.compile(r"^\d{3}-\d{7}-\d{7}$")

# Amazon SP-API endpoints — the only hosts confirm_shipment may POST to.
ALLOWED_MARKETPLACE_HOSTS = frozenset({
    "sellingpartnerapi-eu.amazon.com",
    "sellingpartnerapi-na.amazon.com",
    "sellingpartnerapi-fe.amazon.com",
})


class AmazonAlgoVoi:
    """Amazon SP-API + AlgoVoi payment adapter."""

    def __init__(
        self,
        api_base: str = "https://api1.ilovechicken.co.uk",
        api_key: str = "",
        tenant_id: str = "",
        webhook_secret: str = "",
        default_network: str = "algorand_mainnet",
        base_currency: str = "GBP",
        timeout: int = 30,
    ):
        self.api_base = api_base.rstrip("/")
        self.api_key = api_key
        self.tenant_id = tenant_id
        self.webhook_secret = webhook_secret
        self.default_network = default_network
        self.base_currency = base_currency
        self.timeout = timeout
        self._ssl = ssl.create_default_context()

    # ── Webhook Verification ─────────────────────────────────────────────

    def verify_webhook(self, raw_body: bytes, signature: str) -> Optional[dict]:
        """
        Verify an incoming webhook (from SNS forwarder or direct POST).

        Args:
            raw_body:  Raw POST body as bytes
            signature: X-AlgoVoi-Signature header value

        Returns:
            Parsed payload dict, or None if verification fails

        SECURITY NOTE — replay protection:
            This method does NOT dedupe replays. The HMAC carries no
            timestamp, so an attacker who captures one valid (body, sig)
            pair could replay it indefinitely. Callers MUST track
            processed `amazon_order_id` values in their persistence
            layer and reject duplicates BEFORE calling process_order().
        """
        if not self.webhook_secret:
            return None  # Reject if secret not configured

        # Type guards — compare_digest raises TypeError on bytes/None,
        # which would surface as a 500. Fail closed instead.
        if not isinstance(signature, str) or not signature:
            return None
        if not isinstance(raw_body, (bytes, bytearray)):
            return None
        if len(raw_body) > MAX_WEBHOOK_BODY_BYTES:
            return None

        expected = base64.b64encode(
            hmac.new(
                self.webhook_secret.encode(),
                bytes(raw_body),
                hashlib.sha256,
            ).digest()
        ).decode()

        if not hmac.compare_digest(expected, signature):
            return None

        try:
            return json.loads(raw_body)
        except json.JSONDecodeError:
            return None

    # ── Order Processing ─────────────────────────────────────────────────

    def process_order(
        self,
        amazon_order_id: str,
        amount: float,
        currency: Optional[str] = None,
        network: Optional[str] = None,
        label: Optional[str] = None,
        redirect_url: str = "",
    ) -> Optional[dict]:
        """
        Create an AlgoVoi payment link for an Amazon order.

        Args:
            amazon_order_id: Amazon order ID (e.g. 123-4567890-1234567)
            amount:          Order total
            currency:        ISO currency code (defaults to base_currency)
            network:         Preferred network (defaults to default_network)
            label:           Payment label (defaults to "Amazon Order #...")
            redirect_url:    Return URL after payment (optional)

        Returns:
            dict with checkout_url, token, chain, amount_microunits — or None on failure
        """
        if not network or network not in HOSTED_NETWORKS:
            network = self.default_network
        if not currency:
            currency = self.base_currency
        if not label:
            label = f"Amazon Order #{amazon_order_id}"

        # Defence-in-depth: reject obviously bad amounts before the gateway
        # call. The gateway also validates, but local rejection avoids
        # round-trips and keeps test logs clean.
        if not isinstance(amount, (int, float)) or not math.isfinite(amount) or amount <= 0:
            return None

        payload: dict[str, Any] = {
            "amount": round(float(amount), 2),
            "currency": currency.upper(),
            "label": label,
            "preferred_network": network,
        }
        if redirect_url:
            # https-only — checkout tokens or payment-status parameters
            # appended by the gateway must not travel over plaintext.
            # Also blocks SSRF schemes (file://, gopher://, etc.).
            parsed = urlparse(redirect_url)
            if parsed.scheme != "https" or not parsed.hostname:
                return None
            payload["redirect_url"] = redirect_url
            payload["expires_in_seconds"] = 3600

        resp = self._post("/v1/payment-links", payload)
        if not resp or not resp.get("checkout_url"):
            return None

        token = ""
        m = re.search(r"/checkout/([A-Za-z0-9_-]+)$", resp["checkout_url"])
        if m:
            token = m.group(1)

        return {
            "checkout_url": resp["checkout_url"],
            "token": token,
            "chain": resp.get("chain", "algorand-mainnet"),
            "amount_microunits": int(resp.get("amount_microunits", 0)),
            "amazon_order_id": amazon_order_id,
        }

    def verify_payment(self, token: str) -> bool:
        """
        Check if a payment has been completed.
        Call this before confirming shipment on Amazon.

        Args:
            token: AlgoVoi checkout token

        Returns:
            True only if the API confirms payment is complete
        """
        if not token:
            return False
        # Refuse to send the checkout token over plaintext HTTP.
        if not self.api_base.startswith("https://"):
            return False

        url = f"{self.api_base}/checkout/{quote(token, safe='')}"
        try:
            req = Request(url, method="GET")
            with urlopen(req, timeout=15, context=self._ssl) as resp:  # nosec B310
                if resp.status != 200:
                    return False
                data = json.loads(resp.read())
                return data.get("status") in ("paid", "completed", "confirmed")
        except (URLError, json.JSONDecodeError, OSError):
            return False

    # ── SP-API Integration ───────────────────────────────────────────────

    def parse_sp_api_order(self, notification: dict) -> Optional[dict]:
        """
        Parse an SP-API ORDER_CHANGE notification payload.

        Args:
            notification: The SNS notification payload (parsed JSON)

        Returns:
            dict with amazon_order_id, amount, currency — or None if not parseable
        """
        try:
            payload = notification.get("Payload") or notification.get("payload", {})
            change = payload.get("OrderChangeNotification", {})
            summary = change.get("Summary", {})

            amazon_order_id = change.get("AmazonOrderId", "")
            amount_str = summary.get("OrderTotalAmount", "0")
            currency = summary.get("OrderTotalCurrencyCode", self.base_currency)

            if not amazon_order_id:
                return None

            amount = float(amount_str)
            if not math.isfinite(amount) or amount <= 0:
                return None

            return {
                "amazon_order_id": amazon_order_id,
                "amount": amount,
                "currency": currency,
                "status": summary.get("OrderStatus", ""),
                "marketplace_id": change.get("MarketplaceId", ""),
            }
        except (KeyError, ValueError, TypeError):
            return None

    def confirm_shipment(
        self,
        amazon_order_id: str,
        tx_id: str,
        sp_api_token: str,
        marketplace_url: str = "https://sellingpartnerapi-eu.amazon.com",
    ) -> bool:
        """
        Confirm shipment on Amazon with the AlgoVoi transaction reference.
        Call this AFTER verify_payment() returns True.

        Args:
            amazon_order_id: Amazon order ID, format: \\d{3}-\\d{7}-\\d{7}
            tx_id:           On-chain transaction ID (max 200 chars)
            sp_api_token:    SP-API LWA access token
            marketplace_url: SP-API regional endpoint — MUST be one of
                             ALLOWED_MARKETPLACE_HOSTS or the call is
                             rejected (prevents token leak via SSRF).

        Returns:
            True if shipment confirmation was accepted
        """
        if not tx_id or len(tx_id) > 200:
            return False
        if not amazon_order_id or not AMAZON_ORDER_ID_RE.match(amazon_order_id):
            return False

        # SSRF guard — refuse to send the SP-API access token to any host
        # other than Amazon's official SP-API endpoints.
        parsed = urlparse(marketplace_url or "")
        if parsed.scheme != "https" or parsed.hostname not in ALLOWED_MARKETPLACE_HOSTS:
            return False

        url = f"{marketplace_url}/orders/v0/orders/{quote(amazon_order_id, safe='')}/shipment"
        payload = json.dumps({
            "marketplaceId": "",  # Set by caller
            "shipmentStatus": "ReadyForPickup",
            "orderItems": [],
            "shipmentConfirmationData": {
                "paymentMethod": "Other",
                "paymentMethodDetails": f"AlgoVoi TX: {tx_id}",
            },
        }).encode()

        req = Request(url, data=payload, method="POST", headers={
            "Content-Type": "application/json",
            "x-amz-access-token": sp_api_token,
        })

        try:
            with urlopen(req, timeout=self.timeout, context=self._ssl) as resp:  # nosec B310
                return resp.status in (200, 204)
        except (URLError, OSError):
            return False

    # ── Supported Marketplaces ───────────────────────────────────────────

    MARKETPLACES = {
        "UK": {"id": "A1F83G8C2ARO7P", "endpoint": "https://sellingpartnerapi-eu.amazon.com"},
        "DE": {"id": "A1PA6795UKMFR9", "endpoint": "https://sellingpartnerapi-eu.amazon.com"},
        "FR": {"id": "A13V1IB3VIYZZH", "endpoint": "https://sellingpartnerapi-eu.amazon.com"},
        "US": {"id": "ATVPDKIKX0DER", "endpoint": "https://sellingpartnerapi-na.amazon.com"},
        "CA": {"id": "A2EUQ1WTGCTBG2", "endpoint": "https://sellingpartnerapi-na.amazon.com"},
    }

    # ── Flask Helper ─────────────────────────────────────────────────────

    def flask_webhook_handler(self):
        """
        Returns a Flask view function for the webhook endpoint.

        Usage:
            app.add_url_rule('/webhook/amazon', view_func=adapter.flask_webhook_handler(), methods=['POST'])
        """
        adapter = self

        def handler():
            from flask import request, jsonify

            raw_body = request.get_data()
            signature = request.headers.get("X-AlgoVoi-Signature", "")

            payload = adapter.verify_webhook(raw_body, signature)
            if not payload:
                return jsonify(error="Unauthorized"), 401

            order = adapter.parse_sp_api_order(payload)
            if not order:
                return jsonify(error="Could not parse order"), 400

            if order["status"] not in ("Unshipped", "PartiallyShipped"):
                return jsonify(received=True, skipped="not actionable status")

            result = adapter.process_order(
                amazon_order_id=order["amazon_order_id"],
                amount=order["amount"],
                currency=order["currency"],
            )

            if not result:
                return jsonify(error="Could not create payment link"), 502

            return jsonify(
                received=True,
                amazon_order_id=order["amazon_order_id"],
                checkout_url=result["checkout_url"],
                chain=result["chain"],
            )

        return handler

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
