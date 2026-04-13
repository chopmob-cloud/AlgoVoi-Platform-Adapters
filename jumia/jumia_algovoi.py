"""
AlgoVoi Jumia Payment Adapter

Receives Jumia Order.Created webhook events,
creates AlgoVoi payment links, and updates order status when
payment is confirmed on-chain.

Jumia is Africa's leading e-commerce platform, operating across
Nigeria, Kenya, Egypt, Ghana, Senegal, Ivory Coast, Uganda, Tanzania,
Morocco, and Tunisia.

Works with Flask, Django, FastAPI, or any WSGI framework.
Zero pip dependencies — uses only the Python standard library.

Jumia SellerCenter API docs: https://sellercenter.jumia.com.ng/api

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

JUMIA_COUNTRY_DOMAINS = {
    "nigeria": "jumia.com.ng",
    "kenya": "jumia.co.ke",
    "egypt": "jumia.com.eg",
    "ghana": "jumia.com.gh",
    "senegal": "jumia.sn",
    "ivory_coast": "jumia.ci",
    "uganda": "jumia.ug",
    "tanzania": "jumia.co.tz",
    "morocco": "jumia.ma",
    "tunisia": "jumia.com.tn",
}


class JumiaAlgoVoi:
    """Jumia SellerCenter + AlgoVoi payment adapter."""

    def __init__(
        self,
        api_base: str = "https://api1.ilovechicken.co.uk",
        api_key: str = "",
        tenant_id: str = "",
        jumia_api_key: str = "",
        api_secret: str = "",
        country_domain: str = "jumia.com.ng",
        access_token: str = "",
        webhook_secret: str = "",
        default_network: str = "algorand_mainnet",
        base_currency: str = "NGN",
        timeout: int = 30,
    ):
        self.api_base = api_base.rstrip("/")
        self.api_key = api_key
        self.tenant_id = tenant_id
        self.jumia_api_key = jumia_api_key
        self.api_secret = api_secret
        self.country_domain = country_domain
        self.access_token = access_token
        self.webhook_secret = webhook_secret
        self.default_network = default_network
        self.base_currency = base_currency
        self.timeout = timeout
        self._ssl = ssl.create_default_context()

    @property
    def _jumia_api_base(self) -> str:
        return f"https://sellerapi.sellercenter.{self.country_domain}"

    # ── Webhook Verification ─────────────────────────────────────────────

    def verify_webhook(self, raw_body: bytes, signature: str) -> Optional[dict]:
        """
        Verify a Jumia webhook notification using the X-Jumia-Signature header.

        Jumia signs webhooks with HMAC-SHA256 using the webhook secret.

        Args:
            raw_body:  Raw POST body as bytes
            signature: X-Jumia-Signature header value

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
        Create an AlgoVoi payment link for a Jumia order.

        Args:
            order_id:     Jumia order ID
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
            label = f"Jumia Order #{order_id}"

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

    # ── Jumia API Integration ─────────────────────────────────────────────

    def parse_order_webhook(self, payload: dict) -> Optional[dict]:
        """
        Parse a Jumia Order.Created webhook payload.

        Handles Order.Created and Order.StatusChanged events.

        Args:
            payload: The parsed webhook JSON

        Returns:
            dict with order_id, amount, currency, status — or None
        """
        try:
            event = payload.get("Event", "")
            if event and event not in ("Order.Created", "Order.StatusChanged"):
                return None

            order_id = payload.get("OrderId", payload.get("order_id", ""))
            if not order_id:
                return None

            status = payload.get("Status", payload.get("status", ""))
            timestamp = payload.get("Timestamp", payload.get("timestamp", ""))

            # Full order data requires a separate fetch
            amount = float(payload.get("Price", payload.get("amount", 0)))
            currency = payload.get("Currency", payload.get("currency", self.base_currency))

            return {
                "order_id": str(order_id),
                "amount": amount,
                "currency": currency.upper() if currency else self.base_currency,
                "status": str(status),
                "event": str(event),
                "timestamp": str(timestamp),
            }
        except (KeyError, ValueError, TypeError):
            return None

    def fulfill_order(self, order_id: str, tx_id: str) -> bool:
        """
        Update Jumia order status to ready_to_ship via UpdateOrderStatus.

        Uses the AlgoVoi TX ID as a payment reference.

        Args:
            order_id: Jumia order ID
            tx_id:    On-chain transaction ID

        Returns:
            True if the status update was accepted
        """
        if not tx_id or len(tx_id) > 200:
            return False

        if not self.jumia_api_key:
            return False

        url = f"{self._jumia_api_base}/orders/status"

        body = json.dumps({
            "OrderId": order_id,
            "Status": "ready_to_ship",
            "Reason": f"AlgoVoi TX:{tx_id[:64]}",
        }).encode()

        req = Request(url, data=body, method="POST", headers={
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
        Returns a Flask view function for the Jumia webhook endpoint.

        Usage:
            app.add_url_rule('/webhook/jumia',
                view_func=adapter.flask_webhook_handler(), methods=['POST'])
        """
        adapter = self

        def handler():
            from flask import request, jsonify

            raw_body = request.get_data()
            signature = request.headers.get("X-Jumia-Signature", "")

            payload = adapter.verify_webhook(raw_body, signature)
            if not payload:
                return jsonify(error="Unauthorized"), 401

            order = adapter.parse_order_webhook(payload)
            if not order:
                return jsonify(received=True, skipped="not parseable")

            if order["status"] in ("canceled", "CANCELLED"):
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
