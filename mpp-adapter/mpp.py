"""
AlgoVoi MPP (Machine Payments Protocol) Server Adapter

Drop-in middleware for gating APIs behind MPP payment challenges.
Implements the HTTP Payment Authentication scheme per the IETF draft
(draft-ryan-httpauth-payment) with the "charge" intent.

When a request lacks valid payment credentials, responds with:
  WWW-Authenticate: Payment realm="..." id="..." method="..." intent="charge"
                    request="<b64>" expires="<RFC3339>"
  X-Payment-Required: <base64 JSON with accepts array>

When credentials are present, verifies the on-chain transaction directly
via the Algorand or VOI indexer (no central verification API — per MPP spec).

Works with Flask, Django, FastAPI, or any WSGI/ASGI framework.
Zero pip dependencies — uses only the Python standard library.

Spec: https://paymentauth.org / draft-ryan-httpauth-payment (IETF)
AlgoVoi docs: https://github.com/chopmob-cloud/AlgoVoi-Platform-Adapters
Licensed under the Business Source License 1.1 — see LICENSE for details.

Usage:
    from mpp import MppGate

    gate = MppGate(
        api_base='https://api1.ilovechicken.co.uk',
        api_key='algv_...',
        tenant_id='uuid',
        resource_id='my-api',
        payout_address='<algorand-address>',
    )

    # Flask
    @app.before_request
    def check_payment():
        return gate.flask_guard()

    # Or manual check
    result = gate.check(request_headers)
    if result.requires_payment:
        status, headers, body = result.as_wsgi_response()

Version: 2.3.0
"""

from __future__ import annotations

import hashlib
import hmac as _hmac
import json
import os
import ssl
import time
from base64 import b64decode, b64encode
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Optional
from urllib.request import Request, urlopen
from urllib.error import URLError

__version__ = "2.3.0"

# Payment intent identifier per charge intent spec
INTENT = "charge"

# CAIP-2 network ID → internal network key used for indexer routing
_CAIP2_TO_INTERNAL: dict[str, str] = {
    "algorand:mainnet": "algorand-mainnet",
    "voi:mainnet":      "voi-mainnet",
    "hedera:mainnet":   "hedera-mainnet",
    "stellar:pubnet":   "stellar-mainnet",
    "eip155:8453":      "base-mainnet",
    "solana:5eykt4UsFv8P8NJdTREpY1vzqKqZKvdp": "solana-mainnet",
    "tempo:mainnet":    "tempo-mainnet",
}


def _safe_b64decode(s: str) -> bytes:
    """Decode standard or URL-safe base64 with or without padding."""
    s = s.replace("-", "+").replace("_", "/")
    rem = len(s) % 4
    if rem:
        s += "=" * (4 - rem)
    return b64decode(s)


class MppChallenge:
    """A spec-compliant MPP payment challenge."""

    def __init__(
        self,
        realm: str,
        accepts: list[dict],
        resource_id: str,
        challenge_id: str,
        method: str,
        request_b64: str,
        expires: str,
    ):
        self.realm = realm
        self.accepts = accepts
        self.resource_id = resource_id
        self.challenge_id = challenge_id
        self.method = method
        self.request_b64 = request_b64
        self.expires = expires

    def www_authenticate_header(self) -> str:
        """Build the spec-compliant WWW-Authenticate: Payment header value."""
        return (
            f'Payment realm="{self.realm}", '
            f'id="{self.challenge_id}", '
            f'method="{self.method}", '
            f'intent="{INTENT}", '
            f'request="{self.request_b64}", '
            f'expires="{self.expires}"'
        )

    def as_402_headers(self) -> dict[str, str]:
        """Return all headers for a 402 response."""
        return {
            "WWW-Authenticate": self.www_authenticate_header(),
            "X-Payment-Required": b64encode(json.dumps({
                "accepts": self.accepts,
                "resource": self.resource_id,
            }).encode()).decode(),
        }


class MppReceipt:
    """A verified payment receipt with spec-compliant fields."""

    def __init__(
        self,
        tx_id: str,
        payer: str,
        network: str,
        amount: int,
        method: str = "algorand",
    ):
        self.tx_id = tx_id
        self.payer = payer
        self.network = network
        self.amount = amount
        self.method = method
        self.status = "success"
        self.timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        self.reference = tx_id

    def as_header_value(self) -> str:
        """Encode as base64 JSON for the Payment-Receipt header."""
        return b64encode(json.dumps({
            "status": self.status,
            "method": self.method,
            "timestamp": self.timestamp,
            "reference": self.reference,
            "payer": self.payer,
            "amount": self.amount,
            "network": self.network,
        }).encode()).decode()


