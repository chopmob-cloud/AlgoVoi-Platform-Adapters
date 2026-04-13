"""
AlgoVoi Faire Payment Adapter

Receives Faire wholesale order notifications (via webhook or polling),
creates AlgoVoi payment links, and accepts orders with the AlgoVoi TX
reference when payment is confirmed on-chain.

Faire signs webhook payloads with HMAC-SHA256 in the
X-Faire-Hmac-SHA256 header (hex digest).

For merchants without webhook access, poll_orders() fetches
recent orders via the Faire Orders API.

Works with Flask, Django, FastAPI, or any WSGI framework.
Zero pip dependencies — uses only the Python standard library.

Faire API docs: https://www.faire.com/developer-portal

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

FAIRE_API_BASE = "https://www.faire.com/api/v2"


class FaireAlgoVoi:
    """Faire wholesale marketplace + AlgoVoi payment adapter."""

    def __init__(
        self,
        api_base: str = "https://api1.ilovechicken.co.uk",
        api_key: str = "",
        tenant_id: str = "",
        access_token: str = "",
        brand_id: str = "",
        webhook_secret: str = "",
        default_network: str = "algorand_mainnet",
        base_currency: str = "GBP",
        timeout: int = 30,
    ):
        self.api_base = api_base.rstrip("/")
        self.api_key = api_key
        self.tenant_id = tenant_id
        self.access_token = access_token
        self.brand_id = brand_id
        self.webhook_secret = webhook_secret
        self.default_network = default_network
        self.base_currency = base_currency
        self.timeout = timeout
        self._ssl = ssl.create_default_context()

    # ── Webhook Verification ─────────────────────────────────────────────

    def verify_webhook(self, raw_body: bytes, signature: str) -> Optional[dict]:
        """
        Verify a Faire webhook using the X-Faire-Hmac-SHA256 header.

        Faire signs webhook payloads with HMAC-SHA256 (hex digest).

        Args:
            raw_body:  Raw POST body as bytes
            signature: X-Faire-Hmac-SHA256 header value (hex)

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
        Create an AlgoVoi payment link for a Faire wholesale order.

        Args:
            order_id:     Faire order ID
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
            label = f"Faire Order #{order_id}"

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

    # ── Faire API Integration ────────────────────────────────────────────

    def parse_order_webhook(self, payload: dict) -> Optional[dict]:
        """
        Parse a Faire order webhook payload.

        Args:
            payload: The parsed webhook JSON

        Returns:
            dict with order_id, amount, currency, status — or None
        """
        try:
            # Faire webhooks wrap payload in a type/payload envelope
            event_type = payload.get("type", "")
            data = payload.get("payload", payload)

            order_id = data.get("id", data.get("order_id", ""))
            if not order_id:
                return None

            # Amount: Faire uses minor units (cents) in 'amount_cents' or
            # a nested amount dict
            amount_cents = data.get("amount_cents", 0)
            if amount_cents:
                amount = float(amount_cents) / 100.0
            else:
                amount_dict = data.get("amount", {})
                if isinstance(amount_dict, dict):
                    amount = float(amount_dict.get("amount_cents", 0) or 0) / 100.0
                else:
                    amount = float(amount_dict or 0)

            currency = data.get("currency", self.base_currency)
            status = data.get("state", data.get("status", ""))
            retailer_id = data.get("retailer_id", "")

            return {
                "order_id": str(order_id),
                "amount": round(amount, 2),
                "currency": (currency or self.base_currency).upper(),
                "status": str(status),
                "retailer_id": str(retailer_id),
                "event_type": event_type,
            }
        except (KeyError, ValueError, TypeError):
            return None

    def poll_orders(self, state: str = "NEW") -> Optional[list]:
        """
        Fetch recent orders via the Faire Orders API (polling fallback).

        Args:
            state: Order state filter (NEW, ACCEPTED, etc.)

        Returns:
            List of order dicts or None
        """
        if not self.access_token or not self.brand_id:
            return None

        url = f"{FAIRE_API_BASE}/orders?state={quote(state, safe='')}"
        req = Request(url, method="GET", headers={
            "Authorization": f"Bearer {self.access_token}",
            "X-FAIRE-BRAND-ID": self.brand_id,
            "Content-Type": "application/json",
        })

        try:
            with urlopen(req, timeout=self.timeout, context=self._ssl) as resp:  # nosec B310
                if resp.status != 200:
                    return None
                data = json.loads(resp.read())
                return data.get("orders", [])
        except (URLError, json.JSONDecodeError, OSError):
            return None

    def fulfill_order(
        self,
        order_id: str,
        tx_id: str,
    ) -> bool:
        """
        Accept a Faire order and record the AlgoVoi TX reference.

        Uses POST /orders/{order_id}/accept to accept the wholesale order.

        Args:
            order_id: Faire order ID
            tx_id:    On-chain transaction ID

        Returns:
            True if the accept was acknowledged
        """
        if not tx_id or len(tx_id) > 200:
            return False

        if not self.access_token or not self.brand_id:
            return False

        url = f"{FAIRE_API_BASE}/orders/{quote(str(order_id), safe='')}/accept"

        payload = json.dumps({
            "note": f"AlgoVoi TX: {tx_id[:64]}",
        }).encode()

        req = Request(url, data=payload, method="POST", headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.access_token}",
            "X-FAIRE-BRAND-ID": self.brand_id,
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
        Returns a Flask view function for the Faire webhook endpoint.

        Usage:
            app.add_url_rule('/webhook/faire',
                view_func=adapter.flask_webhook_handler(), methods=['POST'])
        """
        adapter = self

        def handler():
            from flask import request, jsonify

            raw_body = request.get_data()
            signature = request.headers.get("X-Faire-Hmac-SHA256", "")

            payload = adapter.verify_webhook(raw_body, signature)
            if not payload:
                return jsonify(error="Unauthorized"), 401

            order = adapter.parse_order_webhook(payload)
            if not order:
                return jsonify(received=True, skipped="not parseable")

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
