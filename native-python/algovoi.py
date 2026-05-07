"""
AlgoVoi Native Python Payment Adapter

Single-file drop-in for any Python application. No framework required.
Works with Flask, Django, FastAPI, or plain WSGI/ASGI.

Supports:

Tier 1 — one-shot payments
  - Hosted checkout (Algorand, VOI, Hedera) — redirect to AlgoVoi payment page
  - Extension payment (Algorand, VOI) — in-page wallet flow via algosdk
  - Webhook verification with HMAC
  - SSRF protection on checkout URL fetches
  - Cancel-bypass prevention on hosted return

Tier 2 — standing-authority recurring (subscriptions, agent-bound auth)
  - Create / list / get / revoke / pause / resume / confirm / pull authorities
  - Seven chains: Algorand, VOI, Base, Tempo, Solana, Hedera, Stellar
  - Customer signs ONE pre-authorisation; AlgoVoi auto-pulls per cycle
  - Wallet performs chain-native signing — adapter is stdlib-only HTTP

Usage:
    from algovoi import AlgoVoi

    av = AlgoVoi(
        api_base='https://api1.ilovechicken.co.uk',
        api_key='algv_...',
        tenant_id='uuid',
        webhook_secret='your_secret',
    )

    # Tier 1 — one-shot
    link = av.hosted_checkout(amount=10, currency='USD', label='Order #1',
                              network='algorand_mainnet',
                              redirect_url='https://shop.example/return')

    # Tier 2 — recurring (after creating a subscription via the dashboard
    # or /v1/subscriptions endpoint)
    auth = av.create_recurring_authority(
        subscription_id='<sub-uuid>',
        chain='algorand_mainnet',
        customer_wallet_address='ABCD...XYZ',
        cap_amount_minor=120_000_000,         # $120 USDC = 12 × $10
        cap_period_seconds=365 * 86400,
        per_cycle_amount_minor=10_000_000,
    )
    # auth['customer_signing_payload'] is the chain-specific template
    # the customer's wallet (Pera / Defly / MetaMask / Phantom / HashPack /
    # Freighter / etc.) consumes to sign the on-chain authorisation.

AlgoVoi docs: https://github.com/chopmob-cloud/AlgoVoi-Platform-Adapters
Licensed under the Business Source License 1.1 — see LICENSE for details.

Version: 1.2.0
"""

from __future__ import annotations

import hashlib
import hmac
import json
import math
import re
import ssl
from base64 import b64encode
from html import escape
from typing import Any, Optional
from urllib.parse import quote, urlparse
from urllib.request import Request, urlopen
from urllib.error import URLError

__version__ = "1.2.0"

# Default Algorand-family node endpoints used by the extension flow.
# Override at runtime by passing `algod_overrides=` to AlgoVoi() — useful
# if a provider migrates domains.
DEFAULT_ALGOD = {
    "algorand-mainnet": {"url": "https://mainnet-api.algonode.cloud", "asset_id": 31566704, "ticker": "USDC", "dec": 6},
    "voi-mainnet":      {"url": "https://mainnet-api.voi.nodely.io",  "asset_id": 302190,   "ticker": "aUSDC", "dec": 6},
}
# Backwards-compatible alias — older code still imports `ALGOD`.
ALGOD = DEFAULT_ALGOD

HOSTED_NETWORKS = {
    "algorand_mainnet", "voi_mainnet", "hedera_mainnet",
    "stellar_mainnet",
}
EXT_NETWORKS = {"algorand_mainnet", "voi_mainnet"}

# Tier 2 — every v1 chain has a real provider (per
# content/recurring_payments_tier2_design.md, Sprints 1-5):
#
#     Algorand / VOI    — SpendingCapVault contract
#     Base / Tempo      — ERC-20 approve
#     Solana            — SPL Token Approve
#     Hedera            — HTS AccountAllowanceApprove
#     Stellar           — Soroban auth_entry
#
# Testnet variants supported alongside mainnets.
RECURRING_NETWORKS = {
    "algorand_mainnet", "algorand_testnet",
    "voi_mainnet",      "voi_testnet",
    "base_mainnet",     "base_sepolia",
    "tempo_mainnet",    "tempo_testnet",
    "solana_mainnet",   "solana_devnet",
    "hedera_mainnet",   "hedera_testnet",
    "stellar_mainnet",  "stellar_testnet",
}

# Tier 2 webhook event types (in addition to Tier 1's payment.* events).
# Use these to dispatch in your verify_webhook(...) handler.
RECURRING_EVENT_TYPES = {
    "recurring.authority_created",
    "recurring.authority_activated",
    "recurring.authority_paused",
    "recurring.authority_resumed",
    "recurring.authority_revoked",
    "recurring.authority_expired",
    "subscription.charged",          # successful per-cycle pull
    "subscription.payment_failed",   # failed per-cycle pull
}

