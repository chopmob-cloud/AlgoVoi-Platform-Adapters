"""
AlgoVoi Wormhole Cross-Chain Bridge Adapter

Listens for Wormhole guardian attestation events (VAAs) and polls
Wormhole bridge status to detect completed USDC transfers from
Ethereum, Solana, Base, Polygon, Avalanche, or Arbitrum to Algorand
or VOI.

On confirmed bridge completion: creates an AlgoVoi settlement link
to record the on-chain receipt and notify the merchant.

No CEX. No manual swap. USDC arrives natively on Algorand from any
Wormhole-supported source chain.

Works with Flask, Django, FastAPI, or any WSGI framework.
Zero pip dependencies — uses only the Python standard library.

Wormhole docs:  https://docs.wormhole.com/
WormholeScan:   https://wormholescan.io/
Portal Bridge:  https://portalbridge.com/

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

# Wormhole-supported source chains for USDC bridging to Algorand
SUPPORTED_SOURCE_CHAINS = [
    "ethereum",
    "solana",
    "base",
    "polygon",
    "avalanche",
    "arbitrum",
]

# VAA status values returned by WormholeScan
VAA_COMPLETED_STATUSES = {"completed", "confirmed", "redeemed"}


class WormholeAlgoVoi:
    """Wormhole cross-chain bridge + AlgoVoi settlement adapter."""

    def __init__(
        self,
        api_base: str = "https://api1.ilovechicken.co.uk",
        api_key: str = "",
        tenant_id: str = "",
        wormhole_rpc_url: str = "https://api.wormholescan.io",
        webhook_secret: str = "",
        default_network: str = "algorand_mainnet",
        base_currency: str = "USD",
        timeout: int = 30,
    ):
        self.api_base = api_base.rstrip("/")
        self.api_key = api_key
        self.tenant_id = tenant_id
        self.wormhole_rpc_url = wormhole_rpc_url.rstrip("/")
        self.webhook_secret = webhook_secret
        self.default_network = default_network
        self.base_currency = base_currency
        self.timeout = timeout
        self._ssl = ssl.create_default_context()

    # ── Webhook Verification ─────────────────────────────────────────────

    def verify_webhook(self, raw_body: bytes, signature: str) -> Optional[dict]:
        """
        Verify an internal AlgoVoi webhook callback using HMAC-SHA256.

        This covers the internal bridge-event notification path. Wormhole
        itself is on-chain — this HMAC is for AlgoVoi's internal callback
        when it detects a completed VAA on-chain.

        Args:
            raw_body:  Raw POST body as bytes
            signature: HMAC-SHA256 hex signature from the X-AlgoVoi-Signature header

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

    # ── Bridge Event Parsing ─────────────────────────────────────────────

    def parse_bridge_event(self, payload: dict) -> Optional[dict]:
        """
        Parse a Wormhole bridge event / VAA attestation payload.

        Expected payload shape (AlgoVoi internal bridge callback or
        WormholeScan VAA data):

            {
              "vaa_id": "<chain>/<emitter>/<sequence>",
              "source_chain": "ethereum",
              "source_tx": "0xabc...",
              "amount": 100.0,
              "target_chain": "algorand",
              "status": "completed"
            }

        Args:
            payload: The parsed bridge event JSON

        Returns:
            dict with vaa_id, source_chain, source_tx, amount,
            target_chain, status — or None
        """
        try:
            # Support both flat and nested data structures
            data = payload.get("data", payload)

            vaa_id = data.get("vaa_id", data.get("id", data.get("vaaId", "")))
            if not vaa_id:
                return None

            source_chain = str(
                data.get("source_chain", data.get("sourceChain", ""))
            ).lower()
            source_tx = str(data.get("source_tx", data.get("sourceTx", data.get("txHash", ""))))
            amount = float(data.get("amount", data.get("tokenAmount", 0)))
            target_chain = str(
                data.get("target_chain", data.get("targetChain", "algorand"))
            ).lower()
            status = str(data.get("status", "pending")).lower()

            return {
                "vaa_id": str(vaa_id),
                "source_chain": source_chain,
                "source_tx": source_tx,
                "amount": amount,
                "target_chain": target_chain,
                "status": status,
            }
        except (KeyError, ValueError, TypeError):
            return None

    # ── VAA Status Check ─────────────────────────────────────────────────

    def check_vaa_status(self, vaa_id: str) -> Optional[dict]:
        """
        Check the status of a Wormhole VAA via WormholeScan API.

        Calls:
            GET {wormhole_rpc_url}/api/v1/vaas/{vaa_id}

        Args:
            vaa_id: Wormhole VAA identifier in the format
                    <chain_id>/<emitter_address>/<sequence>

        Returns:
            dict with status, vaa_id, and raw API response data — or None
        """
        if not vaa_id:
            return None

        safe_id = quote(vaa_id, safe="/")
        url = f"{self.wormhole_rpc_url}/api/v1/vaas/{safe_id}"

        try:
            req = Request(url, method="GET", headers={"Accept": "application/json"})
            with urlopen(req, timeout=self.timeout, context=self._ssl) as resp:  # nosec B310
                if resp.status != 200:
                    return None
                raw = json.loads(resp.read())
                # WormholeScan wraps response in {"data": {...}}
                data = raw.get("data", raw)
                status = str(data.get("status", data.get("txStatus", "pending"))).lower()
                return {
                    "vaa_id": vaa_id,
                    "status": status,
                    "completed": status in VAA_COMPLETED_STATUSES,
                    "raw": data,
                }
        except (URLError, json.JSONDecodeError, OSError):
            return None

    # ── Settlement Creation ──────────────────────────────────────────────

    def create_settlement(
        self,
        source_tx: str,
        amount: float,
        currency: Optional[str] = None,
        network: Optional[str] = None,
    ) -> Optional[dict]:
        """
        Create an AlgoVoi settlement record for a completed Wormhole bridge transfer.

        Args:
            source_tx: Source chain transaction hash
            amount:    Bridged USDC amount
            currency:  Asset currency code (defaults to base_currency / "USD")
            network:   Target AlgoVoi network (defaults to default_network)

        Returns:
            dict with checkout_url, token, chain, amount_microunits — or None
        """
        if not network or network not in HOSTED_NETWORKS:
            network = self.default_network
        if not currency:
            currency = self.base_currency

        label = f"Wormhole Bridge {source_tx[:20]}..." if len(source_tx) > 20 else f"Wormhole Bridge {source_tx}"

        payload: dict[str, Any] = {
            "amount": round(amount, 2),
            "currency": currency.upper(),
            "label": label,
            "preferred_network": network,
            "reference": source_tx[:64] if source_tx else "",
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
            "source_tx": source_tx,
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
        Returns a Flask view function for the Wormhole bridge callback endpoint.

        Usage:
            app.add_url_rule('/webhook/wormhole',
                view_func=adapter.flask_webhook_handler(), methods=['POST'])
        """
        adapter = self

        def handler():
            from flask import request, jsonify

            raw_body = request.get_data()
            signature = request.headers.get("X-AlgoVoi-Signature", "")

            payload = adapter.verify_webhook(raw_body, signature)
            if not payload:
                return jsonify(error="Unauthorized"), 401

            event = adapter.parse_bridge_event(payload)
            if not event:
                return jsonify(received=True, skipped="not parseable")

            # Only act on completed bridge transfers
            if event["status"] not in VAA_COMPLETED_STATUSES:
                return jsonify(received=True, skipped=f"status={event['status']}")

            # Validate source chain is supported
            if event["source_chain"] and event["source_chain"] not in SUPPORTED_SOURCE_CHAINS:
                return jsonify(received=True, skipped=f"unsupported source chain: {event['source_chain']}")

            result = adapter.create_settlement(
                source_tx=event["source_tx"],
                amount=event["amount"],
            )

            if not result:
                return jsonify(error="Could not create settlement link"), 502

            return jsonify(
                received=True,
                vaa_id=event["vaa_id"],
                source_chain=event["source_chain"],
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
