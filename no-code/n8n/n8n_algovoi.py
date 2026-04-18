"""
AlgoVoi n8n Adapter
====================

Integrates AlgoVoi crypto-payment flows with n8n workflow automation.

Two integration surfaces:

  1. Python webhook handler — deploy as a Flask/FastAPI endpoint that
     n8n's Webhook node or HTTP Request node calls. Validates signatures,
     formats bundles into n8n's item structure, runs action logic.

  2. TypeScript custom node — see n8n-nodes-algovoi/ for the npm package
     that installs directly into your n8n instance, exposing a native
     AlgoVoi node with all operations available in the visual editor.

n8n item convention:
    Results are returned as n8n items:
    { "json": { ...fields... } }
    Errors surface as n8n error items:
    { "json": { "error": "...", "code": "..." } }

Quick start (Flask):

    from flask import Flask, request, jsonify
    from n8n_algovoi import AlgoVoiN8n

    handler = AlgoVoiN8n(
        algovoi_key="algv_...",
        tenant_id="...",
        payout_algorand="ADDR...",
        webhook_secret="whsec_...",
    )

    app = Flask(__name__)

    @app.route("/n8n/webhook", methods=["POST"])
    def n8n_webhook():
        item = handler.receive_webhook(
            raw_body=request.get_data(as_text=True),
            signature=request.headers.get("X-AlgoVoi-Signature", ""),
        )
        status = 200 if "error" not in item["json"] else 401
        return jsonify([item]), status

    @app.route("/n8n/create-payment-link", methods=["POST"])
    def n8n_create():
        body = request.get_json(force=True) or {}
        item = handler.execute_create_payment_link(body)
        status = 200 if "error" not in item["json"] else 400
        return jsonify([item]), status

n8n Node operations (TypeScript node):
    - createPaymentLink
    - verifyPayment
    - listNetworks
    - generateMppChallenge
    - generateX402Challenge
    - generateAp2Mandate
    - verifyWebhookSignature

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

Version: 1.0.0
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import re
import time
import urllib.parse
import urllib.request
import urllib.error
from typing import Any, Optional
from urllib.parse import urlparse

__version__ = "1.0.0"

_API_BASE    = "https://api1.ilovechicken.co.uk"
_MAX_BODY    = 1_048_576
_MAX_STR     = 2_048
_TIMEOUT     = 15
_SAFE_AMOUNT = 10_000_000

SUPPORTED_NETWORKS = {
    "algorand_mainnet", "voi_mainnet", "hedera_mainnet", "stellar_mainnet",
    "algorand_mainnet_algo", "voi_mainnet_voi", "hedera_mainnet_hbar", "stellar_mainnet_xlm",
    "algorand_testnet", "voi_testnet", "hedera_testnet", "stellar_testnet",
    "algorand_testnet_algo", "voi_testnet_voi", "hedera_testnet_hbar", "stellar_testnet_xlm",
}

NETWORK_INFO = {
    "algorand_mainnet":      {"label": "Algorand",        "asset": "USDC",  "asset_id": "31566704",   "decimals": 6},
    "voi_mainnet":           {"label": "VOI",             "asset": "aUSDC", "asset_id": "302190",     "decimals": 6},
    "hedera_mainnet":        {"label": "Hedera",          "asset": "USDC",  "asset_id": "0.0.456858", "decimals": 6},
    "stellar_mainnet":       {"label": "Stellar",         "asset": "USDC",  "asset_id": "USDC:GA5ZSEJYB37JRC5AVCIA5MOP4RHTM335X2KGX3IHOJAPP5RE34K4KZVN", "decimals": 7},
    "algorand_mainnet_algo": {"label": "Algorand",        "asset": "ALGO",  "asset_id": None, "decimals": 6},
    "voi_mainnet_voi":       {"label": "VOI",             "asset": "VOI",   "asset_id": None, "decimals": 6},
    "hedera_mainnet_hbar":   {"label": "Hedera",          "asset": "HBAR",  "asset_id": None, "decimals": 8},
    "stellar_mainnet_xlm":   {"label": "Stellar",         "asset": "XLM",   "asset_id": None, "decimals": 7},
    "algorand_testnet":      {"label": "Algorand Testnet","asset": "USDC",  "asset_id": "10458941",    "decimals": 6},
    "voi_testnet":           {"label": "VOI Testnet",     "asset": "aUSDC", "asset_id": None,          "decimals": 6},
    "hedera_testnet":        {"label": "Hedera Testnet",  "asset": "USDC",  "asset_id": "0.0.4279119", "decimals": 6},
    "stellar_testnet":       {"label": "Stellar Testnet", "asset": "USDC",  "asset_id": "USDC:GBBD47IF6LWK7P7MDEVSCWR7DPUWV3NY3DTQEVFL4NAT4AQH3ZLLFLA5", "decimals": 7},
    "algorand_testnet_algo": {"label": "Algorand Testnet","asset": "ALGO",  "asset_id": None, "decimals": 6},
    "voi_testnet_voi":       {"label": "VOI Testnet",     "asset": "VOI",   "asset_id": None, "decimals": 6},
    "hedera_testnet_hbar":   {"label": "Hedera Testnet",  "asset": "HBAR",  "asset_id": None, "decimals": 8},
    "stellar_testnet_xlm":   {"label": "Stellar Testnet", "asset": "XLM",   "asset_id": None, "decimals": 7},
}


# ── n8n item helpers ───────────────────────────────────────────────────────────

def _item(data: dict) -> dict:
    """Wrap data as an n8n item."""
    return {"json": data}


def _err_item(message: str, code: str = "ERROR") -> dict:
    """Wrap an error as an n8n error item."""
    return {"json": {"error": message, "code": code, "success": False}}


# ── Security helpers ───────────────────────────────────────────────────────────

def _safe_str(v: Any, max_len: int = _MAX_STR) -> str:
    return str(v or "").strip()[:max_len]


def _safe_float(v: Any) -> Optional[float]:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if 0 < f <= _SAFE_AMOUNT else None


def _safe_url(v: Any) -> Optional[str]:
    s = _safe_str(v)
    if not s:
        return None
    try:
        p = urlparse(s)
    except Exception:
        return None
    return s if p.scheme == "https" else None


def _verify_hmac(raw_body: str, signature: str, secret: str) -> bool:
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
    if not url.startswith("https://"):
        raise ValueError("Only https:// URLs allowed")
    data = json.dumps(payload).encode("utf-8")
    req  = urllib.request.Request(
        url, data=data,
        headers={"Content-Type": "application/json", **headers},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:  # noqa: S310
        return json.loads(resp.read())


def _http_get(url: str, headers: dict) -> dict:
    if not url.startswith("https://"):
        raise ValueError("Only https:// URLs allowed")
    req = urllib.request.Request(url, headers=headers, method="GET")
    with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:  # noqa: S310
        return json.loads(resp.read())


# ── Main adapter class ─────────────────────────────────────────────────────────

class AlgoVoiN8n:
    """
    AlgoVoi adapter for n8n workflow automation.

    Each execute_* method returns an n8n item dict: {"json": {...}}
    which can be returned directly in an n8n Code node or HTTP endpoint.

    Args:
        algovoi_key:     AlgoVoi API key (algv_...)
        tenant_id:       AlgoVoi tenant UUID
        payout_algorand: Algorand payout address
        payout_voi:      VOI payout address (optional)
        payout_hedera:   Hedera account (optional)
        payout_stellar:  Stellar address (optional)
        payout_address:  Universal fallback (optional)
        webhook_secret:  AlgoVoi webhook signing secret (optional)
        api_base:        API base URL
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
        api_base:        str = _API_BASE,
    ) -> None:
        if not algovoi_key or not algovoi_key.startswith("algv_"):
            raise ValueError("algovoi_key must start with algv_")
        if not tenant_id:
            raise ValueError("tenant_id is required")
        if not api_base.startswith("https://"):
            raise ValueError("api_base must be https://")

        self._key    = algovoi_key
        self._tenant = tenant_id
        self._secret = webhook_secret
        self._base   = api_base.rstrip("/")

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

    def _payout_for(self, network: str) -> str:
        norm = network.replace("-", "_")
        base = re.sub(r"_(algo|voi|hbar|xlm)$", "", norm) or norm
        return (
            self._payouts.get(norm)
            or self._payouts.get(base)
            or next(iter(self._payouts.values()), "")
        )

    def _auth_headers(self) -> dict:
        return {"Authorization": f"Bearer {self._key}", "X-Tenant-Id": self._tenant}

    # ── 1. Webhook trigger handler ────────────────────────────────────────────

    def receive_webhook(self, raw_body: str, signature: str) -> dict:
        """
        Validate an AlgoVoi webhook and return an n8n item.
        Use as the handler behind an n8n Webhook node (HTTP method: POST).
        """
        if len(raw_body) > _MAX_BODY:
            return _err_item("Request body too large", "BODY_TOO_LARGE")

        if self._secret:
            if not _verify_hmac(raw_body, signature, self._secret):
                return _err_item("Invalid webhook signature", "INVALID_SIGNATURE")

        try:
            payload = json.loads(raw_body)
        except json.JSONDecodeError:
            return _err_item("Invalid JSON body", "INVALID_JSON")

        return _item({
            "success":    True,
            "event_id":   _safe_str(payload.get("event_id", payload.get("id", ""))),
            "event_type": _safe_str(payload.get("event_type", payload.get("type", "payment.received"))),
            "status":     _safe_str(payload.get("status", "")),
            "token":      _safe_str(payload.get("token", "")),
            "amount":     payload.get("amount", 0),
            "currency":   _safe_str(payload.get("currency", "USD")),
            "network":    _safe_str(payload.get("network", "")),
            "tx_id":      _safe_str(payload.get("tx_id", "")),
            "order_id":   _safe_str(payload.get("order_id", payload.get("reference", ""))),
            "payer":      _safe_str(payload.get("payer", payload.get("sender", ""))),
            "timestamp":  payload.get("created_at", int(time.time())),
            "verified":   bool(self._secret),
        })

    # ── 2. Operation: createPaymentLink ──────────────────────────────────────

    def execute_create_payment_link(self, params: dict) -> dict:
        """
        n8n operation: Create Payment Link.

        Params: amount, currency, label, network (optional), redirect_url (optional)
        """
        amount = _safe_float(params.get("amount"))
        if amount is None:
            return _err_item("amount must be a positive number ≤ 10,000,000", "INVALID_AMOUNT")

        currency = _safe_str(params.get("currency", "USD"))
        if len(currency) != 3:
            return _err_item("currency must be a 3-character code", "INVALID_CURRENCY")

        label = _safe_str(params.get("label", ""))
        if not label:
            return _err_item("label is required", "MISSING_LABEL")

        network = _safe_str(params.get("network", "algorand_mainnet"))
        if network not in SUPPORTED_NETWORKS:
            return _err_item(f"unsupported network: {network}", "INVALID_NETWORK")

        payload: dict = {
            "amount":            round(amount, 2),
            "currency":          currency.upper(),
            "label":             label[:200],
            "preferred_network": network,
        }
        redirect_url = _safe_url(params.get("redirect_url", ""))
        if redirect_url:
            payload["redirect_url"]       = redirect_url
            payload["expires_in_seconds"] = 3600

        try:
            resp = _http_post(f"{self._base}/v1/payment-links", payload, self._auth_headers())
        except Exception as exc:
            return _err_item(f"AlgoVoi API error: {type(exc).__name__}", "API_ERROR")

        if not resp.get("checkout_url"):
            return _err_item("API did not return checkout_url", "API_ERROR")

        token = ""
        m = re.search(r"/checkout/([A-Za-z0-9_-]+)$", str(resp.get("checkout_url", "")))
        if m:
            token = m.group(1)

        return _item({
            "success":         True,
            "checkout_url":    resp["checkout_url"],
            "token":           token,
            "amount":          amount,
            "currency":        currency.upper(),
            "network":         network,
            "amount_microunits": resp.get("amount_microunits", 0),
        })

    # ── 3. Operation: verifyPayment ───────────────────────────────────────────

    def execute_verify_payment(self, params: dict) -> dict:
        """n8n operation: Verify Payment. Params: token"""
        token = _safe_str(params.get("token", ""), max_len=200)
        if not token:
            return _err_item("token is required", "MISSING_TOKEN")
        try:
            resp = _http_get(
                f"{self._base}/checkout/{urllib.parse.quote(token, safe='')}/status",
                {},
            )
        except Exception as exc:
            return _err_item(f"AlgoVoi API error: {type(exc).__name__}", "API_ERROR")
        status = str(resp.get("status", "unknown"))
        return _item({"success": True, "token": token, "paid": status in ("paid","completed","confirmed"), "status": status})

    # ── 4. Operation: listNetworks ────────────────────────────────────────────

    def execute_list_networks(self) -> dict:
        """n8n operation: List all 16 supported networks."""
        networks = [
            {"key": k, "label": v["label"], "asset": v["asset"],
             "asset_id": v["asset_id"], "decimals": v["decimals"]}
            for k, v in NETWORK_INFO.items()
        ]
        return _item({"success": True, "networks": networks, "count": len(networks)})

    # ── 5. Operation: generateMppChallenge ────────────────────────────────────

    def execute_generate_mpp_challenge(self, params: dict) -> dict:
        """n8n operation: Generate MPP 402 challenge."""
        resource_id = _safe_str(params.get("resource_id", ""))
        if not resource_id:
            return _err_item("resource_id is required", "MISSING_RESOURCE")

        try:
            amount_mu = int(params.get("amount_microunits", 0))
        except (TypeError, ValueError):
            return _err_item("amount_microunits must be an integer", "INVALID_AMOUNT")
        if amount_mu <= 0:
            return _err_item("amount_microunits must be > 0", "INVALID_AMOUNT")

        network  = _safe_str(params.get("network", "algorand_mainnet"))
        if network not in SUPPORTED_NETWORKS:
            return _err_item(f"unsupported network: {network}", "INVALID_NETWORK")

        expires    = max(1, min(int(params.get("expires_in_seconds", 300)), 86400))
        expires_at = int(time.time()) + expires
        payout     = self._payout_for(network)
        net_info   = NETWORK_INFO.get(network, {})

        challenge = (
            f'AlgoVoi realm="{resource_id}",'
            f'network="{network}",'
            f'receiver="{payout}",'
            f'amount="{amount_mu}",'
            f'asset="{net_info.get("asset_id") or net_info.get("asset", "")}",'
            f'expires="{expires_at}"'
        )
        return _item({
            "success": True, "protocol": "mpp",
            "header_name": "WWW-Authenticate", "header_value": challenge,
            "status_code": 402, "resource_id": resource_id,
            "amount_microunits": amount_mu, "network": network, "expires_at": expires_at,
        })

    # ── 6. Operation: generateX402Challenge ──────────────────────────────────

    def execute_generate_x402_challenge(self, params: dict) -> dict:
        """n8n operation: Generate x402 challenge."""
        resource_id = _safe_str(params.get("resource_id", params.get("resource", "")))
        if not resource_id:
            return _err_item("resource_id is required", "MISSING_RESOURCE")

        try:
            amount_mu = int(params.get("amount_microunits", 0))
        except (TypeError, ValueError):
            return _err_item("amount_microunits must be an integer", "INVALID_AMOUNT")
        if amount_mu <= 0:
            return _err_item("amount_microunits must be > 0", "INVALID_AMOUNT")

        network  = _safe_str(params.get("network", "algorand_mainnet"))
        if network not in SUPPORTED_NETWORKS:
            return _err_item(f"unsupported network: {network}", "INVALID_NETWORK")

        expires    = max(1, min(int(params.get("expires_in_seconds", 300)), 86400))
        expires_at = int(time.time()) + expires
        payout     = self._payout_for(network)
        net_info   = NETWORK_INFO.get(network, {})
        mandate_id = hashlib.sha256(f"{resource_id}:{time.time()}".encode()).hexdigest()[:16]

        payload_obj = {
            "version": 1, "scheme": "exact", "network": network,
            "resource": resource_id, "receiver": payout, "amount": str(amount_mu),
            "asset": net_info.get("asset_id") or net_info.get("asset", ""),
            "expires": expires_at, "mandate": mandate_id,
        }
        encoded = base64.b64encode(json.dumps(payload_obj).encode()).decode()
        return _item({
            "success": True, "protocol": "x402",
            "header_name": "X-Payment-Required", "header_value": encoded,
            "mandate_id": mandate_id, "status_code": 402,
            "network": network, "expires_at": expires_at,
        })

    # ── 7. Operation: generateAp2Mandate ─────────────────────────────────────

    def execute_generate_ap2_mandate(self, params: dict) -> dict:
        """n8n operation: Generate AP2 mandate."""
        resource_id = _safe_str(params.get("resource_id", ""))
        if not resource_id:
            return _err_item("resource_id is required", "MISSING_RESOURCE")

        try:
            amount_mu = int(params.get("amount_microunits", 0))
        except (TypeError, ValueError):
            return _err_item("amount_microunits must be an integer", "INVALID_AMOUNT")
        if amount_mu <= 0:
            return _err_item("amount_microunits must be > 0", "INVALID_AMOUNT")

        network  = _safe_str(params.get("network", "algorand_mainnet"))
        if network not in SUPPORTED_NETWORKS:
            return _err_item(f"unsupported network: {network}", "INVALID_NETWORK")

        expires    = max(1, min(int(params.get("expires_in_seconds", 300)), 86400))
        expires_at = int(time.time()) + expires
        payout     = self._payout_for(network)
        net_info   = NETWORK_INFO.get(network, {})
        mandate_id = hashlib.sha256(f"{resource_id}:{time.time()}".encode()).hexdigest()[:16]

        mandate_obj = {
            "version": "0.1", "mandate_id": mandate_id, "resource": resource_id,
            "network": network, "receiver": payout, "amount": str(amount_mu),
            "asset": net_info.get("asset_id") or net_info.get("asset", ""),
            "expires": expires_at,
        }
        mandate_b64 = base64.b64encode(json.dumps(mandate_obj).encode()).decode()
        return _item({
            "success": True, "protocol": "ap2",
            "mandate_id": mandate_id, "mandate_b64": mandate_b64,
            "status_code": 402, "network": network, "expires_at": expires_at,
        })

    # ── 8. Operation: verifyWebhookSignature ─────────────────────────────────

    def execute_verify_webhook_signature(self, params: dict) -> dict:
        """n8n operation: Verify AlgoVoi webhook signature."""
        raw_body  = _safe_str(params.get("raw_body", ""), max_len=_MAX_BODY)
        signature = _safe_str(params.get("signature", ""), max_len=512)

        if not self._secret:
            return _err_item("webhook_secret not configured", "NOT_CONFIGURED")
        if len(raw_body) > _MAX_BODY:
            return _err_item("Body too large", "BODY_TOO_LARGE")
        if not _verify_hmac(raw_body, signature, self._secret):
            return _err_item("Signature mismatch", "INVALID_SIGNATURE")

        try:
            payload = json.loads(raw_body)
        except json.JSONDecodeError as exc:
            return _err_item(f"JSON error: {exc}", "INVALID_JSON")

        return _item({"success": True, "valid": True, "payload": payload})


# ── Environment-variable constructor ──────────────────────────────────────────

def from_env() -> AlgoVoiN8n:
    return AlgoVoiN8n(
        algovoi_key=     os.environ["ALGOVOI_API_KEY"],
        tenant_id=       os.environ["ALGOVOI_TENANT_ID"],
        payout_algorand= os.environ.get("ALGOVOI_PAYOUT_ALGORAND", ""),
        payout_voi=      os.environ.get("ALGOVOI_PAYOUT_VOI", ""),
        payout_hedera=   os.environ.get("ALGOVOI_PAYOUT_HEDERA", ""),
        payout_stellar=  os.environ.get("ALGOVOI_PAYOUT_STELLAR", ""),
        payout_address=  os.environ.get("ALGOVOI_PAYOUT_ADDRESS", ""),
        webhook_secret=  os.environ.get("ALGOVOI_WEBHOOK_SECRET", ""),
        api_base=        os.environ.get("ALGOVOI_API_BASE", _API_BASE),
    )
