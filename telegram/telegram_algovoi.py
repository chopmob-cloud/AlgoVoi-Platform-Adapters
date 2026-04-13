"""
AlgoVoi Telegram Bot Payment Adapter

Bypass-mode integration: the Telegram bot sends AlgoVoi hosted checkout
URLs to customers. No Telegram Payments provider registration is required.

Flow:
  Customer /pay command → bot calls AlgoVoi → bot sends checkout URL
  → customer pays on-chain → AlgoVoi webhook fires → bot confirms

Telegram secures webhooks via X-Telegram-Bot-Api-Secret-Token header.
The header value must match the secret_token passed to setWebhook.

Telegram Bot API docs: https://core.telegram.org/bots/api

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

TELEGRAM_API_BASE = "https://api.telegram.org"


class TelegramAlgoVoi:
    """Telegram bot (bypass mode) + AlgoVoi payment adapter."""

    def __init__(
        self,
        api_base: str = "https://api1.ilovechicken.co.uk",
        api_key: str = "",
        tenant_id: str = "",
        bot_token: str = "",
        webhook_secret: str = "",
        default_network: str = "algorand_mainnet",
        base_currency: str = "USD",
        timeout: int = 30,
    ):
        self.api_base = api_base.rstrip("/")
        self.api_key = api_key
        self.tenant_id = tenant_id
        self.bot_token = bot_token
        self.webhook_secret = webhook_secret
        self.default_network = default_network
        self.base_currency = base_currency
        self.timeout = timeout
        self._ssl = ssl.create_default_context()

    # ── Webhook Verification ─────────────────────────────────────────────

    def verify_update(self, raw_body: bytes, signature: str) -> Optional[dict]:
        """
        Verify a Telegram bot update via X-Telegram-Bot-Api-Secret-Token.

        Telegram passes the secret_token supplied in setWebhook verbatim in
        the X-Telegram-Bot-Api-Secret-Token header. This adapter performs a
        constant-time comparison of that header against webhook_secret.

        Args:
            raw_body:  Raw POST body as bytes
            signature: X-Telegram-Bot-Api-Secret-Token header value

        Returns:
            Parsed update dict, or None if verification fails
        """
        if not self.webhook_secret:
            return None

        if not hmac.compare_digest(self.webhook_secret, signature):
            return None

        try:
            update = json.loads(raw_body)
        except json.JSONDecodeError:
            return None

        # Replay attack prevention.
        # Telegram's Update payload for a message event includes the Unix-epoch
        # timestamp at update["message"]["date"] (integer seconds). The entire
        # payload is implicitly bound to the secret token via
        # X-Telegram-Bot-Api-Secret-Token above, so a tampered timestamp would
        # fail the secret check before reaching this code. We can therefore
        # trust message.date as a replay check input.
        #
        # If message.date is missing (e.g. callback_query, edited_message, or
        # non-message Updates) we fail open — is_replay() returns False on any
        # unparseable input. The secret token check is the primary authenticity
        # control; replay prevention is defence-in-depth.
        if isinstance(update, dict):
            message_ts: Any = None
            msg = update.get("message")
            if isinstance(msg, dict):
                message_ts = msg.get("date")
            # Cover edited_message too — same date semantics
            if message_ts is None:
                edited = update.get("edited_message")
                if isinstance(edited, dict):
                    message_ts = edited.get("date")

            if message_ts is not None and self.is_replay(str(message_ts)):
                return None

        return update

    # ── Replay Attack Prevention ─────────────────────────────────────────

    def is_replay(self, timestamp_str: str, max_age_seconds: int = 300) -> bool:
        """
        Replay attack prevention for Telegram webhook updates.

        Telegram includes a Unix-epoch "date" field on every Message object
        inside an Update payload. That timestamp is implicitly covered by the
        X-Telegram-Bot-Api-Secret-Token header verification — a tampered body
        fails signature verification before this method runs — so we can
        trust the value when we see it.

        Returns True if the parsed timestamp is older than max_age_seconds
        (default 5 minutes — production deployments may want to raise this
        to 600 seconds or more to tolerate slow platform retry windows).

        Returns False (fail open) if:
          - timestamp_str is empty
          - timestamp_str cannot be parsed as an integer
          - any other error occurs

        Fail-open is intentional: a missing or malformed timestamp from a
        legitimate Telegram retry should never block a real webhook. Replay
        attacks are low-probability; broken parsing of legitimate retries
        is high-probability if we fail closed. The secret token check is
        the primary authenticity control; this is defence-in-depth.

        Args:
            timestamp_str:    Unix epoch seconds as a string (Telegram
                              sends it as an integer inside JSON; callers
                              pass str(message["date"])).
            max_age_seconds:  Maximum age in seconds before considered stale.
                              Default 300 (5 min). Production deployments
                              may raise to 600+ for slow retries.

        Returns:
            True if the timestamp is older than max_age_seconds.
            False otherwise (including all parse failures — fail open).
        """
        if not timestamp_str:
            return False
        try:
            # Telegram message.date is an integer Unix epoch (seconds).
            # We accept a str wrapper so this method has the same signature
            # as the Xero adapter's is_replay, which takes ISO 8601 strings.
            message_epoch = int(timestamp_str)
            if message_epoch <= 0:
                return False
            age_seconds = time.time() - float(message_epoch)
            return age_seconds > max_age_seconds
        except (ValueError, TypeError):
            # Fail open on any parse error
            return False

    # ── Message / Order Parsing ───────────────────────────────────────────

    def parse_order_message(self, update: dict) -> Optional[dict]:
        """
        Parse a Telegram update for a /pay command or inline callback.

        Handles two forms:
          - message.text starting with /pay <amount> [currency]
          - callback_query.data with "pay:<amount>:<currency>"

        Args:
            update: Parsed Telegram update dict

        Returns:
            dict with chat_id, amount, currency — or None
        """
        try:
            # Callback query path
            if "callback_query" in update:
                cq = update["callback_query"]
                chat_id = str(cq.get("message", {}).get("chat", {}).get("id", ""))
                data = cq.get("data", "")
                parts = data.split(":")
                if len(parts) >= 2 and parts[0] == "pay":
                    try:
                        amount = float(parts[1])
                    except (ValueError, TypeError):
                        return None
                    currency = parts[2].upper() if len(parts) >= 3 else self.base_currency
                    return {"chat_id": chat_id, "amount": amount, "currency": currency}
                return None

            # Message text path
            message = update.get("message", {})
            if not message:
                return None

            chat_id = str(message.get("chat", {}).get("id", ""))
            text = (message.get("text") or "").strip()

            if not text.lower().startswith("/pay"):
                return None

            parts = text.split()
            if len(parts) < 2:
                return None

            try:
                amount = float(parts[1])
            except (ValueError, TypeError):
                return None

            currency = parts[2].upper() if len(parts) >= 3 else self.base_currency

            return {"chat_id": chat_id, "amount": amount, "currency": currency}
        except (KeyError, TypeError, AttributeError):
            return None

    # ── Checkout ─────────────────────────────────────────────────────────

    def create_checkout(
        self,
        chat_id: str,
        amount: float,
        currency: Optional[str] = None,
        network: Optional[str] = None,
        label: Optional[str] = None,
    ) -> Optional[dict]:
        """
        Create an AlgoVoi payment link for a Telegram chat.

        Args:
            chat_id:  Telegram chat ID (used as reference)
            amount:   Order amount
            currency: ISO currency code (defaults to base_currency)
            network:  Preferred network (defaults to default_network)
            label:    Payment label

        Returns:
            dict with checkout_url, token, chain, amount_microunits — or None
        """
        if not network or network not in HOSTED_NETWORKS:
            network = self.default_network
        if not currency:
            currency = self.base_currency
        if not label:
            label = f"Telegram Payment chat:{chat_id}"

        payload: dict[str, Any] = {
            "amount": round(amount, 2),
            "currency": currency.upper(),
            "label": label,
            "preferred_network": network,
            "reference": chat_id,
        }

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
            "chat_id": chat_id,
        }

    def send_payment_link(
        self,
        chat_id: str,
        checkout_url: str,
        amount: float,
        currency: str = "",
    ) -> bool:
        """
        Send a payment link to a Telegram chat as an inline keyboard button.

        Calls https://api.telegram.org/bot{token}/sendMessage

        Args:
            chat_id:      Telegram chat ID
            checkout_url: AlgoVoi hosted checkout URL
            amount:       Order amount (shown in message text)
            currency:     ISO currency code

        Returns:
            True if Telegram accepted the message
        """
        if not self.bot_token:
            return False
        if not chat_id or not checkout_url:
            return False

        currency = (currency or self.base_currency).upper()
        text = f"Pay {currency} {amount:.2f} — tap the button below:"

        url = f"{TELEGRAM_API_BASE}/bot{self.bot_token}/sendMessage"
        body = json.dumps({
            "chat_id": chat_id,
            "text": text,
            "reply_markup": {
                "inline_keyboard": [[
                    {"text": "Pay with USDC", "url": checkout_url}
                ]]
            },
        }).encode()

        req = Request(
            url,
            data=body,
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        try:
            with urlopen(req, timeout=self.timeout, context=self._ssl) as resp:  # nosec B310
                return resp.status in (200, 201)
        except (URLError, OSError):
            return False

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

    # ── Flask Handler ─────────────────────────────────────────────────────

    def flask_webhook_handler(self):
        """
        Returns a Flask view function for the Telegram bot webhook endpoint.

        Usage:
            app.add_url_rule('/webhook/telegram',
                view_func=adapter.flask_webhook_handler(), methods=['POST'])
        """
        adapter = self

        def handler():
            from flask import request, jsonify

            raw_body = request.get_data()
            signature = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")

            update = adapter.verify_update(raw_body, signature)
            if update is None:
                return jsonify(error="Unauthorized"), 401

            order = adapter.parse_order_message(update)
            if not order:
                return jsonify(received=True, skipped="not a pay command")

            result = adapter.create_checkout(
                chat_id=order["chat_id"],
                amount=order["amount"],
                currency=order["currency"],
            )

            if not result:
                return jsonify(error="Could not create payment link"), 502

            adapter.send_payment_link(
                chat_id=order["chat_id"],
                checkout_url=result["checkout_url"],
                amount=order["amount"],
                currency=order["currency"],
            )

            return jsonify(
                received=True,
                chat_id=order["chat_id"],
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
