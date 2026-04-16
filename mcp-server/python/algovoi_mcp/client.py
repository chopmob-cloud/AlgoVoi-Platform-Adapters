"""
Thin urllib-based AlgoVoi HTTP client — mirrors the fetch-based TypeScript
client and the existing native-python/algovoi.py adapter.

Stdlib only (urllib, json, re, ssl) — no requests, no httpx, so the MCP
package installs with zero extra transitive deps beyond `mcp` itself.
"""

from __future__ import annotations

import json
import re
import ssl
from typing import Any, Optional
from urllib.parse import quote, urlparse
from urllib.request import Request, urlopen
from urllib.error import URLError


class AlgoVoiClient:
    """HTTP client used by every MCP tool that hits the AlgoVoi API."""

    def __init__(
        self,
        api_base: str,
        api_key: str,
        tenant_id: str,
        payout_address: str,
        timeout: int = 30,
    ) -> None:
        if not api_base.startswith("https://"):
            raise ValueError("api_base must be an https:// URL")
        self.api_base       = api_base.rstrip("/")
        self.api_key        = api_key
        self.tenant_id      = tenant_id
        self.payout_address = payout_address
        self.timeout        = timeout
        self._ssl_ctx       = ssl.create_default_context()

    # ── HTTP primitives ────────────────────────────────────────────────────

    def _post(self, path: str, body: dict) -> dict:
        req = Request(
            self.api_base + path,
            data=json.dumps(body).encode(),
            method="POST",
            headers={
                "Content-Type":  "application/json",
                "Authorization": f"Bearer {self.api_key}",
                "X-Tenant-Id":   self.tenant_id,
            },
        )
        try:
            with urlopen(req, timeout=self.timeout, context=self._ssl_ctx) as resp:  # noqa: S310
                data = json.loads(resp.read())
                return data if isinstance(data, dict) else {"raw": data}
        except URLError as e:
            raise RuntimeError(f"AlgoVoi API {path} failed: {e}") from e
        except (json.JSONDecodeError, OSError) as e:
            raise RuntimeError(f"AlgoVoi API {path} returned invalid JSON: {e}") from e

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
            raise RuntimeError(f"AlgoVoi API {path} failed: {e}") from e
        except (json.JSONDecodeError, OSError) as e:
            raise RuntimeError(f"AlgoVoi API {path} returned invalid JSON: {e}") from e

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
    ) -> dict:
        """Create a hosted-checkout payment link."""
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
        resp = self._post("/v1/payment-links", payload)
        if not resp.get("checkout_url"):
            raise RuntimeError("API did not return checkout_url")
        return resp

    def verify_hosted_return(self, token: str) -> dict:
        """Call the hosted-checkout status endpoint."""
        if not token or len(token) > 200:
            return {"status": "invalid_token", "paid": False, "raw": {}}
        url = f"{self.api_base}/checkout/{quote(token, safe='')}"
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
        """Verify an MPP on-chain receipt."""
        return self._post(
            f"/mpp/{quote(resource_id, safe='')}",
            {"tx_id": tx_id, "network": network, "tenant_id": self.tenant_id},
        )

    def verify_x402_proof(self, proof: str, network: str) -> dict:
        """Verify an x402 base64-encoded proof."""
        return self._post(
            "/x402/verify",
            {"proof": proof, "network": network, "tenant_id": self.tenant_id},
        )

    @staticmethod
    def extract_token(checkout_url: str) -> str:
        """Extract the short token from a checkout URL."""
        m = re.search(r"/checkout/([A-Za-z0-9_-]+)$", checkout_url)
        return m.group(1) if m else ""
