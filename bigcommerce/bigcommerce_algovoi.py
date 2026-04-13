"""
AlgoVoi BigCommerce Payment Adapter

Receives BigCommerce webhook notifications (store/order/created),
creates AlgoVoi payment links, and marks orders as completed when
payment is confirmed on-chain.

BigCommerce webhooks carry only the order ID. AlgoVoi fetches the
full order via the BigCommerce V2 REST API.

BigCommerce signs webhook payloads with HMAC-SHA256 using the client
secret as the key. The signature is base64-encoded and delivered in
the X-BC-Signature header. AlgoVoi verifies this using
hmac.compare_digest to prevent timing attacks.

Works with Flask, Django, FastAPI, or any WSGI framework.
Zero pip dependencies — uses only the Python standard library.

BigCommerce API docs: https://developer.bigcommerce.com/docs/rest-management/orders

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
import base64
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


class BigCommerceAlgoVoi:
    """BigCommerce + AlgoVoi payment adapter."""

    def __init__(
        self,
        api_base: str = "https://api1.ilovechicken.co.uk",
        api_key: str = "",
        tenant_id: str = "",
        store_hash: str = "",
        access_token: str = "",
        webhook_secret: str = "",
        default_network: str = "algorand_mainnet",
        base_currency: str = "USD",
        timeout: int = 30,
    ):
        self.api_base = api_base.rstrip("/")
        self.api_key = api_key
        self.tenant_id = tenant_id
        self.store_hash = store_hash
        self.access_token = access_token
        self.webhook_secret = webhook_secret
        self.default_network = default_network
        self.base_currency = base_currency
        self.timeout = timeout
        self._ssl = ssl.create_default_context()

    # ── Webhook Verification ─────────────────────────────────────────────

    def verify_webhook(self, raw_body: bytes, signature: str) -> Optional[dict]:
        """
        Verify a BigCommerce webhook using the X-BC-Signature header.

        BigCommerce signs webhook payloads with HMAC-SHA256 using the
        client_secret as the key. The result is base64-encoded and sent
        in the X-BC-Signature header.

        Args:
            raw_body:  Raw POST body as bytes
            signature: X-BC-Signature header value (base64-encoded HMAC-SHA256)

        Returns:
            Parsed payload dict, or None if verification fails
        """
        if not self.webhook_secret:
            return None

        expected = base64.b64encode(
            hmac.new(
                self.webhook_secret.encode(),
                raw_body,
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
        order_id: str,
        amount: float,
        currency: Optional[str] = None,
        network: Optional[str] = None,
        label: Optional[str] = None,
        redirect_url: str = "",
    ) -> Optional[dict]:
        """
        Create an AlgoVoi payment link for a BigCommerce order.

        Args:
            order_id:     BigCommerce order ID
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
            label = f"BigCommerce Order #{order_id}"

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

    # ── BigCommerce API Integration ──────────────────────────────────────

    def fetch_order(self, order_id: str) -> Optional[dict]:
        """
        Fetch full order details from BigCommerce V2 API.

        BigCommerce webhooks carry only the order ID — this method
        retrieves the full order with amount and currency.

        Args:
            order_id: BigCommerce order ID

        Returns:
            Order dict or None
        """
        if not self.store_hash or not self.access_token:
            return None

        url = f"https://api.bigcommerce.com/stores/{quote(self.store_hash, safe='')}/v2/orders/{quote(str(order_id), safe='')}"
        req = Request(url, method="GET", headers={
            "X-Auth-Token": self.access_token,
            "Accept": "application/json",
            "Content-Type": "application/json",
        })
        try:
            with urlopen(req, timeout=self.timeout, context=self._ssl) as resp:  # nosec B310
                if resp.status != 200:
                    return None
                return json.loads(resp.read())
        except (URLError, json.JSONDecodeError, OSError):
            return None

    def parse_order_webhook(self, payload: dict) -> Optional[dict]:
        """
        Parse a BigCommerce order webhook payload.

        BigCommerce sends minimal data in the webhook — only the order ID
        is reliable. Use fetch_order() to retrieve full order details.

        Args:
            payload: The parsed webhook JSON

        Returns:
            dict with order_id, amount, currency, status — or None
        """
        try:
            scope = payload.get("scope", "")
            data = payload.get("data", {})

            if not data:
                return None

            order_id = data.get("id", "")
            if not order_id:
                return None

            # BigCommerce webhook only carries order ID; amount may be missing
            amount = float(data.get("total_inc_tax", data.get("total_ex_tax", 0)) or 0)
            currency = data.get("currency_code", self.base_currency) or self.base_currency
            status = str(data.get("status_id", data.get("status", "")))

            return {
                "order_id": str(order_id),
                "amount": amount,
                "currency": currency.upper(),
                "status": status,
                "scope": scope,
            }
        except (KeyError, ValueError, TypeError):
            return None

    def fulfill_order(
        self,
        order_id: str,
        tx_id: str,
    ) -> bool:
        """
        Mark a BigCommerce order as Completed (status_id=10).

        Appends the AlgoVoi TX ID as a staff note on the order.

        Args:
            order_id: BigCommerce order ID
            tx_id:    On-chain transaction ID

        Returns:
            True if the update was accepted
        """
        if not tx_id or len(tx_id) > 200:
            return False

        if not self.store_hash or not self.access_token:
            return False

        url = f"https://api.bigcommerce.com/stores/{quote(self.store_hash, safe='')}/v2/orders/{quote(str(order_id), safe='')}"

        payload = json.dumps({
            "status_id": 10,
            "staff_notes": f"AlgoVoi TX: {tx_id[:64]}",
        }).encode()

        req = Request(url, data=payload, method="PUT", headers={
            "Content-Type": "application/json",
            "X-Auth-Token": self.access_token,
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
        Returns a Flask view function for the BigCommerce webhook endpoint.

        Usage:
            app.add_url_rule('/webhook/bigcommerce',
                view_func=adapter.flask_webhook_handler(), methods=['POST'])
        """
        adapter = self

        def handler():
            from flask import request, jsonify

            raw_body = request.get_data()
            signature = request.headers.get("X-BC-Signature", "")

            payload = adapter.verify_webhook(raw_body, signature)
            if not payload:
                return jsonify(error="Unauthorized"), 401

            order = adapter.parse_order_webhook(payload)
            if not order:
                return jsonify(received=True, skipped="not parseable")

            # Fetch full order details from BigCommerce
            full_order = adapter.fetch_order(order["order_id"])
            if full_order:
                order["amount"] = float(full_order.get("total_inc_tax", order["amount"]) or order["amount"])
                order["currency"] = full_order.get("currency_code", order["currency"]) or order["currency"]

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
