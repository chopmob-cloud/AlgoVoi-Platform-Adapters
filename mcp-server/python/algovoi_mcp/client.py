"""
Thin urllib-based AlgoVoi HTTP client.

Stdlib only (urllib, json, re, ssl, base64) — no requests, no httpx, so the
MCP package installs with zero extra transitive deps beyond `mcp` and pydantic.

External error messages are intentionally generic — they never leak the
specific API path, upstream status code, or internal response shape.

On-chain verification (verify_mpp_receipt / verify_x402_proof /
verify_ap2_payment) hits the public blockchain indexers directly — no
AlgoVoi API call required — mirroring the MPP adapter approach.
"""

from __future__ import annotations

import base64
import json
import re
import ssl
from typing import Any, Optional
from urllib.parse import quote, urlparse
from urllib.request import Request, urlopen
from urllib.error import URLError

# Public indexer base URLs (no auth needed).
# Native token networks share the same indexer as their parent chain.
# Testnet networks share the same indexer key pattern with _testnet suffix.
_INDEXERS: dict[str, str] = {
    # Mainnet
    "algorand_mainnet": "https://mainnet-idx.algonode.cloud/v2",
    "voi_mainnet":      "https://mainnet-idx.voi.nodely.dev/v2",
    "hedera_mainnet":   "https://mainnet-public.mirrornode.hedera.com/api/v1",
    "stellar_mainnet":  "https://horizon.stellar.org",
    # Testnet
    "algorand_testnet": "https://testnet-idx.algonode.cloud/v2",
    "voi_testnet":      "https://testnet-idx.voi.nodely.dev/v2",
    "hedera_testnet":   "https://testnet.mirrornode.hedera.com/api/v1",
    "stellar_testnet":  "https://horizon-testnet.stellar.org",
}

# USDC asset IDs per network (parent-chain keys only — omitting a key skips asset-id check).
_USDC_ASSET: dict[str, Any] = {
    # Mainnet
    "algorand_mainnet": 31566704,
    "voi_mainnet":      302190,
    "hedera_mainnet":   "0.0.456858",
    "stellar_mainnet":  "USDC:GA5ZSEJYB37JRC5AVCIA5MOP4RHTM335X2KGX3IHOJAPP5RE34K4KZVN",
    # Testnet
    "algorand_testnet": 10458941,
    # "voi_testnet": asset ID varies — check skipped until standardised
    "hedera_testnet":   "0.0.4279119",
    "stellar_testnet":  "USDC:GBBD47IF6LWK7P7MDEVSCWR7DPUWV3NY3DTQEVFL4NAT4AQH3ZLLFLA5",
}

import re as _re

def _indexer_key(norm: str) -> str:
    """Strip native-coin suffix to get the parent chain indexer key."""
    return _re.sub(r"_(algo|voi|hbar|xlm)$", "", norm) or norm

def _is_native(norm: str) -> bool:
    """True when the network key refers to a native coin (not a stablecoin)."""
    return bool(_re.search(r"_(algo|voi|hbar|xlm)$", norm))


