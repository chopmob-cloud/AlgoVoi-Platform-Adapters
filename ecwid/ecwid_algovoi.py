"""
AlgoVoi Ecwid Payment Adapter

Receives Ecwid order webhooks (order.created), fetches full order
details via the Ecwid REST API, creates AlgoVoi payment links, and
marks orders as paid with the AlgoVoi TX ID when payment is confirmed
on-chain.

Ecwid signs webhook payloads with HMAC-SHA256. The signature is
delivered in the X-Ecwid-Webhook-Signature header (base64-encoded).

The webhook payload only contains the order ID and event type —
the adapter fetches the full order (amount, currency, etc.) via
GET /api/v3/{store_id}/orders/{order_id}.

Works with Flask, Django, FastAPI, or any WSGI framework.
Zero pip dependencies — uses only the Python standard library.

Ecwid API docs: https://api-docs.ecwid.com/

Version: 1.0.0

AlgoVoi docs: https://github.com/chopmob-cloud/AlgoVoi-Platform-Adapters
Licensed under the Business Source License 1.1 — see LICENSE for details.
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

ECWID_API_BASE = "https://app.ecwid.com/api/v3"


class EcwidAlgoVoi:
    """Ecwid + AlgoVoi payment adapter."""

    def __init__(
        self,
        api_base: str = "https://api1.ilovechicken.co.uk",
        api_key: str = "",
        tenant_id: str = "",
        store_id: str = "",
        client_secret: str = "",
        webhook_secret: str = "",
        default_network: str = "algorand_mainnet",
        base_currency: str = "USD",
        timeout: int = 30,
    ):
        self.api_base = api_base.rstrip("/")
        self.api_key = api_key
        self.tenant_id = tenant_id
        self.store_id = str(store_id)
        self.client_secret = client_secret
        self.webhook_secret = webhook_secret
        self.default_network = default_network
        self.base_currency = base_currency
        self.timeout = timeout
        self._ssl = ssl.create_default_context()

    # ── Webhook Verification ─────────────────────────────────────────────

    def verify_webhook(self, raw_body: bytes, signature: str) -> Optional[dict]:
        """
        Verify an Ecwid webhook using the X-Ecwid-Webhook-Signature header.

        Ecwid signs webhooks with HMAC-SHA256. The signature is base64-encoded.

        Args:
            raw_body:  Raw POST body as bytes
            signature: X-Ecwid-Webhook-Signature header value (base64)

        Returns:
            Parsed payload dict, or None if verification fails
        """
        if not self.webhook_secret:
            return None

        expected_bytes = hmac.new(
            self.webhook_secret.encode(),
            raw_body,
            hashlib.sha256,
        ).digest()
        expected_b64 = base64.b64encode(expected_bytes).decode()

        if not hmac.compare_digest(expected_b64, signature):
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
        Create an AlgoVoi payment link for an Ecwid order.

        Args:
            order_id:     Ecwid order ID
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
            label = f"Ecwid Order #{order_id}"

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

    # ── Ecwid API Integration ────────────────────────────────────────────

    def fetch_order(self, order_id: str) -> Optional[dict]:
        """
        Fetch full order details from the Ecwid REST API.

        Ecwid webhooks only contain the order ID — this method retrieves
        the full order with amount, currency, and line items.

        Args:
            order_id: Ecwid order ID

        Returns:
            Full order dict or None
        """
        if not self.store_id or not self.client_secret:
            return None

        url = f"{ECWID_API_BASE}/{quote(self.store_id, safe='')}/orders/{quote(str(order_id), safe='')}"
        req = Request(url, method="GET", headers={
            "Authorization": f"Bearer {self.client_secret}",
            "Accept": "application/json",
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
        Parse an Ecwid order webhook payload.

        Ecwid webhooks only contain eventType and entityId (the order ID).
        Call fetch_order() to get the full order details.

        Args:
            payload: The parsed webhook JSON

        Returns:
            dict with order_id, event_type, store_id — or None
        """
        try:
            event_type = payload.get("eventType", "")
            entity_id = payload.get("entityId", "")

            if not entity_id:
                return None

            store_id = str(payload.get("storeId", self.store_id))

            return {
                "order_id": str(entity_id),
                "event_type": event_type,
                "store_id": store_id,
                # amount/currency populated after fetch_order
                "amount": float(payload.get("data", {}).get("total", 0) or 0),
                "currency": (payload.get("data", {}).get("currency", self.base_currency) or self.base_currency).upper(),
            }
        except (KeyError, ValueError, TypeError):
            return None

    def fulfill_order(
        self,
        order_id: str,
        tx_id: str,
    ) -> bool:
        """
        Mark an Ecwid order as paid and add the AlgoVoi TX ID as a comment.

        Args:
            order_id: Ecwid order ID
            tx_id:    On-chain transaction ID

        Returns:
            True if the update was accepted
        """
        if not tx_id or len(tx_id) > 200:
            return False

        if not self.store_id or not self.client_secret:
            return False

        url = f"{ECWID_API_BASE}/{quote(self.store_id, safe='')}/orders/{quote(str(order_id), safe='')}"

        payload = json.dumps({
            "paymentStatus": "PAID",
            "privateAdminNotes": f"AlgoVoi TX: {tx_id[:64]}",
        }).encode()

        req = Request(url, data=payload, method="PUT", headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.client_secret}",
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
        Returns a Flask view function for the Ecwid webhook endpoint.

        Verifies the webhook, fetches the full order, creates a payment link.

        Usage:
            app.add_url_rule('/webhook/ecwid',
                view_func=adapter.flask_webhook_handler(), methods=['POST'])
        """
        adapter = self

        def handler():
            from flask import request, jsonify

            raw_body = request.get_data()
            signature = request.headers.get("X-Ecwid-Webhook-Signature", "")

            payload = adapter.verify_webhook(raw_body, signature)
            if not payload:
                return jsonify(error="Unauthorized"), 401

            order_stub = adapter.parse_order_webhook(payload)
            if not order_stub:
                return jsonify(received=True, skipped="not parseable")

            # Fetch full order to get amount/currency
            full_order = adapter.fetch_order(order_stub["order_id"])
            if full_order:
                amount = float(full_order.get("total", 0) or 0)
                currency = full_order.get("currency", adapter.base_currency) or adapter.base_currency
            else:
                amount = order_stub["amount"]
                currency = order_stub["currency"]

            result = adapter.process_order(
                order_id=order_stub["order_id"],
                amount=amount,
                currency=currency,
            )

            if not result:
                return jsonify(error="Could not create payment link"), 502

            return jsonify(
                received=True,
                order_id=order_stub["order_id"],
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
