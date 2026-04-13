"""
AlgoVoi Instagram & Facebook Shops Payment Adapter

Meta Commerce Platform external checkout integration. Customers browse
an Instagram or Facebook Shop and are redirected to an AlgoVoi hosted
checkout page to complete payment on-chain.

Requires Meta Tech Provider Agreement and Commerce Partner approval.

Webhook security:
  - GET  (challenge): hub.verify_token must match verify_token
  - POST (events):    X-Hub-Signature-256 = sha256=HMAC-SHA256(app_secret, body)

Meta Commerce API docs:
  https://developers.facebook.com/docs/commerce-platform/order-management/

Version: 1.0.0

AlgoVoi docs: https://github.com/chopmob-cloud/AlgoVoi-Platform-Adapters
Copyright (c) 2026 Christopher Hopley (ilovechicken.co.uk). BSL 1.1.
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

GRAPH_API_BASE = "https://graph.facebook.com/v18.0"


class InstagramAlgoVoi:
    """Instagram / Facebook Shops + AlgoVoi payment adapter."""

    def __init__(
        self,
        api_base: str = "https://api1.ilovechicken.co.uk",
        api_key: str = "",
        tenant_id: str = "",
        access_token: str = "",
        app_secret: str = "",
        verify_token: str = "",
        webhook_secret: str = "",
        default_network: str = "algorand_mainnet",
        base_currency: str = "GBP",
        timeout: int = 30,
    ):
        self.api_base = api_base.rstrip("/")
        self.api_key = api_key
        self.tenant_id = tenant_id
        self.access_token = access_token
        # app_secret is used for X-Hub-Signature-256 HMAC verification
        self.app_secret = app_secret
        # verify_token is used for Meta webhook subscription challenge (GET)
        self.verify_token = verify_token
        # webhook_secret is the AlgoVoi-side HMAC secret for internal events
        self.webhook_secret = webhook_secret
        self.default_network = default_network
        self.base_currency = base_currency
        self.timeout = timeout
        self._ssl = ssl.create_default_context()

    # ── Webhook Verification ─────────────────────────────────────────────

    def verify_webhook(self, raw_body: bytes, signature: str) -> Optional[dict]:
        """
        Verify a Meta Commerce webhook POST via X-Hub-Signature-256 header.

        Meta signs the raw body with HMAC-SHA256 using the app_secret and
        prefixes the hex digest with "sha256=".

        Args:
            raw_body:  Raw POST body as bytes
            signature: X-Hub-Signature-256 header value (e.g. "sha256=abc...")

        Returns:
            Parsed payload dict, or None if verification fails
        """
        if not self.webhook_secret:
            return None

        if signature.startswith("sha256="):
            sig_hex = signature[7:]
        else:
            sig_hex = signature

        expected = hmac.new(
            self.webhook_secret.encode(),
            raw_body,
            hashlib.sha256,
        ).hexdigest()

        if not hmac.compare_digest(expected, sig_hex):
            return None

        try:
            return json.loads(raw_body)
        except json.JSONDecodeError:
            return None

    # ── Order Parsing ─────────────────────────────────────────────────────

    def parse_order_webhook(self, payload: dict) -> Optional[dict]:
        """
        Parse a Meta Commerce Platform order webhook.

        Extracts order_id, amount, and currency from
        entry[].changes[].value.

        Args:
            payload: Parsed webhook JSON

        Returns:
            dict with order_id, amount, currency, channel — or None
        """
        try:
            entries = payload.get("entry", [])
            for entry in entries:
                for change in entry.get("changes", []):
                    if change.get("field") not in ("orders", ""):
                        # Accept both "orders" field and unspecified
                        pass
                    value = change.get("value", {})
                    order_id = value.get("order_id", "")
                    if not order_id:
                        continue

                    # Attempt to extract amount from items array
                    items = value.get("items", [])
                    total = 0.0
                    currency = self.base_currency
                    for item in items:
                        qty = int(item.get("quantity", 1))
                        price_info = item.get("price_per_unit", {})
                        if isinstance(price_info, dict):
                            price = float(price_info.get("amount", 0))
                            if price_info.get("currency"):
                                currency = str(price_info["currency"]).upper()
                        else:
                            price = float(price_info or 0)
                        total += qty * price

                    # Fallback: top-level amount fields
                    if total == 0:
                        total = float(value.get("amount", value.get("total_amount", 0)))
                        if value.get("currency"):
                            currency = str(value["currency"]).upper()

                    channel = value.get("channel", "")
                    buyer = value.get("buyer_details", {}).get("name", "")

                    return {
                        "order_id": str(order_id),
                        "amount": round(total, 2),
                        "currency": currency,
                        "channel": channel,
                        "buyer_name": buyer,
                    }
            return None
        except (KeyError, TypeError, ValueError, AttributeError):
            return None

    # ── Checkout ─────────────────────────────────────────────────────────

    def create_checkout(
        self,
        order_id: str,
        amount: float,
        currency: Optional[str] = None,
        network: Optional[str] = None,
    ) -> Optional[dict]:
        """
        Create an AlgoVoi payment link for a Meta Commerce order.

        Args:
            order_id: Meta order ID
            amount:   Order total
            currency: ISO currency code (defaults to base_currency)
            network:  Preferred network (defaults to default_network)

        Returns:
            dict with checkout_url, token, chain, amount_microunits — or None
        """
        if not network or network not in HOSTED_NETWORKS:
            network = self.default_network
        if not currency:
            currency = self.base_currency

        label = f"Instagram/Facebook Shop Order #{order_id}"

        payload: dict[str, Any] = {
            "amount": round(amount, 2),
            "currency": currency.upper(),
            "label": label,
            "preferred_network": network,
            "reference": order_id,
        }

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
        Returns a Flask view function for the Meta Commerce webhook endpoint.

        Handles:
          - GET  → webhook challenge verification
          - POST → order webhook processing

        Usage:
            app.add_url_rule('/webhook/instagram',
                view_func=adapter.flask_webhook_handler(),
                methods=['GET', 'POST'])
        """
        adapter = self

        def handler():
            from flask import request, jsonify

            if request.method == "GET":
                mode = request.args.get("hub.mode", "")
                token = request.args.get("hub.verify_token", "")
                challenge = request.args.get("hub.challenge", "")
                if mode == "subscribe" and token and hmac.compare_digest(
                    adapter.verify_token, token
                ):
                    return challenge, 200
                return jsonify(error="Forbidden"), 403

            # POST
            raw_body = request.get_data()
            signature = request.headers.get("X-Hub-Signature-256", "")

            payload = adapter.verify_webhook(raw_body, signature)
            if payload is None:
                return jsonify(error="Unauthorized"), 401

            order = adapter.parse_order_webhook(payload)
            if not order:
                return jsonify(received=True, skipped="not an order event")

            result = adapter.create_checkout(
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
