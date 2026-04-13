"""
AlgoVoi WhatsApp Business Cloud API Payment Adapter

Receives WhatsApp order messages (product_items from catalogue), creates
AlgoVoi hosted payment links, and replies to the customer with a CTA button.

Webhook security:
  - GET  (challenge): hub.verify_token must match verify_token
  - POST (events):    X-Hub-Signature-256 = sha256=HMAC-SHA256(app_secret, body)

WhatsApp Cloud API docs: https://developers.facebook.com/docs/whatsapp/cloud-api

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


class WhatsAppAlgoVoi:
    """WhatsApp Business Cloud API + AlgoVoi payment adapter."""

    def __init__(
        self,
        api_base: str = "https://api1.ilovechicken.co.uk",
        api_key: str = "",
        tenant_id: str = "",
        whatsapp_token: str = "",
        phone_number_id: str = "",
        verify_token: str = "",
        webhook_secret: str = "",
        default_network: str = "algorand_mainnet",
        base_currency: str = "GBP",
        timeout: int = 30,
    ):
        self.api_base = api_base.rstrip("/")
        self.api_key = api_key
        self.tenant_id = tenant_id
        self.whatsapp_token = whatsapp_token
        self.phone_number_id = phone_number_id
        # verify_token is used for Meta webhook subscription challenge (GET)
        self.verify_token = verify_token
        # webhook_secret = app_secret used for X-Hub-Signature-256 HMAC (POST)
        self.webhook_secret = webhook_secret
        self.default_network = default_network
        self.base_currency = base_currency
        self.timeout = timeout
        self._ssl = ssl.create_default_context()

    # ── Webhook Verification ─────────────────────────────────────────────

    def verify_webhook_challenge(
        self, mode: str, token: str, challenge: str
    ) -> Optional[str]:
        """
        Validate a Meta webhook subscription challenge (GET request).

        Meta sends:
            ?hub.mode=subscribe&hub.verify_token=<token>&hub.challenge=<challenge>

        Args:
            mode:      hub.mode parameter
            token:     hub.verify_token parameter
            challenge: hub.challenge parameter

        Returns:
            challenge string if valid, None otherwise
        """
        if mode == "subscribe" and token and hmac.compare_digest(self.verify_token, token):
            return challenge
        return None

    def verify_webhook(self, raw_body: bytes, signature: str) -> Optional[dict]:
        """
        Verify a WhatsApp webhook POST via X-Hub-Signature-256 header.

        Meta signs the raw body with HMAC-SHA256 using the app_secret
        (stored as webhook_secret) and prefixes the hex digest with "sha256=".

        Args:
            raw_body:  Raw POST body as bytes
            signature: X-Hub-Signature-256 header value (e.g. "sha256=abc...")

        Returns:
            Parsed payload dict, or None if verification fails
        """
        if not self.webhook_secret:
            return None

        # Strip "sha256=" prefix
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

    def parse_order_message(self, payload: dict) -> Optional[dict]:
        """
        Parse a WhatsApp order message webhook payload.

        Extracts the sender (from), total order amount, and currency from
        messages[].order.product_items.

        Args:
            payload: Parsed webhook JSON

        Returns:
            dict with from_number, amount, currency — or None
        """
        try:
            entries = payload.get("entry", [])
            for entry in entries:
                for change in entry.get("changes", []):
                    value = change.get("value", {})
                    messages = value.get("messages", [])
                    for message in messages:
                        if message.get("type") != "order":
                            continue
                        from_number = message.get("from", "")
                        order = message.get("order", {})
                        product_items = order.get("product_items", [])
                        if not product_items:
                            continue

                        # Sum all product items: quantity × item_price
                        total = 0.0
                        currency = self.base_currency
                        for item in product_items:
                            qty = int(item.get("quantity", 1))
                            price = float(item.get("item_price", 0))
                            total += qty * price
                            # Currency from first item
                            if item.get("currency"):
                                currency = str(item["currency"]).upper()

                        if from_number and total > 0:
                            return {
                                "from_number": from_number,
                                "amount": round(total, 2),
                                "currency": currency,
                                "catalog_id": order.get("catalog_id", ""),
                            }
            return None
        except (KeyError, TypeError, ValueError, AttributeError):
            return None

    # ── Checkout ─────────────────────────────────────────────────────────

    def create_checkout(
        self,
        to: str,
        amount: float,
        currency: Optional[str] = None,
        network: Optional[str] = None,
        label: Optional[str] = None,
    ) -> Optional[dict]:
        """
        Create an AlgoVoi payment link for a WhatsApp order.

        Args:
            to:       Customer WhatsApp number (used as reference)
            amount:   Order total
            currency: ISO currency code (defaults to base_currency)
            network:  Preferred network (defaults to default_network)
            label:    Payment label

        Returns:
            dict with checkout_url, token, chain, amount_microunits — or None
        """
        if not network or network not in HOSTED_NETWORKS:
            network = self.default_network
        if not currency:
            currency = self.base_currency
        if not label:
            label = f"WhatsApp Order from {to}"

        payload: dict[str, Any] = {
            "amount": round(amount, 2),
            "currency": currency.upper(),
            "label": label,
            "preferred_network": network,
            "reference": to,
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
            "to": to,
        }

    def send_payment_link(
        self,
        to: str,
        checkout_url: str,
        amount: float,
    ) -> bool:
        """
        Send a CTA button message with the checkout URL via WhatsApp Cloud API.

        POST https://graph.facebook.com/v18.0/{phone_number_id}/messages

        Args:
            to:           Recipient WhatsApp number (E.164)
            checkout_url: AlgoVoi hosted checkout URL
            amount:       Order total (shown in message body text)

        Returns:
            True if the Graph API accepted the message
        """
        if not self.whatsapp_token or not self.phone_number_id:
            return False
        if not to or not checkout_url:
            return False

        url = f"{GRAPH_API_BASE}/{self.phone_number_id}/messages"
        body = json.dumps({
            "messaging_product": "whatsapp",
            "to": to,
            "type": "interactive",
            "interactive": {
                "type": "cta_url",
                "body": {
                    "text": f"Your order total is {amount:.2f}. Pay in USDC on Algorand:",
                },
                "action": {
                    "name": "cta_url",
                    "parameters": {
                        "display_text": "Pay with USDC",
                        "url": checkout_url,
                    },
                },
            },
        }).encode()

        req = Request(
            url,
            data=body,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.whatsapp_token}",
            },
        )
        try:
            with urlopen(req, timeout=self.timeout, context=self._ssl) as resp:  # nosec B310
                return resp.status in (200, 201)
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
        Returns a Flask view function for the WhatsApp webhook endpoint.

        Handles:
          - GET  → webhook challenge verification
          - POST → order message processing

        Usage:
            app.add_url_rule('/webhook/whatsapp',
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
                result = adapter.verify_webhook_challenge(mode, token, challenge)
                if result is None:
                    return jsonify(error="Forbidden"), 403
                return result, 200

            # POST
            raw_body = request.get_data()
            signature = request.headers.get("X-Hub-Signature-256", "")

            payload = adapter.verify_webhook(raw_body, signature)
            if payload is None:
                return jsonify(error="Unauthorized"), 401

            order = adapter.parse_order_message(payload)
            if not order:
                return jsonify(received=True, skipped="not an order message")

            result = adapter.create_checkout(
                to=order["from_number"],
                amount=order["amount"],
                currency=order["currency"],
            )

            if not result:
                return jsonify(error="Could not create payment link"), 502

            adapter.send_payment_link(
                to=order["from_number"],
                checkout_url=result["checkout_url"],
                amount=order["amount"],
            )

            return jsonify(
                received=True,
                from_number=order["from_number"],
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
