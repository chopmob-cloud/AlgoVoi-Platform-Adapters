"""
AlgoVoi Printful Payment Adapter

Printful is a print-on-demand fulfillment service. This adapter lets
merchants pay Printful production costs in USDC on Algorand or aUSDC
on VOI instead of fiat, eliminating card fees and FX conversion.

Flow:
  Storefront order → Printful webhook (order_created) → AlgoVoi creates
  checkout link → Merchant pays on-chain → AlgoVoi confirms order with
  Printful via POST /orders/{id}/confirm

Webhook security:
  X-Printful-Signature: HMAC-SHA256(webhook_secret, raw_body) hex digest

Printful API docs: https://developers.printful.com/docs/

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

PRINTFUL_API_BASE = "https://api.printful.com"


class PrintfulAlgoVoi:
    """Printful print-on-demand + AlgoVoi payment adapter."""

    def __init__(
        self,
        api_base: str = "https://api1.ilovechicken.co.uk",
        api_key: str = "",
        tenant_id: str = "",
        printful_token: str = "",
        webhook_secret: str = "",
        default_network: str = "algorand_mainnet",
        base_currency: str = "USD",
        timeout: int = 30,
    ):
        self.api_base = api_base.rstrip("/")
        self.api_key = api_key
        self.tenant_id = tenant_id
        self.printful_token = printful_token
        self.webhook_secret = webhook_secret
        self.default_network = default_network
        self.base_currency = base_currency
        self.timeout = timeout
        self._ssl = ssl.create_default_context()

    # ── Webhook Verification ─────────────────────────────────────────────

    def verify_webhook(self, raw_body: bytes, signature: str) -> Optional[dict]:
        """
        Verify a Printful webhook via X-Printful-Signature header.

        Printful signs webhooks with HMAC-SHA256 of the raw body using
        the webhook secret registered when the webhook was created.

        Args:
            raw_body:  Raw POST body as bytes
            signature: X-Printful-Signature header value (hex digest)

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

    # ── Order Parsing ─────────────────────────────────────────────────────

    def parse_order_webhook(self, payload: dict) -> Optional[dict]:
        """
        Parse a Printful order webhook payload.

        Handles types: order_created, order_updated.

        Args:
            payload: Parsed webhook JSON

        Returns:
            dict with type, order_id, amount, currency — or None
        """
        try:
            event_type = payload.get("type", "")
            if event_type not in ("order_created", "order_updated", ""):
                return None

            data = payload.get("data", {})
            order = data.get("order", data)

            order_id = str(order.get("id", ""))
            if not order_id:
                return None

            # Printful costs object: data.order.costs.total (production cost, USD)
            costs = order.get("costs", {})
            if isinstance(costs, dict):
                total = float(costs.get("total", costs.get("subtotal", 0)))
                currency = str(costs.get("currency", self.base_currency)).upper()
            else:
                total = float(costs or 0)
                currency = self.base_currency

            status = order.get("status", "")

            return {
                "type": event_type,
                "order_id": order_id,
                "amount": round(total, 2),
                "currency": currency,
                "status": str(status),
            }
        except (KeyError, TypeError, ValueError, AttributeError):
            return None

    # ── Payment / Checkout ────────────────────────────────────────────────

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
        Create an AlgoVoi payment link for a Printful production invoice.

        Args:
            order_id:     Printful order ID
            amount:       Production cost (USD)
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
            label = f"Printful Order #{order_id} Production Cost"

        payload: dict[str, Any] = {
            "amount": round(amount, 2),
            "currency": currency.upper(),
            "label": label,
            "preferred_network": network,
            "reference": order_id,
        }
        if redirect_url:
            payload["redirect_url"] = redirect_url
            payload["expires_in_seconds"] = 1800

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

    def confirm_order(self, order_id: str) -> bool:
        """
        Confirm a Printful order after payment is verified on-chain.

        Calls POST https://api.printful.com/orders/{id}/confirm to
        submit the order to production.

        Args:
            order_id: Printful order ID

        Returns:
            True if Printful accepted the confirmation
        """
        if not self.printful_token or not order_id:
            return False

        url = f"{PRINTFUL_API_BASE}/orders/{quote(str(order_id), safe='')}/confirm"
        req = Request(
            url,
            data=b"{}",
            method="POST",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.printful_token}",
            },
        )
        try:
            with urlopen(req, timeout=self.timeout, context=self._ssl) as resp:  # nosec B310
                return resp.status in (200, 201, 204)
        except (URLError, OSError):
            return False


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
        tx_id = token
        if len(tx_id) > 200:
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

    # ── Flask Handler ─────────────────────────────────────────────────────

    def flask_webhook_handler(self):
        """
        Returns a Flask view function for the Printful webhook endpoint.

        Usage:
            app.add_url_rule('/webhook/printful',
                view_func=adapter.flask_webhook_handler(), methods=['POST'])
        """
        adapter = self

        def handler():
            from flask import request, jsonify

            raw_body = request.get_data()
            signature = request.headers.get("X-Printful-Signature", "")

            payload = adapter.verify_webhook(raw_body, signature)
            if payload is None:
                return jsonify(error="Unauthorized"), 401

            order = adapter.parse_order_webhook(payload)
            if not order:
                return jsonify(received=True, skipped="not a parseable order event")

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
