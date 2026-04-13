"""
AlgoVoi AP2 (Agent Payment Protocol v2) Server Adapter

Implements the AP2 v0.1 protocol with the AlgoVoi crypto-algo extension
for on-chain payments on Algorand and VOI.

Extension URI:  https://algovoi.io/ap2/extensions/crypto-algo/v1
Schema:         https://algovoi.io/ap2/extensions/crypto-algo/v1/schema.json
Extensions API: https://api1.ilovechicken.co.uk/ap2/extensions

Flow:
  1. Agent requests resource — adapter issues CartMandate (HTTP 402)
       CartMandate.contents.payment_request.payment_methods lists
       the AlgoVoi crypto-algo extension with on-chain payment terms
  2. Agent pays on-chain (Algorand or VOI USDC/aUSDC)
  3. Agent signs a PaymentMandate (ed25519) containing tx_id + network
  4. Adapter verifies ed25519 signature, then verifies tx on-chain via indexer
  5. HTTP 200 — access granted, mandate details in result.mandate

Extension schema defines two sides:
  PaymentMethodData  — merchant → agent (CartMandate, what to pay)
  PaymentResponseDetails — agent → merchant (PaymentMandate, proof of payment)

Zero pip dependencies — uses only the Python standard library.
ed25519 verification via PyNaCl (preferred) or cryptography package.
Works with Flask, Django, FastAPI, or any WSGI/ASGI framework.

AlgoVoi docs: https://github.com/chopmob-cloud/AlgoVoi-Platform-Adapters
Licensed under the Business Source License 1.1 — see LICENSE for details.

Version: 2.0.0
"""

from __future__ import annotations

import hashlib
import json
import ssl
import time
from base64 import b64decode, b64encode
from typing import Any, Callable, Optional
from urllib.request import Request, urlopen
from urllib.error import URLError

__version__ = "2.0.0"

# ── AP2 constants ─────────────────────────────────────────────────────────────

AP2_VERSION    = "0.1"
EXTENSION_URI  = "https://algovoi.io/ap2/extensions/crypto-algo/v1"
EXTENSION_SCHEMA = f"{EXTENSION_URI}/schema.json"


# ── Network config (AlgoVoi crypto-algo extension — AVM chains only) ──────────

NETWORKS: dict[str, dict] = {
    "algorand-mainnet": {
        "asset_id": 31566704,
        "ticker":   "USDC",
        "indexer":  "https://mainnet-idx.algonode.cloud/v2",
    },
    "voi-mainnet": {
        "asset_id": 302190,
        "ticker":   "aUSDC",
        "indexer":  "https://mainnet-idx.voi.nodely.dev/v2",
    },
}


# ── Data classes ──────────────────────────────────────────────────────────────

class Ap2CartMandate:
    """
    CartMandate issued to an agent when payment is required.

    Conforms to AP2 v0.1 CartMandate structure with the AlgoVoi
    crypto-algo extension listed in payment_methods.
    """

    def __init__(
        self,
        merchant_id: str,
        networks_data: list[dict],
        expires_seconds: int = 600,
    ):
        self.merchant_id  = merchant_id
        self.networks_data = networks_data          # list of PaymentMethodData dicts
        self.expires_at   = int(time.time()) + expires_seconds
        self.request_id   = f"ap2_{int(time.time())}_{id(self) % 100000}"

    def as_dict(self) -> dict:
        return {
            "ap2_version": AP2_VERSION,
            "type":        "CartMandate",
            "merchant_id": self.merchant_id,
            "request_id":  self.request_id,
            "contents": {
                "payment_request": {
                    "payment_methods": [
                        {
                            "supported_methods": EXTENSION_URI,
                            "data": nd,
                        }
                        for nd in self.networks_data
                    ]
                }
            },
            "expires_at": self.expires_at,
        }

    def as_header(self) -> str:
        return b64encode(json.dumps(self.as_dict()).encode()).decode()


class Ap2Mandate:
    """A verified AP2 payment mandate from an agent."""

    def __init__(
        self,
        payer_address: str,
        merchant_id:   str,
        network:       str,
        tx_id:         str,
        note_field:    str,
        signature:     str,
        verified_at:   float = 0,
    ):
        self.payer_address = payer_address
        self.merchant_id   = merchant_id
        self.network       = network
        self.tx_id         = tx_id
        self.note_field    = note_field
        self.signature     = signature
        self.verified_at   = verified_at or time.time()


