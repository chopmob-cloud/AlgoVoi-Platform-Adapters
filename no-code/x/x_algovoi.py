"""
AlgoVoi X (Twitter) Adapter
============================

Integrates AlgoVoi crypto-payment flows with X (Twitter) to auto-post
payment notifications and share hosted checkout links.

Three integration surfaces:

  1. Webhook Handler (AlgoVoi → X)
     Validates an incoming AlgoVoi payment webhook (HMAC-SHA256) and
     auto-posts a configurable tweet when a payment is confirmed.

  2. Action: Post Payment Link
     Creates an AlgoVoi hosted checkout link and posts it as a tweet,
     useful for triggering sales campaigns or gating content.

  3. Action: Post Tweet / List Networks
     Raw tweet posting and network enumeration for use in no-code flows
     (Zapier + Code by Zapier calling this adapter, n8n HTTP Request, etc.)

Quick start (Flask):

    from flask import Flask, request, jsonify
    from x_algovoi import AlgoVoiX

    handler = AlgoVoiX(
        algovoi_key="algv_...",
        tenant_id="...",
        payout_algorand="ADDR...",
        webhook_secret="whsec_...",
        x_api_key="...",
        x_api_key_secret="...",
        x_access_token="...",
        x_access_token_secret="...",
    )

    app = Flask(__name__)

    @app.route("/x/webhook", methods=["POST"])
    def x_webhook():
        res = handler.on_payment_received(
            raw_body=request.get_data(as_text=True),
            signature=request.headers.get("X-AlgoVoi-Signature", ""),
        )
        return jsonify(res.to_dict()), res.http_status

X API credentials:
    All four OAuth 1.0a credentials are required to post tweets.
    Obtain them from https://developer.x.com → your app → "Keys and Tokens".
    Your app must have "Read and Write" permissions.

    X_API_KEY              Consumer / API key
    X_API_KEY_SECRET       Consumer / API key secret
    X_ACCESS_TOKEN         Access token (user context)
    X_ACCESS_TOKEN_SECRET  Access token secret (user context)

Rate limits (X API Free tier):
    500 tweets / month (app-level). Use sparingly in production.

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
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Optional

__version__ = "1.0.0"

_ALGOVOI_BASE = "https://api1.ilovechicken.co.uk"
_X_API_BASE   = "https://api.twitter.com"
_TWEET_URL    = f"{_X_API_BASE}/2/tweets"
_MAX_BODY     = 1_048_576   # 1 MiB
_MAX_STR      = 2_048
_TIMEOUT      = 15
_SAFE_AMOUNT  = 10_000_000
_MAX_TWEET    = 280

# Networks AlgoVoi supports (mainnet + testnet)
SUPPORTED_NETWORKS = {
    "algorand_mainnet", "voi_mainnet", "hedera_mainnet", "stellar_mainnet",
    "algorand_mainnet_algo", "voi_mainnet_voi", "hedera_mainnet_hbar", "stellar_mainnet_xlm",
    "algorand_testnet", "voi_testnet", "hedera_testnet", "stellar_testnet",
    "algorand_testnet_algo", "voi_testnet_voi", "hedera_testnet_hbar", "stellar_testnet_xlm",
}

NETWORK_INFO = {
    "algorand_mainnet":      {"label": "Algorand",         "asset": "USDC",  "decimals": 6},
    "voi_mainnet":           {"label": "VOI",              "asset": "aUSDC", "decimals": 6},
    "hedera_mainnet":        {"label": "Hedera",           "asset": "USDC",  "decimals": 6},
    "stellar_mainnet":       {"label": "Stellar",          "asset": "USDC",  "decimals": 7},
    "algorand_mainnet_algo": {"label": "Algorand",         "asset": "ALGO",  "decimals": 6},
    "voi_mainnet_voi":       {"label": "VOI",              "asset": "VOI",   "decimals": 6},
    "hedera_mainnet_hbar":   {"label": "Hedera",           "asset": "HBAR",  "decimals": 8},
    "stellar_mainnet_xlm":   {"label": "Stellar",          "asset": "XLM",   "decimals": 7},
    "algorand_testnet":      {"label": "Algorand Testnet", "asset": "USDC",  "decimals": 6},
    "voi_testnet":           {"label": "VOI Testnet",      "asset": "aUSDC", "decimals": 6},
    "hedera_testnet":        {"label": "Hedera Testnet",   "asset": "USDC",  "decimals": 6},
    "stellar_testnet":       {"label": "Stellar Testnet",  "asset": "USDC",  "decimals": 7},
    "algorand_testnet_algo": {"label": "Algorand Testnet", "asset": "ALGO",  "decimals": 6},
    "voi_testnet_voi":       {"label": "VOI Testnet",      "asset": "VOI",   "decimals": 6},
    "hedera_testnet_hbar":   {"label": "Hedera Testnet",   "asset": "HBAR",  "decimals": 8},
    "stellar_testnet_xlm":   {"label": "Stellar Testnet",  "asset": "XLM",   "decimals": 7},
}

# Default tweet templates (overridable via tweet_template= constructor arg)
_TMPL_PAYMENT = (
    "✅ {amount_display} {asset} payment confirmed on {network_label}\n\n"
    "Verified directly on the blockchain by AlgoVoi — "
    "open-source crypto payment adapters for Zapier, Make, n8n, AI agents & more. "
    "No banks, no card processors.\n\n"
    "TX: {tx_id_short}\n"
    "#AlgoVoi #crypto"
)

# Note: {checkout_url} is always placed last so it is never truncated.
# X counts any URL as 23 characters regardless of actual length, so
# the X-counted length stays comfortably under 280 even with long URLs.
# label_short = label truncated to 60 chars — keeps total raw length ≤ 280.
_TMPL_LINK = (
    "{label_short}\n\n"
    "Pay {amount_display} {asset} on {network_label} with crypto — "
    "verified on-chain by AlgoVoi. No account needed, just a wallet.\n\n"
    "{checkout_url}\n"
    "#AlgoVoi"
)


# ── Result type ────────────────────────────────────────────────────────────────

@dataclass
class XResult:
    """Uniform return type for all X adapter methods."""
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


# ── Security / string helpers ──────────────────────────────────────────────────

def _safe_str(v: Any, max_len: int = _MAX_STR) -> str:
    return str(v or "").strip()[:max_len]


def _safe_float(v: Any) -> Optional[float]:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    if not (0 < f <= _SAFE_AMOUNT):
        return None
    return f


def _safe_url(v: Any) -> Optional[str]:
    s = _safe_str(v)
    if not s:
        return None
    try:
        parsed = urllib.parse.urlparse(s)
    except Exception:
        return None
    if parsed.scheme != "https":
        return None
    return s


def _verify_hmac(raw_body: str, signature: str, secret: str) -> bool:
    """Constant-time HMAC-SHA256 check of an AlgoVoi webhook signature."""
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


# ── OAuth 1.0a signing (stdlib only) ──────────────────────────────────────────

def _pct(s: str) -> str:
    """RFC 3986 percent-encode a string (used in OAuth signature building)."""
    return urllib.parse.quote(str(s), safe="")


def _oauth1_auth_header(
    method: str,
    url: str,
    api_key: str,
    api_key_secret: str,
    access_token: str,
    access_token_secret: str,
) -> str:
    """
    Build an OAuth 1.0a Authorization header for a JSON-body request.

    For JSON bodies (Content-Type: application/json) the body parameters
    are NOT included in the signature base string — only the oauth_* params.
    """
    nonce     = base64.b64encode(os.urandom(32)).decode("ascii").rstrip("=")
    timestamp = str(int(time.time()))

    oauth_params: dict[str, str] = {
        "oauth_consumer_key":     api_key,
        "oauth_nonce":            nonce,
        "oauth_signature_method": "HMAC-SHA1",
        "oauth_timestamp":        timestamp,
        "oauth_token":            access_token,
        "oauth_version":          "1.0",
    }

    # Signature base string
    # 1. Collect and sort all parameters
    sorted_params = "&".join(
        f"{_pct(k)}={_pct(v)}"
        for k, v in sorted(oauth_params.items())
    )
    base_url = url.split("?")[0]  # strip query string
    base_string = "&".join([
        method.upper(),
        _pct(base_url),
        _pct(sorted_params),
    ])

    # 2. Signing key
    signing_key = f"{_pct(api_key_secret)}&{_pct(access_token_secret)}"

    # 3. HMAC-SHA1
    sig_bytes = hmac.new(
        signing_key.encode("ascii"),
        base_string.encode("ascii"),
        hashlib.sha1,
    ).digest()
    signature = base64.b64encode(sig_bytes).decode("ascii")

    # 4. Authorization header
    oauth_params["oauth_signature"] = signature
    parts = ", ".join(
        f'{k}="{_pct(v)}"'
        for k, v in sorted(oauth_params.items())
    )
    return f"OAuth {parts}"


# ── HTTP helpers ───────────────────────────────────────────────────────────────

def _http_post_json(url: str, payload: dict, headers: dict) -> tuple[int, dict]:
    """POST JSON, return (status_code, response_dict). Raises on network error."""
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https":
        raise ValueError("Only https:// URLs are allowed")
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json", **headers},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        try:
            return exc.code, json.loads(body)
        except Exception:
            return exc.code, {"error": body[:500]}


def _http_post_algovoi(url: str, payload: dict, api_key: str, tenant_id: str) -> dict:
    headers = {
        "Authorization": f"Bearer {api_key}",
        "X-Tenant-Id":   tenant_id,
    }
    status, body = _http_post_json(url, payload, headers)
    if status not in (200, 201):
        raise RuntimeError(f"AlgoVoi API {status}: {body}")
    return body


# ── Tweet builder ──────────────────────────────────────────────────────────────

def _format_amount(amount_microunits: int, decimals: int) -> str:
    val = amount_microunits / (10 ** decimals)
    if val == int(val):
        return str(int(val))
    return f"{val:.{decimals}f}".rstrip("0").rstrip(".")


def _build_payment_tweet(event: dict, network_info: dict, template: str) -> str:
    network    = _safe_str(event.get("network", ""))
    asset      = network_info.get("asset", "USDC")
    label      = network_info.get("label", network)
    decimals   = network_info.get("decimals", 6)
    amount_mu  = int(event.get("amount_microunits", 0))
    tx_id      = _safe_str(event.get("tx_id", ""))

    amount_display = _format_amount(amount_mu, decimals) if amount_mu else str(event.get("amount", ""))
    tx_id_short    = tx_id[:16] + "…" if len(tx_id) > 16 else tx_id

    text = template.format(
        amount_display = amount_display,
        asset          = asset,
        network_label  = label,
        network        = network,
        tx_id          = tx_id,
        tx_id_short    = tx_id_short,
        payer          = _safe_str(event.get("payer", "")),
        order_id       = _safe_str(event.get("order_id", "")),
        token          = _safe_str(event.get("token", "")),
    )
    return text[:_MAX_TWEET]


def _build_link_tweet(
    label: str,
    checkout_url: str,
    amount: float,
    currency: str,
    network: str,
    template: str,
) -> str:
    net_info = NETWORK_INFO.get(network, {})

    # X counts any URL as 23 chars regardless of actual length.
    # Reserve room so the URL+hashtag tail is never truncated.
    # Worst case tail: "\n{url}\n#AlgoVoi" = 1 + len(url) + 1 + 8 = ~84 chars raw.
    # Keep non-URL body ≤ 196 chars raw so total raw ≤ 280.
    _URL_RESERVE = len(checkout_url) + 10   # "\n" + url + "\n#AlgoVoi"
    _BODY_MAX    = _MAX_TWEET - _URL_RESERVE

    # Truncate label to 60 chars so it fits cleanly in the body budget
    label_short = label[:60] + ("…" if len(label) > 60 else "")

    text = template.format(
        label          = label,
        label_short    = label_short,
        checkout_url   = checkout_url,
        amount_display = str(round(amount, 6)).rstrip("0").rstrip("."),
        asset          = net_info.get("asset", currency),
        network_label  = net_info.get("label", network),
        network        = network,
        currency       = currency,
    )

    # If the full formatted text still exceeds _MAX_TWEET raw chars,
    # trim the body but preserve the URL tail intact.
    if len(text) > _MAX_TWEET:
        url_tag_tail = f"\n{checkout_url}\n#AlgoVoi"
        body = text[: _MAX_TWEET - len(url_tag_tail)].rstrip()
        text = body + "\n\n" + url_tag_tail.lstrip("\n")

    return text


# ── Main adapter class ─────────────────────────────────────────────────────────

class AlgoVoiX:
    """
    AlgoVoi adapter for X (Twitter).

    Args:
        algovoi_key:          AlgoVoi API key (algv_...)
        tenant_id:            AlgoVoi tenant UUID
        payout_algorand:      Algorand payout address
        payout_voi:           VOI payout address (optional)
        payout_hedera:        Hedera account e.g. 0.0.123456 (optional)
        payout_stellar:       Stellar address G... (optional)
        payout_address:       Universal fallback payout address (optional)
        webhook_secret:       AlgoVoi webhook signing secret (optional)
        x_api_key:            X (Twitter) API key / Consumer key
        x_api_key_secret:     X API key secret / Consumer secret
        x_access_token:       X access token (user context)
        x_access_token_secret:X access token secret (user context)
        payment_tweet_template: f-string template for payment notification tweets
        link_tweet_template:    f-string template for payment link tweets
        api_base:             AlgoVoi API base URL
    """

    def __init__(
        self,
        algovoi_key:             str,
        tenant_id:               str,
        payout_algorand:         str = "",
        payout_voi:              str = "",
        payout_hedera:           str = "",
        payout_stellar:          str = "",
        payout_address:          str = "",
        webhook_secret:          str = "",
        x_api_key:               str = "",
        x_api_key_secret:        str = "",
        x_access_token:          str = "",
        x_access_token_secret:   str = "",
        payment_tweet_template:  str = _TMPL_PAYMENT,
        link_tweet_template:     str = _TMPL_LINK,
        api_base:                str = _ALGOVOI_BASE,
    ) -> None:
        if not algovoi_key or not algovoi_key.startswith("algv_"):
            raise ValueError("algovoi_key must start with algv_")
        if not tenant_id:
            raise ValueError("tenant_id is required")

        self._key      = algovoi_key
        self._tenant   = tenant_id
        self._secret   = webhook_secret
        self._base     = api_base.rstrip("/")

        if not self._base.startswith("https://"):
            raise ValueError("api_base must be https://")

        # X OAuth 1.0a credentials
        self._x_api_key             = x_api_key
        self._x_api_key_secret      = x_api_key_secret
        self._x_access_token        = x_access_token
        self._x_access_token_secret = x_access_token_secret

        # Tweet templates
        self._payment_tmpl = payment_tweet_template or _TMPL_PAYMENT
        self._link_tmpl    = link_tweet_template    or _TMPL_LINK

        # Payout address map
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

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _payout_for(self, network: str) -> str:
        norm = network.replace("-", "_")
        base = re.sub(r"_(algo|voi|hbar|xlm)$", "", norm) or norm
        return (
            self._payouts.get(norm)
            or self._payouts.get(base)
            or next(iter(self._payouts.values()), "")
        )

    def _has_x_creds(self) -> bool:
        return bool(
            self._x_api_key and self._x_api_key_secret
            and self._x_access_token and self._x_access_token_secret
        )

    # ── Core: post a tweet ────────────────────────────────────────────────────

    def post_tweet(self, text: str) -> XResult:
        """
        Post a tweet.

        Args:
            text: Tweet body — truncated to 280 chars automatically.

        Returns:
            XResult with tweet_id and tweet_url on success.
        """
        if not self._has_x_creds():
            return XResult(False, 401, error="X API credentials not configured")

        text = str(text or "").strip()[:_MAX_TWEET]
        if not text:
            return XResult(False, 400, error="Tweet text is required")

        auth_header = _oauth1_auth_header(
            method              = "POST",
            url                 = _TWEET_URL,
            api_key             = self._x_api_key,
            api_key_secret      = self._x_api_key_secret,
            access_token        = self._x_access_token,
            access_token_secret = self._x_access_token_secret,
        )

        status, body = _http_post_json(
            _TWEET_URL,
            {"text": text},
            {"Authorization": auth_header},
        )

        if status == 201:
            tweet_data = body.get("data", {})
            tweet_id   = tweet_data.get("id", "")
            return XResult(True, 200, data={
                "tweet_id":   tweet_id,
                "tweet_url":  f"https://x.com/i/web/status/{tweet_id}" if tweet_id else "",
                "text":       tweet_data.get("text", text),
            })

        # Handle X API error response
        error_msg = ""
        if "errors" in body and body["errors"]:
            error_msg = body["errors"][0].get("message", str(body))
        elif "detail" in body:
            error_msg = body["detail"]
        elif "error" in body:
            error_msg = str(body["error"])
        else:
            error_msg = str(body)[:200]

        return XResult(False, status, error=f"X API error {status}: {error_msg}")

    # ── 1. Webhook handler ────────────────────────────────────────────────────

    def on_payment_received(self, raw_body: str, signature: str) -> XResult:
        """
        Validate an incoming AlgoVoi payment webhook and post a tweet.

        Args:
            raw_body:  Raw request body string (not parsed).
            signature: X-AlgoVoi-Signature header value.

        Returns:
            XResult — http_status 200 on success, 401 on bad sig, 400 on bad body.
        """
        if len(raw_body) > _MAX_BODY:
            return XResult(False, 400, error="Request body too large")

        if self._secret:
            if not _verify_hmac(raw_body, signature, self._secret):
                return XResult(False, 401, error="Invalid webhook signature")

        try:
            event = json.loads(raw_body)
        except json.JSONDecodeError:
            return XResult(False, 400, error="Invalid JSON body")

        # Only act on confirmed payments
        status = str(event.get("status", "")).lower()
        if status not in ("paid", "completed", "confirmed"):
            return XResult(True, 200, data={
                "tweeted": False,
                "reason":  f"event status '{status}' — not a confirmed payment",
                "event_type": str(event.get("event_type", "")),
            })

        network  = _safe_str(event.get("network", "algorand_mainnet"))
        net_info = NETWORK_INFO.get(network, {"label": network, "asset": "crypto", "decimals": 6})
        text     = _build_payment_tweet(event, net_info, self._payment_tmpl)

        tweet_result = self.post_tweet(text)
        if not tweet_result.success:
            return XResult(False, tweet_result.http_status, error=tweet_result.error,
                           data={"tweeted": False, "event": event})

        return XResult(True, 200, data={
            "tweeted":   True,
            "tweet_id":  tweet_result.data.get("tweet_id", ""),
            "tweet_url": tweet_result.data.get("tweet_url", ""),
            "text":      text,
            "event":     {
                "tx_id":   _safe_str(event.get("tx_id", "")),
                "network": network,
                "amount":  event.get("amount_microunits", event.get("amount", 0)),
                "payer":   _safe_str(event.get("payer", "")),
            },
        })

    # ── 2. Action: post payment link tweet ────────────────────────────────────

    def post_payment_link(self, data: dict) -> XResult:
        """
        Create an AlgoVoi hosted checkout link and post a tweet with the URL.

        Expected keys in `data`:
            amount        (float, required)
            currency      (str 3-char, required)
            label         (str, required — becomes tweet headline)
            network       (str, optional — defaults to algorand_mainnet)
            redirect_url  (str https://, optional)
            tweet_text    (str, optional — fully custom tweet; overrides template)
        """
        amount = _safe_float(data.get("amount"))
        if amount is None:
            return XResult(False, 400, error="amount must be a positive number ≤ 10,000,000")

        currency = _safe_str(data.get("currency", "USD"))
        if len(currency) != 3:
            return XResult(False, 400, error="currency must be a 3-character code")

        label = _safe_str(data.get("label", ""))
        if not label:
            return XResult(False, 400, error="label is required")

        network = _safe_str(data.get("network", "algorand_mainnet"))
        if network not in SUPPORTED_NETWORKS:
            return XResult(False, 400, error=f"unsupported network: {network}")

        # 1. Create payment link
        payload: dict = {
            "amount":            round(amount, 2),
            "currency":          currency.upper(),
            "label":             label[:200],
            "preferred_network": network,
        }
        redirect_url = _safe_url(data.get("redirect_url", ""))
        if redirect_url:
            payload["redirect_url"]       = redirect_url
            payload["expires_in_seconds"] = 3600

        try:
            resp = _http_post_algovoi(
                f"{self._base}/v1/payment-links",
                payload,
                self._key,
                self._tenant,
            )
        except Exception as exc:
            return XResult(False, 502, error=f"AlgoVoi API error: {type(exc).__name__}: {exc}")

        checkout_url = str(resp.get("checkout_url", ""))
        if not checkout_url:
            return XResult(False, 502, error="AlgoVoi did not return checkout_url")

        token_match = re.search(r"/checkout/([A-Za-z0-9_-]+)", checkout_url)
        token       = token_match.group(1) if token_match else ""

        # 2. Build and post tweet
        custom_text = _safe_str(data.get("tweet_text", ""))
        if custom_text:
            tweet_text = custom_text[:_MAX_TWEET]
        else:
            tweet_text = _build_link_tweet(
                label        = label,
                checkout_url = checkout_url,
                amount       = amount,
                currency     = currency.upper(),
                network      = network,
                template     = self._link_tmpl,
            )

        tweet_result = self.post_tweet(tweet_text)
        if not tweet_result.success:
            # Payment link was created — include it even on tweet failure
            return XResult(False, tweet_result.http_status, error=tweet_result.error, data={
                "checkout_url": checkout_url,
                "token":        token,
                "tweeted":      False,
            })

        return XResult(True, 200, data={
            "checkout_url":     checkout_url,
            "token":            token,
            "amount":           amount,
            "currency":         currency.upper(),
            "network":          network,
            "amount_microunits": resp.get("amount_microunits", 0),
            "tweeted":          True,
            "tweet_id":         tweet_result.data.get("tweet_id", ""),
            "tweet_url":        tweet_result.data.get("tweet_url", ""),
            "tweet_text":       tweet_text,
        })

    # ── 3. Action: list networks ──────────────────────────────────────────────

    def list_networks(self) -> XResult:
        """Return all 16 supported networks — no API call needed."""
        networks = [
            {
                "key":      k,
                "label":    v["label"],
                "asset":    v["asset"],
                "decimals": v["decimals"],
            }
            for k, v in NETWORK_INFO.items()
        ]
        return XResult(True, 200, data={"networks": networks, "count": len(networks)})

    # ── 4. Webhook signature verification (standalone) ────────────────────────

    def verify_webhook_signature(self, raw_body: str, signature: str) -> dict:
        """
        Standalone HMAC-SHA256 signature check (no tweet posting).
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

def from_env() -> AlgoVoiX:
    """Construct AlgoVoiX from standard environment variables."""
    return AlgoVoiX(
        algovoi_key=              os.environ["ALGOVOI_API_KEY"],
        tenant_id=                os.environ["ALGOVOI_TENANT_ID"],
        payout_algorand=          os.environ.get("ALGOVOI_PAYOUT_ALGORAND", ""),
        payout_voi=               os.environ.get("ALGOVOI_PAYOUT_VOI", ""),
        payout_hedera=            os.environ.get("ALGOVOI_PAYOUT_HEDERA", ""),
        payout_stellar=           os.environ.get("ALGOVOI_PAYOUT_STELLAR", ""),
        payout_address=           os.environ.get("ALGOVOI_PAYOUT_ADDRESS", ""),
        webhook_secret=           os.environ.get("ALGOVOI_WEBHOOK_SECRET", ""),
        x_api_key=                os.environ.get("X_API_KEY", ""),
        x_api_key_secret=         os.environ.get("X_API_KEY_SECRET", ""),
        x_access_token=           os.environ.get("X_ACCESS_TOKEN", ""),
        x_access_token_secret=    os.environ.get("X_ACCESS_TOKEN_SECRET", ""),
        payment_tweet_template=   os.environ.get("X_PAYMENT_TWEET_TEMPLATE", _TMPL_PAYMENT),
        link_tweet_template=      os.environ.get("X_LINK_TWEET_TEMPLATE", _TMPL_LINK),
        api_base=                 os.environ.get("ALGOVOI_API_BASE", _ALGOVOI_BASE),
    )
