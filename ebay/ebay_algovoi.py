"""
AlgoVoi eBay Payment Adapter

Receives eBay Platform Notifications (checkout.order.created),
creates AlgoVoi payment links, and marks orders as shipped when
payment is confirmed on-chain.

eBay also sends a challenge-response GET request to verify webhook
endpoints before activating a subscription. This adapter handles
both the challenge-response and the notification webhook.

eBay signs Platform Notifications with ECDSA in the X-EBAY-SIGNATURE
header (base64 JSON: alg, kid, signature, digest). Full ECDSA
verification requires the cryptography package. This adapter performs
structural validation of the header and falls back to a configurable
HMAC-SHA256 shared secret for operator-controlled environments.

Works with Flask, Django, FastAPI, or any WSGI framework.
Zero pip dependencies — uses only the Python standard library.

eBay API docs: https://developer.ebay.com/api-docs/commerce/notification/overview.html

Version: 1.0.0

AlgoVoi docs: https://github.com/chopmob-cloud/AlgoVoi-Platform-Adapters
Copyright (c) 2026 Christopher Hopley (ilovechicken.co.uk). BSL 1.1.
"""

# PROVISIONAL: This adapter has not been end-to-end tested against a live
# platform environment. API details are based on official documentation and
# community sources. Verify against your platform's current API before
# production use. See README.md for status.

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re
import ssl
import time
from typing import Any, Optional
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen
from urllib.error import URLError

__version__ = "1.0.0"

HOSTED_NETWORKS = {"algorand_mainnet", "voi_mainnet", "hedera_mainnet", "stellar_mainnet"}

CHAIN_LABELS = {
    "algorand_mainnet": "USDC on Algorand",
    "voi_mainnet": "aUSDC on VOI",
    "hedera_mainnet": "USDC on Hedera",
    "stellar_mainnet": "USDC on Stellar",
}

EBAY_API_BASE = "https://api.ebay.com"
EBAY_FULFILLMENT_BASE = "https://api.ebay.com/sell/fulfillment/v1"