class Ap2Result:
    """Result of Ap2Gate.check()."""

    def __init__(
        self,
        requires_payment: bool,
        cart_mandate:     Optional[Ap2CartMandate] = None,
        mandate:          Optional[Ap2Mandate]     = None,
        error:            Optional[str]            = None,
    ):
        self.requires_payment = requires_payment
        self.cart_mandate     = cart_mandate
        self.mandate          = mandate
        self.error            = error

    def as_flask_response(self) -> tuple:
        """Return a Flask-compatible (body, status, headers) tuple."""
        if not self.requires_payment:
            return {}, 200, {}

        body: dict = {
            "error":       "Payment Required",
            "ap2_version": AP2_VERSION,
            "detail":      self.error or "This endpoint requires an AP2 PaymentMandate.",
        }
        headers: dict = {"Content-Type": "application/json"}

        if self.cart_mandate:
            body["cart_mandate"]          = self.cart_mandate.as_dict()
            headers["X-AP2-Cart-Mandate"] = self.cart_mandate.as_header()

        return json.dumps(body), 402, headers

    def as_wsgi_response(self) -> tuple[str, list[tuple[str, str]], bytes]:
        """Return a WSGI-compatible (status, headers, body) tuple."""
        body_str, status_code, header_dict = self.as_flask_response()
        headers = list(header_dict.items())
        body_bytes = body_str.encode() if isinstance(body_str, str) else json.dumps(body_str).encode()
        return f"{status_code} Payment Required", headers, body_bytes


# ── Gate ──────────────────────────────────────────────────────────────────────

