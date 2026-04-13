"""
AlgoVoi Mercado Libre Payment Adapter

Receives Mercado Libre orders_v2 webhook notifications,
creates AlgoVoi payment links, and updates shipments when
payment is confirmed on-chain.

Mercado Libre is the leading e-commerce marketplace in Latin America,
operating across Argentina, Brazil, Mexico, Colombia, Chile, and other
LATAM countries.

Works with Flask, Django, FastAPI, or any WSGI framework.
Zero pip dependencies — uses only the Python standard library.

Mercado Libre API docs: https://developers.mercadolibre.com

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

MERCADOLIBRE_API_BASE = "https://api.mercadolibre.com"


class MercadoLibreAlgoVoi:
    """Mercado Libre + AlgoVoi payment adapter."""

    def __init__(
        self,
        api_base: str = "https://api1.ilovechicken.co.uk",
        api_key: str = "",
        tenant_id: str = "",
        access_token: str = "",
        client_secret: str = "",
        webhook_secret: str = "",
        default_network: str = "algorand_mainnet",
        base_currency: str = "BRL",
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
        Verify a Mercado Libre webhook using the x-signature header.

        Mercado Libre signs webhooks with HMAC-SHA256 of:
            ts:v1:{data_id}
        using the client_secret.

        The x-signature header format is: ts=<timestamp>,v1=<hex_hash>

        Args:
            raw_body:  Raw POST body as bytes
            signature: x-signature header value

        Returns:
            Parsed payload dict, or None if verification fails
        """
        if not self.webhook_secret:
            return None

        # Parse ts=...,v1=... from x-signature
        ts_match = re.search(r"ts=([^,]+)", signature)
        v1_match = re.search(r"v1=([^,]+)", signature)
        if not ts_match or not v1_match:
            # Fallback: plain HMAC of raw_body
            expected = hmac.new(
                self.webhook_secret.encode(),
                raw_body,
                hashlib.sha256,
            ).hexdigest()
            if not hmac.compare_digest(expected, signature):
                return None
        else:
            ts = ts_match.group(1)
            v1_provided = v1_match.group(1)

            try:
                payload_for_verify = json.loads(raw_body)
                data_id = str(
                    payload_for_verify.get("data", {}).get("id", "")
                    or payload_for_verify.get("resource", "").split("/")[-1]
                )
            except (json.JSONDecodeError, AttributeError):
                data_id = ""

            sign_template = f"id:{data_id};request-id:{ts};ts:{ts};"
            expected = hmac.new(
                self.webhook_secret.encode(),
                sign_template.encode(),
                hashlib.sha256,
            ).hexdigest()

            if not hmac.compare_digest(expected, v1_provided):
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
        Create an AlgoVoi payment link for a Mercado Libre order.

        Args:
            order_id:     Mercado Libre order ID
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
            label = f"Mercado Libre Order #{order_id}"

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

    # ── Mercado Libre API Integration ─────────────────────────────────────

    def parse_order_webhook(self, payload: dict) -> Optional[dict]:
        """
        Parse a Mercado Libre orders_v2 notification payload.

        The notification contains a resource URL like /orders/{order_id}.
        AlgoVoi extracts the order ID for subsequent fetching.

        Args:
            payload: The parsed webhook JSON

        Returns:
            dict with order_id, amount, currency, status — or None
        """
        try:
            topic = payload.get("topic", "")
            if topic and topic not in ("orders_v2", "orders", "payments", ""):
                return None

            # Extract order ID from resource URL: /orders/1234567890
            resource = payload.get("resource", "")
            order_id = ""
            if resource:
                m = re.search(r"/orders/(\d+)", resource)
                if m:
                    order_id = m.group(1)

            # Nested data.id path (newer notifications)
            if not order_id:
                data = payload.get("data", {})
                order_id = str(data.get("id", ""))

            if not order_id:
                return None

            user_id = payload.get("user_id", "")
            application_id = payload.get("application_id", "")
            sent = payload.get("sent", "")

            # Amount requires a GET /orders/{order_id} call
            amount = float(payload.get("total_amount", 0))
            currency = payload.get("currency_id", self.base_currency)

            return {
                "order_id": str(order_id),
                "amount": amount,
                "currency": currency.upper() if currency else self.base_currency,
                "status": "pending",
                "topic": str(topic),
                "user_id": str(user_id),
                "application_id": str(application_id),
                "sent": str(sent),
            }
        except (KeyError, ValueError, TypeError):
            return None

    def fulfill_order(self, order_id: str, tx_id: str) -> bool:
        """
        Update a Mercado Libre order shipment via the Shipments API.

        Uses the AlgoVoi TX ID as the tracking number reference.

        Args:
            order_id: Mercado Libre order ID
            tx_id:    On-chain transaction ID

        Returns:
            True if the shipment update was accepted
        """
        if not tx_id or len(tx_id) > 200:
            return False

        if not self.access_token:
            return False

        url = f"{MERCADOLIBRE_API_BASE}/orders/{quote(str(order_id), safe='')}/shipments"

        body = json.dumps({
            "status": "shipped",
            "tracking_number": f"TX:{tx_id[:64]}",
            "tracking_method": "AlgoVoi",
            "shipped_date": time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime()),
        }).encode()

        req = Request(url, data=body, method="PUT", headers={
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
        Returns a Flask view function for the Mercado Libre webhook endpoint.

        Usage:
            app.add_url_rule('/webhook/mercadolibre',
                view_func=adapter.flask_webhook_handler(), methods=['POST'])
        """
        adapter = self

        def handler():
            from flask import request, jsonify

            raw_body = request.get_data()
            signature = request.headers.get("x-signature", "")

            payload = adapter.verify_webhook(raw_body, signature)
            if not payload:
                return jsonify(error="Unauthorized"), 401

            order = adapter.parse_order_webhook(payload)
            if not order:
                return jsonify(received=True, skipped="not parseable")

            if order["status"] in ("cancelled", "CANCELLED"):
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