class EbayAlgoVoi:
    """eBay Platform Notifications + AlgoVoi payment adapter."""

    def __init__(
        self,
        api_base: str = "https://api1.ilovechicken.co.uk",
        api_key: str = "",
        tenant_id: str = "",
        access_token: str = "",
        client_secret: str = "",
        webhook_secret: str = "",
        default_network: str = "algorand_mainnet",
        base_currency: str = "GBP",
        timeout: int = 30,
    ):
        self.api_base = api_base.rstrip("/")
        self.api_key = api_key
        self.tenant_id = tenant_id
        self.access_token = access_token
        self.client_secret = client_secret
        self.webhook_secret = webhook_secret
        self.default_network = default_network
        self.base_currency = base_currency
        self.timeout = timeout
        self._ssl = ssl.create_default_context()

    # ── Webhook Verification ─────────────────────────────────────────────

    def verify_webhook(self, raw_body: bytes, signature: str) -> Optional[dict]:
        """
        Verify an eBay Platform Notification using the X-EBAY-SIGNATURE header.

        eBay signs Platform Notifications with ECDSA. The X-EBAY-SIGNATURE
        header is a base64-encoded JSON structure: {"alg":"ECDSA","kid":"...",
        "signature":"...","digest":"SHA1"}. Full ECDSA verification requires
        the cryptography package (not stdlib).

        This method performs structural validation of the ECDSA header when
        present. If webhook_secret is set, it additionally verifies a
        HMAC-SHA256 shared secret for operator-controlled environments where
        the operator injects their own signing layer.

        Args:
            raw_body:  Raw POST body as bytes
            signature: X-EBAY-SIGNATURE header value (base64 JSON)

        Returns:
            Parsed payload dict, or None if verification fails
        """
        if not self.webhook_secret:
            return None

        if not signature:
            return None

        # Attempt structural validation of eBay ECDSA header
        if signature:
            try:
                decoded = base64.b64decode(signature + "==")
                sig_data = json.loads(decoded)
                # Valid eBay signature must contain these keys
                if not all(k in sig_data for k in ("alg", "kid", "signature")):
                    return None
                # Full ECDSA verify requires cryptography package — not stdlib.
                # Accept structurally valid headers; operators should add
                # cryptography-based verification in production.
            except (ValueError, json.JSONDecodeError, Exception):
                # Fallback: treat as HMAC-SHA256 hex for operator-controlled env
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

    def handle_challenge(self, challenge_code: str, endpoint: str) -> Optional[str]:
        """
        Handle eBay challenge-response endpoint verification.

        eBay sends a GET with challengeCode. Respond with
        sha256(challengeCode + verificationToken + endpoint).

        Args:
            challenge_code: The challengeCode query parameter from eBay
            endpoint:       The full URL of this webhook endpoint

        Returns:
            Hex digest to return as {'challengeResponse': <value>}
        """
        if not challenge_code or not self.webhook_secret:
            return None
        h = hashlib.sha256()
        h.update(challenge_code.encode())
        h.update(self.webhook_secret.encode())
        h.update(endpoint.encode())
        return h.hexdigest()

    # ── Order Processing ─────────────────────────────────────────────────

    def process_order(
        self,
        order_id: str,
        amount: float,
        currency: Optional[str] = None,
        network: Optional[str] = None,
        label: Optional[str] = None,
        redirect_url: str = "",
    ) -> Optional[dict]:
        """
        Create an AlgoVoi payment link for an eBay order.

        Args:
            order_id:     eBay order ID
            amount:       Order total
            currency:     ISO currency code (defaults to base_currency)
            network:      Preferred network (defaults to default_network)
            label:        Payment label
            redirect_url: Return URL after payment (optional)

        Returns:
            dict with checkout_url, token, chain, amount_microunits — or None
        """
        if not network or network not in HOSTED_NETWORKS:
            network = self.default_network
        if not currency:
            currency = self.base_currency
        if not label:
            label = f"eBay Order #{order_id}"

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

        token = ""
        m = re.search(r"/checkout/([A-Za-z0-9_-]+)$", resp["checkout_url"])
        if m:
            token = m.group(1)

        return {
            "checkout_url": resp["checkout_url"],
            "token": token,
            "chain": resp.get("chain", "algorand-mainnet"),
            "amount_microunits": int(resp.get("amount_microunits", 0)),
            "order_id": order_id,
        }

    def verify_payment(self, token: str) -> bool:
        """
        Check if a payment has been completed.

        Args:
            token: AlgoVoi checkout token

        Returns:
            True only if the API confirms payment is complete
        """
        if not token:
            return False

        url = f"{self.api_base}/checkout/{quote(token, safe='')}"
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

    # ── eBay API Integration ─────────────────────────────────────────────

    def parse_order_webhook(self, payload: dict) -> Optional[dict]:
        """
        Parse an eBay Platform Notification payload.

        Handles checkout.order.created and similar events.

        Args:
            payload: The parsed webhook JSON

        Returns:
            dict with order_id, amount, currency, status — or None
        """
        try:
            notification = payload.get("notification", payload)
            topic = notification.get("topic", payload.get("topic", ""))
            data = notification.get("data", notification)

            order_id = data.get("orderId", data.get("order", {}).get("orderId", ""))
            if not order_id:
                # Try top-level
                order_id = payload.get("orderId", "")
            if not order_id:
                return None

            # Amount from pricingSummary.total or total
            pricing = data.get("pricingSummary", {})
            total_field = pricing.get("total", {})
            if isinstance(total_field, dict):
                amount = float(total_field.get("value", 0) or 0)
                currency = total_field.get("currency", self.base_currency)
            else:
                amount = float(total_field or 0)
                currency = self.base_currency

            buyer = data.get("buyer", {})
            buyer_username = buyer.get("username", "") if isinstance(buyer, dict) else ""
            status = data.get("orderFulfillmentStatus", data.get("status", ""))

            return {
                "order_id": str(order_id),
                "amount": amount,
                "currency": (currency or self.base_currency).upper(),
                "status": str(status),
                "buyer_username": buyer_username,
                "topic": topic,
            }
        except (KeyError, ValueError, TypeError):
            return None

    def fulfill_order(
        self,
        order_id: str,
        tx_id: str,
    ) -> bool:
        """
        Mark an eBay order as shipped using the Fulfillment API.

        Posts a shipping_fulfillment with the AlgoVoi TX ID as tracking.

        Args:
            order_id: eBay order ID
            tx_id:    On-chain transaction ID

        Returns:
            True if the fulfilment was accepted
        """
        if not tx_id or len(tx_id) > 200:
            return False

        if not self.access_token:
            return False

        url = f"{EBAY_FULFILLMENT_BASE}/order/{quote(str(order_id), safe='')}/shipping_fulfillment"

        payload = json.dumps({
            "lineItems": [{"lineItemId": order_id, "quantity": 1}],
            "shippedDate": time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime()),
            "shippingCarrierCode": "AlgoVoi",
            "trackingNumber": f"TX:{tx_id[:64]}",
        }).encode()

        req = Request(url, data=payload, method="POST", headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.access_token}",
            "User-Agent": "AlgoVoi/1.0",
        })

        try:
            with urlopen(req, timeout=self.timeout, context=self._ssl) as resp:  # nosec B310
                return resp.status in (200, 201, 204)
        except (URLError, OSError):
            return False

    # ── Flask Helper ─────────────────────────────────────────────────────

    def flask_webhook_handler(self):
        """
        Returns a Flask view function for the eBay Platform Notification endpoint.

        Handles both the challenge-response GET and POST notifications.

        Usage:
            app.add_url_rule('/webhook/ebay',
                view_func=adapter.flask_webhook_handler(), methods=['GET', 'POST'])
        """
        adapter = self

        def handler():
            from flask import request, jsonify

            # Challenge-response for eBay endpoint verification
            if request.method == "GET":
                challenge_code = request.args.get("challenge_code", "")
                if challenge_code:
                    response_hash = adapter.handle_challenge(
                        challenge_code,
                        request.url,
                    )
                    if response_hash:
                        return jsonify(challengeResponse=response_hash)
                return jsonify(error="Bad Request"), 400

            raw_body = request.get_data()
            signature = request.headers.get("X-Ebay-Signature", "")

            payload = adapter.verify_webhook(raw_body, signature)
            if not payload:
                return jsonify(error="Unauthorized"), 401

            order = adapter.parse_order_webhook(payload)
            if not order:
                return jsonify(received=True, skipped="not parseable")

            result = adapter.process_order(
                order_id=order["order_id"],
                amount=order["amount"],
                currency=order["currency"],
            )

            if not result:
                return jsonify(error="Could not create payment link"), 502

            return jsonify(
                received=True,
                order_id=order["order_id"],
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