class Ap2Gate:
    """
    AP2 payment gate — checks requests for valid AP2 PaymentMandates.

    Accepts mandates via:
      X-AP2-Mandate: <base64 JSON>   (header)
      body["ap2_mandate"]            (JSON body field)
      Raw JSON string in X-AP2-Mandate (non-base64)

    PaymentMandate structure:
      {
        "ap2_version": "0.1",
        "type":        "PaymentMandate",
        "merchant_id": "<your-merchant-id>",
        "payer_address": "<algorand-address>",
        "payment_response": {
          "method_name": "https://algovoi.io/ap2/extensions/crypto-algo/v1",
          "details": {
            "network":     "algorand-mainnet",
            "tx_id":       "<on-chain-tx-id>",
            "note_field":  "<sha256hex-optional>"
          }
        },
        "signature": "<base64-ed25519-signature>"
      }
    """

    def __init__(
        self,
        merchant_id:       str,
        api_base:          str,
        api_key:           str,
        tenant_id:         str,
        amount_microunits: int            = 100000,
        networks:          Optional[list[str]] = None,
        payout_address:    str            = "",
        expires_seconds:   int            = 600,
    ):
        """
        Args:
            merchant_id:       Your AP2 merchant identifier
            api_base:          AlgoVoi API base URL
            api_key:           AlgoVoi API key
            tenant_id:         AlgoVoi tenant UUID
            amount_microunits: Required payment in USDC microunits (default: 100000 = 0.10 USDC)
            networks:          List of network keys from NETWORKS (default: both AVM chains)
            payout_address:    On-chain receiver address (same for Algorand and VOI)
            expires_seconds:   CartMandate TTL in seconds (default: 600)
        """
        self.merchant_id       = merchant_id
        self.api_base          = api_base.rstrip("/")
        self.api_key           = api_key
        self.tenant_id         = tenant_id
        self.amount_microunits = amount_microunits
        self.networks          = networks or ["algorand-mainnet", "voi-mainnet"]
        self.payout_address    = payout_address
        self.expires_seconds   = expires_seconds
        self._ssl_ctx          = ssl.create_default_context()  # nosec B310
        self._used_tx_ids: set[str] = set()

    # ── Core check ────────────────────────────────────────────────────────────

    def check(
        self,
        headers: dict[str, str],
        body:    Optional[dict] = None,
    ) -> Ap2Result:
        """
        Check a request for a valid AP2 PaymentMandate.

        Returns Ap2Result. Check .requires_payment before proceeding.
        If requires_payment is False, .mandate has payer details.
        """
        h = {k.lower(): v for k, v in headers.items()}

        # Extract mandate from header or body
        mandate_raw = h.get("x-ap2-mandate", "")
        if not mandate_raw and isinstance(body, dict):
            mandate_raw = body.get("ap2_mandate", "")

        if not mandate_raw:
            return Ap2Result(
                requires_payment=True,
                cart_mandate=self._build_cart_mandate(),
            )

        # Parse mandate JSON
        try:
            if mandate_raw.startswith("{"):
                mandate_data = json.loads(mandate_raw)
            else:
                mandate_data = json.loads(b64decode(mandate_raw + "=="))
        except Exception:
            return Ap2Result(
                requires_payment=True,
                cart_mandate=self._build_cart_mandate(),
                error="Invalid mandate encoding",
            )

        # merchant_id check
        if mandate_data.get("merchant_id") != self.merchant_id:
            return Ap2Result(
                requires_payment=True,
                cart_mandate=self._build_cart_mandate(),
                error="Merchant ID mismatch",
            )

        payer   = mandate_data.get("payer_address", "")
        sig     = mandate_data.get("signature", "")

        if not payer or not sig:
            return Ap2Result(
                requires_payment=True,
                cart_mandate=self._build_cart_mandate(),
                error="Missing payer_address or signature",
            )

        # Extract payment details from PaymentMandate structure
        pr      = mandate_data.get("payment_response", {})
        details = pr.get("details", {})
        network   = details.get("network", "algorand-mainnet")
        tx_id     = details.get("tx_id", "")
        note_field = details.get("note_field", "")

        # tx_id length guard
        if tx_id and len(tx_id) > 200:
            return Ap2Result(
                requires_payment=True,
                cart_mandate=self._build_cart_mandate(),
                error="tx_id exceeds maximum length",
            )

        # Replay protection
        if tx_id and tx_id in self._used_tx_ids:
            return Ap2Result(
                requires_payment=True,
                cart_mandate=self._build_cart_mandate(),
                error="Payment proof already used",
            )

        # Verify ed25519 signature
        if not self._verify_signature(mandate_data):
            return Ap2Result(
                requires_payment=True,
                cart_mandate=self._build_cart_mandate(),
                error="Mandate signature verification failed",
            )

        # Verify on-chain tx (if tx_id provided and network is AVM)
        if tx_id and network in NETWORKS:
            if not self._verify_on_chain(tx_id, network):
                return Ap2Result(
                    requires_payment=True,
                    cart_mandate=self._build_cart_mandate(),
                    error="On-chain payment verification failed",
                )
            self._used_tx_ids.add(tx_id)

        return Ap2Result(
            requires_payment=False,
            mandate=Ap2Mandate(
                payer_address=payer,
                merchant_id=self.merchant_id,
                network=network,
                tx_id=tx_id,
                note_field=note_field,
                signature=sig,
            ),
        )

    # ── CartMandate builder ───────────────────────────────────────────────────

    def _build_cart_mandate(self) -> Ap2CartMandate:
        """Build an AP2 CartMandate with extension data for each configured network."""
        networks_data = []
        for net in self.networks:
            cfg = NETWORKS.get(net)
            if not cfg:
                continue
            networks_data.append({
                "network":           net,
                "receiver":          self.payout_address,
                "amount_microunits": self.amount_microunits,
                "asset_id":          cfg["asset_id"],
                "min_confirmations": 1,
                "memo_required":     True,
            })
        return Ap2CartMandate(
            merchant_id=self.merchant_id,
            networks_data=networks_data,
            expires_seconds=self.expires_seconds,
        )

    # ── Signature verification ────────────────────────────────────────────────

    def _verify_signature(self, mandate_data: dict) -> bool:
        """
        Verify the ed25519 signature over the canonical mandate JSON.

        Signing message: JSON of all mandate fields except 'signature',
        keys sorted, no spaces:
          json.dumps({k:v ...}, sort_keys=True, separators=(",",":"))

        Public key is derived from payer_address (Algorand base32 address
        encodes the 32-byte ed25519 public key directly).

        Requires PyNaCl or the cryptography package.
        """
        payer_address = mandate_data.get("payer_address", "")
        sig_b64       = mandate_data.get("signature", "")

        if not payer_address or not sig_b64:
            return False

        # Derive ed25519 public key from Algorand address
        try:
            from algosdk import encoding as _enc  # type: ignore
            public_key_bytes = _enc.decode_address(payer_address)
        except Exception:
            try:
                import base64 as _b64
                decoded = _b64.b32decode(payer_address.upper() + "======")
                public_key_bytes = decoded[:32]
            except Exception:
                return False

        # Canonical signing message (all fields except signature)
        try:
            fields  = {k: v for k, v in mandate_data.items() if k != "signature"}
            message = json.dumps(fields, sort_keys=True, separators=(",", ":")).encode()
        except Exception:
            return False

        try:
            sig_bytes = b64decode(sig_b64)
        except Exception:
            return False

        # PyNaCl (preferred)
        try:
            from nacl.signing import VerifyKey          # type: ignore
            from nacl.exceptions import BadSignatureError  # type: ignore
            VerifyKey(public_key_bytes).verify(message, sig_bytes)
            return True
        except Exception:
            pass

        # cryptography fallback
        try:
            from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey  # type: ignore
            Ed25519PublicKey.from_public_bytes(public_key_bytes).verify(sig_bytes, message)
            return True
        except Exception:
            pass

        return False

    # ── On-chain verification (AVM) ───────────────────────────────────────────

    def _verify_on_chain(self, tx_id: str, network: str) -> bool:
        """
        Verify an on-chain AVM (Algorand / VOI) payment via the chain indexer.

        Checks:
          - receiver == payout_address
          - amount >= amount_microunits
          - asset-id matches network's USDC/aUSDC asset
          - confirmed-round is present (tx is finalised)
        """
        cfg     = NETWORKS.get(network)
        if not cfg:
            return False
        indexer = cfg["indexer"]

        try:
            url = f"{indexer}/transactions/{tx_id}"
            req = Request(url, headers={"User-Agent": "AlgoVoi-AP2/2.0"})
            with urlopen(req, context=self._ssl_ctx, timeout=10) as r:  # nosec B310
                data = json.loads(r.read())
        except Exception:
            return False

        tx  = data.get("transaction", {})
        if not tx.get("confirmed-round"):
            return False

        atx = tx.get("asset-transfer-transaction", {})
        if atx.get("receiver") != self.payout_address:
            return False
        if atx.get("amount", 0) < self.amount_microunits:
            return False
        if atx.get("asset-id") != cfg["asset_id"]:
            return False

        return True

    # ── Framework helpers ──────────────────────────────────────────────────────

    def flask_guard(self, body: Optional[dict] = None) -> Optional[tuple]:
        """
        Flask route guard. Returns None to proceed, or a 402 response tuple.

        Usage:
            @app.route('/api/premium', methods=['POST'])
            def premium():
                guard = gate.flask_guard(request.get_json(silent=True))
                if guard:
                    return guard
                return jsonify(data='premium content')
        """
        from flask import request as flask_request  # type: ignore
        result = self.check(dict(flask_request.headers), body)
        if not result.requires_payment:
            return None
        return result.as_flask_response()

    def django_decorator(self, view_func: Callable) -> Callable:
        """Django view decorator."""
        from django.http import JsonResponse  # type: ignore
        from functools import wraps

        @wraps(view_func)
        def wrapped(request: Any, *args: Any, **kwargs: Any) -> Any:
            hdrs = {
                k.replace("HTTP_", "").replace("_", "-").title(): v
                for k, v in request.META.items() if k.startswith("HTTP_")
            }
            try:
                body = json.loads(request.body) if request.body else None
            except json.JSONDecodeError:
                body = None
            result = self.check(hdrs, body)
            if result.requires_payment:
                body_str, status, resp_headers = result.as_flask_response()
                resp = JsonResponse(
                    json.loads(body_str) if isinstance(body_str, str) else body_str,
                    status=status,
                )
                for k, v in resp_headers.items():
                    resp[k] = v
                return resp
            return view_func(request, *args, **kwargs)

        return wrapped
