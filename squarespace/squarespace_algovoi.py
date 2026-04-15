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

Version: 1.1.0

AlgoVoi docs: https://github.com/chopmob-cloud/AlgoVoi-Platform-Adapters
Licensed under the Business Source License 1.1 — see LICENSE for details.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import math
import re
import ssl
import time
from typing import Any, Optional
from urllib.parse import quote, urlparse
from urllib.request import Request, urlopen
from urllib.error import URLError

__version__ = "1.1.0"

# Hard cap on inbound webhook bodies — Squarespace order webhooks are <8 KB.
MAX_WEBHOOK_BODY_BYTES = 64 * 1024

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

        Squarespace signs webhooks with HMAC-SHA256 using the webhook secret
        and a hex digest.

        Args:
            raw_body:  Raw POST body as bytes
            signature: Squarespace-Signature header value (hex digest)

        Returns:
            Parsed payload dict, or None if verification fails

        SECURITY NOTE — replay protection:
            This method does NOT dedupe replays. The HMAC carries no
            timestamp, so an attacker who captures one valid (body, sig)
            pair could replay it indefinitely. Callers MUST track
            processed `order_id` values in their persistence layer and
            reject duplicates BEFORE calling process_order().
        """
        if not self.webhook_secret:
            return None
        # Type guards — compare_digest raises TypeError on bytes/None,
        # which would surface as a 500. Fail closed instead.
        if not isinstance(signature, str) or not signature:
            return None
        if not isinstance(raw_body, (bytes, bytearray)):
            return None
        if len(raw_body) > MAX_WEBHOOK_BODY_BYTES:
            return None

        expected = hmac.new(
            self.webhook_secret.encode(),
            bytes(raw_body),
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

        # Defence-in-depth: reject obviously bad amounts before the
        # gateway call.
        if not isinstance(amount, (int, float)) or not math.isfinite(amount) or amount <= 0:
            return None

        payload: dict[str, Any] = {
            "amount": round(float(amount), 2),
            "currency": currency.upper(),
            "label": label,
            "preferred_network": network,
        }
        if redirect_url:
            # https-only — checkout tokens or payment-status parameters
            # appended by the gateway must not travel over plaintext.
            # Also blocks SSRF schemes (file://, gopher://, javascript:).
            parsed = urlparse(redirect_url)
            if parsed.scheme != "https" or not parsed.hostname:
                return None
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

        Note: GET /checkout/{token} is a public endpoint — the token
        IS the authorisation, no Bearer header is required. If the
        gateway changes that contract, this method must add Auth.
        """
        if not token:
            return False
        # Refuse to send the checkout token over plaintext HTTP.
        if not self.api_base.startswith("https://"):
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

        Handles order.create and order.update topics. Squarespace always
        wraps the order payload in a top-level "data" key — payloads
        without it are rejected (avoids accepting flat / spoofed bodies
        as legitimate orders).

        Args:
            payload: The parsed webhook JSON

        Returns:
            dict with order_id, amount, currency, status — or None
        """
        # Defence: malformed or null-injected webhooks must NOT crash
        # the handler. Coerce defensively at every step and add
        # AttributeError to the except tuple as belt-and-suspenders.
        if not isinstance(payload, dict):
            return None
        try:
            topic = payload.get("topic") or ""
            if topic not in ("order.create", "order.update", ""):
                return None

            data = payload.get("data")
            # Reject flat / unwrapped payloads — Squarespace always
            # delivers the order under "data". Without this, a spoofed
            # webhook that omits the wrapper could be parsed as valid.
            if not isinstance(data, dict):
                return None

            order_id = data.get("id") or data.get("orderId") or ""
            if not order_id:
                return None

            # Squarespace uses grandTotal with value and currency.
            # Coerce a null grandTotal to {} so the dict path runs and
            # missing-amount is surfaced explicitly rather than masked
            # as 0.0 (which `float(None or 0)` would silently produce).
            grand_total = data.get("grandTotal")
            if grand_total is None:
                grand_total = data.get("subtotal")
            if grand_total is None:
                return None
            if not isinstance(grand_total, dict):
                # Squarespace always sends the {value, currency} dict.
                # A scalar in this slot is malformed.
                return None

            amount_str = grand_total.get("value")
            if amount_str is None:
                amount_str = grand_total.get("decimalValue")
            if amount_str is None:
                return None

            amount = float(amount_str)
            if not math.isfinite(amount) or amount <= 0:
                return None

            currency = grand_total.get("currency") or self.base_currency

            status         = data.get("fulfillmentStatus") or data.get("financialStatus") or ""
            order_number   = data.get("orderNumber") or ""
            customer_email = data.get("customerEmail") or ""

            return {
                "order_id": str(order_id),
                "order_number": str(order_number),
                "amount": amount,
                "currency": currency.upper() if isinstance(currency, str) else self.base_currency,
                "status": str(status),
                "customer_email": customer_email,
                "topic": topic,
            }
        except (KeyError, ValueError, TypeError, AttributeError):
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
        if not order_id or not isinstance(order_id, str):
            return False

        url = f"https://api.squarespace.com/1.0/commerce/orders/{quote(order_id, safe='')}/fulfillments"

        if not shipments:
            # Don't truncate tx_id — the 200-char cap above is the only
            # length guard. Algorand 52 / Stellar 64 / Voi 52 / Hedera
            # all fit comfortably; truncating produces unverifiable refs.
            #
            # We deliberately omit `trackingUrl`: the previous version
            # built a URL on api1.ilovechicken.co.uk using a truncated TX
            # as if it were a checkout token — that URL would always
            # 404. Squarespace accepts shipments without a trackingUrl;
            # the merchant can always look the TX up by hand via the
            # full hash in trackingNumber.
            shipments = [{
                "shipDate": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "carrierName": "AlgoVoi",
                "trackingNumber": f"TX:{tx_id}",
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
