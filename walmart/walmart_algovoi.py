"""
AlgoVoi Walmart Marketplace Payment Adapter

Receives Walmart Marketplace order notifications (PO_CREATED),
creates AlgoVoi payment links, and acknowledges orders with the
AlgoVoi TX reference when payment is confirmed on-chain.

Walmart signs webhook payloads with HMAC-SHA256. The signature is
delivered in the WM_SEC.AUTH_SIGNATURE header. A Bearer token fallback
(Authorization: Bearer <webhook_secret>) is also supported.

Works with Flask, Django, FastAPI, or any WSGI framework.
Zero pip dependencies — uses only the Python standard library.

Walmart Marketplace API docs:
  https://developer.walmart.com/doc/us/mp/us-mp-orders/

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

WALMART_API_BASE = "https://marketplace.walmartapis.com"


class WalmartAlgoVoi:
    """Walmart Marketplace + AlgoVoi payment adapter."""

    def __init__(
        self,
        api_base: str = "https://api1.ilovechicken.co.uk",
        api_key: str = "",
        tenant_id: str = "",
        client_id: str = "",
        client_secret: str = "",
        webhook_secret: str = "",
        default_network: str = "algorand_mainnet",
        base_currency: str = "USD",
        timeout: int = 30,
    ):
        self.api_base = api_base.rstrip("/")
        self.api_key = api_key
        self.tenant_id = tenant_id
        self.client_id = client_id
        self.client_secret = client_secret
        self.webhook_secret = webhook_secret
        self.default_network = default_network
        self.base_currency = base_currency
        self.timeout = timeout
        self._ssl = ssl.create_default_context()

    # ── Webhook Verification ─────────────────────────────────────────────

    def verify_webhook(self, raw_body: bytes, signature: str) -> Optional[dict]:
        """
        Verify a Walmart webhook using the WM_SEC.AUTH_SIGNATURE header.

        Walmart signs webhooks with HMAC-SHA256 (hex digest).
        Also supports Bearer token fallback where signature == webhook_secret.

        Args:
            raw_body:  Raw POST body as bytes
            signature: WM_SEC.AUTH_SIGNATURE header value (hex)

        Returns:
            Parsed payload dict, or None if verification fails
        """
        if not self.webhook_secret:
            return None

        # Primary: HMAC-SHA256 of body
        expected = hmac.new(
            self.webhook_secret.encode(),
            raw_body,
            hashlib.sha256,
        ).hexdigest()

        # Fallback: Bearer token comparison (verbatim secret)
        bearer_match = hmac.compare_digest(self.webhook_secret.encode(), signature.encode())
        hmac_match = hmac.compare_digest(expected, signature)

        if not hmac_match and not bearer_match:
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
        Create an AlgoVoi payment link for a Walmart order.

        Args:
            order_id:     Walmart purchase order ID
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
            label = f"Walmart Order #{order_id}"

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

    # ── Walmart API Integration ──────────────────────────────────────────

    def parse_order_webhook(self, payload: dict) -> Optional[dict]:
        """
        Parse a Walmart PO_CREATED webhook payload.

        Sums all PRODUCT charges across all order lines.

        Args:
            payload: The parsed webhook JSON

        Returns:
            dict with order_id, amount, currency, status — or None
        """
        try:
            event_type = payload.get("eventType", "")
            order = payload.get("order", {})

            if not order:
                return None

            order_id = order.get("purchaseOrderId", order.get("customerOrderId", ""))
            if not order_id:
                return None

            # Sum PRODUCT charges across all order lines
            amount = 0.0
            currency = self.base_currency
            order_lines = order.get("orderLines", {})
            lines = order_lines.get("orderLine", [])
            if isinstance(lines, dict):
                lines = [lines]
            for line in lines:
                charges = line.get("charges", {})
                charge_list = charges.get("charge", [])
                if isinstance(charge_list, dict):
                    charge_list = [charge_list]
                for charge in charge_list:
                    if charge.get("chargeType") == "PRODUCT":
                        charge_amt = charge.get("chargeAmount", {})
                        amount += float(charge_amt.get("amount", 0) or 0)
                        currency = charge_amt.get("currency", currency) or currency

            order_date = order.get("orderDate", "")
            customer_order_id = order.get("customerOrderId", "")

            return {
                "order_id": str(order_id),
                "customer_order_id": str(customer_order_id),
                "amount": round(amount, 2),
                "currency": (currency or self.base_currency).upper(),
                "event_type": event_type,
                "order_date": order_date,
            }
        except (KeyError, ValueError, TypeError):
            return None

    def fulfill_order(
        self,
        order_id: str,
        tx_id: str,
        access_token: str = "",
    ) -> bool:
        """
        Acknowledge a Walmart order and update its status with the AlgoVoi TX.

        Args:
            order_id:     Walmart purchase order ID
            tx_id:        On-chain transaction ID
            access_token: Walmart OAuth access token

        Returns:
            True if the update was accepted
        """
        if not tx_id or len(tx_id) > 200:
            return False

        if not self.client_id or not self.client_secret:
            return False

        token = access_token or self._get_access_token()
        if not token:
            return False

        url = f"{WALMART_API_BASE}/v3/orders/{quote(str(order_id), safe='')}/acknowledge"

        payload = json.dumps({
            "orderAcknowledgement": {
                "purchaseOrderId": str(order_id),
                "acknowledgementStatus": "SUCCESS",
                "trackingInfo": {
                    "trackingId": f"TX:{tx_id[:64]}",
                    "carrierName": "AlgoVoi",
                },
            }
        }).encode()

        req = Request(url, data=payload, method="POST", headers={
            "Content-Type": "application/json",
            "WM-SEC.ACCESS-TOKEN": token,
            "WM-SVC.NAME": "Walmart Marketplace",
            "WM-QOS-CORRELATION-ID": str(int(time.time() * 1000)),
            "User-Agent": "AlgoVoi/1.0",
        })

        try:
            with urlopen(req, timeout=self.timeout, context=self._ssl) as resp:  # nosec B310
                return resp.status in (200, 201, 204)
        except (URLError, OSError):
            return False

    def _get_access_token(self) -> Optional[str]:
        """
        Exchange client credentials for a Walmart access token.

        Returns:
            Access token string or None
        """
        if not self.client_id or not self.client_secret:
            return None

        import base64
        credentials = base64.b64encode(
            f"{self.client_id}:{self.client_secret}".encode()
        ).decode()

        url = f"{WALMART_API_BASE}/v3/token"
        body = urlencode({"grant_type": "client_credentials"}).encode()
        req = Request(url, data=body, method="POST", headers={
            "Authorization": f"Basic {credentials}",
            "Content-Type": "application/x-www-form-urlencoded",
            "WM-SVC.NAME": "Walmart Marketplace",
            "WM-QOS-CORRELATION-ID": str(int(time.time() * 1000)),
        })

        try:
            with urlopen(req, timeout=self.timeout, context=self._ssl) as resp:  # nosec B310
                if resp.status != 200:
                    return None
                data = json.loads(resp.read())
                return data.get("access_token")
        except (URLError, json.JSONDecodeError, OSError):
            return None

    # ── Flask Helper ─────────────────────────────────────────────────────

    def flask_webhook_handler(self):
        """
        Returns a Flask view function for the Walmart webhook endpoint.

        Usage:
            app.add_url_rule('/webhook/walmart',
                view_func=adapter.flask_webhook_handler(), methods=['POST'])
        """
        adapter = self

        def handler():
            from flask import request, jsonify

            raw_body = request.get_data()
            # Walmart sends WM_SEC.AUTH_SIGNATURE
            signature = request.headers.get("WM_SEC.AUTH_SIGNATURE", "")
            if not signature:
                # Bearer token fallback
                auth = request.headers.get("Authorization", "")
                if auth.startswith("Bearer "):
                    signature = auth[7:]

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