class MppResult:
    """Result of checking a request for MPP credentials."""

    def __init__(
        self,
        requires_payment: bool,
        challenge: Optional[MppChallenge] = None,
        receipt: Optional[MppReceipt] = None,
        error: Optional[str] = None,
    ):
        self.requires_payment = requires_payment
        self.challenge = challenge
        self.receipt = receipt
        self.error = error

    def as_wsgi_response(self) -> tuple[str, list[tuple[str, str]], bytes]:
        """Return (status, headers, body) for WSGI when payment is required."""
        assert self.requires_payment and self.challenge
        resp_headers = [("Content-Type", "application/json")]
        for k, v in self.challenge.as_402_headers().items():
            resp_headers.append((k, v))
        body = json.dumps({
            "error": "Payment Required",
            "detail": self.error or "This endpoint requires payment via MPP.",
        }).encode()
        return "402 Payment Required", resp_headers, body


class MppGate:
    """MPP payment gate — checks requests for valid payment credentials."""

    NETWORKS = {
        # ── Stablecoin / ASA / HTS / trust-line ─────────────────────────────
        "algorand_mainnet": {
            "asset_id": 31566704,
            "ticker": "USDC",
            "network": "algorand-mainnet",
            "native": False,
            "decimals": 6,
        },
        "voi_mainnet": {
            "asset_id": 302190,
            "ticker": "aUSDC",
            "network": "voi-mainnet",
            "native": False,
            "decimals": 6,
        },
        "hedera_mainnet": {
            "asset_id": "0.0.456858",
            "ticker": "USDC",
            "network": "hedera-mainnet",
            "native": False,
            "decimals": 6,
        },
        "stellar_mainnet": {
            "asset_id": "USDC:GA5ZSEJYB37JRC5AVCIA5MOP4RHTM335X2KGX3IHOJAPP5RE34K4KZVN",
            "ticker": "USDC",
            "network": "stellar-mainnet",
            "native": False,
            "decimals": 7,
        },
        # ── Native tokens ────────────────────────────────────────────────────
        "algorand_mainnet_algo": {
            "asset_id": None,
            "ticker": "ALGO",
            "network": "algorand-mainnet",
            "native": True,
            "decimals": 6,
        },
        "voi_mainnet_voi": {
            "asset_id": None,
            "ticker": "VOI",
            "network": "voi-mainnet",
            "native": True,
            "decimals": 6,
        },
        "hedera_mainnet_hbar": {
            "asset_id": None,
            "ticker": "HBAR",
            "network": "hedera-mainnet",
            "native": True,
            "decimals": 8,
        },
        "stellar_mainnet_xlm": {
            "asset_id": None,
            "ticker": "XLM",
            "network": "stellar-mainnet",
            "native": True,
            "decimals": 7,
        },
        # ── EVM / Solana chains ──────────────────────────────────────────────
        "base_mainnet": {
            "asset_id": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
            "ticker": "USDC",
            "network": "base-mainnet",
            "native": False,
            "decimals": 6,
        },
        "solana_mainnet": {
            "asset_id": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
            "ticker": "USDC",
            "network": "solana-mainnet",
            "native": False,
            "decimals": 6,
        },
        "tempo_mainnet": {
            "asset_id": "0x20c000000000000000000000b9537d11c60e8b50",
            "ticker": "USDC",
            "network": "tempo-mainnet",
            "native": False,
            "decimals": 6,
        },
    }

    # EVM USDC contract addresses (Base and Tempo)
    _EVM_USDC: dict[str, str] = {
        "base-mainnet":  "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
        "base_mainnet":  "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
        "tempo-mainnet": "0x20c000000000000000000000b9537d11c60e8b50",
        "tempo_mainnet": "0x20c000000000000000000000b9537d11c60e8b50",
    }

    # Public API base URLs for direct on-chain verification
    INDEXERS = {
        "algorand-mainnet":      "https://mainnet-idx.algonode.cloud/v2",
        "algorand_mainnet":      "https://mainnet-idx.algonode.cloud/v2",
        "algorand_mainnet_algo": "https://mainnet-idx.algonode.cloud/v2",
        "voi-mainnet":           "https://mainnet-idx.voi.nodely.dev/v2",
        "voi_mainnet":           "https://mainnet-idx.voi.nodely.dev/v2",
        "voi_mainnet_voi":       "https://mainnet-idx.voi.nodely.dev/v2",
        "hedera-mainnet":        "https://mainnet-public.mirrornode.hedera.com/api/v1",
        "hedera_mainnet":        "https://mainnet-public.mirrornode.hedera.com/api/v1",
        "hedera_mainnet_hbar":   "https://mainnet-public.mirrornode.hedera.com/api/v1",
        "stellar-mainnet":       "https://horizon.stellar.org",
        "stellar_mainnet":       "https://horizon.stellar.org",
        "stellar_mainnet_xlm":   "https://horizon.stellar.org",
        "base-mainnet":          "https://mainnet.base.org",
        "base_mainnet":          "https://mainnet.base.org",
        "solana-mainnet":        "https://api.mainnet-beta.solana.com",
        "solana_mainnet":        "https://api.mainnet-beta.solana.com",
        "tempo-mainnet":         os.environ.get("ALGOVOI_TEMPO_RPC", "https://tempo-mainnet.g.alchemy.com/v2/YOUR_ALCHEMY_KEY"),
        "tempo_mainnet":         os.environ.get("ALGOVOI_TEMPO_RPC", "https://tempo-mainnet.g.alchemy.com/v2/YOUR_ALCHEMY_KEY"),
    }

    def __init__(
        self,
        api_base: str,
        api_key: str,
        tenant_id: str,
        resource_id: str,
        amount_microunits: int = 1000000,
        networks: Optional[list[str]] = None,
        realm: str = "API Access",
        payout_address: str = "",
        method: str = "algorand",
        challenge_ttl: int = 300,
    ):
        """
        Args:
            api_base:          AlgoVoi API base URL
            api_key:           AlgoVoi API key (also used as HMAC key for challenge IDs)
            tenant_id:         AlgoVoi tenant UUID
            resource_id:       Resource identifier string
            amount_microunits: Required payment in USDC microunits (1 USDC = 1,000,000)
            networks:          List of network keys to accept (default: ["algorand_mainnet"])
            realm:             Human-readable protection space name
            payout_address:    On-chain address that receives payment
            method:            Payment method identifier (default: "algorand")
            challenge_ttl:     Challenge expiry in seconds (default: 300)
        """
        self.api_base = api_base.rstrip("/")
        self.api_key = api_key
        self.tenant_id = tenant_id
        self.resource_id = resource_id
        self.amount_microunits = amount_microunits
        self.networks = networks or ["algorand_mainnet"]
        self.realm = realm
        self.payout_address = payout_address
        self.method = method
        self.challenge_ttl = challenge_ttl
        self._ssl_ctx = ssl.create_default_context()
        # In-memory replay protection — single-use proof enforcement per spec.
        # For multi-process deployments, back this with a shared store (Redis, DB).
        self._used_tx_ids: set[str] = set()
        # Issued challenge IDs → expiry timestamp (UTC epoch float).
        # Validates challenge echo in Authorization: Payment credentials.
        self._issued_challenges: dict[str, float] = {}

    # ── Core check ───────────────────────────────────────────────────────

    def check(self, headers: dict[str, str]) -> MppResult:
        """
        Check a request for valid MPP payment credentials.

        Args:
            headers: Request headers dict (case-insensitive)

        Returns:
            MppResult — check .requires_payment to decide whether to gate
        """
        h = {k.lower(): v for k, v in headers.items()}

        # Accept both Authorization: Payment <b64> and X-Payment: <b64>
        auth = h.get("authorization", "")
        payment_proof = h.get("x-payment", "")

        credential = None
        if auth.lower().startswith("payment "):
            credential = auth[8:].strip()
        elif payment_proof:
            credential = payment_proof.strip()

        if not credential:
            return MppResult(requires_payment=True, challenge=self._build_challenge())

        try:
            decoded = json.loads(_safe_b64decode(credential))
        except Exception:
            return MppResult(
                requires_payment=True,
                challenge=self._build_challenge(),
                error="Invalid credential encoding",
            )

        # Validate challenge echo (IETF spec Table 3 — required field)
        challenge_obj = decoded.get("challenge") or {}
        if challenge_obj:
            c_id = challenge_obj.get("id", "")
            if not self._validate_challenge_id(c_id):
                return MppResult(
                    requires_payment=True,
                    challenge=self._build_challenge(),
                    error="Invalid or expired challenge",
                )

        payload = decoded.get("payload") or {}
        tx_id = (
            payload.get("txId")
            or payload.get("tx_id")
            or decoded.get("tx_id")
            or ""
        )

        # Network: prefer challenge.method (CAIP-2) → top-level network → default
        raw_network = (
            challenge_obj.get("method")
            or decoded.get("network")
            or "algorand-mainnet"
        )
        network = _CAIP2_TO_INTERNAL.get(raw_network, raw_network)

        if not tx_id or len(tx_id) > 200:
            return MppResult(
                requires_payment=True,
                challenge=self._build_challenge(),
                error="Missing or invalid txId",
            )

        # Single-use proof enforcement (replay protection)
        if tx_id in self._used_tx_ids:
            return MppResult(
                requires_payment=True,
                challenge=self._build_challenge(),
                error="Payment proof already used",
            )

        receipt = self._verify_payment(tx_id, network)
        if not receipt:
            return MppResult(
                requires_payment=True,
                challenge=self._build_challenge(),
                error="Payment verification failed",
            )

        self._used_tx_ids.add(tx_id)
        return MppResult(requires_payment=False, receipt=receipt)

    # ── Challenge construction ───────────────────────────────────────────

    def _make_challenge_id(self, request_b64: str, expires: str) -> str:
        """
        Compute HMAC-SHA256 challenge ID bound to parameters.
        Per spec: id MUST be bound to (realm, method, intent, request, expires).
        """
        msg = f"{self.realm}|{self.method}|{INTENT}|{request_b64}|{expires}"
        key = (self.api_key or "mpp").encode()
        return _hmac.new(key, msg.encode(), hashlib.sha256).hexdigest()[:32]

    def _validate_challenge_id(self, challenge_id: str) -> bool:
        """
        Validate that a challenge ID was issued by this gate and has not expired.
        Uses constant-time comparison to prevent timing attacks.
        """
        if not challenge_id:
            return False
        expiry = self._issued_challenges.get(challenge_id)
        if expiry is None:
            return False
        return time.time() < expiry

    def _build_challenge(self) -> MppChallenge:
        """Build a spec-compliant MPP challenge with all configured networks."""
        accepts = []
        for net_key in self.networks:
            cfg = self.NETWORKS.get(net_key)
            if not cfg:
                continue
            entry: dict = {
                "network": cfg["network"],
                "amount": str(self.amount_microunits),
                "payTo": self.payout_address,
                "resource": self.resource_id,
                "ticker": cfg["ticker"],
            }
            if cfg.get("asset_id") is not None:
                entry["asset"] = str(cfg["asset_id"])
            else:
                # Native token — signal with "native" asset key
                entry["asset"] = "native"
            accepts.append(entry)

        expires_dt = datetime.now(timezone.utc) + timedelta(seconds=self.challenge_ttl)
        expires_str = expires_dt.strftime("%Y-%m-%dT%H:%M:%SZ")

        # Charge intent request object
        request_obj = {
            "amount": str(self.amount_microunits),
            "currency": accepts[0]["ticker"].lower() if accepts else "usdc",
            "recipient": self.payout_address,
            "methodDetails": {
                "accepts": accepts,
                "resource": self.resource_id,
            },
        }
        request_b64 = b64encode(
            json.dumps(request_obj, separators=(",", ":")).encode()
        ).decode()
        challenge_id = self._make_challenge_id(request_b64, expires_str)

        # Store issued challenge for echo validation
        self._issued_challenges[challenge_id] = (
            datetime.now(timezone.utc) + timedelta(seconds=self.challenge_ttl)
        ).timestamp()
        # Prune expired entries to avoid unbounded growth
        now = time.time()
        self._issued_challenges = {
            k: v for k, v in self._issued_challenges.items() if v > now
        }

        return MppChallenge(
            realm=self.realm,
            accepts=accepts,
            resource_id=self.resource_id,
            challenge_id=challenge_id,
            method=self.method,
            request_b64=request_b64,
            expires=expires_str,
        )

    # ── On-chain verification ────────────────────────────────────────────

    def _verify_payment(self, tx_id: str, network: str) -> Optional[MppReceipt]:
        """Route to the correct chain verifier based on network."""
        norm = network.replace("-", "_")
        if "algorand" in norm or "voi" in norm:
            return self._verify_avm(tx_id, network)
        if "hedera" in norm:
            return self._verify_hedera(tx_id, network)
        if "stellar" in norm:
            return self._verify_stellar(tx_id, network)
        if "base" in norm or "tempo" in norm:
            ok = self._verify_evm(tx_id, network)
            if not ok:
                return None
            return MppReceipt(tx_id=tx_id, payer="", network=network, amount=self.amount_microunits, method=self.method)
        if "solana" in norm:
            ok = self._verify_solana(tx_id, network)
            if not ok:
                return None
            return MppReceipt(tx_id=tx_id, payer="", network=network, amount=self.amount_microunits, method=self.method)
        return None

    def _verify_avm(self, tx_id: str, network: str) -> Optional[MppReceipt]:
        """
        Verify an Algorand or VOI payment via the chain indexer.

        Handles two TX types:
          • asset-transfer-transaction — USDC / aUSDC (ASA / ARC-200)
          • payment-transaction        — native ALGO / VOI

        Checks: receiver == payout_address, amount >= amount_microunits,
        asset-id matches expected token (USDC path), confirmed-round present.
        """
        indexer = self.INDEXERS.get(network)
        if not indexer:
            return None

        url = f"{indexer}/transactions/{tx_id}"
        try:
            req = Request(url, headers={"Accept": "application/json"})
            with urlopen(req, timeout=15, context=self._ssl_ctx) as resp:  # nosec B310
                if resp.status != 200:
                    return None
                data = json.loads(resp.read())
        except (URLError, json.JSONDecodeError, OSError):
            return None

        tx = data.get("transaction", {})
        if not tx.get("confirmed-round"):
            return None

        net_cfg = self.NETWORKS.get(network.replace("-", "_"))
        is_native = net_cfg.get("native", False) if net_cfg else False

        if is_native:
            # Native ALGO / VOI — payment-transaction type
            ptx = tx.get("payment-transaction", {})
            if ptx.get("receiver") != self.payout_address:
                return None
            amount = ptx.get("amount", 0)
            if amount < self.amount_microunits:
                return None
            return MppReceipt(
                tx_id=tx_id,
                payer=tx.get("sender", ""),
                network=network,
                amount=amount,
                method=self.method,
            )

        # Stablecoin — asset-transfer-transaction type (USDC / aUSDC)
        atx = tx.get("asset-transfer-transaction", {})
        if atx.get("receiver") != self.payout_address:
            return None
        if atx.get("amount", 0) < self.amount_microunits:
            return None
        if net_cfg and atx.get("asset-id") != net_cfg["asset_id"]:
            return None

        return MppReceipt(
            tx_id=tx_id,
            payer=tx.get("sender", ""),
            network=network,
            amount=atx.get("amount", 0),
            method=self.method,
        )

    def _verify_hedera(self, tx_id: str, network: str) -> Optional[MppReceipt]:
        """
        Verify a Hedera payment via the Hedera Mirror Node.

        Handles two modes:
          • HTS token_transfers — USDC (token_id 0.0.456858)
          • HBAR transfers      — native HBAR (tinybars, 8 decimals)

        Checks: result == SUCCESS, positive credit to payout_address
        with amount >= amount_microunits.
        """
        base = self.INDEXERS.get(network)
        if not base:
            return None

        # Normalise Hedera TX ID formats:
        #   wallet:      0.0.account@seconds.nanos
        #   mirror node: 0.0.account-seconds-nanos
        if "@" in tx_id:
            account_part, time_part = tx_id.split("@", 1)
            normalised = f"{account_part}-{time_part.replace('.', '-', 1)}"
        else:
            normalised = tx_id
        url = f"{base}/transactions/{normalised}"
        try:
            req = Request(url, headers={"Accept": "application/json"})
            with urlopen(req, timeout=15, context=self._ssl_ctx) as resp:  # nosec B310
                if resp.status != 200:
                    return None
                data = json.loads(resp.read())
        except (URLError, json.JSONDecodeError, OSError):
            return None

        transactions = data.get("transactions", [])
        if not transactions:
            return None
        tx = transactions[0]
        if tx.get("result") != "SUCCESS":
            return None

        net_cfg = self.NETWORKS.get(network.replace("-", "_"))
        is_native = net_cfg.get("native", False) if net_cfg else False

        if is_native:
            # HBAR native — check the `transfers` array (tinybars, signed amounts)
            payer = ""
            for transfer in tx.get("transfers", []):
                amt = transfer.get("amount", 0)
                if amt < 0:
                    payer = transfer.get("account", "")
                if (transfer.get("account") == self.payout_address
                        and amt >= self.amount_microunits):
                    return MppReceipt(
                        tx_id=tx_id,
                        payer=payer,
                        network=network,
                        amount=amt,
                        method=self.method,
                    )
            return None

        # HTS token — check token_transfers for USDC
        expected_token = net_cfg["asset_id"] if net_cfg else "0.0.456858"
        payer = ""
        for transfer in tx.get("token_transfers", []):
            if transfer.get("token_id") != expected_token:
                continue
            amt = transfer.get("amount", 0)
            if amt < 0:
                payer = transfer.get("account", "")
            if (transfer.get("account") == self.payout_address
                    and amt >= self.amount_microunits):
                return MppReceipt(
                    tx_id=tx_id,
                    payer=payer,
                    network=network,
                    amount=amt,
                    method=self.method,
                )
        return None

    def _verify_stellar(self, tx_id: str, network: str) -> Optional[MppReceipt]:
        """
        Verify a Stellar payment via Horizon.

        Handles two modes:
          • USDC — payment op with asset_code==USDC + matching issuer
          • XLM  — payment op with asset_type=="native"

        Stellar amounts are decimal strings (e.g. "0.0100000").
        USDC has 7 decimal places on Stellar (stroops); XLM also 7.
        We convert to integer microunits using 10^7 = 10_000_000.
        """
        base = self.INDEXERS.get(network)
        if not base:
            return None

        url = f"{base}/transactions/{tx_id}/operations"
        try:
            req = Request(url, headers={"Accept": "application/json"})
            with urlopen(req, timeout=15, context=self._ssl_ctx) as resp:  # nosec B310
                if resp.status != 200:
                    return None
                data = json.loads(resp.read())
        except (URLError, json.JSONDecodeError, OSError):
            return None

        net_cfg = self.NETWORKS.get(network.replace("-", "_"))
        if not net_cfg:
            return None

        is_native = net_cfg.get("native", False)
        decimals = net_cfg.get("decimals", 7)
        scale = 10 ** decimals  # 10_000_000 for 7-decimal Stellar assets

        if not is_native:
            # USDC trust-line — asset_id is "CODE:ISSUER"
            parts = (net_cfg["asset_id"] or "").split(":", 1)
            expected_code = parts[0]
            expected_issuer = parts[1] if len(parts) > 1 else ""

        for op in data.get("_embedded", {}).get("records", []):
            if op.get("type") != "payment":
                continue
            if op.get("to") != self.payout_address:
                continue

            if is_native:
                # XLM — asset_type must be "native"
                if op.get("asset_type") != "native":
                    continue
            else:
                # USDC — check code + issuer
                if op.get("asset_code") != expected_code:
                    continue
                if op.get("asset_issuer") != expected_issuer:
                    continue

            try:
                amount_units = int(float(op.get("amount", "0")) * scale)
            except (ValueError, TypeError):
                continue
            if amount_units >= self.amount_microunits:
                return MppReceipt(
                    tx_id=tx_id,
                    payer=op.get("from", ""),
                    network=network,
                    amount=amount_units,
                    method=self.method,
                )
        return None

    def _verify_evm(self, tx_id: str, network: str) -> bool:
        """Verify Base or Tempo ERC-20/TIP-20 USDC transfer via JSON-RPC."""
        import json as _json
        rpc = self.INDEXERS.get(network)
        if not rpc:
            return False
        TRANSFER_TOPIC = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
        usdc_contract = self._EVM_USDC.get(network, "").lower()
        try:
            payload = json.dumps({
                "jsonrpc": "2.0", "id": 1,
                "method": "eth_getTransactionReceipt",
                "params": [tx_id if tx_id.startswith("0x") else "0x" + tx_id],
            }).encode()
            req = Request(rpc, data=payload, headers={"Content-Type": "application/json"})
            with urlopen(req, timeout=15, context=self._ssl_ctx) as resp:  # nosec B310
                data = json.loads(resp.read())
        except Exception:
            return False
        result = data.get("result") or {}
        if not result or result.get("status") != "0x1":
            return False
        for log in result.get("logs", []):
            topics = log.get("topics", [])
            if (
                log.get("address", "").lower() == usdc_contract
                and len(topics) >= 3
                and topics[0].lower() == TRANSFER_TOPIC
            ):
                to_addr = "0x" + topics[2][-40:]
                payout = self.payout_address.lower().lstrip("0x")
                if to_addr.lower() == "0x" + payout:
                    raw = int(log.get("data", "0x0"), 16)
                    if raw >= self.amount_microunits:
                        return True
        return False

    def _verify_solana(self, tx_id: str, network: str) -> bool:
        """Verify Solana SPL-USDC transfer via JSON-RPC getTransaction."""
        rpc = self.INDEXERS.get(network)
        if not rpc:
            return False
        USDC_MINT = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
        try:
            payload = json.dumps({
                "jsonrpc": "2.0", "id": 1,
                "method": "getTransaction",
                "params": [tx_id, {"encoding": "json", "commitment": "finalized", "maxSupportedTransactionVersion": 0}],
            }).encode()
            req = Request(rpc, data=payload, headers={"Content-Type": "application/json"})
            with urlopen(req, timeout=20, context=self._ssl_ctx) as resp:  # nosec B310
                data = json.loads(resp.read())
        except Exception:
            return False
        result = data.get("result") or {}
        if not result:
            return False
        meta = result.get("meta") or {}
        if meta.get("err") is not None:
            return False
        pre  = {b["accountIndex"]: b for b in (meta.get("preTokenBalances")  or [])}
        post = {b["accountIndex"]: b for b in (meta.get("postTokenBalances") or [])}
        for idx, pb in post.items():
            if pb.get("mint") != USDC_MINT:
                continue
            owner = pb.get("owner", "")
            if owner != self.payout_address:
                continue
            pre_amt  = int((pre.get(idx)  or {}).get("uiTokenAmount", {}).get("amount", "0"))
            post_amt = int(pb.get("uiTokenAmount", {}).get("amount", "0"))
            delta = post_amt - pre_amt
            if delta >= self.amount_microunits:
                return True
        return False

    # ── Framework helpers ────────────────────────────────────────────────

    def flask_guard(self) -> Optional[Any]:
        """
        Flask before_request guard. Returns None (allow) or a 402 response.

        Usage:
            @app.before_request
            def check_payment():
                return gate.flask_guard()
        """
        from flask import request, jsonify, make_response  # type: ignore

        result = self.check(dict(request.headers))
        if not result.requires_payment:
            return None

        resp = make_response(jsonify({
            "error": "Payment Required",
            "detail": result.error or "This endpoint requires payment via MPP.",
            "resource": self.resource_id,
        }), 402)
        for k, v in result.challenge.as_402_headers().items():
            resp.headers[k] = v
        return resp

    def django_middleware(self, get_response: Callable) -> Callable:
        """
        Django middleware factory.

        Usage in settings.py:
            MIDDLEWARE = ['yourapp.middleware.mpp_middleware', ...]

        In yourapp/middleware.py:
            gate = MppGate(...)
            mpp_middleware = gate.django_middleware
        """
        from django.http import JsonResponse  # type: ignore

        def middleware(request: Any) -> Any:
            headers = {
                k.replace("HTTP_", "").replace("_", "-").title(): v
                for k, v in request.META.items()
                if k.startswith("HTTP_")
            }
            result = self.check(headers)
            if result.requires_payment:
                resp = JsonResponse({
                    "error": "Payment Required",
                    "detail": result.error or "This endpoint requires payment via MPP.",
                }, status=402)
                for k, v in result.challenge.as_402_headers().items():
                    resp[k] = v
                return resp
            return get_response(request)

        return middleware

    def wsgi_guard(self, environ: dict) -> Optional[tuple[str, list[tuple[str, str]], bytes]]:
        """
        WSGI guard. Returns None (allow) or (status, headers, body) tuple.

        Usage:
            result = gate.wsgi_guard(environ)
            if result:
                status, headers, body = result
                start_response(status, headers)
                return [body]
        """
        headers = {
            key[5:].replace("_", "-").title(): value
            for key, value in environ.items()
            if key.startswith("HTTP_")
        }
        result = self.check(headers)
        if not result.requires_payment:
            return None

        _, resp_headers, body = result.as_wsgi_response()
        return "402 Payment Required", resp_headers, body
