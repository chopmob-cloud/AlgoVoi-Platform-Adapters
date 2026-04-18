"""
AlgoVoi OnBuy Payment Adapter

Polls the OnBuy Orders API for OPEN orders, creates AlgoVoi payment links,
and dispatches orders when payment is confirmed on-chain.

OnBuy does not support push webhooks. This adapter polls
GET /orders?status=awaiting_dispatch and dispatches via
PUT /orders/{order_id}/dispatch.

Authentication uses OAuth2 client credentials (consumer_key / secret_key).
HMAC-SHA256 request signing is also supported for the manual bypass path.

A manual bypass path is also supported: operators can POST orders directly
and include an HMAC-SHA256 signature for verify_webhook().

OnBuy API docs: https://api.onbuy.com/

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

_ONBUY_API = "https://api.onbuy.com/v2"
_ONBUY_AUTH = "https://api.onbuy.com/v2/oauth/token"
_ONBUY_DEFAULT_SITE_ID = "2000"


class OnbuyAlgoVoi:
    """OnBuy Orders API + AlgoVoi payment adapter (polling-based)."""

    def __init__(
        self,
        api_base: str = "https://api1.ilovechicken.co.uk",
        api_key: str = "",
        tenant_id: str = "",
        site_id: str = _ONBUY_DEFAULT_SITE_ID,
        onbuy_api_key: str = "",
        webhook_secret: str = "",
        default_network: str = "algorand_mainnet",
        base_currency: str = "GBP",
        timeout: int = 30,
    ):
        self.api_base = api_base.rstrip("/")
        self.api_key = api_key
        self.tenant_id = tenant_id
        self.site_id = site_id or _ONBUY_DEFAULT_SITE_ID
        self.onbuy_api_key = onbuy_api_key
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

    def _sign_request(self, method: str, path: str, body: bytes = b"") -> str:
        """
        Compute HMAC-SHA256 request signature for OnBuy API calls.

        OnBuy uses the api_key as the signing secret.

        Args:
            method: HTTP method (uppercase)
            path:   Request path (without base URL)
            body:   Raw request body bytes

        Returns:
            Hex HMAC-SHA256 signature string
        """
        if not self.onbuy_api_key:
            return ""
        message = f"{method}\n{path}\n".encode() + body
        return hmac.new(
            self.onbuy_api_key.encode(),
            message,
            hashlib.sha256,
        ).hexdigest()

    # ── OAuth2 Token Management ──────────────────────────────────────────

    def _refresh_token(self) -> bool:
        """Obtain a new access token via OnBuy OAuth2 client_credentials flow."""
        if not self.onbuy_api_key:
            return False

        body = urlencode({
            "grant_type": "client_credentials",
            "client_id": self.onbuy_api_key,
            "client_secret": self.webhook_secret or "",
        }).encode()

        req = Request(
            _ONBUY_AUTH,
            data=body,
            method="POST",
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json",
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
        Create an AlgoVoi payment link for an OnBuy order.

        Args:
            order_id:     OnBuy order ID
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
            label = f"OnBuy Order #{order_id}"

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

    # ── OnBuy API Integration ────────────────────────────────────────────

    def parse_order(self, data: dict) -> Optional[dict]:
        """
        Parse an OnBuy order response into a normalised order dict.

        Args:
            data: Order JSON from GET /orders or individual order

        Returns:
            dict with order_id, amount, currency, status, buyer_email — or None
        """
        try:
            order_id = str(data.get("order_id", data.get("id", "")))
            if not order_id:
                return None

            amount = float(data.get("total", data.get("order_total", data.get("amount", 0))))
            currency = data.get("currency_code", data.get("currency", self.base_currency)) or self.base_currency
            status = data.get("order_status", data.get("status", "awaiting_dispatch"))
            buyer_email = data.get("buyer_email", data.get("email", ""))

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
        Poll OnBuy API for orders with awaiting_dispatch status.

        Args:
            since_datetime: ISO8601 timestamp (unused; OnBuy uses status filter)

        Returns:
            List of parsed order dicts
        """
        if not self._ensure_token():
            return []

        url = f"{_ONBUY_API}/orders?site_id={quote(self.site_id, safe='')}&status=awaiting_dispatch"
        try:
            req = Request(url, method="GET", headers={
                "Authorization": f"Bearer {self._access_token}",
                "Accept": "application/json",
            })
            with urlopen(req, timeout=self.timeout, context=self._ssl) as resp:  # nosec B310
                data = json.loads(resp.read())
        except (URLError, json.JSONDecodeError, OSError):
            return []

        if isinstance(data, list):
            orders_raw = data
        else:
            orders_raw = data.get("results", data.get("orders", []))

        results = []
        for order in orders_raw:
            parsed = self.parse_order(order)
            if parsed:
                results.append(parsed)
        return results

    def fulfill_order(self, order_id: str, tx_id: str) -> bool:
        """
        Dispatch an OnBuy order with the AlgoVoi TX reference.

        Uses PUT /orders/{order_id}/dispatch.

        Args:
            order_id: OnBuy order ID
            tx_id:    On-chain transaction ID

        Returns:
            True if the dispatch call was accepted
        """
        if not tx_id or len(tx_id) > 200:
            return False

        if not self._ensure_token():
            return False

        url = f"{_ONBUY_API}/orders/{quote(str(order_id), safe='')}/dispatch"

        payload = json.dumps({
            "site_id": self.site_id,
            "tracking_number": tx_id[:64],
            "tracking_url": f"https://www.algovoi.co.uk/tx/{tx_id[:40]}",
            "courier_name": "AlgoVoi",
        }).encode()

        req = Request(url, data=payload, method="PUT", headers={
            "Authorization": f"Bearer {self._access_token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
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
