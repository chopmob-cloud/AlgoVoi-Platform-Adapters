"""
AlgoVoi Squarespace Commerce Payment Adapter

Receives Squarespace Commerce webhook notifications (order.create),
creates AlgoVoi payment links, and marks orders as fulfilled when
payment is confirmed on-chain.

Squarespace does NOT support custom payment gateways at checkout.
This adapter handles post-order B2B payment flows:
  - B2B / wholesale invoicing — send crypto payment request to trade buyers
  - Seller settlement — settle invoices in USDC/aUSDC between parties
  - Manual payment links — merchant sends link to buyer after order

Works with Flask, Django, FastAPI, or any WSGI framework.
Zero pip dependencies — uses only the Python standard library.

Squarespace API docs: https://developers.squarespace.com/commerce-apis/overview

Version: 1.0.0

AlgoVoi docs: https://github.com/chopmob-cloud/AlgoVoi-Platform-Adapters
Licensed under the Business Source License 1.1 — see LICENSE for details.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re
import ssl
import time
from typing import Any, Optional
from urllib.parse import quote
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


class SquarespaceAlgoVoi:
    """Squarespace Commerce + AlgoVoi payment adapter."""

    def __init__(
        self,
        api_base: str = "https://api1.ilovechicken.co.uk",
        api_key: str = "",
        tenant_id: str = "",
        squarespace_api_key: str = "",
        webhook_secret: str = "",
        default_network: str = "algorand_mainnet",
        base_currency: str = "GBP",
        timeout: int = 30,
    ):
        self.api_base = api_base.rstrip("/")
        self.api_key = api_key
        self.tenant_id = tenant_id
        self.squarespace_api_key = squarespace_api_key
        self.webhook_secret = webhook_secret
        self.default_network = default_network
        self.base_currency = base_currency
        self.timeout = timeout
        self._ssl = ssl.create_default_context()

    # ── Webhook Verification ─────────────────────────────────────────────

    def verify_webhook(self, raw_body: bytes, signature: str) -> Optional[dict]:
        """
        Verify a Squarespace webhook using the Squarespace-Signature header.

        Squarespace signs webhooks with HMAC-SHA256 using the webhook secret.

        Args:
            raw_body:  Raw POST body as bytes
            signature: Squarespace-Signature header value

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
        Create an AlgoVoi payment link for a Squarespace order.

        Args:
            order_id:     Squarespace order ID
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
            label = f"Squarespace Order #{order_id}"

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
        try:
            req = Request(url, method="GET")
            with urlopen(req, timeout=15, context=self._ssl) as resp:  # nosec B310
                if resp.status != 200:
                    return False
                data = json.loads(resp.read())
                return data.get("status") in ("paid", "completed", "confirmed")
        except (URLError, json.JSONDecodeError, OSError):
            return False

    # ── Squarespace API Integration ──────────────────────────────────────

    def parse_order_webhook(self, payload: dict) -> Optional[dict]:
        """
        Parse a Squarespace order webhook payload.

        Handles order.create and order.update topics.

        Args:
            payload: The parsed webhook JSON

        Returns:
            dict with order_id, amount, currency, status — or None
        """
        try:
            topic = payload.get("topic", "")
            data = payload.get("data", payload)

            if topic not in ("order.create", "order.update", ""):
                return None

            order_id = data.get("id", data.get("orderId", ""))
            if not order_id:
                return None

            # Squarespace uses grandTotal with value and currency
            grand_total = data.get("grandTotal", data.get("subtotal", {}))
            if isinstance(grand_total, dict):
                amount = float(grand_total.get("value", grand_total.get("decimalValue", "0")))
                currency = grand_total.get("currency", self.base_currency)
            else:
                amount = float(grand_total or 0)
                currency = self.base_currency

            status = data.get("fulfillmentStatus", data.get("financialStatus", ""))
            order_number = data.get("orderNumber", "")
            customer_email = data.get("customerEmail", "")

            return {
                "order_id": str(order_id),
                "order_number": str(order_number),
                "amount": amount,
                "currency": currency.upper() if currency else self.base_currency,
                "status": str(status),
                "customer_email": customer_email,
                "topic": topic,
            }
        except (KeyError, ValueError, TypeError):
            return None

    def fulfill_order(
        self,
        order_id: str,
        tx_id: str,
        shipments: Optional[list] = None,
    ) -> bool:
        """
        Mark a Squarespace order as fulfilled with the AlgoVoi TX reference.

        Squarespace doesn't have a "mark as paid" endpoint — fulfilment
        is the closest equivalent. This sets the order status to FULFILLED
        and adds the TX ID as a tracking reference.

        Args:
            order_id:  Squarespace order ID
            tx_id:     On-chain transaction ID
            shipments: Optional shipment details (auto-generated if empty)

        Returns:
            True if the fulfilment was accepted
        """
        if not tx_id or len(tx_id) > 200:
            return False

        if not self.squarespace_api_key:
            return False

        url = f"https://api.squarespace.com/1.0/commerce/orders/{quote(order_id, safe='')}/fulfillments"

        if not shipments:
            shipments = [{
                "shipDate": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "carrierName": "AlgoVoi",
                "trackingNumber": f"TX:{tx_id[:64]}",
                "trackingUrl": f"https://api1.ilovechicken.co.uk/checkout/{tx_id[:40]}",
            }]

        payload = json.dumps({
            "shouldSendNotification": True,
            "shipments": shipments,
        }).encode()

        req = Request(url, data=payload, method="POST", headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.squarespace_api_key}",
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
        Returns a Flask view function for the Squarespace webhook endpoint.

        Usage:
            app.add_url_rule('/webhook/squarespace',
                view_func=adapter.flask_webhook_handler(), methods=['POST'])
        """
        adapter = self

        def handler():
            from flask import request, jsonify

            raw_body = request.get_data()
            signature = request.headers.get("Squarespace-Signature", "")

            payload = adapter.verify_webhook(raw_body, signature)
            if not payload:
                return jsonify(error="Unauthorized"), 401

            order = adapter.parse_order_webhook(payload)
            if not order:
                return jsonify(received=True, skipped="not parseable")

            # Skip already fulfilled orders
            if order["status"] in ("FULFILLED", "CANCELED"):
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
                order_number=order["order_number"],
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
