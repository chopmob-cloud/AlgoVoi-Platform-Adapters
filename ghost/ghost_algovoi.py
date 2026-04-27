"""
AlgoVoi Ghost Payment Adapter

Accepts AlgoVoi stablecoin payments as a crypto tip / membership-access
mechanism for Ghost 5.x blogs. Non-custodial: funds go straight to the
merchant's configured wallet. On verified payment, the adapter calls the
Ghost Admin API to upgrade the reader's member record (e.g. set a label
or grant a comped subscription to a named tier).

Supported hosted networks: Algorand, VOI, Hedera, Stellar, Base, Solana, Tempo.

Use cases:
  - "Pay with Crypto" alternative to Ghost's built-in Stripe flow
  - Tip jar for individual posts
  - Agent / bot buying access to a gated newsletter
  - Gift subscriptions

Works with Flask, Django, FastAPI, or any WSGI framework.

Python dependencies:
  - PyJWT >= 2.0   (for Ghost Admin API JWT auth — HS256, see
                   https://ghost.org/docs/admin-api/#token-authentication)
  - All other HTTP + HMAC work uses the standard library only.

Version: 1.1.0

AlgoVoi docs: https://github.com/chopmob-cloud/AlgoVoi-Platform-Adapters
Licensed under the Business Source License 1.1 — see LICENSE for details.
"""

from __future__ import annotations

import base64
import binascii
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

HOSTED_NETWORKS = {"algorand_mainnet", "voi_mainnet", "hedera_mainnet", "stellar_mainnet", "base_mainnet", "solana_mainnet", "tempo_mainnet"}

# Hard caps, mirroring the B2B webhook adapters.
MAX_WEBHOOK_BODY_BYTES = 64 * 1024
MAX_TX_ID_LEN          = 200
MAX_EMAIL_LEN          = 254   # RFC 5321
MAX_LABEL_LEN          = 191   # Ghost label limit

# Ghost Admin API key format: "<24-hex-id>:<64-hex-secret>"
GHOST_ADMIN_KEY_RE = re.compile(r"^[0-9a-f]{24}:[0-9a-f]{64}$")


