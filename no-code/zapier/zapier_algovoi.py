"""
AlgoVoi Zapier Adapter
======================

Integrates AlgoVoi crypto-payment flows with Zapier automation:

Three integration surfaces:

  1. Webhook Bridge (AlgoVoi → Zapier)
     Receives AlgoVoi payment webhooks, validates the HMAC signature,
     and forwards the event to a Zapier Catch Hook URL so it can
     trigger downstream Zaps (e.g. fulfil order, notify Slack, etc.)

  2. Action Handlers (Zapier → AlgoVoi)
     Action endpoints Zapier can call via the "Code by Zapier" step
     or a deployed webhook:
       POST /zap/create-payment-link
       POST /zap/verify-payment
       GET  /zap/list-networks
       POST /zap/generate-challenge

  3. Native Zapier App (JavaScript)
     See zapier-app/ for the full Zapier CLI app that publishes
     triggers and actions directly to your Zapier account.

Quick start (Flask):

    from flask import Flask, request, jsonify
    from zapier_algovoi import AlgoVoiZapier, ZapierActionResult

    handler = AlgoVoiZapier(
        algovoi_key="algv_...",
        tenant_id="...",
        payout_algorand="ADDR...",
        webhook_secret="whsec_...",
        zapier_hook_url="https://hooks.zapier.com/hooks/catch/XXXX/YYYY/",
    )

    app = Flask(__name__)

    @app.route("/algovoi/webhook", methods=["POST"])
    def algovoi_webhook():
        res = handler.receive_and_forward(
            raw_body=request.get_data(as_text=True),
            signature=request.headers.get("X-AlgoVoi-Signature", ""),
        )
        return jsonify(res.to_dict()), res.http_status

    @app.route("/zap/create-payment-link", methods=["POST"])
    def zap_create():
        data = request.get_json(force=True) or {}
        res = handler.action_create_payment_link(data)
        return jsonify(res.to_dict()), res.http_status

Networks:
    "algorand_mainnet"      USDC  (ASA 31566704)
    "voi_mainnet"           aUSDC (ARC-200 302190)
    "hedera_mainnet"        USDC  (HTS 0.0.456858)
    "stellar_mainnet"       USDC  (Circle)
    "algorand_mainnet_algo" ALGO  (native)
    "voi_mainnet_voi"       VOI   (native)
    "hedera_mainnet_hbar"   HBAR  (native)
    "stellar_mainnet_xlm"   XLM   (native)
    + testnet variants for all 8 networks

AlgoVoi repo: https://github.com/chopmob-cloud/AlgoVoi-Platform-Adapters
Licensed under the Business Source License 1.1 — see LICENSE for details.

Version: 1.1.0
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import time
import urllib.request
import urllib.error
from dataclasses import dataclass, field
from typing import Any, Optional
from urllib.parse import urlparse

__version__ = "1.1.0"

_API_BASE    = "https://api1.ilovechicken.co.uk"
_MAX_BODY    = 1_048_576   # 1 MiB
_MAX_STR     = 2_048
_TIMEOUT     = 15
_SAFE_AMOUNT = 10_000_000

# Networks AlgoVoi supports (mainnet + testnet)
SUPPORTED_NETWORKS = {
    "algorand_mainnet", "voi_mainnet", "hedera_mainnet", "stellar_mainnet",
    "algorand_mainnet_algo", "voi_mainnet_voi", "hedera_mainnet_hbar", "stellar_mainnet_xlm",
    "algorand_testnet", "voi_testnet", "hedera_testnet", "stellar_testnet",
    "algorand_testnet_algo", "voi_testnet_voi", "hedera_testnet_hbar", "stellar_testnet_xlm",
    "base_mainnet", "solana_mainnet", "tempo_mainnet",
}

NETWORK_INFO = {
    "algorand_mainnet":      {"label": "Algorand", "asset": "USDC",  "asset_id": "31566704",   "decimals": 6},
    "voi_mainnet":           {"label": "VOI",      "asset": "aUSDC", "asset_id": "302190",     "decimals": 6},
    "hedera_mainnet":        {"label": "Hedera",   "asset": "USDC",  "asset_id": "0.0.456858", "decimals": 6},
    "stellar_mainnet":       {"label": "Stellar",  "asset": "USDC",  "asset_id": "USDC:GA5ZSEJYB37JRC5AVCIA5MOP4RHTM335X2KGX3IHOJAPP5RE34K4KZVN", "decimals": 7},
    "base_mainnet":          {"label": "Base",     "asset": "USDC",  "asset_id": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913", "decimals": 6},
    "solana_mainnet":        {"label": "Solana",   "asset": "USDC",  "asset_id": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v", "decimals": 6},
    "tempo_mainnet":         {"label": "Tempo",    "asset": "USDC",  "asset_id": "0x20c000000000000000000000b9537d11c60e8b50", "decimals": 6},
    "algorand_mainnet_algo": {"label": "Algorand", "asset": "ALGO",  "asset_id": None, "decimals": 6},
    "voi_mainnet_voi":       {"label": "VOI",      "asset": "VOI",   "asset_id": None, "decimals": 6},
    "hedera_mainnet_hbar":   {"label": "Hedera",   "asset": "HBAR",  "asset_id": None, "decimals": 8},
    "stellar_mainnet_xlm":   {"label": "Stellar",  "asset": "XLM",   "asset_id": None, "decimals": 7},
    "algorand_testnet":      {"label": "Algorand Testnet", "asset": "USDC",  "asset_id": "10458941",   "decimals": 6},
    "voi_testnet":           {"label": "VOI Testnet",      "asset": "aUSDC", "asset_id": None,         "decimals": 6},
    "hedera_testnet":        {"label": "Hedera Testnet",   "asset": "USDC",  "asset_id": "0.0.4279119","decimals": 6},
    "stellar_testnet":       {"label": "Stellar Testnet",  "asset": "USDC",  "asset_id": "USDC:GBBD47IF6LWK7P7MDEVSCWR7DPUWV3NY3DTQEVFL4NAT4AQH3ZLLFLA5", "decimals": 7},
    "algorand_testnet_algo": {"label": "Algorand Testnet", "asset": "ALGO",  "asset_id": None, "decimals": 6},
    "voi_testnet_voi":       {"label": "VOI Testnet",      "asset": "VOI",   "asset_id": None, "decimals": 6},
    "hedera_testnet_hbar":   {"label": "Hedera Testnet",   "asset": "HBAR",  "asset_id": None, "decimals": 8},
    "stellar_testnet_xlm":   {"label": "Stellar Testnet",  "asset": "XLM",   "asset_id": None, "decimals": 7},
}


# ── Result type ────────────────────────────────────────────────────────────────

@dataclass
class ZapierActionResult:
    """Uniform return type for all action and webhook handlers."""
    success:     bool
    http_status: int
    data:        dict = field(default_factory=dict)
    error:       Optional[str] = None

    def to_dict(self) -> dict:
        out: dict = {"success": self.success}
        if self.error:
            out["error"] = self.error
        out.update(self.data)
        return out


# ── Security helpers ───────────────────────────────────────────────────────────

def _safe_str(v: Any, max_len: int = _MAX_STR) -> str:
    s = str(v or "").strip()
    return s[:max_len]


def _safe_float(v: Any, gt: float = 0, le: float = _SAFE_AMOUNT) -> Optional[float]:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    if not (gt < f <= le):
        return None
    return f


def _safe_url(v: Any) -> Optional[str]:
    s = _safe_str(v)
    if not s:
        return None
    try:
        parsed = urlparse(s)
    except Exception:
        return None
    if parsed.scheme != "https":
        return None
    return s


def _verify_hmac(raw_body: str, signature: str, secret: str) -> bool:
    """Constant-time HMAC-SHA256 verification of an AlgoVoi webhook signature."""
    if not secret or not signature:
        return False
    expected = hmac.new(
        secret.encode("utf-8"),
        raw_body.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    try:
        return hmac.compare_digest(expected, signature)
    except Exception:
        return False


# ── HTTP helpers ───────────────────────────────────────────────────────────────

def _http_post(url: str, payload: dict, headers: dict) -> dict:
    """Minimal urllib POST — no requests dependency."""
    parsed = urlparse(url)
    if parsed.scheme != "https":
        raise ValueError("Only https:// URLs are allowed")
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json", **headers},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:  # noqa: S310
        return json.loads(resp.read())


def _http_get(url: str, headers: dict) -> dict:
    parsed = urlparse(url)
    if parsed.scheme != "https":
        raise ValueError("Only https:// URLs are allowed")
    req = urllib.request.Request(url, headers=headers, method="GET")
    with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:  # noqa: S310
        return json.loads(resp.read())


# ── Main adapter class ─────────────────────────────────────────────────────────

class AlgoVoiZapier:
    """
    AlgoVoi adapter for Zapier automation.

    Args:
        algovoi_key:      AlgoVoi API key (algv_...)
        tenant_id:        AlgoVoi tenant UUID
        payout_algorand:  Algorand payout address
        payout_voi:       VOI payout address (optional)
        payout_hedera:    Hedera account e.g. 0.0.123456 (optional)
        payout_stellar:   Stellar address G... (optional)
        payout_address:   Universal fallback payout address (optional)
        webhook_secret:   AlgoVoi webhook signing secret (optional)
        zapier_hook_url:  Zapier Catch Hook URL to forward webhooks to (optional)
        api_base:         AlgoVoi API base URL (default: api1.ilovechicken.co.uk)
    """

    def __init__(
        self,
        algovoi_key:     str,
        tenant_id:       str,
        payout_algorand: str = "",
        payout_voi:      str = "",
        payout_hedera:   str = "",
        payout_stellar:  str = "",
        payout_address:  str = "",
        webhook_secret:  str = "",
        zapier_hook_url: str = "",
        api_base:        str = _API_BASE,
    ) -> None:
        self._key     = algovoi_key
        self._tenant  = tenant_id
        self._secret  = webhook_secret
        self._hook    = zapier_hook_url
        self._base    = api_base.rstrip("/")

        if not self._base.startswith("https://"):
            raise ValueError("api_base must be https://")

        self._payouts: dict[str, str] = {}
        for chain, addr in [
            ("algorand_mainnet", payout_algorand),
            ("voi_mainnet",      payout_voi),
            ("hedera_mainnet",   payout_hedera),
            ("stellar_mainnet",  payout_stellar),
        ]:
            if addr:
                self._payouts[chain] = addr
        if payout_address and not self._payouts:
            self._payouts["_fallback"] = payout_address

        if not self._payouts:
            raise ValueError("At least one payout address must be provided")

        if not algovoi_key or not algovoi_key.startswith("algv_"):
            raise ValueError("algovoi_key must start with algv_")
        if not tenant_id:
            raise ValueError("tenant_id is required")

    # ── Payout address lookup ─────────────────────────────────────────────────

    def _payout_for(self, network: str) -> str:
        norm = network.replace("-", "_")
        # Strip native suffix for lookup
        base = re.sub(r"_(algo|voi|hbar|xlm)$", "", norm) or norm
        return (
            self._payouts.get(norm)
            or self._payouts.get(base)
            or next(iter(self._payouts.values()), "")
        )

    # ── AlgoVoi API calls ─────────────────────────────────────────────────────

    def _auth_headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self._key}",
            "X-Tenant-Id":   self._tenant,
        }

    def _api_post(self, path: str, payload: dict) -> dict:
        return _http_post(f"{self._base}{path}", payload, self._auth_headers())

    def _api_get(self, path: str) -> dict:
        return _http_get(f"{self._base}{path}", self._auth_headers())

    # ── 1. Webhook bridge ─────────────────────────────────────────────────────

    def receive_and_forward(self, raw_body: str, signature: str) -> ZapierActionResult:
        """
        Validate an incoming AlgoVoi webhook and forward it to Zapier.

        Returns ZapierActionResult with http_status 200 on success,
        401 on bad signature, 400 on invalid body.
        """
        if len(raw_body) > _MAX_BODY:
            return ZapierActionResult(False, 400, error="Request body too large")

        if self._secret:
            if not _verify_hmac(raw_body, signature, self._secret):
                return ZapierActionResult(False, 401, error="Invalid webhook signature")

        try:
            payload = json.loads(raw_body)
        except json.JSONDecodeError:
            return ZapierActionResult(False, 400, error="Invalid JSON body")

        # Format for Zapier
        zap_payload = self._format_for_zapier(payload)

        # Forward to Zapier Catch Hook if configured
        if self._hook:
            try:
                _http_post(self._hook, zap_payload, {})
            except Exception as exc:
                return ZapierActionResult(
                    False, 502,
                    error=f"Failed to forward to Zapier: {type(exc).__name__}",
                )

        return ZapierActionResult(True, 200, data={"forwarded": bool(self._hook), "event": zap_payload})

    def _format_for_zapier(self, payload: dict) -> dict:
        """Normalise AlgoVoi webhook payload to Zapier-friendly flat structure."""
        return {
            "id":               _safe_str(payload.get("event_id", payload.get("id", ""))),
            "event_type":       _safe_str(payload.get("event_type", payload.get("type", "payment.received"))),
            "status":           _safe_str(payload.get("status", "")),
            "token":            _safe_str(payload.get("token", "")),
            "amount":           payload.get("amount", 0),
            "currency":         _safe_str(payload.get("currency", "USD")),
            "network":          _safe_str(payload.get("network", "")),
            "tx_id":            _safe_str(payload.get("tx_id", "")),
            "order_id":         _safe_str(payload.get("order_id", payload.get("reference", ""))),
            "payer":            _safe_str(payload.get("payer", payload.get("sender", ""))),
            "created_at":       payload.get("created_at", int(time.time())),
            "algovoi_raw":      json.dumps(payload)[:4096],
        }

    # ── 2. Action: create payment link ────────────────────────────────────────

    def action_create_payment_link(self, data: dict) -> ZapierActionResult:
        """
        Zapier action: Create a hosted checkout payment link.

        Expected keys in `data`:
            amount       (float, required)
            currency     (str 3-char, required)
            label        (str, required)
            network      (str, optional — defaults to algorand_mainnet)
            redirect_url (str https://, optional)
        """
        amount = _safe_float(data.get("amount"))
        if amount is None:
            return ZapierActionResult(False, 400, error="amount must be a positive number ≤ 10,000,000")

        currency = _safe_str(data.get("currency", "USD"))
        if len(currency) != 3:
            return ZapierActionResult(False, 400, error="currency must be a 3-character code")

        label = _safe_str(data.get("label", ""))
        if not label:
            return ZapierActionResult(False, 400, error="label is required")

        network = _safe_str(data.get("network", "algorand_mainnet"))
        if network not in SUPPORTED_NETWORKS:
            return ZapierActionResult(False, 400, error=f"unsupported network: {network}")

        payload: dict = {
            "amount":           round(amount, 2),
            "currency":         currency.upper(),
            "label":            label[:200],
            "preferred_network": network,
        }

        redirect_url = _safe_url(data.get("redirect_url", ""))
        if redirect_url:
            payload["redirect_url"]      = redirect_url
            payload["expires_in_seconds"] = 3600

        try:
            resp = self._api_post("/v1/payment-links", payload)
        except Exception as exc:
            return ZapierActionResult(False, 502, error=f"AlgoVoi API error: {type(exc).__name__}")

        if not resp.get("checkout_url"):
            return ZapierActionResult(False, 502, error="API did not return checkout_url")

        token = ""
        m = re.search(r"/checkout/([A-Za-z0-9_-]+)$", str(resp.get("checkout_url", "")))
        if m:
            token = m.group(1)

        return ZapierActionResult(True, 200, data={
            "checkout_url":     resp["checkout_url"],
            "token":            token,
            "amount":           amount,
            "currency":         currency.upper(),
            "network":          network,
            "amount_microunits": resp.get("amount_microunits", 0),
        })

    # ── 3. Action: verify payment ─────────────────────────────────────────────

    def action_verify_payment(self, data: dict) -> ZapierActionResult:
        """
        Zapier action: Check whether a payment token has been paid.

        Expected keys: token (str)
        """
        token = _safe_str(data.get("token", ""), max_len=200)
        if not token:
            return ZapierActionResult(False, 400, error="token is required")

        try:
            resp = _http_get(
                f"{self._base}/checkout/{urllib.parse.quote(token, safe='')}/status",
                {},
            )
        except Exception as exc:
            return ZapierActionResult(False, 502, error=f"AlgoVoi API error: {type(exc).__name__}")

        status = str(resp.get("status", "unknown"))
        paid   = status in ("paid", "completed", "confirmed")
        return ZapierActionResult(True, 200, data={
            "token":  token,
            "paid":   paid,
            "status": status,
        })

    # ── 4. Action: list networks ──────────────────────────────────────────────

    def action_list_networks(self) -> ZapierActionResult:
        """Return all 16 supported networks — no API call needed."""
        networks = [
            {
                "key":      k,
                "label":    v["label"],
                "asset":    v["asset"],
                "asset_id": v["asset_id"],
                "decimals": v["decimals"],
            }
            for k, v in NETWORK_INFO.items()
        ]
        return ZapierActionResult(True, 200, data={"networks": networks, "count": len(networks)})

    # ── 5. Action: generate challenge ─────────────────────────────────────────

    def action_generate_challenge(self, data: dict) -> ZapierActionResult:
        """
        Zapier action: Generate an MPP / x402 / AP2 payment challenge header.

        Expected keys:
            protocol         ("mpp" | "x402" | "ap2", required)
            resource_id      (str, required)
            amount_microunits (int, required)
            network          (str, optional)
            expires_in_seconds (int, optional)
        """
        import hashlib as _hl
        import os as _os

        protocol = _safe_str(data.get("protocol", "")).lower()
        if protocol not in ("mpp", "x402", "ap2"):
            return ZapierActionResult(False, 400, error="protocol must be mpp, x402, or ap2")

        resource_id = _safe_str(data.get("resource_id", ""))
        if not resource_id:
            return ZapierActionResult(False, 400, error="resource_id is required")

        try:
            amount_mu = int(data.get("amount_microunits", 0))
        except (TypeError, ValueError):
            return ZapierActionResult(False, 400, error="amount_microunits must be an integer")
        if amount_mu <= 0:
            return ZapierActionResult(False, 400, error="amount_microunits must be > 0")

        network  = _safe_str(data.get("network", "algorand_mainnet"))
        if network not in SUPPORTED_NETWORKS:
            return ZapierActionResult(False, 400, error=f"unsupported network: {network}")

        expires  = int(data.get("expires_in_seconds", 300))
        expires  = max(1, min(expires, 86400))
        payout   = self._payout_for(network)
        net_info = NETWORK_INFO.get(network, {})
        expires_at = int(time.time()) + expires

        if protocol == "mpp":
            challenge = (
                f'AlgoVoi realm="{resource_id}",'
                f'network="{network}",'
                f'receiver="{payout}",'
                f'amount="{amount_mu}",'
                f'asset="{net_info.get("asset_id") or net_info.get("asset", "")}",'
                f'expires="{expires_at}"'
            )
            return ZapierActionResult(True, 402, data={
                "protocol":          "mpp",
                "header_name":       "WWW-Authenticate",
                "header_value":      challenge,
                "resource_id":       resource_id,
                "amount_microunits": amount_mu,
                "network":           network,
                "expires_at":        expires_at,
            })

        if protocol == "x402":
            import base64 as _b64
            mandate_id = _hl.sha256(f"{resource_id}:{time.time()}".encode()).hexdigest()[:16]
            payload_obj = {
                "version":  1,
                "scheme":   "exact",
                "network":  network,
                "resource": resource_id,
                "receiver": payout,
                "amount":   str(amount_mu),
                "asset":    net_info.get("asset_id") or net_info.get("asset", ""),
                "expires":  expires_at,
                "mandate":  mandate_id,
            }
            encoded = _b64.b64encode(json.dumps(payload_obj).encode()).decode()
            return ZapierActionResult(True, 402, data={
                "protocol":    "x402",
                "header_name": "X-Payment-Required",
                "header_value": encoded,
                "mandate_id":  mandate_id,
                "network":     network,
                "expires_at":  expires_at,
            })

        # AP2
        mandate_id = _hl.sha256(f"{resource_id}:{time.time()}".encode()).hexdigest()[:16]
        import base64 as _b64
        mandate_obj = {
            "version":    "0.1",
            "mandate_id": mandate_id,
            "resource":   resource_id,
            "network":    network,
            "receiver":   payout,
            "amount":     str(amount_mu),
            "asset":      net_info.get("asset_id") or net_info.get("asset", ""),
            "expires":    expires_at,
        }
        mandate_b64 = _b64.b64encode(json.dumps(mandate_obj).encode()).decode()
        return ZapierActionResult(True, 402, data={
            "protocol":      "ap2",
            "mandate_id":    mandate_id,
            "mandate_b64":   mandate_b64,
            "network":       network,
            "expires_at":    expires_at,
        })

    # ── 6. Webhook signature verification (standalone) ────────────────────────

    def verify_webhook_signature(self, raw_body: str, signature: str) -> dict:
        """
        Standalone HMAC-SHA256 signature check (no forwarding).
        Returns {"valid": bool, "payload": dict|None, "error": str|None}
        """
        if not self._secret:
            return {"valid": False, "payload": None, "error": "webhook_secret not configured"}
        if len(raw_body) > _MAX_BODY:
            return {"valid": False, "payload": None, "error": "Body too large"}
        if not _verify_hmac(raw_body, signature, self._secret):
            return {"valid": False, "payload": None, "error": "Signature mismatch"}
        try:
            payload = json.loads(raw_body)
        except json.JSONDecodeError as exc:
            return {"valid": False, "payload": None, "error": f"JSON error: {exc}"}
        return {"valid": True, "payload": payload, "error": None}


# ── Environment-variable constructor ──────────────────────────────────────────

def from_env() -> AlgoVoiZapier:
    """Construct AlgoVoiZapier from standard environment variables."""
    return AlgoVoiZapier(
        algovoi_key=     os.environ["ALGOVOI_API_KEY"],
        tenant_id=       os.environ["ALGOVOI_TENANT_ID"],
        payout_algorand= os.environ.get("ALGOVOI_PAYOUT_ALGORAND", ""),
        payout_voi=      os.environ.get("ALGOVOI_PAYOUT_VOI", ""),
        payout_hedera=   os.environ.get("ALGOVOI_PAYOUT_HEDERA", ""),
        payout_stellar=  os.environ.get("ALGOVOI_PAYOUT_STELLAR", ""),
        payout_address=  os.environ.get("ALGOVOI_PAYOUT_ADDRESS", ""),
        webhook_secret=  os.environ.get("ALGOVOI_WEBHOOK_SECRET", ""),
        zapier_hook_url= os.environ.get("ZAPIER_HOOK_URL", ""),
        api_base=        os.environ.get("ALGOVOI_API_BASE", _API_BASE),
    )
