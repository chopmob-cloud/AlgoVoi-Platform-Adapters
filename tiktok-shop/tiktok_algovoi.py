"""
AlgoVoi TikTok Shop Payment Adapter

Receives TikTok Shop Open Platform order webhooks, creates AlgoVoi
payment links, and updates order shipping info when payment is confirmed.

Use cases:
  - B2B / supplier invoicing — issue crypto payment to fulfilment partners
  - Seller fee settlement — settle inter-company invoices in USDC/aUSDC
  - Operator-initiated flows — your backend sends order data to AlgoVoi

TikTok Shop processes all consumer checkout payments internally.
This adapter handles post-order B2B payment flows only.

Works with Flask, Django, FastAPI, or any WSGI framework.
Zero pip dependencies — uses only the Python standard library.

Version: 1.0.0

AlgoVoi docs: https://github.com/chopmob-cloud/AlgoVoi-Platform-Adapters
Copyright (c) 2026 Christopher Hopley (ilovechicken.co.uk). BSL 1.1.
"""

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


class TikTokAlgoVoi:
    """TikTok Shop Open Platform + AlgoVoi payment adapter."""

    def __init__(
        self,
        api_base: str = "https://api1.ilovechicken.co.uk",
        api_key: str = "",
        tenant_id: str = "",
        webhook_secret: str = "",
        tiktok_app_secret: str = "",
        default_network: str = "algorand_mainnet",
        base_currency: str = "GBP",
        timeout: int = 30,
    ):
        self.api_base = api_base.rstrip("/")
        self.api_key = api_key
        self.tenant_id = tenant_id
        self.webhook_secret = webhook_secret
        self.tiktok_app_secret = tiktok_app_secret
        self.default_network = default_network
        self.base_currency = base_currency
        self.timeout = timeout
        self._ssl = ssl.create_default_context()

    # ── TikTok Webhook Verification ──────────────────────────────────────

    def verify_tiktok_webhook(self, raw_body: bytes, signature: str) -> Optional[dict]:
        """
        Verify a TikTok Shop Open Platform webhook.

        TikTok signs webhooks with HMAC-SHA256 using the app secret.
        The signature is sent in the X-Tts-Signature header.

        Args:
            raw_body:  Raw POST body as bytes
            signature: X-Tts-Signature header value

        Returns:
            Parsed payload dict, or None if verification fails
        """
        if not self.tiktok_app_secret:
            return None

        expected = hmac.new(
            self.tiktok_app_secret.encode(),
            raw_body,
            hashlib.sha256,
        ).hexdigest()

        if not hmac.compare_digest(expected, signature):
            return None

        try:
            return json.loads(raw_body)
        except json.JSONDecodeError:
            return None

    def verify_algovoi_webhook(self, raw_body: bytes, signature: str) -> Optional[dict]:
        """
        Verify an AlgoVoi platform webhook (for payment confirmations).

        Args:
            raw_body:  Raw POST body as bytes
            signature: X-AlgoVoi-Signature header value

        Returns:
            Parsed payload dict, or None if verification fails
        """
        if not self.webhook_secret:
            return None

        expected = base64.b64encode(
            hmac.new(
                self.webhook_secret.encode(),
                raw_body,
                hashlib.sha256,
            ).digest()
        ).decode()

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
        Create an AlgoVoi payment link for a TikTok Shop order.

        Args:
            order_id:     TikTok order ID
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
            label = f"TikTok Order #{order_id}"

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
        try:
            req = Request(url, method="GET")
            with urlopen(req, timeout=15, context=self._ssl) as resp:  # nosec B310
                if resp.status != 200:
                    return False
                data = json.loads(resp.read())
                return data.get("status") in ("paid", "completed", "confirmed")
        except (URLError, json.JSONDecodeError, OSError):
            return False

    # ── TikTok Open Platform Integration ─────────────────────────────────

    def parse_order_webhook(self, payload: dict) -> Optional[dict]:
        """
        Parse a TikTok Shop order webhook payload.

        Handles both ORDER_STATUS_CHANGE and ORDER_CREATED event types.

        Args:
            payload: The parsed webhook JSON

        Returns:
            dict with order_id, amount, currency, status — or None
        """
        try:
            event_type = payload.get("type", "")
            data = payload.get("data", {})

            if event_type in ("ORDER_STATUS_CHANGE", "ORDER_CREATED", "1"):
                order_id = data.get("order_id", "")
                if not order_id:
                    # Try nested structure
                    order_id = data.get("order", {}).get("order_id", "")

                payment = data.get("payment", data.get("order", {}).get("payment", {}))
                amount_str = payment.get("total_amount", payment.get("original_total_price", "0"))
                currency = payment.get("currency", self.base_currency)
                status = data.get("order_status", data.get("status", ""))

                if not order_id:
                    return None

                return {
                    "order_id": str(order_id),
                    "amount": float(amount_str),
                    "currency": currency.upper() if currency else self.base_currency,
                    "status": str(status),
                    "event_type": event_type,
                }

            return None
        except (KeyError, ValueError, TypeError):
            return None

    def update_shipping(
        self,
        order_id: str,
        tx_id: str,
        access_token: str,
        api_base: str = "https://open-api.tiktokglobalshop.com",
    ) -> bool:
        """
        Update shipping info on TikTok Shop with the AlgoVoi TX reference.

        Args:
            order_id:     TikTok order ID
            tx_id:        On-chain transaction ID
            access_token: TikTok Open Platform access token
            api_base:     TikTok API base URL

        Returns:
            True if the update was accepted
        """
        if not tx_id or len(tx_id) > 200:
            return False

        url = f"{api_base}/api/orders/shipping/update"
        payload = json.dumps({
            "order_id": order_id,
            "tracking_number": f"AlgoVoi-TX:{tx_id[:64]}",
            "shipping_provider_id": "OTHER",
        }).encode()

        req = Request(url, data=payload, method="POST", headers={
            "Content-Type": "application/json",
            "x-tts-access-token": access_token,
        })

        try:
            with urlopen(req, timeout=self.timeout, context=self._ssl) as resp:  # nosec B310
                return resp.status in (200, 204)
        except (URLError, OSError):
            return False

    # ── Flask Helper ─────────────────────────────────────────────────────

    def flask_webhook_handler(self):
        """
        Returns a Flask view function for the TikTok webhook endpoint.

        Usage:
            app.add_url_rule('/webhook/tiktok', view_func=adapter.flask_webhook_handler(), methods=['POST'])
        """
        adapter = self

        def handler():
            from flask import request, jsonify

            raw_body = request.get_data()
            signature = request.headers.get("X-Tts-Signature", "")

            payload = adapter.verify_tiktok_webhook(raw_body, signature)
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
