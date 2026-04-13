"""
AlgoVoi Shopee Payment Adapter

Receives Shopee push notifications (order status changes),
creates AlgoVoi payment links, and marks orders shipped when
payment is confirmed on-chain.

Shopee does NOT support custom payment gateways at checkout.
This adapter handles post-order B2B payment flows:
  - B2B / wholesale invoicing — send crypto payment request to trade buyers
  - Seller settlement — settle invoices in USDC/aUSDC between parties
  - Manual payment links — merchant sends link to buyer after order

Works with Flask, Django, FastAPI, or any WSGI framework.
Zero pip dependencies — uses only the Python standard library.

Shopee Open Platform docs: https://open.shopee.com/documents

Version: 1.0.0

AlgoVoi docs: https://github.com/chopmob-cloud/AlgoVoi-Platform-Adapters
Licensed under the Business Source License 1.1 — see LICENSE for details.
"""

# PROVISIONAL: This adapter has not been end-to-end tested against a live
# platform environment. API details are based on official documentation and
# community sources. Verify against your platform's current API before
# production use. See README.md for status.

from __future__ import annotations

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

SHOPEE_API_BASE = "https://partner.shopeemobile.com/api/v2"


class ShopeeAlgoVoi:
    """Shopee Open Platform + AlgoVoi payment adapter."""

    def __init__(
        self,
        api_base: str = "https://api1.ilovechicken.co.uk",
        api_key: str = "",
        tenant_id: str = "",
        partner_id: str = "",
        partner_key: str = "",
        shop_id: str = "",
        access_token: str = "",
        webhook_secret: str = "",
        default_network: str = "algorand_mainnet",
        base_currency: str = "SGD",
        timeout: int = 30,
    ):
        self.api_base = api_base.rstrip("/")
        self.api_key = api_key
        self.tenant_id = tenant_id
        self.partner_id = partner_id
        self.partner_key = partner_key
        self.shop_id = shop_id
        self.access_token = access_token
        self.webhook_secret = webhook_secret
        self.default_network = default_network
        self.base_currency = base_currency
        self.timeout = timeout
        self._ssl = ssl.create_default_context()

    # ── Webhook Verification ─────────────────────────────────────────────

    def verify_webhook(self, raw_body: bytes, signature: str) -> Optional[dict]:
        """
        Verify a Shopee push notification using the Authorization header.

        Shopee signs webhooks with HMAC-SHA256(partner_key, raw_body).
        The signature is delivered in the Authorization header of each push
        request (not X-Shopee-Signature).

        Args:
            raw_body:  Raw POST body as bytes
            signature: Authorization header value from the push request

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
        Create an AlgoVoi payment link for a Shopee order.

        Args:
            order_id:     Shopee order SN (order_sn)
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
            label = f"Shopee Order #{order_id}"

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

    # ── Shopee API Integration ──────────────────────────────────────────

    def parse_order_webhook(self, payload: dict) -> Optional[dict]:
        """
        Parse a Shopee push notification payload.

        Shopee push code 3 = order status update.
        The order_sn is used as the order ID.

        Args:
            payload: The parsed webhook JSON

        Returns:
            dict with order_id, amount, currency, status — or None
        """
        try:
            code = payload.get("code")
            # Code 3 = order status push notification
            if code is not None and code != 3:
                return None

            data = payload.get("data", {})
            order_id = data.get("ordersn", data.get("order_sn", ""))
            if not order_id:
                return None

            status = data.get("status", "")
            shop_id = payload.get("shop_id", "")
            timestamp = payload.get("timestamp", 0)

            # Amount may not be in the push notification — zero means fetch needed
            amount = float(data.get("total_amount", data.get("amount", 0)))
            currency = data.get("currency", self.base_currency)

            return {
                "order_id": str(order_id),
                "amount": amount,
                "currency": currency.upper() if currency else self.base_currency,
                "status": str(status),
                "shop_id": str(shop_id),
                "timestamp": int(timestamp),
                "code": code,
            }
        except (KeyError, ValueError, TypeError):
            return None

    def _build_sign(self, path: str, timestamp: int) -> str:
        """
        Build Shopee API request signature.

        Base string: {partner_id}{path}{timestamp}{access_token}{shop_id}
        Signed with partner_key using HMAC-SHA256.
        """
        base_string = (
            f"{self.partner_id}{path}{timestamp}{self.access_token}{self.shop_id}"
        )
        return hmac.new(
            self.partner_key.encode(),
            base_string.encode(),
            hashlib.sha256,
        ).hexdigest()

    def fulfill_order(self, order_id: str, tx_id: str) -> bool:
        """
        Mark a Shopee order as shipped via POST /logistics/ship_order.

        Uses the AlgoVoi TX ID as the tracking number reference.

        Args:
            order_id: Shopee order SN
            tx_id:    On-chain transaction ID

        Returns:
            True if the shipment was accepted
        """
        if not tx_id or len(tx_id) > 200:
            return False

        if not self.partner_key or not self.partner_id:
            return False

        path = "/api/v2/logistics/ship_order"
        timestamp = int(time.time())
        sign = self._build_sign(path, timestamp)

        params = urlencode({
            "partner_id": self.partner_id,
            "shop_id": self.shop_id,
            "access_token": self.access_token,
            "timestamp": timestamp,
            "sign": sign,
        })

        url = f"{SHOPEE_API_BASE}/logistics/ship_order?{params}"

        body = json.dumps({
            "order_sn": order_id,
            "pickup": {
                "address_id": 0,
                "pickup_time_id": "",
            },
            "tracking_no": f"TX:{tx_id[:64]}",
        }).encode()

        req = Request(url, data=body, method="POST", headers={
            "Content-Type": "application/json",
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
        Returns a Flask view function for the Shopee webhook endpoint.

        Usage:
            app.add_url_rule('/webhook/shopee',
                view_func=adapter.flask_webhook_handler(), methods=['POST'])
        """
        adapter = self

        def handler():
            from flask import request, jsonify

            raw_body = request.get_data()
            signature = request.headers.get("Authorization", "")

            payload = adapter.verify_webhook(raw_body, signature)
            if not payload:
                return jsonify(error="Unauthorized"), 401

            order = adapter.parse_order_webhook(payload)
            if not order:
                return jsonify(received=True, skipped="not parseable")

            if order["status"] in ("CANCELLED", "UNPAID"):
                return jsonify(received=True, skipped=f"status={order['status']}")

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
