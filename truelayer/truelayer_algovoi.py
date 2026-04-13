"""
AlgoVoi TrueLayer Open Banking Payment Adapter

Receives TrueLayer payment webhooks (payment_executed, payment_settled),
verifies the HMAC-SHA256 Tl-Signature header, and creates AlgoVoi
settlement links for on-chain stablecoin payout.

Fiat in (Faster Payments / SEPA Instant) → stablecoin out (USDC on
Algorand or aUSDC on VOI).

Works with Flask, Django, FastAPI, or any WSGI framework.
Zero pip dependencies — uses only the Python standard library.

TrueLayer API docs: https://docs.truelayer.com/

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

TRUELAYER_PAYMENT_EVENTS = {"payment_executed", "payment_settled", "payment_creditable"}


class TrueLayerAlgoVoi:
    """TrueLayer Open Banking + AlgoVoi settlement adapter."""

    def __init__(
        self,
        api_base: str = "https://api1.ilovechicken.co.uk",
        api_key: str = "",
        tenant_id: str = "",
        truelayer_client_id: str = "",
        truelayer_client_secret: str = "",
        webhook_secret: str = "",
        default_network: str = "algorand_mainnet",
        base_currency: str = "GBP",
        timeout: int = 30,
    ):
        self.api_base = api_base.rstrip("/")
        self.api_key = api_key
        self.tenant_id = tenant_id
        self.truelayer_client_id = truelayer_client_id
        self.truelayer_client_secret = truelayer_client_secret
        self.webhook_secret = webhook_secret
        self.default_network = default_network
        self.base_currency = base_currency
        self.timeout = timeout
        self._ssl = ssl.create_default_context()

    # ── Webhook Verification ─────────────────────────────────────────────

    def verify_webhook(self, raw_body: bytes, signature: str) -> Optional[dict]:
        """
        Verify a TrueLayer webhook using the Tl-Signature header.

        TrueLayer signs webhooks with HMAC-SHA256 using the webhook secret.
        (Production TrueLayer uses ES512/JWS — this adapter implements the
        HMAC-SHA256 variant used for AlgoVoi internal webhook callbacks.)

        Args:
            raw_body:  Raw POST body as bytes
            signature: Tl-Signature header value (hex-encoded HMAC-SHA256)

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

    # ── Payment Webhook Parsing ──────────────────────────────────────────

    def parse_payment_webhook(self, payload: dict) -> Optional[dict]:
        """
        Parse a TrueLayer payment webhook payload.

        Handles payment_executed, payment_settled, and payment_creditable
        event types.

        Args:
            payload: The parsed webhook JSON

        Returns:
            dict with payment_id, amount, currency, status, metadata — or None
        """
        try:
            event_type = payload.get("type", payload.get("event_type", ""))
            data = payload.get("payment", payload.get("data", payload))

            payment_id = data.get("id", data.get("payment_id", ""))
            if not payment_id:
                return None

            # TrueLayer amounts are in minor units (pence/cents) or major
            raw_amount = data.get("amount_in_minor", data.get("amount", 0))
            currency = data.get("currency", self.base_currency)

            # Convert minor units to major if above 100 (heuristic: > 10000 is pence)
            if isinstance(raw_amount, int) and raw_amount > 100 and "minor" in str(
                payload.get("type", "")
            ).lower():
                amount = raw_amount / 100.0
            else:
                amount = float(raw_amount)

            status = data.get("status", event_type)
            metadata = data.get("metadata", payload.get("metadata", {}))

            return {
                "payment_id": str(payment_id),
                "amount": amount,
                "currency": currency.upper() if currency else self.base_currency,
                "status": str(status),
                "metadata": metadata if isinstance(metadata, dict) else {},
            }
        except (KeyError, ValueError, TypeError):
            return None

    # ── Settlement Creation ──────────────────────────────────────────────

    def create_settlement(
        self,
        payment_id: str,
        amount: float,
        currency: Optional[str] = None,
        network: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> Optional[dict]:
        """
        Create an AlgoVoi settlement link for a confirmed TrueLayer payment.

        Args:
            payment_id: TrueLayer payment ID
            amount:     Payment amount
            currency:   ISO currency code (defaults to base_currency)
            network:    Target network (defaults to default_network)
            metadata:   Optional metadata dict

        Returns:
            dict with checkout_url, token, chain, amount_microunits — or None
        """
        if not network or network not in HOSTED_NETWORKS:
            network = self.default_network
        if not currency:
            currency = self.base_currency

        label = f"TrueLayer Payment {payment_id}"

        payload: dict[str, Any] = {
            "amount": round(amount, 2),
            "currency": currency.upper(),
            "label": label,
            "preferred_network": network,
            "reference": payment_id,
        }
        if metadata:
            payload["metadata"] = metadata

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
            "payment_id": payment_id,
        }

    # ── Payment Verification ─────────────────────────────────────────────

    def verify_payment(self, token: str) -> bool:
        """
        Check if a settlement payment has been completed.

        Args:
            token: AlgoVoi checkout token

        Returns:
            True only if the API confirms payment is complete
        """
        if not token:
            return False
        tx_id = token
        if len(tx_id) > 200:
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

    # ── Flask Helper ─────────────────────────────────────────────────────

    def flask_webhook_handler(self):
        """
        Returns a Flask view function for the TrueLayer webhook endpoint.

        Usage:
            app.add_url_rule('/webhook/truelayer',
                view_func=adapter.flask_webhook_handler(), methods=['POST'])
        """
        adapter = self

        def handler():
            from flask import request, jsonify

            raw_body = request.get_data()
            signature = request.headers.get("Tl-Signature", "")

            payload = adapter.verify_webhook(raw_body, signature)
            if not payload:
                return jsonify(error="Unauthorized"), 401

            payment = adapter.parse_payment_webhook(payload)
            if not payment:
                return jsonify(received=True, skipped="not parseable")

            # Only act on successful payment events
            if payment["status"] not in (
                "payment_executed", "payment_settled", "payment_creditable",
                "executed", "settled", "creditable", "EXECUTED", "SETTLED",
            ):
                return jsonify(received=True, skipped=f"status={payment['status']}")

            result = adapter.create_settlement(
                payment_id=payment["payment_id"],
                amount=payment["amount"],
                currency=payment["currency"],
                metadata=payment.get("metadata"),
            )

            if not result:
                return jsonify(error="Could not create settlement link"), 502

            return jsonify(
                received=True,
                payment_id=payment["payment_id"],
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

    def _get(self, path: str) -> Optional[dict]:
        req = Request(
            f"{self.api_base}{path}",
            method="GET",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "X-Tenant-Id": self.tenant_id,
            },
        )
        try:
            with urlopen(req, timeout=self.timeout, context=self._ssl) as resp:  # nosec B310
                if resp.status != 200:
                    return None
                return json.loads(resp.read())
        except (URLError, json.JSONDecodeError, OSError):
            return None