class GhostAlgoVoi:
    """Ghost + AlgoVoi payment-to-access adapter."""

    def __init__(
        self,
        ghost_url: str,
        ghost_admin_key: str,
        api_base: str = "https://api1.ilovechicken.co.uk",
        api_key: str = "",
        tenant_id: str = "",
        webhook_secret: str = "",
        default_network: str = "algorand_mainnet",
        base_currency: str = "USD",
        timeout: int = 30,
    ):
        if not GHOST_ADMIN_KEY_RE.match(ghost_admin_key or ""):
            raise ValueError(
                "ghost_admin_key must be in <id>:<secret> form (see "
                "Ghost → Settings → Integrations → Custom Integrations)"
            )
        self.ghost_url       = ghost_url.rstrip("/")
        self.ghost_admin_key = ghost_admin_key
        self.api_base        = api_base.rstrip("/")
        self.api_key         = api_key
        self.tenant_id       = tenant_id
        self.webhook_secret  = webhook_secret
        self.default_network = default_network
        self.base_currency   = base_currency
        self.timeout         = timeout
        self._ssl            = ssl.create_default_context()

    # ── Webhook verification ─────────────────────────────────────────────

    def verify_webhook(self, raw_body: bytes, signature: str) -> Optional[dict]:
        """
        Verify an AlgoVoi platform webhook (base64 HMAC-SHA256 in
        `X-AlgoVoi-Signature`).

        Returns the parsed payload dict on success, or None on any failure.
        Same defensive pattern as the amazon-mws / tiktok-shop / squarespace
        adapters.

        SECURITY NOTE — replay protection: this method does NOT dedupe
        replays. Callers MUST track processed tx_id values in their
        persistence layer.
        """
        if not self.webhook_secret:
            return None
        if not isinstance(signature, str) or not signature:
            return None
        if not isinstance(raw_body, (bytes, bytearray)):
            return None
        if len(raw_body) > MAX_WEBHOOK_BODY_BYTES:
            return None

        expected = base64.b64encode(
            hmac.new(
                self.webhook_secret.encode(),
                bytes(raw_body),
                hashlib.sha256,
            ).digest()
        ).decode()
        if not hmac.compare_digest(expected, signature):
            return None

        try:
            data = json.loads(raw_body)
        except json.JSONDecodeError:
            return None
        return data if isinstance(data, dict) else None

    # ── Payment link creation ─────────────────────────────────────────────

    def process_payment(
        self,
        reader_email: str,
        amount: float,
        label: Optional[str] = None,
        currency: Optional[str] = None,
        network: Optional[str] = None,
        redirect_url: str = "",
    ) -> Optional[dict]:
        """
        Create an AlgoVoi payment link for a Ghost reader.

        The `reader_email` is embedded in the payment `label` so the
        inbound webhook can map the on-chain TX back to the right Ghost
        member. Callers should also store the returned `token` against
        the reader's record so `verify_payment()` can cross-check.

        Args:
            reader_email: Email of the Ghost reader we'll grant access to
            amount:       Payment amount (in `currency` units, not microunits)
            label:        Free-text label; defaults to "Ghost: <email>"
            currency:     ISO currency code (defaults to self.base_currency)
            network:      Chain (defaults to self.default_network)
            redirect_url: Where the reader lands after paying (optional).
                          Must be https — file:// / javascript: are rejected.

        Returns:
            {"checkout_url", "token", "chain", "amount_microunits"}
            or None on failure.
        """
        if not self._is_valid_email(reader_email):
            return None
        if not isinstance(amount, (int, float)) or not math.isfinite(amount) or amount <= 0:
            return None
        if not self.api_base.startswith("https://"):
            return None

        network  = network  if (network  and network  in HOSTED_NETWORKS)    else self.default_network
        currency = (currency or self.base_currency).upper()
        label    = (label or f"Ghost: {reader_email}")[:MAX_LABEL_LEN]

        payload: dict[str, Any] = {
            "amount":            round(float(amount), 2),
            "currency":          currency,
            "label":             label,
            "preferred_network": network,
        }
        if redirect_url:
            parsed = urlparse(redirect_url)
            if parsed.scheme != "https" or not parsed.hostname:
                return None
            payload["redirect_url"]       = redirect_url
            payload["expires_in_seconds"] = 3600

        resp = self._post("/v1/payment-links", payload)
        if not resp or not resp.get("checkout_url"):
            return None

        token = ""
        m = re.search(r"/checkout/([A-Za-z0-9_-]+)$", resp["checkout_url"])
        if m:
            token = m.group(1)

        return {
            "checkout_url":      resp["checkout_url"],
            "token":             token,
            "chain":             resp.get("chain", "algorand-mainnet"),
            "amount_microunits": int(resp.get("amount_microunits", 0)),
            "reader_email":      reader_email,
        }

    def verify_payment(self, token: str) -> bool:
        """
        Check if a payment has been completed. Call before granting Ghost
        access — cancel-bypass guard.

        Args:
            token: AlgoVoi checkout token

        Returns:
            True only if the gateway confirms payment is complete.
        """
        if not token or len(token) > MAX_TX_ID_LEN:
            return False
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

    # ── Ghost Admin API ───────────────────────────────────────────────────

    def upgrade_member(
        self,
        reader_email: str,
        tx_id: str,
        tier_id: Optional[str] = None,
        label: str = "AlgoVoi-paid",
    ) -> bool:
        """
        Grant / upgrade a Ghost member record after on-chain payment.

        If the email already exists, updates the member (adds label and
        optionally comps the specified tier). If it doesn't, creates a
        new member with the same properties.

        Args:
            reader_email: Email of the reader to upgrade
            tx_id:        On-chain transaction ID (used in Ghost note for audit)
            tier_id:      Optional Ghost tier ID to comp the reader onto
            label:        Ghost label to attach (default "AlgoVoi-paid")

        Returns:
            True on success, False on any failure (logs internally).
        """
        if not self._is_valid_email(reader_email):
            return False
        if not tx_id or not isinstance(tx_id, str) or len(tx_id) > MAX_TX_ID_LEN:
            return False
        if not self.ghost_url.startswith("https://"):
            # Refuse to POST the admin JWT over plaintext HTTP.
            return False

        # Try to find an existing member by email.
        existing = self._ghost_request(
            "GET",
            f"/ghost/api/admin/members/?filter={quote(f'email:{reader_email}', safe=':')}",
        )
        member_id = None
        if existing and isinstance(existing, dict):
            members = existing.get("members") or []
            if members and isinstance(members[0], dict):
                member_id = members[0].get("id")

        body: dict[str, Any] = {
            "members": [{
                "email":  reader_email,
                "name":   reader_email.split("@")[0][:191],
                "labels": [{"name": label[:MAX_LABEL_LEN]}],
                "note":   f"Paid via AlgoVoi. TX: {tx_id}",
            }]
        }
        if tier_id:
            body["members"][0]["tiers"] = [{"id": tier_id}]

        if member_id:
            ok = self._ghost_request(
                "PUT",
                f"/ghost/api/admin/members/{quote(member_id, safe='')}/",
                body,
            )
        else:
            ok = self._ghost_request("POST", "/ghost/api/admin/members/", body)

        return ok is not None

    # ── Flask helper ─────────────────────────────────────────────────────

    def flask_webhook_handler(self, tier_id: Optional[str] = None):
        """
        Returns a Flask view function for the webhook endpoint.

        Usage:
            app.add_url_rule(
                '/webhook/algovoi',
                view_func=adapter.flask_webhook_handler(tier_id='65abcdef...'),
                methods=['POST'],
            )
        """
        adapter = self
        pinned_tier = tier_id

        def handler():
            from flask import request, jsonify

            raw_body  = request.get_data()
            signature = request.headers.get("X-AlgoVoi-Signature", "")

            payload = adapter.verify_webhook(raw_body, signature)
            if not payload:
                return jsonify(error="Unauthorized"), 401

            tx_id        = str(payload.get("tx_id") or payload.get("transaction_id") or "")
            reader_email = str(payload.get("reader_email") or payload.get("email") or "")
            token        = str(payload.get("token") or "")

            if not tx_id or not reader_email:
                return jsonify(error="Missing tx_id or reader_email"), 400

            # Cross-check is MANDATORY — a webhook that omits `token` or
            # sends an empty one must not grant access. Even with a valid
            # HMAC, we require the gateway to confirm the payment before
            # upgrading the member.
            if not token:
                return jsonify(error="Missing token — cannot verify payment"), 400
            if not adapter.verify_payment(token):
                return jsonify(error="Payment not confirmed by gateway"), 402

            ok = adapter.upgrade_member(reader_email, tx_id, tier_id=pinned_tier)
            if not ok:
                return jsonify(error="Could not upgrade Ghost member"), 502

            return jsonify(
                received=True,
                reader_email=reader_email,
                tx_id=tx_id,
            )

        return handler

    # ── Internal ──────────────────────────────────────────────────────────

    @staticmethod
    def _is_valid_email(email: str) -> bool:
        if not email or not isinstance(email, str) or len(email) > MAX_EMAIL_LEN:
            return False
        # Loose RFC 5321 check — Ghost will do its own validation server-side.
        return bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email))

    def _ghost_jwt(self) -> Optional[str]:
        """
        Build a short-lived Ghost Admin API JWT (HS256).

        Uses PyJWT so we don't hand-roll crypto. `iat` / `exp` window is
        5 minutes, matching Ghost's recommended token lifetime.
        """
        try:
            import jwt  # type: ignore
        except ImportError:
            raise ImportError(
                "PyJWT is required for Ghost Admin API auth. "
                "pip install PyJWT"
            )

        try:
            key_id, secret_hex = self.ghost_admin_key.split(":", 1)
            secret_bytes       = binascii.unhexlify(secret_hex)
        except (ValueError, binascii.Error):
            return None

        now     = int(time.time())
        payload = {
            "iat": now,
            "exp": now + 5 * 60,
            "aud": "/admin/",
        }
        token = jwt.encode(
            payload,
            secret_bytes,
            algorithm="HS256",
            headers={"alg": "HS256", "typ": "JWT", "kid": key_id},
        )
        # PyJWT 1.x returns bytes; 2.x returns str. Normalise so the caller
        # doesn't end up with "Ghost b'eyJ...'" in the Authorization header
        # on the 1.x code path.
        if isinstance(token, (bytes, bytearray)):
            token = token.decode("ascii")
        return token

    def _ghost_request(
        self,
        method: str,
        path: str,
        body: Optional[dict] = None,
    ) -> Optional[dict]:
        if not self.ghost_url.startswith("https://"):
            return None

        token = self._ghost_jwt()
        if token is None:
            return None

        url     = f"{self.ghost_url}{path}"
        data    = json.dumps(body).encode() if body is not None else None
        headers = {
            "Authorization": f"Ghost {token}",
            "Content-Type":  "application/json",
            "Accept":        "application/json",
        }
        req = Request(url, data=data, method=method, headers=headers)
        try:
            with urlopen(req, timeout=self.timeout, context=self._ssl) as resp:  # nosec B310
                status = resp.status
                raw    = resp.read()
                if status < 200 or status >= 300:
                    return None
                try:
                    return json.loads(raw) if raw else {}
                except json.JSONDecodeError:
                    return {}
        except (URLError, OSError):
            return None

    def _post(self, path: str, data: dict) -> Optional[dict]:
        if not self.api_base.startswith("https://"):
            return None
        body = json.dumps(data).encode()
        req  = Request(
            f"{self.api_base}{path}",
            data=body,
            method="POST",
            headers={
                "Content-Type":  "application/json",
                "Authorization": f"Bearer {self.api_key}",
                "X-Tenant-Id":   self.tenant_id,
            },
        )
        try:
            with urlopen(req, timeout=self.timeout, context=self._ssl) as resp:  # nosec B310
                if resp.status < 200 or resp.status >= 300:
                    return None
                return json.loads(resp.read())
        except (URLError, json.JSONDecodeError, OSError):
            return None
