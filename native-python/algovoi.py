"""
AlgoVoi Native Python Payment Adapter

Single-file drop-in for any Python application. No framework required.
Works with Flask, Django, FastAPI, or plain WSGI/ASGI.

Supports:
  - Hosted checkout (Algorand, VOI, Hedera) — redirect to AlgoVoi payment page
  - Extension payment (Algorand, VOI) — in-page wallet flow via algosdk
  - Webhook verification with HMAC
  - SSRF protection on checkout URL fetches
  - Cancel-bypass prevention on hosted return

Usage:
    from algovoi import AlgoVoi

    av = AlgoVoi(
        api_base='https://api1.ilovechicken.co.uk',
        api_key='algv_...',
        tenant_id='uuid',
        webhook_secret='your_secret',
    )

AlgoVoi docs: https://github.com/chopmob-cloud/AlgoVoi-Platform-Adapters
Copyright (c) 2026 Christopher Hopley (ilovechicken.co.uk). BSL 1.1.

Version: 1.0.0
"""

from __future__ import annotations

import hashlib
import hmac
import json
import re
import ssl
from base64 import b64encode
from html import escape
from typing import Any, Optional
from urllib.parse import quote, urlparse
from urllib.request import Request, urlopen
from urllib.error import URLError

__version__ = "1.0.0"

ALGOD = {
    "algorand-mainnet": {"url": "https://mainnet-api.algonode.cloud", "asset_id": 31566704, "ticker": "USDC", "dec": 6},
    "voi-mainnet":      {"url": "https://mainnet-api.voi.nodely.io",  "asset_id": 302190,   "ticker": "aUSDC", "dec": 6},
}

HOSTED_NETWORKS = {
    "algorand_mainnet", "voi_mainnet", "hedera_mainnet",
    "stellar_mainnet",
}
EXT_NETWORKS = {"algorand_mainnet", "voi_mainnet"}


class AlgoVoi:
    """AlgoVoi payment adapter — zero dependencies beyond the standard library."""

    def __init__(
        self,
        api_base: str = "https://api1.ilovechicken.co.uk",
        api_key: str = "",
        tenant_id: str = "",
        webhook_secret: str = "",
        timeout: int = 30,
    ):
        self.api_base = api_base.rstrip("/")
        self.api_key = api_key
        self.tenant_id = tenant_id
        self.webhook_secret = webhook_secret
        self.timeout = timeout
        self._ssl_ctx = ssl.create_default_context()

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
        payload: dict[str, Any] = {
            "amount": round(amount, 2),
            "currency": currency.upper(),
            "label": label,
            "preferred_network": network,
        }
        if redirect_url:
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

        url = f"{self.api_base}/checkout/{quote(token, safe='')}"
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
        algod = ALGOD.get(chain, ALGOD["algorand-mainnet"])

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
            token: The checkout token
            tx_id: The on-chain transaction ID

        Returns:
            API response dict — check for 'success' key
        """
        if not token or not tx_id or len(tx_id) > 200:
            return {"error": "Invalid parameters", "_http_code": 400}

        url = f"{self.api_base}/checkout/{quote(token, safe='')}/verify"
        return self._post_raw(url, {"tx_id": tx_id})

    # ── Webhook Handling ─────────────────────────────────────────────────

    def verify_webhook(self, raw_body: bytes, signature: str) -> Optional[dict]:
        """
        Verify and parse an incoming webhook request.

        Args:
            raw_body:  The raw POST body as bytes
            signature: The X-AlgoVoi-Signature header value

        Returns:
            Parsed webhook payload dict, or None if verification fails
        """
        if not self.webhook_secret:
            return None  # Reject if secret not configured

        expected = b64encode(
            hmac.new(
                self.webhook_secret.encode(),
                raw_body,
                hashlib.sha256,
            ).digest()
        ).decode()

        if not hmac.compare_digest(expected, signature):
            return None

        try:
            return json.loads(raw_body)
        except json.JSONDecodeError:
            return None

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
        """
        sa = escape(f"{payment_data['amount_display']} {payment_data['ticker']}")
        sc = escape("VOI" if "voi" in payment_data["chain"] else "Algorand")
        sco = escape(payment_data["checkout_url"])
        jr = json.dumps(payment_data["receiver"])
        jm = json.dumps(payment_data["memo"])
        ja = json.dumps(payment_data["algod_url"])
        jv = json.dumps(verify_url)
        js_ = json.dumps(success_url)
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

    # ── Internal Helpers ─────────────────────────────────────────────────

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