# Hard caps and validation patterns
MAX_WEBHOOK_BODY_BYTES = 64 * 1024     # AlgoVoi webhooks are <2 KB in practice
MAX_TOKEN_LEN          = 200            # checkout tokens are short — guard upper bound
MAX_RECURRING_BODY_BYTES = 16 * 1024    # recurring API responses are typically <4 KB
MAX_UUID_LEN           = 36             # standard UUID string length


class AlgoVoi:
    """AlgoVoi payment adapter — zero dependencies beyond the standard library."""

    def __init__(
        self,
        api_base: str = "https://api1.ilovechicken.co.uk",
        api_key: str = "",
        tenant_id: str = "",
        webhook_secret: str = "",
        timeout: int = 30,
        algod_overrides: Optional[dict] = None,
    ):
        self.api_base = api_base.rstrip("/")
        self.api_key = api_key
        self.tenant_id = tenant_id
        self.webhook_secret = webhook_secret
        self.timeout = timeout
        self._ssl_ctx = ssl.create_default_context()
        # Allow callers to override the bundled ALGOD endpoints if a
        # provider migrates domains. We deep-copy DEFAULT_ALGOD then
        # apply the overrides so a partial dict (just one chain) works.
        self.algod = {k: dict(v) for k, v in DEFAULT_ALGOD.items()}
        if algod_overrides:
            for chain, override in algod_overrides.items():
                if chain in self.algod and isinstance(override, dict):
                    self.algod[chain].update(override)

    # ── Payment Link Creation ────────────────────────────────────────────

    def create_payment_link(
        self,
        amount: float,
        currency: str,
        label: str,
        network: str,
        redirect_url: str = "",
    ) -> Optional[dict]:
        """
        Create a payment link via the AlgoVoi API.

        Args:
            amount:       Order total
            currency:     ISO currency code (e.g. USD, GBP)
            label:        Order label (e.g. "Order #123")
            network:      Preferred network (algorand_mainnet, voi_mainnet, hedera_mainnet, stellar_mainnet)
            redirect_url: Return URL after hosted checkout (optional)

        Returns:
            API response dict or None on failure
        """
        # Defence-in-depth: reject obviously bad amounts before the
        # gateway call.
        if not isinstance(amount, (int, float)) or not math.isfinite(amount) or amount <= 0:
            return None

        payload: dict[str, Any] = {
            "amount": round(float(amount), 2),
            "currency": currency.upper(),
            "label": label,
            "preferred_network": network,
        }
        if redirect_url:
            # https-only — checkout tokens or payment-status parameters
            # appended by the gateway must not travel over plaintext.
            # Also blocks SSRF schemes (file://, gopher://, javascript:).
            parsed = urlparse(redirect_url)
            if parsed.scheme != "https" or not parsed.hostname:
                return None
            payload["redirect_url"] = redirect_url
            payload["expires_in_seconds"] = 3600

        resp = self._post("/v1/payment-links", payload)
        if not resp or not resp.get("checkout_url"):
            return None
        return resp

    @staticmethod
    def extract_token(checkout_url: str) -> str:
        """Extract the short token from a checkout URL."""
        m = re.search(r"/checkout/([A-Za-z0-9_-]+)$", checkout_url)
        return m.group(1) if m else ""

    # ── Hosted Checkout Flow ─────────────────────────────────────────────

    def hosted_checkout(
        self,
        amount: float,
        currency: str,
        label: str,
        network: str,
        redirect_url: str,
    ) -> Optional[dict]:
        """
        Start a hosted checkout. Returns checkout URL and token, or None on failure.

        Args:
            amount:       Order total
            currency:     ISO currency code
            label:        Order label
            network:      Must be one of HOSTED_NETWORKS
            redirect_url: URL to return to after payment

        Returns:
            dict with checkout_url, token, chain, amount_microunits — or None
        """
        if network not in HOSTED_NETWORKS:
            network = "algorand_mainnet"

        link = self.create_payment_link(amount, currency, label, network, redirect_url)
        if not link:
            return None

        return {
            "checkout_url": link["checkout_url"],
            "token": self.extract_token(link["checkout_url"]),
            "chain": link.get("chain", "algorand-mainnet"),
            "amount_microunits": int(link.get("amount_microunits", 0)),
        }

    def verify_hosted_return(self, token: str) -> bool:
        """
        Verify that a hosted checkout was actually paid before marking an order complete.
        Call this when the customer returns from the hosted checkout page.

        CRITICAL: Without this check, a customer can cancel payment and still
        appear to have paid (cancel-bypass vulnerability).

        Args:
            token: The checkout token stored when the payment was created

        Returns:
            True only if the API confirms payment is complete
        """
        if not token:
            return False

        url = f"{self.api_base}/checkout/{quote(token, safe='')}/status"
        if not url.startswith("https://"):
            return False
        try:
            req = Request(url, method="GET")
            with urlopen(req, timeout=15, context=self._ssl_ctx) as resp:  # nosec B310
                if resp.status != 200:
                    return False
                data = json.loads(resp.read())
                return data.get("status") in ("paid", "completed", "confirmed")
        except (URLError, json.JSONDecodeError, OSError):
            return False

    # ── Extension Payment Flow ───────────────────────────────────────────

    def extension_checkout(
        self,
        amount: float,
        currency: str,
        label: str,
        network: str,
    ) -> Optional[dict]:
        """
        Prepare data for the extension (in-page) payment flow.
        Returns all variables needed to render the JavaScript payment UI.

        Args:
            amount:   Order total
            currency: ISO currency code
            label:    Order label
            network:  Must be one of EXT_NETWORKS

        Returns:
            Payment data dict for JS rendering, or None on failure
        """
        if network not in EXT_NETWORKS:
            network = "algorand_mainnet"

        link = self.create_payment_link(amount, currency, label, network)
        if not link:
            return None

        checkout_url = link["checkout_url"]
        chain = link.get("chain", "algorand-mainnet")
        amount_mu = int(link.get("amount_microunits", 0))
        algod = self.algod.get(chain, self.algod["algorand-mainnet"])

        # SSRF guard + scrape
        scraped = self._scrape_checkout(checkout_url)
        if not scraped:
            return None

        token = self.extract_token(checkout_url)

        return {
            "token": token,
            "receiver": scraped["receiver"],
            "memo": scraped["memo"],
            "amount_mu": amount_mu,
            "asset_id": algod["asset_id"],
            "algod_url": algod["url"],
            "ticker": algod["ticker"],
            "amount_display": f"{amount_mu / (10 ** algod['dec']):.2f}",
            "chain": chain,
            "checkout_url": checkout_url,
        }

    def verify_extension_payment(self, token: str, tx_id: str) -> dict:
        """
        Verify an extension payment transaction with the AlgoVoi API.

        Args:
            token: The checkout token (max MAX_TOKEN_LEN chars)
            tx_id: The on-chain transaction ID (max 200 chars)

        Returns:
            API response dict — check for 'success' key
        """
        # Length-cap BOTH inputs — token was previously only checked for
        # truthiness, allowing arbitrary-length payloads to be URL-quoted
        # into the request path.
        if (not token or not tx_id or
                len(token) > MAX_TOKEN_LEN or len(tx_id) > 200):
            return {"error": "Invalid parameters", "_http_code": 400}

        url = f"{self.api_base}/checkout/{quote(token, safe='')}/verify"
        return self._post_raw(url, {"tx_id": tx_id})

    # ── Webhook Handling ─────────────────────────────────────────────────

    def verify_webhook(self, raw_body: bytes, signature: str) -> Optional[dict]:
        """
        Verify and parse an incoming webhook request.

        Args:
            raw_body:  The raw POST body as bytes
            signature: The X-AlgoVoi-Signature header value (base64 digest)

        Returns:
            Parsed webhook payload dict, or None if verification fails

        SECURITY NOTE — replay protection:
            This method does NOT dedupe replays. The HMAC carries no
            timestamp, so an attacker who captures one valid (body, sig)
            pair could replay it indefinitely. Callers MUST track
            processed webhook identifiers (e.g. order_id) in their
            persistence layer and reject duplicates.
        """
        if not self.webhook_secret:
            return None  # Reject if secret not configured
        # Type guards — compare_digest raises TypeError on bytes/None,
        # which would surface as a 500. Fail closed instead.
        if not isinstance(signature, str) or not signature:
            return None
        if not isinstance(raw_body, (bytes, bytearray)):
            return None
        if len(raw_body) > MAX_WEBHOOK_BODY_BYTES:
            return None

        expected = b64encode(
            hmac.new(
                self.webhook_secret.encode(),
                bytes(raw_body),
                hashlib.sha256,
            ).digest()
        ).decode()

        if not hmac.compare_digest(expected, signature):
            return None

        try:
            return json.loads(raw_body)
        except json.JSONDecodeError:
            return None

    @staticmethod
    def is_recurring_event(payload: dict) -> bool:
        """
        Return True if the parsed webhook payload is a Tier 2 recurring
        event (subscription.charged, recurring.authority_*, etc.).

        Use this to fork your handler:

            payload = av.verify_webhook(raw_body, signature)
            if payload is None:
                abort(400)
            if av.is_recurring_event(payload):
                handle_recurring(payload)   # subscription.charged, etc.
            else:
                handle_one_shot(payload)    # payment.succeeded, etc.
        """
        if not isinstance(payload, dict):
            return False
        evt = payload.get("event_type") or payload.get("type")
        return isinstance(evt, str) and evt in RECURRING_EVENT_TYPES

    # ── HTML Rendering Helpers ───────────────────────────────────────────

    @staticmethod
    def render_chain_selector(field_name: str, mode: str = "hosted") -> str:
        """
        Render chain selector radio buttons as HTML.

        Args:
            field_name: Form field name for the radio group
            mode:       'hosted' (3 chains) or 'extension' (2 chains)

        Returns:
            HTML string
        """
        chains = [
            ("algorand_mainnet", "Algorand", "USDC", "#3b82f6"),
            ("voi_mainnet", "VOI", "aUSDC", "#8b5cf6"),
        ]
        if mode == "hosted":
            chains.append(("hedera_mainnet", "Hedera", "USDC", "#00a9a5"))
            chains.append(("stellar_mainnet", "Stellar", "USDC", "#7C63D0"))

        name = escape(field_name)
        html = (
            '<div style="margin:.5rem 0;font-size:12px;color:#6b7280;font-weight:600;'
            'text-transform:uppercase;letter-spacing:.04em;">Select network</div>'
            '<div style="display:flex;gap:16px;flex-wrap:wrap;margin-bottom:.5rem;">'
        )
        for i, (value, label, ticker, colour) in enumerate(chains):
            checked = " checked" if i == 0 else ""
            html += (
                f'<label style="display:flex;align-items:center;gap:6px;cursor:pointer;font-size:13px;">'
                f'<input type="radio" name="{name}" value="{escape(value)}"{checked} '
                f'style="accent-color:{colour};">'
                f" {escape(label)} &mdash; {escape(ticker)}"
                f"</label>"
            )
        html += "</div>"
        return html

    @staticmethod
    def _safe_url_for_script(url: str) -> str:
        """
        Render a caller-supplied URL safe for embedding in a <script>
        block. Two layers of defence:

        1. URL must be http(s) with a hostname, OR a same-origin path
           starting with "/". Anything else (file://, javascript:, raw
           strings) is replaced with "/" — the caller's mistake won't
           silently turn into XSS.
        2. The JSON-stringified output has '</' escaped as '<\\/' so a
           pathological URL containing the literal '</script>' cannot
           break out of the surrounding <script> tag.
        """
        safe = "/"
        if isinstance(url, str) and url:
            if url.startswith("/") and not url.startswith("//"):
                safe = url
            else:
                p = urlparse(url)
                if p.scheme in ("http", "https") and p.hostname:
                    safe = url
        # Belt-and-suspenders: even after URL validation, neutralise </
        # so any future regression here can't reopen the XSS path.
        return json.dumps(safe).replace("</", "<\\/")

    @staticmethod
    def render_extension_payment_ui(
        payment_data: dict,
        verify_url: str,
        success_url: str,
    ) -> str:
        """
        Render the extension payment JavaScript UI as an HTML string.

        Args:
            payment_data: Return value from extension_checkout()
            verify_url:   Your server endpoint that calls verify_extension_payment()
            success_url:  URL to redirect to after successful payment

        Returns:
            HTML + JS block string

        SECURITY: verify_url and success_url are validated by
        _safe_url_for_script() — only http(s) URLs or absolute same-origin
        paths are honoured. Anything else (javascript:, file://, raw HTML)
        falls back to "/" rather than being injected into the page.
        """
        sa = escape(f"{payment_data['amount_display']} {payment_data['ticker']}")
        sc = escape("VOI" if "voi" in payment_data["chain"] else "Algorand")
        sco = escape(payment_data["checkout_url"])
        # Apply the </script>-safe encoder to every JS literal we embed,
        # not just the caller-supplied ones — defence-in-depth for the
        # day the gateway/scrape returns unexpected content.
        def _safe_js(value):
            return json.dumps(value).replace("</", "<\\/")
        jr = _safe_js(payment_data["receiver"])
        jm = _safe_js(payment_data["memo"])
        ja = _safe_js(payment_data["algod_url"])
        jv = AlgoVoi._safe_url_for_script(verify_url)
        js_ = AlgoVoi._safe_url_for_script(success_url)
        mu = payment_data["amount_mu"]
        aid = payment_data["asset_id"]

        return f"""<div id="av-ext-pay" style="max-width:520px;margin:2rem auto;padding:1.5rem 1.75rem;background:#1e2130;border:1px solid #2a2d3a;border-radius:12px;color:#f1f2f6;font-family:system-ui,sans-serif;">
  <div style="font-size:.68rem;font-weight:700;letter-spacing:.07em;text-transform:uppercase;color:#6b7280;margin-bottom:.85rem;">
    <span style="color:#3b82f6;">AlgoVoi</span> &middot; {sc} Extension Payment
  </div>
  <p style="margin:0 0 1.25rem;color:#9ca3af;font-size:.9rem;line-height:1.6;">
    Send <strong style="color:#10b981;">{sa}</strong> on <strong style="color:#f1f2f6;">{sc}</strong> via the AlgoVoi browser extension.
  </p>
  <div id="av-no-ext" style="display:none;margin-bottom:1rem;padding:.75rem 1rem;background:rgba(239,68,68,.1);border:1px solid rgba(239,68,68,.3);border-radius:8px;font-size:.85rem;color:#ef4444;">
    AlgoVoi extension not detected. <a href="{sco}" target="_blank" rel="noopener" style="color:#3b82f6;">Pay on hosted checkout &rarr;</a>
  </div>
  <div id="av-msg" style="display:none;margin-bottom:.85rem;padding:.65rem .9rem;border-radius:8px;font-size:.85rem;"></div>
  <button id="av-pay-btn" onclick="avPayWithExtension()"
    style="display:inline-flex;align-items:center;gap:.5rem;padding:.8rem 1.6rem;background:#3b82f6;color:#fff;border:none;border-radius:8px;font-size:.95rem;font-weight:600;cursor:pointer;">
    &#9889; Pay {sa} via Extension
  </button>
  <p style="margin:.85rem 0 0;font-size:.75rem;color:#6b7280;">
    No extension? <a href="{sco}" target="_blank" rel="noopener" style="color:#3b82f6;">Pay on hosted checkout</a> instead.
  </p>
</div>
<script src="https://cdn.jsdelivr.net/npm/algosdk@2/dist/browser/algosdk.min.js"></script>
<script>
(function(){{
  var AV={{receiver:{jr},memo:{jm},microunits:{mu},assetId:{aid},algodUrl:{ja},verifyUrl:{jv},successUrl:{js_}}};
  function showMsg(h,t){{var e=document.getElementById('av-msg');e.innerHTML=h;e.style.display='block';e.style.background=t==='ok'?'rgba(16,185,129,.1)':'rgba(239,68,68,.1)';e.style.border=t==='ok'?'1px solid rgba(16,185,129,.3)':'1px solid rgba(239,68,68,.3)';e.style.color=t==='ok'?'#10b981':'#ef4444';}}
  function setBtn(t,d){{var b=document.getElementById('av-pay-btn');if(!b)return;b.textContent=t;b.disabled=!!d;b.style.opacity=d?'.6':'1';}}
  function u8b64(a){{var s='';for(var i=0;i<a.length;i++)s+=String.fromCharCode(a[i]);return btoa(s);}}
  window.avPayWithExtension=async function(){{
    try{{
      setBtn('Connecting\\u2026',true);
      if(!window.algorand||!window.algorand.isAlgoVoi){{document.getElementById('av-no-ext').style.display='block';document.getElementById('av-pay-btn').style.display='none';return;}}
      setBtn('Fetching params\\u2026',true);
      var algodClient=new algosdk.Algodv2('',AV.algodUrl,'');
      var sp=await algodClient.getTransactionParams().do();
      setBtn('Connecting wallet\\u2026',true);
      var er=await window.algorand.enable({{genesisHash:sp.genesisHash}});
      if(!er.accounts||!er.accounts.length)throw new Error('No accounts returned.');
      var sender=er.accounts[0];
      setBtn('Building tx\\u2026',true);
      var nb=new TextEncoder().encode(AV.memo);
      var txn=algosdk.makeAssetTransferTxnWithSuggestedParamsFromObject({{from:sender,to:AV.receiver,assetIndex:AV.assetId,amount:AV.microunits,note:nb,suggestedParams:sp}});
      setBtn('Sign & send\\u2026',true);
      var res=await window.algorand.signAndSendTransactions({{txns:[{{txn:u8b64(txn.toByte())}}]}});
      if(!res.stxns||!res.stxns[0])throw new Error('No signed transaction returned.');
      var stxnBytes=Uint8Array.from(atob(res.stxns[0]),function(c){{return c.charCodeAt(0);}});
      setBtn('Submitting\\u2026',true);
      var submitResp=await fetch(AV.algodUrl+'/v2/transactions',{{method:'POST',headers:{{'Content-Type':'application/x-binary'}},body:stxnBytes}});
      var submitData=await submitResp.json();
      if(!submitResp.ok)throw new Error('Algod submission failed: '+(submitData.message||submitResp.status));
      var txId=submitData.txId;
      if(!txId)throw new Error('No txId in response.');
      setBtn('Waiting for confirmation\\u2026',true);
      var confirmed=0;
      for(var a=0;a<20;a++){{await new Promise(function(r){{setTimeout(r,3000);}});var pr=await fetch(AV.algodUrl+'/v2/transactions/pending/'+encodeURIComponent(txId));if(pr.status===404){{confirmed=1;break;}}var pd=await pr.json();if(pd['confirmed-round']&&pd['confirmed-round']>0){{confirmed=pd['confirmed-round'];break;}}if(pd['pool-error']&&pd['pool-error'].length>0)throw new Error('Transaction rejected: '+pd['pool-error']);}}
      if(!confirmed)throw new Error('Transaction not confirmed after timeout. TX: '+txId);
      await new Promise(function(r){{setTimeout(r,4000);}});
      setBtn('Verifying\\u2026',true);
      var vr=await fetch(AV.verifyUrl,{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{tx_id:txId}})}});
      var vd=await vr.json();
      if(vr.ok&&vd.success){{showMsg('\\u2713 Payment verified! Redirecting\\u2026','ok');setBtn('Paid \\u2713',true);setTimeout(function(){{location=AV.successUrl;}},2000);}}
      else{{throw new Error(vd.detail||vd.error||'Verification failed.');}}
    }}catch(err){{showMsg('&#9888; '+err.message,'err');setBtn('\\u26a1 Retry',false);}}
  }};
  window.addEventListener('load',function(){{setTimeout(function(){{if(!window.algorand||!window.algorand.isAlgoVoi)document.getElementById('av-no-ext').style.display='block';}},700);}});
}})();
</script>"""

    # ── Tier 2 — Standing-Authority Recurring Payments ───────────────────
    #
    # Tier 2 is "customer signs ONCE, AlgoVoi auto-pulls per cycle".
    # Tier 1 (above) is "customer clicks pay on every invoice".
    #
    # The lifecycle a tenant drives via these methods:
    #
    #   1. Tenant creates a Tier 1 subscription (either via the dashboard
    #      or POST /v1/subscriptions — out of scope of this adapter).
    #   2. Tenant calls create_recurring_authority(...) — gateway returns
    #      `customer_signing_payload`, a chain-specific template.
    #   3. Tenant's frontend hands the template to the customer's wallet
    #      (Pera / Defly / MetaMask / Phantom / HashPack / Freighter / etc.)
    #      which constructs + signs the on-chain authorisation.
    #   4. Once the on-chain transaction lands, tenant calls
    #      confirm_authority(authority_id, on_chain_address=...) to
    #      transition the row to status='active' (or AlgoVoi's webhook
    #      handler does this for tenants using the hosted widget).
    #   5. AlgoVoi's cycle reaper auto-pulls per cap_period_seconds.
    #      Each pull emits subscription.charged / subscription.payment_failed
    #      webhooks the tenant handles via verify_webhook(...).
    #   6. To stop: revoke_authority(id) — gateway constructs the revocation
    #      transaction. To pause/resume without on-chain action: pause/resume.
    #
    # All methods return the parsed JSON response on success, or None on
    # failure (mirrors the Tier 1 pattern). For granular error inspection
    # use _request_with_status(...) which returns (data, http_code).

    def create_recurring_authority(
        self,
        subscription_id: str,
        chain: str,
        customer_wallet_address: str,
        cap_amount_minor: int,
        cap_period_seconds: int,
        per_cycle_amount_minor: int,
        asset: str = "USDC",
        metadata: Optional[dict] = None,
    ) -> Optional[dict]:
        """
        Create a Tier 2 standing authority for an existing subscription.

        Args:
            subscription_id:        UUID of the Tier 1 subscription this
                                    authority is bound to.
            chain:                  One of RECURRING_NETWORKS.
            customer_wallet_address: The customer's chain-native address
                                    (Algorand 58-char base32, EVM 0x-prefix
                                    hex, Solana base58, Hedera 0.0.X,
                                    Stellar G-address).
            cap_amount_minor:       Total spend cap over cap_period_seconds,
                                    in chain-native atomic units (e.g. 6
                                    decimals for USDC on most chains; 7 on
                                    Stellar). Cannot be exceeded even with
                                    multiple pulls.
            cap_period_seconds:     Cap window length. Must be >= 86400.
                                    Typical: 365 * 86400 for annual.
            per_cycle_amount_minor: Per-pull cap. Each cycle pulls at most
                                    this much.
            asset:                  Asset symbol — "USDC" by default.
                                    Native coins (VOI / HBAR / XLM / ETH /
                                    SOL) supported on a per-chain basis.
            metadata:               Free-form tenant metadata (forwarded
                                    on every webhook event).

        Returns:
            dict with keys:
                'authority': server-recorded row (id, status='pending', etc.)
                'customer_signing_payload': chain-specific template the
                    customer's wallet signs to land the on-chain
                    authorisation. Hand this to your frontend wallet UI.
                'authorisation_url': optional hosted-page URL (some chains
                    use this; others return None and you render the wallet
                    UI yourself).
            None on failure.
        """
        if chain not in RECURRING_NETWORKS:
            return None
        if not isinstance(subscription_id, str) or len(subscription_id) > MAX_UUID_LEN:
            return None
        if not isinstance(customer_wallet_address, str) or not customer_wallet_address:
            return None
        # Atomic-unit amounts must be positive integers in i64 range
        for label, value in (
            ("cap_amount_minor", cap_amount_minor),
            ("cap_period_seconds", cap_period_seconds),
            ("per_cycle_amount_minor", per_cycle_amount_minor),
        ):
            if not isinstance(value, int) or value <= 0:
                return None
        if cap_period_seconds < 86400:
            return None  # gateway enforces same lower bound
        if per_cycle_amount_minor > cap_amount_minor:
            return None  # per-cycle can't exceed total cap

        body: dict[str, Any] = {
            "subscription_id":        subscription_id,
            "chain":                  chain,
            "customer_wallet_address": customer_wallet_address,
            "cap_amount_minor":       cap_amount_minor,
            "cap_period_seconds":     cap_period_seconds,
            "per_cycle_amount_minor": per_cycle_amount_minor,
            "asset":                  asset.upper(),
        }
        if metadata is not None:
            if not isinstance(metadata, dict):
                return None
            body["metadata"] = metadata
        return self._post("/v1/recurring/authorities", body)

    def get_authority(self, authority_id: str) -> Optional[dict]:
        """
        Fetch the current state of a recurring authority by id.

        Returns the authority row with status, on_chain_address (once
        active), cap_remaining_minor, cycles_pulled, cycles_failed,
        last_error, etc. None on failure.
        """
        if not isinstance(authority_id, str) or len(authority_id) > MAX_UUID_LEN:
            return None
        return self._request("GET", f"/v1/recurring/authorities/{quote(authority_id, safe='')}")

    def list_authorities(
        self,
        subscription_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Optional[list]:
        """
        List recurring authorities for this tenant. Optionally filter by
        subscription_id or status (one of: pending / active / paused /
        revoking / revoked / expired).

        Returns a list of authority rows (possibly empty), or None on failure.
        """
        if limit < 1 or limit > 200 or offset < 0:
            return None
        params = [f"limit={int(limit)}", f"offset={int(offset)}"]
        if subscription_id:
            if not isinstance(subscription_id, str) or len(subscription_id) > MAX_UUID_LEN:
                return None
            params.append(f"subscription_id={quote(subscription_id, safe='')}")
        if status:
            if not isinstance(status, str) or len(status) > 32 or not status.replace("_", "").isalnum():
                return None
            params.append(f"status={quote(status, safe='')}")
        path = "/v1/recurring/authorities?" + "&".join(params)
        result = self._request("GET", path)
        if isinstance(result, list):
            return result
        return None

    def confirm_authority(
        self,
        authority_id: str,
        on_chain_address: str,
        first_cycle_due_at: Optional[str] = None,
    ) -> Optional[dict]:
        """
        Mark a pending authority active after on-chain landing.

        Args:
            authority_id:       UUID returned by create_recurring_authority.
            on_chain_address:   Chain-native identifier of the landed auth
                                (e.g. 'app:<application_id>' on Algorand /
                                VOI, '0x<tx_hash>' on EVM, base58 sig on
                                Solana, '<tx_id>' on Hedera, 64-char hex
                                tx hash on Stellar).
            first_cycle_due_at: ISO8601 timestamp for the first cycle pull.
                                Defaults to now + cap_period_seconds /
                                expected-cycles if omitted.

        Most tenants don't need to call this directly — the AlgoVoi widget
        and webhook flow drives it. Surfaced here for tenants who land
        signed transactions out-of-band.
        """
        if not isinstance(authority_id, str) or len(authority_id) > MAX_UUID_LEN:
            return None
        if not isinstance(on_chain_address, str) or not on_chain_address:
            return None
        if len(on_chain_address) > 200:
            return None  # defensive cap on chain-native ids
        body: dict[str, Any] = {"on_chain_address": on_chain_address}
        if first_cycle_due_at is not None:
            if not isinstance(first_cycle_due_at, str) or len(first_cycle_due_at) > 64:
                return None
            body["first_cycle_due_at"] = first_cycle_due_at
        return self._post(
            f"/v1/recurring/authorities/{quote(authority_id, safe='')}/confirm",
            body,
        )

    def revoke_authority(self, authority_id: str) -> Optional[dict]:
        """
        Revoke an active authority. Gateway constructs the chain-specific
        revocation transaction; the customer's wallet signs it.

        Authority transitions to status='revoking' until the on-chain
        revocation lands, then 'revoked'. Returns the updated authority row.
        """
        if not isinstance(authority_id, str) or len(authority_id) > MAX_UUID_LEN:
            return None
        return self._post(
            f"/v1/recurring/authorities/{quote(authority_id, safe='')}/revoke",
            {},
        )

    def pause_authority(self, authority_id: str) -> Optional[dict]:
        """
        Pause an active authority — no chain action. Stops cycle pulls
        until resume_authority(...) is called. Useful for billing holds /
        manual review.
        """
        if not isinstance(authority_id, str) or len(authority_id) > MAX_UUID_LEN:
            return None
        return self._post(
            f"/v1/recurring/authorities/{quote(authority_id, safe='')}/pause",
            {},
        )

    def resume_authority(
        self,
        authority_id: str,
        next_cycle_due_at: Optional[str] = None,
    ) -> Optional[dict]:
        """
        Resume a paused authority. Optionally specify next_cycle_due_at
        (ISO8601) to delay the first post-resume pull; otherwise pulls
        resume immediately on the existing schedule.
        """
        if not isinstance(authority_id, str) or len(authority_id) > MAX_UUID_LEN:
            return None
        body: dict[str, Any] = {}
        if next_cycle_due_at is not None:
            if not isinstance(next_cycle_due_at, str) or len(next_cycle_due_at) > 64:
                return None
            body["next_cycle_due_at"] = next_cycle_due_at
        return self._post(
            f"/v1/recurring/authorities/{quote(authority_id, safe='')}/resume",
            body,
        )

    def manual_pull(
        self,
        authority_id: str,
        amount_minor: int,
        idempotency_key: Optional[str] = None,
    ) -> Optional[dict]:
        """
        Manually trigger a pull (e.g. catch-up after error escalation,
        prorated mid-cycle billing). Most pulls fire automatically via
        the cycle reaper — tenants don't need to call this in normal use.

        Args:
            authority_id:    UUID of an active authority.
            amount_minor:    Pull amount in atomic units. Must be
                             <= per_cycle_amount_minor of the authority.
            idempotency_key: Optional client-supplied key for retry safety.

        Returns the updated authority row (with cycles_pulled incremented
        on success). HTTP 202 — the chain submission is async.
        """
        if not isinstance(authority_id, str) or len(authority_id) > MAX_UUID_LEN:
            return None
        if not isinstance(amount_minor, int) or amount_minor <= 0:
            return None
        body: dict[str, Any] = {
            "authority_id": authority_id,
            "amount_minor": amount_minor,
        }
        if idempotency_key is not None:
            if not isinstance(idempotency_key, str) or len(idempotency_key) > 128:
                return None
            body["idempotency_key"] = idempotency_key
        return self._post("/v1/recurring/pulls", body)

    # ── Internal Helpers ─────────────────────────────────────────────────

    def _request(self, method: str, path: str, data: Optional[dict] = None) -> Any:
        """
        Generic JSON HTTPS request to the AlgoVoi API.

        Returns parsed JSON on 2xx. Returns None on any non-2xx, network
        error, or JSON-decode error — mirrors _post's failure mode so
        Tier 2 methods compose with the same caller-side null check.

        Used by Tier 2 methods that need GET (list / get) on top of the
        existing POST helpers.
        """
        if method not in ("GET", "POST", "DELETE"):
            return None
        if not self.api_base.startswith("https://"):
            return None
        body = json.dumps(data).encode() if data is not None else None
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "X-Tenant-Id": self.tenant_id,
        }
        if body is not None:
            headers["Content-Type"] = "application/json"
        req = Request(
            f"{self.api_base}{path}",
            data=body,
            method=method,
            headers=headers,
        )
        try:
            with urlopen(req, timeout=self.timeout, context=self._ssl_ctx) as resp:  # nosec B310
                if resp.status < 200 or resp.status >= 300:
                    return None
                # Cap response body — Tier 2 list responses are bounded by
                # gateway's limit=200, but defence-in-depth.
                raw = resp.read(MAX_RECURRING_BODY_BYTES + 1)
                if len(raw) > MAX_RECURRING_BODY_BYTES:
                    return None
                return json.loads(raw)
        except (URLError, json.JSONDecodeError, OSError):
            return None

    def _post(self, path: str, data: dict) -> Optional[dict]:
        """POST JSON to the AlgoVoi API with authentication."""
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
            with urlopen(req, timeout=self.timeout, context=self._ssl_ctx) as resp:  # nosec B310
                if resp.status < 200 or resp.status >= 300:
                    return None
                return json.loads(resp.read())
        except (URLError, json.JSONDecodeError, OSError):
            return None

    def _post_raw(self, url: str, data: dict) -> dict:
        """POST JSON to an arbitrary URL, returning response with _http_code."""
        if not url.startswith("https://"):
            return {"_http_code": 400}
        body = json.dumps(data).encode()
        req = Request(
            url,
            data=body,
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        try:
            with urlopen(req, timeout=self.timeout, context=self._ssl_ctx) as resp:  # nosec B310
                result = json.loads(resp.read())
                result["_http_code"] = resp.status
                return result
        except URLError as e:
            code = getattr(e, "code", 502) if hasattr(e, "code") else 502
            try:
                body_data = json.loads(e.read()) if hasattr(e, "read") else {}
            except Exception:
                body_data = {}
            body_data["_http_code"] = code
            return body_data
        except (json.JSONDecodeError, OSError):
            return {"error": "Request failed", "_http_code": 502}

    def _scrape_checkout(self, checkout_url: str) -> Optional[dict]:
        """Fetch checkout page and extract receiver + memo with SSRF guard."""
        api_host = urlparse(self.api_base).hostname
        checkout_host = urlparse(checkout_url).hostname
        if not api_host or checkout_host != api_host:
            return None

        try:
            req = Request(checkout_url, method="GET")
            with urlopen(req, timeout=15, context=self._ssl_ctx) as resp:  # nosec B310
                html = resp.read().decode("utf-8", errors="replace")
        except (URLError, OSError):
            return None

        receiver = memo = ""
        m = re.search(r'<div[^>]+id=["\']addr["\'][^>]*>([A-Z2-7]{58})<', html)
        if m:
            receiver = m.group(1)
        m = re.search(r'<div[^>]+id=["\']memo["\'][^>]*>(algovoi:[^<]+)<', html)
        if m:
            memo = m.group(1).strip()

        if not receiver or not memo:
            return None
        return {"receiver": receiver, "memo": memo}
