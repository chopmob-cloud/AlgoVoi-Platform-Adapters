"""
AlgoVoi Allegro Payment Adapter

Polls the Allegro Order Events API to detect new orders, creates AlgoVoi
payment links, and marks orders as fulfilled when payment is confirmed on-chain.

Allegro does NOT support push webhooks. This adapter polls
GET /order/events to find ORDER_CREATED / ORDER_STATUS_CHANGED events,
fetches the full checkout-form, and fulfils via PATCH
/order/checkout-forms/{id}/fulfillment.

A manual bypass path is also supported: operators can POST orders directly
to their own endpoint and include an HMAC-SHA256 signature that
verify_order_signature() validates.

Allegro API docs: https://developer.allegro.pl/documentation/

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
import ssl
import time
from typing import Any, Optional
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen
from urllib.error import URLError

__version__ = "1.0.0"

HOSTED_NETWORKS = {"algorand_mainnet", "voi_mainnet", "hedera_mainnet", "stellar_mainnet"}

_ALLEGRO_API = "https://api.allegro.pl"
_ALLEGRO_AUTH = "https://allegro.pl/auth/oauth/token"
_ALLEGRO_ACCEPT = "application/vnd.allegro.public.v1+json"


class AllegroAlgoVoi:
    """Allegro + AlgoVoi payment adapter (polling-based)."""

    def __init__(
        self,
        api_base: str = "https://api1.ilovechicken.co.uk",
        api_key: str = "",
        tenant_id: str = "",
        client_id: str = "",
        client_secret: str = "",
        access_token: str = "",
        webhook_secret: str = "",
        default_network: str = "algorand_mainnet",
        base_currency: str = "PLN",
        timeout: int = 30,
    ):
        self.api_base = api_base.rstrip("/")
        self.api_key = api_key
        self.tenant_id = tenant_id
        self.client_id = client_id
        self.client_secret = client_secret
        self.access_token = access_token
        self.webhook_secret = webhook_secret
        self.default_network = default_network
        self.base_currency = base_currency
        self.timeout = timeout
        self._ssl = ssl.create_default_context()
        self._token_expires_at: float = 0.0

    # ── Signature Verification (bypass/manual POST path) ─────────────────

    def verify_webhook(self, raw_body: bytes, signature: str) -> Optional[dict]:
        """
        Verify an HMAC-SHA256 signature on a manually POSTed order payload.

        This provides a bypass path for operators who POST order data directly.

        Args:
            raw_body:  Raw POST body as bytes
            signature: Hex HMAC-SHA256 digest to verify

        Returns:
            Parsed payload dict, or None if verification fails
        """
        return self.verify_order_signature(raw_body, signature)

    def verify_order_signature(self, raw_body: bytes, signature: str) -> Optional[dict]:
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
        """Obtain a new access token using client_credentials flow."""
        if not self.client_id or not self.client_secret:
            return False

        creds = base64.b64encode(
            f"{self.client_id}:{self.client_secret}".encode()
        ).decode()

        body = urlencode({"grant_type": "client_credentials"}).encode()
        req = Request(
            _ALLEGRO_AUTH,
            data=body,
            method="POST",
            headers={
                "Authorization": f"Basic {creds}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
        )
        try:
            with urlopen(req, timeout=self.timeout, context=self._ssl) as resp:  # nosec B310
                data = json.loads(resp.read())
                self.access_token = data.get("access_token", "")
                expires_in = int(data.get("expires_in", 3600))
                self._token_expires_at = time.time() + expires_in - 60
                return bool(self.access_token)
        except (URLError, json.JSONDecodeError, OSError, KeyError, ValueError):
            return False

    def _ensure_token(self) -> bool:
        """Refresh access token if expired or missing."""
        if self.access_token and time.time() < self._token_expires_at:
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
        Create an AlgoVoi payment link for an Allegro order.

        Args:
            order_id:     Allegro checkout-form ID
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
            label = f"Allegro Order #{order_id}"

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

    # ── Allegro API Integration ──────────────────────────────────────────

    def parse_order(self, data: dict) -> Optional[dict]:
        """
        Parse an Allegro checkout-form response into a normalised order dict.

        Args:
            data: Checkout-form JSON from GET /order/checkout-forms/{id}

        Returns:
            dict with order_id, amount, currency, status, buyer_email — or None
        """
        try:
            order_id = data.get("id", "")
            if not order_id:
                return None

            summary = data.get("summary", {})
            amount_obj = summary.get("totalToPay", {})
            amount = float(amount_obj.get("amount", 0))
            currency = amount_obj.get("currency", self.base_currency)

            status = data.get("status", "")
            buyer = data.get("buyer", {})
            buyer_email = buyer.get("email", "")

            return {
                "order_id": str(order_id),
                "amount": amount,
                "currency": currency.upper() if currency else self.base_currency,
                "status": str(status),
                "buyer_email": buyer_email,
            }
        except (KeyError, ValueError, TypeError):
            return None

    def poll_orders(self, since_datetime: Optional[str] = None) -> list:
        """
        Poll Allegro order events for new orders.

        Uses the order events API to find ORDER_CREATED / ORDER_STATUS_CHANGED
        events, then fetches each checkout-form for full details.

        Args:
            since_datetime: ISO8601 timestamp string (unused; Allegro uses
                            lastEventId cursor internally)

        Returns:
            List of parsed order dicts
        """
        return self.poll_new_orders()

    def poll_new_orders(self) -> list:
        """
        Fetch new ORDER_CREATED events from Allegro.

        Returns:
            List of (order_id, amount, currency) tuples for newly found orders
        """
        if not self._ensure_token():
            return []

        url = f"{_ALLEGRO_API}/order/events?type=ORDER_STATUS_CHANGED"
        try:
            req = Request(url, method="GET", headers={
                "Authorization": f"Bearer {self.access_token}",
                "Accept": _ALLEGRO_ACCEPT,
            })
            with urlopen(req, timeout=self.timeout, context=self._ssl) as resp:  # nosec B310
                data = json.loads(resp.read())
        except (URLError, json.JSONDecodeError, OSError):
            return []

        results = []
        for event in data.get("events", []):
            if event.get("type") not in ("BOUGHT", "ORDER_CREATED", "ORDER_STATUS_CHANGED"):
                continue
            order_ref = event.get("order", {})
            checkout_id = order_ref.get("checkoutForm", {}).get("id", "")
            if not checkout_id:
                continue
            order_data = self._fetch_checkout_form(checkout_id)
            if not order_data:
                continue
            parsed = self.parse_order(order_data)
            if parsed:
                results.append((parsed["order_id"], parsed["amount"], parsed["currency"]))

        return results

    def _fetch_checkout_form(self, checkout_id: str) -> Optional[dict]:
        """Fetch a single checkout-form from the Allegro API."""
        if not self._ensure_token():
            return None

        url = f"{_ALLEGRO_API}/order/checkout-forms/{quote(checkout_id, safe='')}"
        try:
            req = Request(url, method="GET", headers={
                "Authorization": f"Bearer {self.access_token}",
                "Accept": _ALLEGRO_ACCEPT,
            })
            with urlopen(req, timeout=self.timeout, context=self._ssl) as resp:  # nosec B310
                return json.loads(resp.read())
        except (URLError, json.JSONDecodeError, OSError):
            return None

    def fulfill_order(self, order_id: str, tx_id: str) -> bool:
        """
        Mark an Allegro order as ready-for-processing with the AlgoVoi TX reference.

        Uses PATCH /order/checkout-forms/{id}/fulfillment.

        Args:
            order_id: Allegro checkout-form ID
            tx_id:    On-chain transaction ID

        Returns:
            True if the fulfilment was accepted
        """
        if not tx_id or len(tx_id) > 200:
            return False

        if not self._ensure_token():
            return False

        url = f"{_ALLEGRO_API}/order/checkout-forms/{quote(order_id, safe='')}/fulfillment"

        payload = json.dumps({
            "status": "READY_FOR_PROCESSING",
            "shipmentSummary": {
                "lineItemsSent": "NONE",
            },
        }).encode()

        req = Request(url, data=payload, method="PATCH", headers={
            "Authorization": f"Bearer {self.access_token}",
            "Accept": _ALLEGRO_ACCEPT,
            "Content-Type": _ALLEGRO_ACCEPT,
        })

        try:
            with urlopen(req, timeout=self.timeout, context=self._ssl) as resp:  # nosec B310
                return resp.status in (200, 201, 204)
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