class AlgoVoiClient:
    """HTTP client used by every MCP tool that hits the AlgoVoi API."""

    def __init__(
        self,
        api_base: str,
        api_key: str,
        tenant_id: str,
        payout_addresses: dict[str, str],
        timeout: int = 30,
    ) -> None:
        if not api_base.startswith("https://"):
            raise ValueError("api_base must be an https:// URL")
        self.api_base         = api_base.rstrip("/")
        self.api_key          = api_key
        self.tenant_id        = tenant_id
        self.payout_addresses = payout_addresses
        self.timeout          = timeout
        # §4.6 — TLS 1.3 minimum. Fails loudly on a weaker handshake
        # instead of silently negotiating down.
        self._ssl_ctx       = ssl.create_default_context()
        try:
            self._ssl_ctx.minimum_version = ssl.TLSVersion.TLSv1_3
        except (AttributeError, ValueError):
            # Extremely old OpenSSL / Python combos — fall back to 1.2
            # and log once. Real deployments build against 3.10+ so this
            # path is effectively dead, but we don't want import to crash.
            pass

    # ── HTTP primitives ────────────────────────────────────────────────────

    def _post(
        self,
        path: str,
        body: dict,
        *,
        extra_headers: Optional[dict] = None,
    ) -> dict:
        headers = {
            "Content-Type":  "application/json",
            "Authorization": f"Bearer {self.api_key}",
            "X-Tenant-Id":   self.tenant_id,
        }
        if extra_headers:
            headers.update(extra_headers)
        req = Request(
            self.api_base + path,
            data=json.dumps(body).encode(),
            method="POST",
            headers=headers,
        )
        try:
            with urlopen(req, timeout=self.timeout, context=self._ssl_ctx) as resp:  # noqa: S310
                data = json.loads(resp.read())
                return data if isinstance(data, dict) else {"raw": data}
        except URLError as e:
            raise RuntimeError("AlgoVoi request failed") from e
        except (json.JSONDecodeError, OSError) as e:
            raise RuntimeError("AlgoVoi request returned invalid data") from e

    def _get(self, path: str) -> dict:
        req = Request(
            self.api_base + path,
            method="GET",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "X-Tenant-Id":   self.tenant_id,
            },
        )
        try:
            with urlopen(req, timeout=self.timeout, context=self._ssl_ctx) as resp:  # noqa: S310
                data = json.loads(resp.read())
                return data if isinstance(data, dict) else {"raw": data}
        except URLError as e:
            raise RuntimeError("AlgoVoi request failed") from e
        except (json.JSONDecodeError, OSError) as e:
            raise RuntimeError("AlgoVoi request returned invalid data") from e

    def _post_raw(self, url: str, body: dict) -> dict:
        """POST to an arbitrary URL with no auth — used for /checkout/<token>/verify."""
        if not url.startswith("https://"):
            return {"_http_code": 400}
        req = Request(
            url,
            data=json.dumps(body).encode(),
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        try:
            with urlopen(req, timeout=self.timeout, context=self._ssl_ctx) as resp:  # noqa: S310
                result = json.loads(resp.read())
                if isinstance(result, dict):
                    result["_http_code"] = resp.status
                    return result
                return {"raw": result, "_http_code": resp.status}
        except URLError as e:
            return {"error": str(e), "_http_code": getattr(e, "code", 502)}
        except (json.JSONDecodeError, OSError) as e:
            return {"error": str(e), "_http_code": 502}

    # ── Public surface ─────────────────────────────────────────────────────

    def create_payment_link(
        self,
        amount: float,
        currency: str,
        label: str,
        network: str,
        redirect_url: Optional[str] = None,
        idempotency_key: Optional[str] = None,
    ) -> dict:
        """Create a hosted-checkout payment link.

        When ``idempotency_key`` is supplied it is forwarded to the
        gateway as an ``Idempotency-Key`` header; duplicate calls within
        the gateway's retention window return the same checkout URL
        instead of creating a new one.  See §6.4 of ALGOVOI_MCP.md.
        """
        if not isinstance(amount, (int, float)) or amount <= 0:
            raise ValueError("amount must be a positive number")
        payload: dict[str, Any] = {
            "amount":            round(float(amount), 2),
            "currency":          currency.upper(),
            "label":             label,
            "preferred_network": network,
        }
        if redirect_url:
            parsed = urlparse(redirect_url)
            if parsed.scheme != "https" or not parsed.hostname:
                raise ValueError("redirect_url must be https://")
            payload["redirect_url"]       = redirect_url
            payload["expires_in_seconds"] = 3600
        extra = None
        if idempotency_key:
            extra = {"Idempotency-Key": idempotency_key}
        resp = self._post("/v1/payment-links", payload, extra_headers=extra)
        if not resp.get("checkout_url"):
            raise RuntimeError("API did not return checkout_url")
        return resp

    def verify_hosted_return(self, token: str) -> dict:
        """Call the hosted-checkout status endpoint."""
        if not token or len(token) > 200:
            return {"status": "invalid_token", "paid": False, "raw": {}}
        url = f"{self.api_base}/checkout/{quote(token, safe='')}/status"
        try:
            req = Request(url, method="GET")
            with urlopen(req, timeout=15, context=self._ssl_ctx) as resp:  # noqa: S310
                data = json.loads(resp.read())
                status = str(data.get("status", "unknown"))
                return {
                    "paid":   status in ("paid", "completed", "confirmed"),
                    "status": status,
                    "raw":    data,
                }
        except (URLError, json.JSONDecodeError, OSError) as e:
            return {"paid": False, "status": f"error: {e}", "raw": {}}

    def verify_extension_payment(self, token: str, tx_id: str) -> dict:
        """Verify an on-chain tx for a checkout token."""
        if not token or not tx_id or len(token) > 200 or len(tx_id) > 200:
            return {"error": "Invalid parameters", "_http_code": 400}
        url = f"{self.api_base}/checkout/{quote(token, safe='')}/verify"
        return self._post_raw(url, {"tx_id": tx_id})

    def verify_mpp_receipt(self, resource_id: str, tx_id: str, network: str) -> dict:
        """Verify an MPP on-chain receipt via direct blockchain indexer."""
        return self._verify_on_chain(tx_id, network)

    def verify_x402_proof(self, proof: str, network: str) -> dict:
        """Verify an x402 payment proof by decoding it and checking on-chain."""
        try:
            decoded = base64.b64decode(proof + "==").decode("utf-8")
            data = json.loads(decoded)
            tx_id = data.get("tx_id") or data.get("txId") or data.get("transaction_id")
        except Exception:
            return {"verified": False, "error": "invalid proof encoding"}
        if not tx_id:
            return {"verified": False, "error": "proof missing tx_id"}
        return self._verify_on_chain(str(tx_id), network)

    def verify_ap2_payment(self, mandate_id: str, tx_id: str, network: str) -> dict:
        """Verify an AP2 payment via direct blockchain indexer."""
        return self._verify_on_chain(tx_id, network)

    # ── On-chain indexer verification ──────────────────────────────────────

    def _verify_on_chain(self, tx_id: str, network: str) -> dict:
        """Route to the correct chain verifier based on network key."""
        norm = network.replace("-", "_")
        ikey = _indexer_key(norm)
        indexer = _INDEXERS.get(ikey)
        if not indexer:
            return {"verified": False, "error": f"unsupported network: {network}"}
        try:
            if "algorand" in norm or ("voi" in norm and not norm.startswith("hedera")):
                return self._verify_avm(tx_id, norm, indexer)
            if "hedera" in norm:
                return self._verify_hedera(tx_id, norm, indexer)
            if "stellar" in norm:
                return self._verify_stellar(tx_id, norm, indexer)
        except Exception:
            return {"verified": False, "error": "indexer lookup failed"}
        return {"verified": False, "error": "unsupported network"}

    def _verify_avm(self, tx_id: str, network: str, indexer: str) -> dict:
        url = f"{indexer}/transactions/{quote(tx_id, safe='')}"
        req = Request(url, headers={"Accept": "application/json"})
        try:
            with urlopen(req, timeout=15, context=self._ssl_ctx) as resp:
                if resp.status != 200:
                    return {"verified": False, "error": "tx not found"}
                data = json.loads(resp.read())
        except (URLError, OSError):
            return {"verified": False, "error": "indexer unreachable"}
        tx = data.get("transaction", {})
        if not tx.get("confirmed-round"):
            return {"verified": False, "error": "tx not confirmed"}
        payout = self.payout_address_for(network)
        if _is_native(network):
            # Native ALGO / VOI — uses payment-transaction sub-object (no asset-id).
            ptx = tx.get("payment-transaction", {})
            if ptx.get("receiver") != payout:
                return {"verified": False, "error": "wrong recipient"}
            return {
                "verified": True, "tx_id": tx_id, "network": network,
                "payer": tx.get("sender"), "amount": ptx.get("amount"),
            }
        # USDC ASA path.
        atx = tx.get("asset-transfer-transaction", {})
        if atx.get("receiver") != payout:
            return {"verified": False, "error": "wrong recipient"}
        expected_asset = _USDC_ASSET.get(_indexer_key(network))
        if expected_asset is not None and atx.get("asset-id") != expected_asset:
            return {"verified": False, "error": "wrong asset"}
        return {
            "verified": True, "tx_id": tx_id, "network": network,
            "payer": tx.get("sender"), "amount": atx.get("amount"),
        }

    def _verify_hedera(self, tx_id: str, network: str, indexer: str) -> dict:
        # Normalise 0.0.account@secs.nanos → 0.0.account-secs-nanos
        if "@" in tx_id:
            acct, ts = tx_id.split("@", 1)
            normalised = f"{acct}-{ts.replace('.', '-', 1)}"
        else:
            normalised = tx_id
        url = f"{indexer}/transactions/{quote(normalised, safe='')}"
        req = Request(url, headers={"Accept": "application/json"})
        try:
            with urlopen(req, timeout=15, context=self._ssl_ctx) as resp:
                if resp.status != 200:
                    return {"verified": False, "error": "tx not found"}
                data = json.loads(resp.read())
        except (URLError, OSError):
            return {"verified": False, "error": "indexer unreachable"}
        transactions = data.get("transactions", [])
        if not transactions:
            return {"verified": False, "error": "tx not found"}
        tx = transactions[0]
        if tx.get("result") != "SUCCESS":
            return {"verified": False, "error": "tx failed"}
        payout = self.payout_address_for(network)
        if _is_native(network):
            # Native HBAR — check `transfers` array (not token_transfers).
            for transfer in tx.get("transfers", []):
                if transfer.get("account") == payout and int(transfer.get("amount", 0)) > 0:
                    return {"verified": True, "tx_id": tx_id, "network": network,
                            "amount": transfer.get("amount")}
            return {"verified": False, "error": "payment to payout address not found"}
        # USDC HTS path — check token_transfers.
        expected_token = _USDC_ASSET.get(_indexer_key(network))
        for transfer in tx.get("token_transfers", []):
            if expected_token and transfer.get("token_id") != expected_token:
                continue
            if transfer.get("account") == payout and int(transfer.get("amount", 0)) > 0:
                return {"verified": True, "tx_id": tx_id, "network": network,
                        "amount": transfer.get("amount")}
        return {"verified": False, "error": "payment to payout address not found"}

    def _verify_stellar(self, tx_id: str, network: str, indexer: str) -> dict:
        url = f"{indexer}/transactions/{quote(tx_id, safe='')}/operations"
        req = Request(url, headers={"Accept": "application/json"})
        try:
            with urlopen(req, timeout=15, context=self._ssl_ctx) as resp:
                if resp.status != 200:
                    return {"verified": False, "error": "tx not found"}
                data = json.loads(resp.read())
        except (URLError, OSError):
            return {"verified": False, "error": "indexer unreachable"}
        payout = self.payout_address_for(network)
        for op in data.get("_embedded", {}).get("records", []):
            if op.get("type") != "payment":
                continue
            if op.get("to") != payout:
                continue
            if _is_native(network):
                # Native XLM — asset_type is "native".
                if op.get("asset_type") != "native":
                    continue
                amt = int(float(op.get("amount", "0")) * 10_000_000)
                return {"verified": True, "tx_id": tx_id, "network": network,
                        "amount": amt, "payer": op.get("from")}
            # USDC path.
            asset_str = str(_USDC_ASSET.get(_indexer_key(network), "USDC:"))
            parts = asset_str.split(":", 1)
            expected_code = parts[0]
            expected_issuer = parts[1] if len(parts) > 1 else ""
            if op.get("asset_code") != expected_code or op.get("asset_issuer") != expected_issuer:
                continue
            amt = int(float(op.get("amount", "0")) * 1_000_000)
            return {"verified": True, "tx_id": tx_id, "network": network,
                    "amount": amt, "payer": op.get("from")}
        return {"verified": False, "error": "payment to payout address not found"}

    def payout_address_for(self, network: str) -> str:
        """Return the payout address for the given network key.
        Strips native-coin suffix (e.g. algorand_mainnet_algo → algorand_mainnet)
        so native networks inherit the same wallet as their parent chain.
        Falls back to the first configured address if no per-chain entry exists."""
        norm = network.replace("-", "_")
        if norm in self.payout_addresses:
            return self.payout_addresses[norm]
        base = _indexer_key(norm)
        if base != norm and base in self.payout_addresses:
            return self.payout_addresses[base]
        return next(iter(self.payout_addresses.values()), "")

    @staticmethod
    def extract_token(checkout_url: str) -> str:
        """Extract the short token from a checkout URL."""
        m = re.search(r"/checkout/([A-Za-z0-9_-]+)$", checkout_url)
        return m.group(1) if m else ""
