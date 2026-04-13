"""
AlgoVoi Printify Payment Adapter

Printify connects merchants to 900+ print providers. This adapter lets
merchants pay Printify production costs in USDC on Algorand or aUSDC
on VOI instead of fiat, eliminating card fees and FX conversion.

Flow:
  Storefront order → Printify webhook (order:created) → AlgoVoi creates
  checkout link → Merchant pays on-chain → AlgoVoi submits the order to
  production via POST /orders/{id}/send_to_production.json

Webhook security:
  X-Printify-Signature: HMAC-SHA256(webhook_secret, raw_body) hex digest
  (header name matches Printify docs: x-pfy-signature)

Printify API docs: https://developers.printify.com/

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

PRINTIFY_API_BASE = "https://api.printify.com/v1"


class PrintifyAlgoVoi:
    """Printify print-on-demand + AlgoVoi payment adapter."""

    def __init__(
        self,
        api_base: str = "https://api1.ilovechicken.co.uk",
        api_key: str = "",
        tenant_id: str = "",
        printify_token: str = "",
        shop_id: str = "",
        webhook_secret: str = "",
        default_network: str = "algorand_mainnet",
        base_currency: str = "USD",
        timeout: int = 30,
    ):
        self.api_base = api_base.rstrip("/")
        self.api_key = api_key
        self.tenant_id = tenant_id
        self.printify_token = printify_token
        self.shop_id = shop_id
        self.webhook_secret = webhook_secret
        self.default_network = default_network
        self.base_currency = base_currency
        self.timeout = timeout
        self._ssl = ssl.create_default_context()

    # ── Webhook Verification ─────────────────────────────────────────────

    def verify_webhook(self, raw_body: bytes, signature: str) -> Optional[dict]:
        """
        Verify a Printify webhook via X-Pfy-Signature header.

        Printify signs webhooks with HMAC-SHA256 of the raw body using
        the secret registered when the webhook was created. The official
        header is X-Pfy-Signature with value sha256={hex_digest}.

        Args:
            raw_body:  Raw POST body as bytes
            signature: hex digest (sha256= prefix already stripped)

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
        Parse a Printify order:created webhook payload.

        Printify sends total_price in cents — divide by 100 to get dollars.

        Args:
            payload: Parsed webhook JSON

        Returns:
            dict with type, order_id, amount, currency — or None
        """
        try:
            event_type = payload.get("type", "")
            if event_type not in ("order:created", "order:updated", ""):
                return None

            data = payload.get("data", payload)

            order_id = str(data.get("id", ""))
            if not order_id:
                return None

            # Printify total_price is in cents
            total_price_cents = int(data.get("total_price", 0))
            amount = round(total_price_cents / 100, 2)

            currency = str(data.get("currency", self.base_currency)).upper()
            status = str(data.get("status", ""))

            return {
                "type": event_type,
                "order_id": order_id,
                "amount": amount,
                "currency": currency,
                "status": status,
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
        Create an AlgoVoi payment link for a Printify production invoice.

        Args:
            order_id:     Printify order ID
            amount:       Production cost in major currency units
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
            label = f"Printify Order #{order_id} Production Cost"

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

    def submit_order(self, order_id: str) -> bool:
        """
        Submit a Printify order to production after on-chain payment.

        Calls POST https://api.printify.com/v1/shops/{shop_id}/orders/{id}/send_to_production.json

        Args:
            order_id: Printify order ID

        Returns:
            True if Printify accepted the submission
        """
        if not self.printify_token or not self.shop_id or not order_id:
            return False

        url = (
            f"{PRINTIFY_API_BASE}/shops/{quote(str(self.shop_id), safe='')}/"
            f"orders/{quote(str(order_id), safe='')}/send_to_production.json"
        )
        req = Request(
            url,
            data=b"{}",
            method="POST",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.printify_token}",
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
        Returns a Flask view function for the Printify webhook endpoint.

        Usage:
            app.add_url_rule('/webhook/printify',
                view_func=adapter.flask_webhook_handler(), methods=['POST'])
        """
        adapter = self

        def handler():
            from flask import request, jsonify

            raw_body = request.get_data()
            # Official Printify header is X-Pfy-Signature (sha256={digest})
            # Also accept X-Printify-Signature for backwards compatibility
            sig_raw = (
                request.headers.get("X-Pfy-Signature")
                or request.headers.get("x-pfy-signature")
                or request.headers.get("X-Printify-Signature", "")
            )
            # Strip sha256= prefix if present
            signature = sig_raw[7:] if sig_raw.startswith("sha256=") else sig_raw

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
