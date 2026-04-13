"""
AlgoVoi Bol.com Payment Adapter

Polls the Bol.com Retailer API v10 for OPEN orders, creates AlgoVoi
payment links, and updates order shipment records when payment is
confirmed on-chain.

Bol.com does not support outbound webhooks. This adapter polls
GET /orders?status=OPEN and updates via PUT /orders/{orderId}/shipment.

A manual bypass path is also supported: operators can POST orders directly
and include an HMAC-SHA256 signature for verify_webhook().

Bol.com Retailer API docs: https://api.bol.com/retailer/public/redoc/

Version: 1.0.0

AlgoVoi docs: https://github.com/chopmob-cloud/AlgoVoi-Platform-Adapters
Copyright (c) 2026 Christopher Hopley (ilovechicken.co.uk). BSL 1.1.
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
import ssl
import time
from typing import Any, Optional
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen
from urllib.error import URLError

__version__ = "1.0.0"

HOSTED_NETWORKS = {"algorand_mainnet", "voi_mainnet", "hedera_mainnet", "stellar_mainnet"}

_BOLCOM_API = "https://api.bol.com/retailer"
_BOLCOM_AUTH = "https://login.bol.com/token"


class BolcomAlgoVoi:
    """Bol.com Retailer API + AlgoVoi payment adapter (polling-based)."""

    def __init__(
        self,
        api_base: str = "https://api1.ilovechicken.co.uk",
        api_key: str = "",
        tenant_id: str = "",
        client_id: str = "",
        client_secret: str = "",
        webhook_secret: str = "",
        default_network: str = "algorand_mainnet",
        base_currency: str = "EUR",
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
        self._access_token: str = ""
        self._token_expires_at: float = 0.0

    # ── Signature Verification (bypass/manual POST path) ─────────────────

    def verify_webhook(self, raw_body: bytes, signature: str) -> Optional[dict]:
        """
        Verify HMAC-SHA256 signature for manually POSTed order payloads.

        Args:
            raw_body:  Raw POST body as bytes
            signature: Hex HMAC-SHA256 digest

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

    # ── OAuth2 Token Management ──────────────────────────────────────────

    def _refresh_token(self) -> bool:
        """Obtain a new access token via client_credentials flow."""
        if not self.client_id or not self.client_secret:
            return False

        creds = base64.b64encode(
            f"{self.client_id}:{self.client_secret}".encode()
        ).decode()

        body = urlencode({"grant_type": "client_credentials"}).encode()
        req = Request(
            _BOLCOM_AUTH,
            data=body,
            method="POST",
            headers={
                "Authorization": f"Basic {creds}",
                "Accept": "application/json",
                "Content-Type": "application/x-www-form-urlencoded",
            },
        )
        try:
            with urlopen(req, timeout=self.timeout, context=self._ssl) as resp:  # nosec B310
                data = json.loads(resp.read())
                self._access_token = data.get("access_token", "")
                expires_in = int(data.get("expires_in", 3600))
                self._token_expires_at = time.time() + expires_in - 60
                return bool(self._access_token)
        except (URLError, json.JSONDecodeError, OSError, KeyError, ValueError):
            return False

    def _ensure_token(self) -> bool:
        """Refresh access token if expired or missing."""
        if self._access_token and time.time() < self._token_expires_at:
            return True
        return self._refresh_token()

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
        Create an AlgoVoi payment link for a Bol.com order.

        Args:
            order_id:     Bol.com order ID
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
            label = f"Bol.com Order #{order_id}"

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

        import re
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

    # ── Bol.com API Integration ──────────────────────────────────────────

    def parse_order(self, data: dict) -> Optional[dict]:
        """
        Parse a Bol.com order response into a normalised order dict.

        Args:
            data: Order JSON from GET /orders or GET /orders/{orderId}

        Returns:
            dict with order_id, amount, currency, status, shipment_details — or None
        """
        try:
            order_id = str(data.get("orderId", data.get("id", "")))
            if not order_id:
                return None

            # Bol.com order amounts come from orderItems
            order_items = data.get("orderItems", [])
            amount = 0.0
            for item in order_items:
                unit_price = float(item.get("unitPrice", item.get("offerPrice", 0)))
                qty = int(item.get("quantity", 1))
                amount += unit_price * qty

            # totalAmount may be at root level
            if not amount:
                amount = float(data.get("totalAmount", 0))

            currency = data.get("currency", self.base_currency) or self.base_currency
            status = data.get("status", "OPEN")
            customer = data.get("billingDetails", data.get("shipmentDetails", {}))
            buyer_email = customer.get("email", "")

            return {
                "order_id": order_id,
                "amount": round(amount, 2),
                "currency": currency.upper(),
                "status": str(status),
                "buyer_email": buyer_email,
            }
        except (KeyError, ValueError, TypeError):
            return None

    def poll_orders(self, since_datetime: Optional[str] = None) -> list:
        """
        Poll Bol.com Retailer API for OPEN orders.

        Args:
            since_datetime: ISO8601 timestamp (unused; Bol.com uses status filter)

        Returns:
            List of parsed order dicts
        """
        if not self._ensure_token():
            return []

        url = f"{_BOLCOM_API}/orders?status=OPEN"
        try:
            req = Request(url, method="GET", headers={
                "Authorization": f"Bearer {self._access_token}",
                "Accept": "application/vnd.retailer.v10+json",
            })
            with urlopen(req, timeout=self.timeout, context=self._ssl) as resp:  # nosec B310
                data = json.loads(resp.read())
        except (URLError, json.JSONDecodeError, OSError):
            return []

        orders = data.get("orders", [])
        results = []
        for order in orders:
            parsed = self.parse_order(order)
            if parsed:
                results.append(parsed)
        return results

    def fulfill_order(self, order_id: str, tx_id: str) -> bool:
        """
        Update a Bol.com order shipment with the AlgoVoi TX reference.

        Uses PUT /orders/{orderId}/shipment.

        Args:
            order_id: Bol.com order ID
            tx_id:    On-chain transaction ID

        Returns:
            True if the shipment update was accepted
        """
        if not tx_id or len(tx_id) > 200:
            return False

        if not self._ensure_token():
            return False

        url = f"{_BOLCOM_API}/orders/{quote(str(order_id), safe='')}/shipment"

        payload = json.dumps({
            "orderItems": [],
            "shipmentReference": f"TX:{tx_id[:64]}",
            "transport": {
                "transporterCode": "ALGOVOI",
                "trackAndTrace": tx_id[:40],
            },
        }).encode()

        req = Request(url, data=payload, method="PUT", headers={
            "Authorization": f"Bearer {self._access_token}",
            "Accept": "application/vnd.retailer.v10+json",
            "Content-Type": "application/vnd.retailer.v10+json",
        })

        try:
            with urlopen(req, timeout=self.timeout, context=self._ssl) as resp:  # nosec B310
                return resp.status in (200, 201, 202, 204)
        except (URLError, OSError):
            return False

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
