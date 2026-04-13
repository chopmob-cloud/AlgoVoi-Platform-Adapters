"""
AlgoVoi Discord Bot Payment Adapter

Integrates Discord slash commands with AlgoVoi hosted payment links.
Customers run a /pay command in a Discord server; the bot responds with
an ephemeral AlgoVoi checkout URL. Payment is completed on-chain (USDC
on Algorand, aUSDC on VOI).

Discord signs interactions with Ed25519 using the application Public Key.
The stdlib has no Ed25519 support — install PyNaCl in production and
swap in the commented verify_interaction_nacl() method. The fallback
here verifies internal AlgoVoi webhook POSTs via HMAC-SHA256 of
(timestamp + raw_body) against webhook_secret.

Discord API docs: https://discord.com/developers/docs/interactions/overview

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

# Discord interaction types
INTERACTION_PING = 1
INTERACTION_APPLICATION_COMMAND = 2


class DiscordAlgoVoi:
    """Discord bot + AlgoVoi payment adapter."""

    def __init__(
        self,
        api_base: str = "https://api1.ilovechicken.co.uk",
        api_key: str = "",
        tenant_id: str = "",
        discord_public_key: str = "",
        webhook_secret: str = "",
        default_network: str = "algorand_mainnet",
        base_currency: str = "USD",
        timeout: int = 30,
    ):
        self.api_base = api_base.rstrip("/")
        self.api_key = api_key
        self.tenant_id = tenant_id
        # NOTE: discord_public_key is the Ed25519 application public key from
        # the Discord Developer Portal. Verifying Ed25519 requires PyNaCl
        # (pip install pynacl). This stdlib adapter stores the key for
        # reference but cannot perform the real Ed25519 check without it.
        self.discord_public_key = discord_public_key
        self.webhook_secret = webhook_secret
        self.default_network = default_network
        self.base_currency = base_currency
        self.timeout = timeout
        self._ssl = ssl.create_default_context()

    # ── Interaction / Webhook Verification ───────────────────────────────

    def verify_interaction(
        self,
        raw_body: bytes,
        signature: str,
        timestamp: str,
    ) -> bool:
        """
        Verify a Discord interaction or internal webhook.

        For production Discord interactions the correct check is Ed25519:
            VerifyKey(bytes.fromhex(self.discord_public_key))
            .verify(timestamp.encode() + raw_body, bytes.fromhex(signature))
        That requires PyNaCl which is not in the stdlib.

        This method therefore does two things:
          1. If discord_public_key is set it logs that Ed25519 is required
             and returns False (safe default — do not accept unverified).
          2. For internal AlgoVoi webhook POSTs (where signature is an
             HMAC-SHA256 hex digest) it falls back to HMAC-SHA256 of
             (timestamp + raw_body) against webhook_secret.

        Args:
            raw_body:  Raw POST body as bytes
            signature: X-Signature-Ed25519 header (or HMAC hex for internal)
            timestamp: X-Signature-Timestamp header

        Returns:
            True only if verification passes
        """
        if not self.webhook_secret and not self.discord_public_key:
            return False

        # Real Ed25519 path — requires PyNaCl, not available in stdlib.
        # Uncomment and install pynacl for production Discord interactions:
        #
        # from nacl.signing import VerifyKey
        # from nacl.exceptions import BadSignatureError
        # try:
        #     vk = VerifyKey(bytes.fromhex(self.discord_public_key))
        #     vk.verify(timestamp.encode() + raw_body, bytes.fromhex(signature))
        #     return True
        # except (BadSignatureError, ValueError):
        #     return False
        #
        if self.discord_public_key:
            # Ed25519 path not available in stdlib — reject safely.
            # Deploy with PyNaCl for production Discord interactions.
            return False

        # HMAC-SHA256 fallback for internal AlgoVoi webhook POSTs.
        if not self.webhook_secret:
            return False

        try:
            expected = hmac.new(
                self.webhook_secret.encode(),
                timestamp.encode() + raw_body,
                hashlib.sha256,
            ).hexdigest()
            return hmac.compare_digest(expected, signature)
        except (TypeError, ValueError):
            return False

    # ── Interaction Parsing ───────────────────────────────────────────────

    def parse_interaction(self, payload: dict) -> Optional[dict]:
        """
        Parse a Discord APPLICATION_COMMAND interaction payload.

        Extracts the slash command name and its options (amount, currency,
        user_id).

        Args:
            payload: Parsed JSON interaction payload from Discord

        Returns:
            dict with command_name, user_id, amount, currency — or None
        """
        try:
            if payload.get("type") != INTERACTION_APPLICATION_COMMAND:
                return None

            data = payload.get("data", {})
            command_name = data.get("name", "")
            if not command_name:
                return None

            # Extract user_id from member (guild) or user (DM)
            member = payload.get("member", {})
            user = member.get("user", payload.get("user", {}))
            user_id = user.get("id", "")

            # Build options dict from the options array
            options = {}
            for opt in data.get("options", []):
                options[opt.get("name", "")] = opt.get("value")

            amount_raw = options.get("amount", 0)
            try:
                amount = float(amount_raw)
            except (TypeError, ValueError):
                amount = 0.0

            currency = str(options.get("currency", self.base_currency)).upper()
            reference = str(options.get("reference", ""))

            return {
                "command_name": command_name,
                "user_id": user_id,
                "amount": amount,
                "currency": currency,
                "reference": reference,
                "interaction_id": payload.get("id", ""),
                "interaction_token": payload.get("token", ""),
            }
        except (KeyError, TypeError, AttributeError):
            return None

    # ── Checkout ─────────────────────────────────────────────────────────

    def create_checkout(
        self,
        interaction_id: str,
        amount: float,
        currency: Optional[str] = None,
        network: Optional[str] = None,
        user_id: str = "",
    ) -> Optional[dict]:
        """
        Create an AlgoVoi payment link for a Discord interaction.

        Args:
            interaction_id: Discord interaction ID (used as order reference)
            amount:         Order amount
            currency:       ISO currency code (defaults to base_currency)
            network:        Preferred network (defaults to default_network)
            user_id:        Discord user snowflake ID

        Returns:
            dict with checkout_url, token, chain, amount_microunits — or None
        """
        if not network or network not in HOSTED_NETWORKS:
            network = self.default_network
        if not currency:
            currency = self.base_currency

        label = f"Discord Payment from {user_id}" if user_id else f"Discord Interaction {interaction_id}"

        payload: dict[str, Any] = {
            "amount": round(amount, 2),
            "currency": currency.upper(),
            "label": label,
            "preferred_network": network,
            "reference": interaction_id,
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
            "interaction_id": interaction_id,
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

    def discord_interactions_handler(self):
        """
        Returns a Flask view function for the Discord interactions endpoint.

        Handles:
          - PING (type 1)  → responds with {"type": 1}
          - APPLICATION_COMMAND (type 2) → creates checkout and responds

        Usage:
            app.add_url_rule('/discord/interactions',
                view_func=adapter.discord_interactions_handler(),
                methods=['POST'])

        Note: Discord requires Ed25519 signature verification. Deploy with
        PyNaCl and set discord_public_key to enable the real Ed25519 path.
        """
        adapter = self

        def handler():
            from flask import request, jsonify

            raw_body = request.get_data()
            signature = request.headers.get("X-Signature-Ed25519", "")
            timestamp = request.headers.get("X-Signature-Timestamp", "")

            # Note: verify_interaction returns False when only discord_public_key
            # is set (Ed25519 requires PyNaCl). In production, install PyNaCl
            # and enable the Ed25519 verify path in verify_interaction().
            if not adapter.verify_interaction(raw_body, signature, timestamp):
                # For PING during endpoint registration we still need to respond.
                # Allow through only if we can parse type==1 with no secret check.
                try:
                    payload = json.loads(raw_body)
                except (json.JSONDecodeError, ValueError):
                    return jsonify(error="Unauthorized"), 401
                if payload.get("type") != INTERACTION_PING:
                    return jsonify(error="Unauthorized"), 401

            try:
                payload = json.loads(raw_body)
            except (json.JSONDecodeError, ValueError):
                return jsonify(error="Bad request"), 400

            # Respond to Discord PING challenge
            if payload.get("type") == INTERACTION_PING:
                return jsonify(type=1)

            # Handle slash command
            interaction = adapter.parse_interaction(payload)
            if not interaction:
                return jsonify(error="Unrecognised interaction"), 400

            if interaction["amount"] <= 0:
                return jsonify(
                    type=4,
                    data={"content": "Amount must be greater than zero.", "flags": 64},
                )

            result = adapter.create_checkout(
                interaction_id=interaction["interaction_id"],
                amount=interaction["amount"],
                currency=interaction["currency"],
                user_id=interaction["user_id"],
            )

            if not result:
                return jsonify(
                    type=4,
                    data={"content": "Could not create payment link.", "flags": 64},
                )

            chain_label = CHAIN_LABELS.get(adapter.default_network, adapter.default_network)
            content = (
                f"Pay {interaction['currency']} {interaction['amount']:.2f} "
                f"in {chain_label}:"
            )

            return jsonify(
                type=4,
                data={
                    "content": content,
                    "flags": 64,
                    "components": [{
                        "type": 1,
                        "components": [{
                            "type": 2,
                            "style": 5,
                            "label": "Pay with USDC",
                            "url": result["checkout_url"],
                        }],
                    }],
                },
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
