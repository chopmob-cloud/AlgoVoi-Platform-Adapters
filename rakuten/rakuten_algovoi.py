"""
AlgoVoi Rakuten Ichiba Payment Adapter

Polls the Rakuten RMS (Rakuten Merchant Server) API for new orders,
creates AlgoVoi payment links, and writes TX references back to order notes.

Rakuten does NOT support outbound webhooks. This adapter polls
GET /order/searchOrder/ with a last-modified timestamp, fetches
new orders, and updates them with TX data via RMS API.

A manual bypass path is also supported: operators can POST orders directly
and include an HMAC-SHA256 signature for verify_webhook().

RMS API docs: https://api.rms.rakuten.co.jp/es/1.0/

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

_RMS_API = "https://api.rms.rakuten.co.jp/es/1.0"


class RakutenAlgoVoi:
    """Rakuten RMS API + AlgoVoi payment adapter (polling-based)."""

    def __init__(
        self,
        api_base: str = "https://api1.ilovechicken.co.uk",
        api_key: str = "",
        tenant_id: str = "",
        service_secret: str = "",
        license_key: str = "",
        webhook_secret: str = "",
        default_network: str = "algorand_mainnet",
        base_currency: str = "JPY",
        timeout: int = 30,
    ):
        self.api_base = api_base.rstrip("/")
        self.api_key = api_key
        self.tenant_id = tenant_id
        self.service_secret = service_secret
        self.license_key = license_key
        self.webhook_secret = webhook_secret
        self.default_network = default_network
        self.base_currency = base_currency
        self.timeout = timeout
        self._ssl = ssl.create_default_context()

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

    # ── Rakuten RMS Auth ─────────────────────────────────────────────────

    def _rms_auth_header(self) -> str:
        """Build the Basic Authorization header for RMS API calls."""
        if not self.service_secret or not self.license_key:
            return ""
        creds = base64.b64encode(
            f"{self.service_secret}:{self.license_key}".encode()
        ).decode()
        return f"ESA {creds}"

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
        Create an AlgoVoi payment link for a Rakuten order.

        Args:
            order_id:     Rakuten order number
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
            label = f"Rakuten Order #{order_id}"

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

    # ── RMS API Integration ──────────────────────────────────────────────

    def parse_order(self, data: dict) -> Optional[dict]:
        """
        Parse a Rakuten RMS order response into a normalised order dict.

        Handles both searchOrder results (which may be wrapped) and individual
        order records.

        Args:
            data: Order JSON from RMS searchOrder or single order endpoint

        Returns:
            dict with order_id, amount, currency, status, buyer_email — or None
        """
        try:
            order_id = str(
                data.get("orderNumber", data.get("orderId", data.get("order_number", "")))
            )
            if not order_id:
                return None

            amount = float(
                data.get("goodsPrice", data.get("totalPrice", data.get("amount", 0)))
            )
            # Rakuten Ichiba is JPY by default; rakuten.fr/de use EUR
            currency = data.get("currency", self.base_currency) or self.base_currency
            status = data.get("orderStatus", data.get("status", ""))
            buyer_email = data.get(
                "mailAddress",
                data.get("buyerEmail", data.get("buyer_email", "")),
            )

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
        Poll Rakuten RMS for new orders using a last-modified timestamp.

        Args:
            since_datetime: ISO8601 or RMS-format timestamp string.
                            Defaults to the last hour if not specified.

        Returns:
            List of parsed order dicts
        """
        auth = self._rms_auth_header()
        if not auth:
            return []

        if not since_datetime:
            # Default: orders modified in the last hour
            since_datetime = time.strftime(
                "%Y-%m-%dT%H:%M:%S+0900",
                time.gmtime(time.time() - 3600),
            )

        params = urlencode({
            "dateType": "2",
            "startDatetime": since_datetime,
            "PaginationRequestModel.requestRecordsAmount": "100",
            "PaginationRequestModel.requestPage": "1",
        })

        url = f"{_RMS_API}/order/searchOrder/?{params}"
        try:
            req = Request(url, method="GET", headers={
                "Authorization": auth,
                "Accept": "application/json",
            })
            with urlopen(req, timeout=self.timeout, context=self._ssl) as resp:  # nosec B310
                data = json.loads(resp.read())
        except (URLError, json.JSONDecodeError, OSError):
            return []

        # RMS returns {"orderModelList": [...]} or similar wrapper
        if isinstance(data, list):
            orders_raw = data
        else:
            orders_raw = (
                data.get("orderModelList", [])
                or data.get("orders", [])
                or data.get("results", [])
            )

        results = []
        for order in orders_raw:
            parsed = self.parse_order(order)
            if parsed:
                results.append(parsed)
        return results

    def fulfill_order(self, order_id: str, tx_id: str) -> bool:
        """
        Update a Rakuten RMS order with the AlgoVoi TX reference.

        Writes the TX ID to the order seller memo / notes field.

        Args:
            order_id: Rakuten order number
            tx_id:    On-chain transaction ID

        Returns:
            True if the update call was accepted
        """
        if not tx_id or len(tx_id) > 200:
            return False

        auth = self._rms_auth_header()
        if not auth:
            return False

        url = f"{_RMS_API}/order/updateOrder/"

        payload = json.dumps({
            "orderNumber": order_id,
            "remarks": f"AlgoVoi TX: {tx_id[:64]}",
            "memo": f"Paid via AlgoVoi. TX: {tx_id[:40]}",
        }).encode()

        req = Request(url, data=payload, method="POST", headers={
            "Authorization": auth,
            "Content-Type": "application/json",
            "Accept": "application/json",
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
