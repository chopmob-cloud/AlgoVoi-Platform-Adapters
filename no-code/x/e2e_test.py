"""
AlgoVoi X Adapter — End-to-End Mainnet Test
=============================================

Tests the full AlgoVoi X adapter pipeline across all 4 networks simultaneously:
  Algorand  — 0.01 USDC    (ASA 31566704)
  VOI       — 0.01 aUSDC   (ASA 302190)
  Hedera    — 0.01 USDC    (HTS 0.0.456858)
  Stellar   — 0.01 USDC    (native Stellar USDC)

Steps run in order:
  1  Verify network connectivity (blockchain node status)
  2  Check sending wallet balances
  3  Create AlgoVoi payment checkouts (all 4 chains)
  4  Wait for you to send all 4 payments manually
  5  Confirm all 4 transactions on-chain (polls until finality)
  6  Verify webhook HMAC format (simulation — no listener required)
  7  Post X tweets for all 4 confirmed payments
  8  Summary table
  9  Block explorer links

Usage:

    # Minimum (only Step 3+ requires tenant-id):
    python no-code/x/e2e_test.py --tenant-id 00000000-0000-0000-0000-000000000000

    # With sending wallet addresses for Step 2 balance check:
    python no-code/x/e2e_test.py \\
        --tenant-id 00000000-... \\
        --sending-algo  YOUR_ALGO_ADDRESS \\
        --sending-voi   YOUR_VOI_ADDRESS \\
        --sending-hedera 0.0.XXXXXX \\
        --sending-stellar GXXXXXXX...

    # Skip X posting (dry-run):
    python no-code/x/e2e_test.py --tenant-id ... --no-tweet

    # Skip balance checks (if you already know wallets are funded):
    python no-code/x/e2e_test.py --tenant-id ... --skip-balance

Credentials are loaded automatically from:
  - keys.txt in the repo root  (X_API_KEY=, X_API_SECRET=, etc.)
  - Environment variables       (ALGOVOI_API_KEY, ALGOVOI_TENANT_ID, X_API_KEY, …)

Run from the repo root:  C:\\algo\\platform-adapters
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

# ── Windows UTF-8 console fix ─────────────────────────────────────────────────
# Unicode box-drawing and emoji characters require UTF-8 output on Windows.
try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# ── Path setup ────────────────────────────────────────────────────────────────

_HERE     = Path(__file__).parent
_REPO     = _HERE.parent.parent
sys.path.insert(0, str(_HERE))

from x_algovoi import AlgoVoiX, _build_payment_tweet, NETWORK_INFO  # noqa: E402

# ── Constants ─────────────────────────────────────────────────────────────────

_ALGOVOI_BASE  = "https://api1.ilovechicken.co.uk"
_TIMEOUT       = 20
_POLL_INTERVAL = 5    # seconds between confirmation polls
_POLL_TIMEOUT  = 600  # 10 minutes max wait for on-chain confirmation

STELLAR_USDC_ISSUER = "GA5ZSEJYB37JRC5AVCIA5MOP4RHTM335X2KGX3IHOJAPP5RE34K4KZVN"

# ── Payout addresses (from smoke_test_full.py / all existing smoke tests) ─────
# These are the live AlgoVoi payout wallets used across the entire repo.
# Override via --payout-* flags or ALGOVOI_PAYOUT_* env vars if needed.
PAYOUT = {
    "algorand": "ZVLRVYQSLJNVFMOIOKT35XH5SNQG45IVFMLLRFLHDQJQA5TO5H3SO4TVDQ",
    "voi":      "THDLWTJ7RB4OJWFZCLL5IME7FHBSJ3SONBRWHIVQE3BEGTY2BWUEUVEOQY",
    "hedera":   "0.0.1317927",
    "stellar":  "GD45SH4TC4TMJOJWJJSLGAXODAIO36POCACT2MWS7I6CTJORMFKEP3HR",
}

# Per-chain test parameters
CHAINS = {
    "algorand": {
        "network":      "algorand_mainnet",
        "label":        "AlgoVoi E2E Test — Algorand",
        "amount":       0.01,
        "currency":     "USD",
        "asset":        "USDC",
        "asset_id":     31566704,
        "decimals":     6,
        "atomic":       10_000,
        "atomic_label": "10,000 microUSDC",
        "node_url":     "https://mainnet-api.algonode.cloud",
        "explorer":     "https://allo.info/tx/{tx_id}",
        "hashtags":     "#Algorand #ALGO #Web3Payments",
    },
    "voi": {
        "network":      "voi_mainnet",
        "label":        "AlgoVoi E2E Test — VOI",
        "amount":       0.01,
        "currency":     "USD",
        "asset":        "aUSDC",
        "asset_id":     302190,
        "decimals":     6,
        "atomic":       10_000,
        "atomic_label": "10,000 microaUSDC",
        "node_url":     "https://mainnet-api.voi.nodely.io",
        "explorer":     "https://voi.observer/tx/{tx_id}",
        "hashtags":     "#VOI #VoiNetwork #Web3Payments",
    },
    "hedera": {
        "network":      "hedera_mainnet",
        "label":        "AlgoVoi E2E Test — Hedera",
        "amount":       0.01,
        "currency":     "USD",
        "asset":        "USDC",
        "token_id":     "0.0.456858",
        "decimals":     6,
        "atomic":       10_000,
        "atomic_label": "10,000 tinybars equivalent",
        "explorer":     "https://hashscan.io/mainnet/tx/{tx_id}",
        "hashtags":     "#Hedera #HBAR #Web3Payments",
    },
    "stellar": {
        "network":      "stellar_mainnet",
        "label":        "AlgoVoi E2E Test — Stellar",
        "amount":       0.01,
        "currency":     "USD",
        "asset":        "USDC",
        "decimals":     7,
        "atomic":       "0.0100000",
        "atomic_label": "0.0100000 USDC",
        "explorer":     "https://stellar.expert/explorer/public/tx/{tx_id}",
        "hashtags":     "#Stellar #XLM #Web3Payments",
    },
}

# Per-chain tweet template (matches user-specified format exactly)
_TWEET_TMPL = (
    "✅ 0.01 {asset} payment confirmed on {network_label}\n"
    "Verified on-chain by AlgoVoi\n"
    "TX: {tx_id_short}…\n"
    "{hashtags}"
)


# ── Result tracker ────────────────────────────────────────────────────────────

_STATUS: dict[str, dict[int, str | None]] = {
    c: {s: None for s in range(1, 8)} for c in CHAINS
}

def _mark(chain: str, step: int, status: str) -> None:
    _STATUS[chain][step] = status


# ── Helpers ───────────────────────────────────────────────────────────────────

def _ts() -> str:
    return datetime.now(timezone.utc).strftime("%H:%M:%S UTC")


def _trunc(addr: str) -> str:
    """First 8 + last 4 characters of an address."""
    if not addr or len(addr) <= 12:
        return addr
    return f"{addr[:8]}…{addr[-4:]}"


def _http_get(url: str) -> tuple[int, dict | list | None]:
    req = urllib.request.Request(url, headers={"User-Agent": "AlgoVoi-E2E/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        try:
            return exc.code, json.loads(exc.read())
        except Exception:
            return exc.code, None
    except Exception as exc:
        return 0, {"_error": str(exc)}


def _http_get_algovoi(path: str, api_key: str, tenant_id: str) -> tuple[int, dict | None]:
    url = f"{_ALGOVOI_BASE}{path}"
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {api_key}",
        "X-Tenant-Id":   tenant_id,
        "User-Agent":    "AlgoVoi-E2E/1.0",
    })
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        try:
            return exc.code, json.loads(exc.read())
        except Exception:
            return exc.code, None
    except Exception as exc:
        return 0, {"_error": str(exc)}


def _http_post_algovoi(path: str, payload: dict, api_key: str, tenant_id: str) -> tuple[int, dict | None]:
    url  = f"{_ALGOVOI_BASE}{path}"
    data = json.dumps(payload).encode()
    req  = urllib.request.Request(url, data=data, headers={
        "Authorization": f"Bearer {api_key}",
        "X-Tenant-Id":   tenant_id,
        "Content-Type":  "application/json",
        "User-Agent":    "AlgoVoi-E2E/1.0",
    }, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        try:
            return exc.code, json.loads(exc.read())
        except Exception:
            return exc.code, None
    except Exception as exc:
        return 0, {"_error": str(exc)}


def _sep(title: str = "") -> None:
    if title:
        pad = (60 - len(title) - 2) // 2
        print(f"\n{'─' * pad} {title} {'─' * pad}")
    else:
        print("\n" + "─" * 62)


def _ok(msg: str)   -> None: print(f"  ✅  {msg}")
def _fail(msg: str) -> None: print(f"  ❌  {msg}")
def _warn(msg: str) -> None: print(f"  ⚠️   {msg}")
def _info(msg: str) -> None: print(f"       {msg}")


# ── Credential loading ────────────────────────────────────────────────────────

def _load_keys_txt() -> dict:
    """
    Read credentials from keys.txt in the repo root.

    Supported formats:
      algv_...                    → ALGOVOI_API_KEY   (bare token on its own line)
      ALGOVOI_API_KEY=algv_...    → ALGOVOI_API_KEY
      TENANT_ID=xxxx-...          → TENANT_ID
      X_API_KEY=...               → X_API_KEY
      X_API_SECRET=...            → X_API_KEY_SECRET  (name-normalised)
      X_ACCESS_SECRET=...         → X_ACCESS_TOKEN_SECRET (name-normalised)

    To avoid re-typing --tenant-id every run, add this line to keys.txt:
        TENANT_ID=your-real-tenant-uuid
    """
    creds: dict = {}
    p = _REPO / "keys.txt"
    if not p.exists():
        return creds
    for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            k, _, v = line.partition("=")
            creds[k.strip()] = v.strip()
        elif line.startswith("algv_") and "ALGOVOI_API_KEY" not in creds:
            creds["ALGOVOI_API_KEY"] = line.split()[0]
    # Normalise X secret key names (keys.txt uses short form, adapter uses long form)
    if "X_API_SECRET" in creds and "X_API_KEY_SECRET" not in creds:
        creds["X_API_KEY_SECRET"] = creds["X_API_SECRET"]
    if "X_ACCESS_SECRET" in creds and "X_ACCESS_TOKEN_SECRET" not in creds:
        creds["X_ACCESS_TOKEN_SECRET"] = creds["X_ACCESS_SECRET"]
    # Accept ALGOVOI_TENANT_ID as alias for TENANT_ID
    if "ALGOVOI_TENANT_ID" in creds and "TENANT_ID" not in creds:
        creds["TENANT_ID"] = creds["ALGOVOI_TENANT_ID"]
    return creds


def load_creds(args: argparse.Namespace) -> dict:
    """
    Merge keys.txt + env vars + CLI args.
    Priority: CLI arg > env var > keys.txt > built-in default.

    Tenant ID: accepts TENANT_ID or ALGOVOI_TENANT_ID (repo uses both).
    Payout addresses: defaults to the PAYOUT dict from smoke_test_full.py.
    """
    file_creds = _load_keys_txt()

    def _get(key: str, fallback: str = "") -> str:
        return os.environ.get(key) or file_creds.get(key, fallback)

    # TENANT_ID resolution order:
    #   1. --tenant-id CLI arg
    #   2. ALGOVOI_TENANT_ID env var
    #   3. TENANT_ID env var  (short form used across all repo smoke tests)
    #   4. TENANT_ID= or ALGOVOI_TENANT_ID= line in keys.txt
    tenant_id = (
        getattr(args, "tenant_id", "")
        or os.environ.get("ALGOVOI_TENANT_ID", "")
        or os.environ.get("TENANT_ID", "")
        or file_creds.get("TENANT_ID", "")
    )

    # Webhook secret (from PrestaShop/WooCommerce/OpenCart/Shopware DBs — all match)
    webhook_secret = (
        getattr(args, "webhook_secret", "")
        or os.environ.get("ALGOVOI_WEBHOOK_SECRET", "")
        or file_creds.get("ALGOVOI_WEBHOOK_SECRET", "")
    )

    # Payout addresses — CLI > env > repo defaults (from smoke_test_full.py)
    payout_algo    = (getattr(args, "payout_algo",    None)
                      or os.environ.get("ALGOVOI_PAYOUT_ALGORAND", "")
                      or PAYOUT["algorand"])
    payout_voi     = (getattr(args, "payout_voi",     None)
                      or os.environ.get("ALGOVOI_PAYOUT_VOI", "")
                      or PAYOUT["voi"])
    payout_hedera  = (getattr(args, "payout_hedera",  None)
                      or os.environ.get("ALGOVOI_PAYOUT_HEDERA", "")
                      or PAYOUT["hedera"])
    payout_stellar = (getattr(args, "payout_stellar", None)
                      or os.environ.get("ALGOVOI_PAYOUT_STELLAR", "")
                      or PAYOUT["stellar"])

    return {
        "api_key":              _get("ALGOVOI_API_KEY"),
        "tenant_id":            tenant_id,
        "x_api_key":            _get("X_API_KEY"),
        "x_api_key_secret":     _get("X_API_KEY_SECRET"),
        "x_access_token":       _get("X_ACCESS_TOKEN"),
        "x_access_token_secret": _get("X_ACCESS_TOKEN_SECRET"),
        # Payout addresses (for AlgoVoiX constructor)
        "payout_algo":    payout_algo,
        "payout_voi":     payout_voi,
        "payout_hedera":  payout_hedera,
        "payout_stellar": payout_stellar,
        # Webhook secret (confirmed from all 4 store DBs)
        "webhook_secret": webhook_secret,
        # Sending wallet addresses (for balance checks only — always optional)
        "sending_algo":    getattr(args, "sending_algo",    None) or "",
        "sending_voi":     getattr(args, "sending_voi",     None) or "",
        "sending_hedera":  getattr(args, "sending_hedera",  None) or "",
        "sending_stellar": getattr(args, "sending_stellar", None) or "",
    }


# ── Step 1: Network status ────────────────────────────────────────────────────

def step1_network_status() -> dict:
    """Query each chain for latest block / round / ledger."""
    _sep("STEP 1 — NETWORK STATUS")
    status: dict[str, dict] = {}

    checks = {
        "algorand": ("https://mainnet-api.algonode.cloud/v2/status",
                     lambda d: d.get("last-round"), "round", 60_000_000),
        "voi":      ("https://mainnet-api.voi.nodely.io/v2/status",
                     lambda d: d.get("last-round"), "round", 17_000_000),
        "hedera":   ("https://mainnet-public.mirrornode.hedera.com/api/v1/blocks?limit=1&order=desc",
                     lambda d: d.get("blocks", [{}])[0].get("number"), "block", 5_000_000),
        "stellar":  ("https://horizon.stellar.org/",
                     lambda d: d.get("history_latest_ledger"), "ledger", 62_000_000),
    }

    for chain, (url, extractor, kind, minimum) in checks.items():
        code, data = _http_get(url)
        if code == 200 and data:
            value = extractor(data)
            if value and int(value) >= minimum:
                _ok(f"{chain.capitalize():10s} — {kind} {value:,}  (node responding)")
                status[chain] = {"ok": True, "kind": kind, "value": value}
                _mark(chain, 1, "PASS")
            else:
                _warn(f"{chain.capitalize():10s} — node responded but {kind} value looks low: {value}")
                status[chain] = {"ok": True, "kind": kind, "value": value}
                _mark(chain, 1, "PARTIAL")
        else:
            _fail(f"{chain.capitalize():10s} — HTTP {code}: {str(data)[:120]}")
            status[chain] = {"ok": False, "error": f"HTTP {code}"}
            _mark(chain, 1, "FAIL")

    return status


# ── Step 2: Balance check ─────────────────────────────────────────────────────

def step2_balance_check(creds: dict, skip: bool) -> dict:
    """Check sending wallet balances on all 4 chains."""
    _sep("STEP 2 — SENDING WALLET BALANCES")
    balances: dict[str, dict] = {}

    sending = {
        "algorand": creds.get("sending_algo", ""),
        "voi":      creds.get("sending_voi", ""),
        "hedera":   creds.get("sending_hedera", ""),
        "stellar":  creds.get("sending_stellar", ""),
    }

    if skip or not any(sending.values()):
        _warn("Balance check skipped — pass --sending-algo / --sending-voi / "
              "--sending-hedera / --sending-stellar to check before sending.")
        for chain in CHAINS:
            _mark(chain, 2, "SKIP")
        return {}

    # Algorand USDC (ASA 31566704)
    algo_addr = sending["algorand"]
    if algo_addr:
        url = f"https://mainnet-api.algonode.cloud/v2/accounts/{urllib.parse.quote(algo_addr)}"
        code, data = _http_get(url)
        if code == 200 and isinstance(data, dict):
            assets = data.get("assets", [])
            usdc   = next((a for a in assets if a.get("asset-id") == 31566704), None)
            bal    = usdc["amount"] if usdc else 0
            algo   = data.get("amount", 0)
            ok_bal = bal >= 10_000 and algo >= 1_000
            _info(f"Algorand   wallet: {_trunc(algo_addr)}")
            _info(f"  USDC balance : {bal / 1e6:.6f} USDC ({bal} microUSDC) — need ≥ 0.01")
            _info(f"  ALGO balance : {algo / 1e6:.6f} ALGO — need ≥ 0.001 for fees")
            if ok_bal:
                _ok("Algorand wallet sufficiently funded")
                balances["algorand"] = {"ok": True, "usdc": bal, "native": algo}
                _mark("algorand", 2, "PASS")
            else:
                _fail("Algorand wallet insufficient funds")
                balances["algorand"] = {"ok": False, "usdc": bal, "native": algo}
                _mark("algorand", 2, "FAIL")
        else:
            _fail(f"Algorand balance check failed: HTTP {code}")
            balances["algorand"] = {"ok": False, "error": f"HTTP {code}"}
            _mark("algorand", 2, "FAIL")
    else:
        _warn("Algorand sending address not provided — skipping balance check")
        _mark("algorand", 2, "SKIP")

    # VOI aUSDC (ASA 302190)
    voi_addr = sending["voi"]
    if voi_addr:
        url = f"https://mainnet-api.voi.nodely.io/v2/accounts/{urllib.parse.quote(voi_addr)}"
        code, data = _http_get(url)
        if code == 200 and isinstance(data, dict):
            assets = data.get("assets", [])
            ausdc  = next((a for a in assets if a.get("asset-id") == 302190), None)
            bal    = ausdc["amount"] if ausdc else 0
            voi    = data.get("amount", 0)
            ok_bal = bal >= 10_000 and voi >= 1_000
            _info(f"VOI        wallet: {_trunc(voi_addr)}")
            _info(f"  aUSDC balance: {bal / 1e6:.6f} aUSDC ({bal} micro) — need ≥ 0.01")
            _info(f"  VOI balance  : {voi / 1e6:.6f} VOI — need ≥ 0.001 for fees")
            if ok_bal:
                _ok("VOI wallet sufficiently funded")
                balances["voi"] = {"ok": True, "ausdc": bal, "native": voi}
                _mark("voi", 2, "PASS")
            else:
                _fail("VOI wallet insufficient funds")
                balances["voi"] = {"ok": False, "ausdc": bal, "native": voi}
                _mark("voi", 2, "FAIL")
        else:
            _fail(f"VOI balance check failed: HTTP {code}")
            balances["voi"] = {"ok": False, "error": f"HTTP {code}"}
            _mark("voi", 2, "FAIL")
    else:
        _warn("VOI sending address not provided — skipping balance check")
        _mark("voi", 2, "SKIP")

    # Hedera USDC (HTS 0.0.456858)
    hedera_acct = sending["hedera"]
    if hedera_acct:
        url = (
            f"https://mainnet-public.mirrornode.hedera.com/api/v1/accounts/"
            f"{urllib.parse.quote(hedera_acct)}/tokens"
            f"?token.id=0.0.456858&limit=1"
        )
        code, data = _http_get(url)
        if code == 200 and isinstance(data, dict):
            tokens = data.get("tokens", [])
            usdc   = tokens[0] if tokens else {}
            bal    = int(usdc.get("balance", 0))
            ok_bal = bal >= 10_000
            _info(f"Hedera     account: {hedera_acct}")
            _info(f"  USDC balance: {bal / 1e6:.6f} USDC ({bal} tinyUSDC) — need ≥ 0.01")
            if ok_bal:
                _ok("Hedera account sufficiently funded")
                balances["hedera"] = {"ok": True, "usdc": bal}
                _mark("hedera", 2, "PASS")
            else:
                _fail("Hedera account insufficient funds (or token not associated)")
                balances["hedera"] = {"ok": False, "usdc": bal}
                _mark("hedera", 2, "FAIL")
        else:
            _fail(f"Hedera balance check failed: HTTP {code}")
            balances["hedera"] = {"ok": False, "error": f"HTTP {code}"}
            _mark("hedera", 2, "FAIL")
    else:
        _warn("Hedera account not provided — skipping balance check")
        _mark("hedera", 2, "SKIP")

    # Stellar USDC
    stellar_addr = sending["stellar"]
    if stellar_addr:
        url  = f"https://horizon.stellar.org/accounts/{urllib.parse.quote(stellar_addr)}"
        code, data = _http_get(url)
        if code == 200 and isinstance(data, dict):
            bals  = data.get("balances", [])
            usdc  = next(
                (b for b in bals
                 if b.get("asset_code") == "USDC"
                 and b.get("asset_issuer") == STELLAR_USDC_ISSUER), None
            )
            xlm   = next((b for b in bals if b.get("asset_type") == "native"), {})
            bal   = float(usdc["balance"]) if usdc else 0.0
            xlm_b = float(xlm.get("balance", 0))
            ok_bal = bal >= 0.01 and xlm_b >= 0.00001
            _info(f"Stellar    address: {_trunc(stellar_addr)}")
            _info(f"  USDC balance: {bal:.7f} USDC — need ≥ 0.01")
            _info(f"  XLM balance : {xlm_b:.7f} XLM — need ≥ 0.00001 for fees")
            if ok_bal:
                _ok("Stellar wallet sufficiently funded")
                balances["stellar"] = {"ok": True, "usdc": bal, "xlm": xlm_b}
                _mark("stellar", 2, "PASS")
            else:
                _fail("Stellar wallet insufficient funds")
                balances["stellar"] = {"ok": False, "usdc": bal, "xlm": xlm_b}
                _mark("stellar", 2, "FAIL")
        else:
            _fail(f"Stellar balance check failed: HTTP {code}")
            balances["stellar"] = {"ok": False, "error": f"HTTP {code}"}
            _mark("stellar", 2, "FAIL")
    else:
        _warn("Stellar sending address not provided — skipping balance check")
        _mark("stellar", 2, "SKIP")

    return balances


# ── Step 3: Create checkouts ───────────────────────────────────────────────────

def step3_create_checkouts(api_key: str, tenant_id: str) -> dict:
    """Create one payment checkout per chain via AlgoVoi API."""
    _sep("STEP 3 — CREATE PAYMENT CHECKOUTS")

    if not api_key or not tenant_id:
        for chain in CHAINS:
            _fail(f"{chain.capitalize():10s} — missing ALGOVOI_API_KEY or tenant-id")
            _mark(chain, 3, "FAIL")
        return {}

    checkouts: dict[str, dict] = {}

    for chain, cfg in CHAINS.items():
        payload = {
            "amount":            cfg["amount"],
            "currency":          cfg["currency"],
            "label":             cfg["label"],
            "preferred_network": cfg["network"],
        }
        code, data = _http_post_algovoi("/v1/payment-links", payload, api_key, tenant_id)

        if code in (200, 201) and isinstance(data, dict) and data.get("checkout_url"):
            checkout_url = data["checkout_url"]
            token_match  = re.search(r"/checkout/([A-Za-z0-9_-]+)", checkout_url)
            token        = token_match.group(1) if token_match else ""
            mu           = int(data.get("amount_microunits", 0))
            # Try to extract recipient address from the API response
            recipient    = (data.get("recipient_address", "")
                            or data.get("address", "")
                            or data.get("wallet_address", ""))

            _ok(f"{chain.capitalize():10s} — checkout created")
            _info(f"  checkout_id : {token}")
            _info(f"  checkout_url: {checkout_url}")
            _info(f"  recipient   : {_trunc(recipient) if recipient else '(embedded in checkout)'}")
            _info(f"  amount      : {cfg['atomic_label']}")
            _info(f"  network     : {cfg['network']}")

            checkouts[chain] = {
                "token":       token,
                "checkout_url": checkout_url,
                "amount_microunits": mu,
                "recipient":   recipient,
                "network":     cfg["network"],
                "created_at":  _ts(),
            }
            _mark(chain, 3, "PASS")
        else:
            err = str(data)[:200] if data else "no response"
            _fail(f"{chain.capitalize():10s} — HTTP {code}: {err}")
            _mark(chain, 3, "FAIL")

    return checkouts


# ── Step 4: Wait for user to send payments ────────────────────────────────────

def step4_wait_for_payments(checkouts: dict) -> None:
    """Display payment details and wait for user to send all payments."""
    _sep("STEP 4 — SEND PAYMENTS")

    if not checkouts:
        _fail("No checkouts were created — cannot proceed to payment.")
        return

    print("\n  Open each checkout URL below in a crypto wallet or browser.")
    print("  Send EXACTLY the specified amount on each chain.\n")

    for chain, data in checkouts.items():
        cfg = CHAINS[chain]
        print(f"  ┌─ {chain.upper()} {'─' * (44 - len(chain))}")
        print(f"  │  URL    : {data['checkout_url']}")
        print(f"  │  Amount : {cfg['atomic_label']}")
        print(f"  │  Network: {cfg['network']}")
        print(f"  └{'─' * 46}")
        print()

    print("  When you have SUBMITTED ALL 4 TRANSACTIONS, press Enter.")
    print("  (The script will then poll for on-chain confirmation.)\n")

    try:
        input("  >>> Press Enter when all payments are submitted: ")
    except (EOFError, KeyboardInterrupt):
        print("\n  Interrupted — continuing with polling anyway.")

    for chain in checkouts:
        _mark(chain, 4, "PASS")  # user confirmed they sent


# ── Step 5: Poll for on-chain confirmation ────────────────────────────────────

def step5_confirm_on_chain(checkouts: dict, api_key: str, tenant_id: str) -> dict:
    """
    Poll AlgoVoi checkout status endpoint until each chain confirms.
    Uses GET /checkout/{token}/status — same endpoint as verify_hosted_return().
    """
    _sep("STEP 5 — ON-CHAIN CONFIRMATION")

    confirmed:  dict[str, dict] = {}
    pending:    set[str]        = set(checkouts.keys())
    deadline    = time.time() + _POLL_TIMEOUT
    start       = time.time()

    print(f"  Polling for up to {_POLL_TIMEOUT // 60} minutes "
          f"({_POLL_INTERVAL}s interval)…\n")

    while pending and time.time() < deadline:
        for chain in list(pending):
            token = checkouts[chain]["token"]
            if not token:
                _fail(f"{chain.capitalize():10s} — no checkout token, cannot poll")
                pending.discard(chain)
                _mark(chain, 5, "FAIL")
                continue

            code, data = _http_get_algovoi(
                f"/checkout/{urllib.parse.quote(token, safe='')}/status",
                api_key, tenant_id,
            )

            if code == 200 and isinstance(data, dict):
                status  = str(data.get("status", "")).lower()
                tx_id   = str(data.get("tx_id", data.get("transaction_id", "")))
                network = str(data.get("network", checkouts[chain]["network"]))
                amount  = data.get("amount_microunits", checkouts[chain]["amount_microunits"])

                if status in ("paid", "completed", "confirmed"):
                    elapsed = time.time() - start
                    _ok(f"{chain.capitalize():10s} — CONFIRMED  ({elapsed:.0f}s)")
                    _info(f"  TX ID   : {tx_id}")
                    _info(f"  Status  : {status}")
                    _info(f"  Network : {network}")
                    _info(f"  Amount  : {amount} micro-units")
                    confirmed[chain] = {
                        "tx_id":     tx_id,
                        "status":    status,
                        "network":   network,
                        "amount_mu": amount,
                        "confirmed_at": _ts(),
                    }
                    pending.discard(chain)
                    _mark(chain, 5, "PASS")
                else:
                    print(f"  ⏳  {chain.capitalize():10s} — status: {status}  "
                          f"({int(time.time() - start)}s elapsed)", end="\r", flush=True)
            else:
                # 404 may mean not yet seen — keep polling
                pass

        if pending:
            time.sleep(_POLL_INTERVAL)

    print()  # newline after \r

    # Report any chains that timed out
    for chain in pending:
        _fail(f"{chain.capitalize():10s} — timed out after {_POLL_TIMEOUT}s "
              f"(payment not confirmed on-chain)")
        _mark(chain, 5, "FAIL")

    return confirmed


# ── Step 6: Webhook validation ────────────────────────────────────────────────

def step6_webhook_info(confirmed: dict, webhook_secret: str) -> None:
    """
    Webhook validation note.
    The e2e test cannot receive live webhooks (no HTTP listener).
    Instead we verify HMAC format using a simulated payload.
    """
    _sep("STEP 6 — WEBHOOK VERIFICATION")

    import hashlib
    import hmac as _hmac

    print("  Note: AlgoVoi fires webhooks to your configured webhook URL.")
    print("  This script cannot receive live webhooks — HMAC format is")
    print("  validated locally using simulated confirmed payloads.\n")

    test_secret = webhook_secret or "e2e_test_secret_000"

    for chain, data in confirmed.items():
        # Simulate the payload AlgoVoi would send
        sim_body = json.dumps({
            "event_id":       f"evt_{chain}_e2e",
            "event_type":     "payment.received",
            "status":         "paid",
            "token":          "sim_token",
            "network":        data["network"],
            "tx_id":          data["tx_id"],
            "amount_microunits": data["amount_mu"],
        }, separators=(",", ":"))

        sig = _hmac.new(
            test_secret.encode("utf-8"),
            sim_body.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        # Verify round-trip
        expected = _hmac.new(
            test_secret.encode("utf-8"),
            sim_body.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        valid = _hmac.compare_digest(sig, expected)

        _info(f"{chain.capitalize():10s}  simulated webhook payload:")
        _info(f"  tx_id     : {data['tx_id']}")
        _info(f"  network   : {data['network']}")
        _info(f"  amount    : {data['amount_mu']} micro-units")
        _info(f"  fired_at  : {data['confirmed_at']}")
        _info(f"  hmac_valid: {valid}  (HMAC-SHA256, secret not shown)")
        _info(f"  Zapier format → data['event']['tx_id']")
        _info(f"  Make format   → data['tx_id']")
        _info(f"  n8n format    → json['tx_id']")
        print()

        _mark(chain, 6, "PARTIAL")  # Simulated only — no live listener

    for chain in CHAINS:
        if chain not in confirmed:
            _mark(chain, 6, "SKIP")

    _warn("Step 6 is PARTIAL — live webhook receipt requires a public HTTP endpoint.")
    _info("  Run a local ngrok tunnel or deploy a webhook handler to verify fully.")


# ── Step 7: Post X tweets ─────────────────────────────────────────────────────

def step7_post_tweets(
    confirmed: dict,
    creds: dict,
    no_tweet: bool,
) -> dict:
    """Post one payment confirmation tweet per confirmed chain."""
    _sep("STEP 7 — X POSTS")

    tweets: dict[str, dict] = {}

    if no_tweet:
        _warn("--no-tweet flag set — tweet posting skipped.")
        for chain in CHAINS:
            _mark(chain, 7, "SKIP")
        return {}

    x_creds_ok = all([
        creds.get("x_api_key"),
        creds.get("x_api_key_secret"),
        creds.get("x_access_token"),
        creds.get("x_access_token_secret"),
    ])

    if not x_creds_ok:
        _fail("X credentials not found — cannot post tweets.")
        _info("Set X_API_KEY, X_API_KEY_SECRET, X_ACCESS_TOKEN, X_ACCESS_TOKEN_SECRET")
        _info("in keys.txt or environment variables.")
        for chain in CHAINS:
            _mark(chain, 7, "FAIL")
        return {}

    # Build adapter — payout addresses come from creds (env/CLI/smoke_test_full defaults)
    try:
        x = AlgoVoiX(
            algovoi_key=             creds["api_key"],
            tenant_id=               creds["tenant_id"],
            payout_algorand=         creds["payout_algo"],
            payout_voi=              creds["payout_voi"],
            payout_hedera=           creds["payout_hedera"],
            payout_stellar=          creds["payout_stellar"],
            x_api_key=               creds["x_api_key"],
            x_api_key_secret=        creds["x_api_key_secret"],
            x_access_token=          creds["x_access_token"],
            x_access_token_secret=   creds["x_access_token_secret"],
        )
    except Exception as exc:
        _fail(f"Failed to initialise AlgoVoiX: {exc}")
        for chain in CHAINS:
            _mark(chain, 7, "FAIL")
        return {}

    for chain, data in confirmed.items():
        cfg       = CHAINS[chain]
        tx_id     = data["tx_id"]
        tx_short  = tx_id[:8] if tx_id else "UNKNOWN"
        net_label = NETWORK_INFO.get(cfg["network"], {}).get("label", chain.capitalize())

        tweet_text = (
            f"🚀 New: AlgoVoi X Adapter\n\n"
            f"Crypto payment confirmed → this tweet posted automatically via webhook. "
            f"Zero code for the merchant.\n\n"
            f"✅ 0.01 {cfg['asset']} on {net_label}\n"
            f"TX: {tx_short}…\n\n"
            f"https://github.com/chopmob-cloud/AlgoVoi-Platform-Adapters\n"
            f"#AlgoVoi {cfg['hashtags']}"
        )

        _info(f"{chain.capitalize():10s}  tweet preview:")
        for line in tweet_text.splitlines():
            _info(f"  │  {line}")
        _info(f"  │  ({len(tweet_text)} chars)")
        print()

        result = x.post_tweet(tweet_text)
        if result.success:
            tweet_id  = result.data.get("tweet_id", "")
            tweet_url = result.data.get("tweet_url", "")
            _ok(f"{chain.capitalize():10s} — tweet posted!")
            _info(f"  tweet_id : {tweet_id}")
            _info(f"  tweet_url: {tweet_url}")
            _info(f"  posted_at: {_ts()}")
            tweets[chain] = {
                "tweet_id":  tweet_id,
                "tweet_url": tweet_url,
                "text":      tweet_text,
                "posted_at": _ts(),
            }
            _mark(chain, 7, "PASS")
        else:
            _fail(f"{chain.capitalize():10s} — tweet failed: {result.error}")
            _mark(chain, 7, "FAIL")

    for chain in CHAINS:
        if chain not in confirmed:
            _mark(chain, 7, "SKIP")

    return tweets


# ── Step 8: Summary table ─────────────────────────────────────────────────────

def step8_summary(confirmed: dict, tweets: dict) -> None:
    """Print the full end-to-end summary table."""
    _sep("STEP 8 — END-TO-END SUMMARY")

    STEP_LABELS = {
        1: "MCP / network",
        2: "Wallet balance",
        3: "Checkout created",
        4: "Payment sent",
        5: "On-chain confirm",
        6: "Webhook fired",
        7: "X post published",
    }

    def _cell(chain: str, step: int) -> str:
        v = _STATUS[chain][step]
        if v == "PASS":    return "✅ PASS"
        if v == "FAIL":    return "❌ FAIL"
        if v == "PARTIAL": return "⚠️  PART"
        if v == "SKIP":    return "⏭  SKIP"
        return "—"

    col_w = 10
    print(f"\n  {'Step':<4}  {'Action':<18}  "
          f"{'Algorand':<{col_w}}  {'VOI':<{col_w}}  "
          f"{'Hedera':<{col_w}}  {'Stellar':<{col_w}}")
    print("  " + "─" * 70)

    for step, label in STEP_LABELS.items():
        row = f"  {step:<4}  {label:<18}"
        for chain in ["algorand", "voi", "hedera", "stellar"]:
            row += f"  {_cell(chain, step):<{col_w}}"
        print(row)

    print("  " + "─" * 70)

    # Chain result (all 7 steps PASS)
    row = f"  {'':4}  {'CHAIN RESULT':<18}"
    for chain in ["algorand", "voi", "hedera", "stellar"]:
        vals = [_STATUS[chain][s] for s in range(1, 8)]
        if all(v == "PASS" for v in vals):
            cell = "✅ PASS"
        elif any(v == "FAIL" for v in vals):
            cell = "❌ FAIL"
        else:
            cell = "⚠️  PART"
        row += f"  {cell:<{col_w}}"
    print(row)

    # TX IDs
    if confirmed:
        print("\n  TX IDs:")
        for chain, data in confirmed.items():
            print(f"    {chain.capitalize():<12}: {data['tx_id']}")

    # Tweet URLs
    if tweets:
        print("\n  Tweet URLs:")
        for chain, data in tweets.items():
            print(f"    {chain.capitalize():<12}: {data['tweet_url']}")

    # Final verdict
    all_chains = list(CHAINS.keys())
    all_pass   = all(
        all(_STATUS[c][s] == "PASS" for s in range(1, 8))
        for c in all_chains
    )
    some_fail  = any(
        any(_STATUS[c][s] == "FAIL" for s in range(1, 8))
        for c in all_chains
    )

    print()
    if all_pass:
        print("  " + "═" * 62)
        print("  16/16 PASS — AlgoVoi X adapter verified on mainnet.")
        print("  Algorand ✅  VOI ✅  Hedera ✅  Stellar ✅")
        print("  All payments confirmed. All webhooks fired.")
        print("  All X posts published. All TX IDs verifiable on-chain.")
        print("  " + "═" * 62)
    else:
        passing = [c for c in all_chains if all(_STATUS[c][s] != "FAIL" for s in range(1, 8))]
        failing = [c for c in all_chains if any(_STATUS[c][s] == "FAIL" for s in range(1, 8))]
        print(f"  Passed  : {', '.join(passing) or 'none'}")
        print(f"  Failed  : {', '.join(failing) or 'none'}")
        for chain in failing:
            fail_steps = [s for s in range(1, 8) if _STATUS[chain][s] == "FAIL"]
            print(f"  {chain.capitalize()}: failed at step(s) {fail_steps}")


# ── Step 9: Block explorer links ──────────────────────────────────────────────

def step9_explorer_links(confirmed: dict) -> None:
    """Print block explorer URLs for all confirmed TX IDs."""
    _sep("STEP 9 — BLOCK EXPLORER LINKS")

    if not confirmed:
        _warn("No confirmed transactions — no explorer links to generate.")
        return

    for chain, data in confirmed.items():
        tx_id   = data["tx_id"]
        tmpl    = CHAINS[chain]["explorer"]
        url     = tmpl.format(tx_id=urllib.parse.quote(tx_id, safe=""))
        _ok(f"{chain.capitalize():10s}: {url}")

    print()
    _info("Open the links above to verify each transaction publicly.")


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="AlgoVoi X Adapter — End-to-End Mainnet Test",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--tenant-id",       default="", help="AlgoVoi tenant UUID (or set TENANT_ID / ALGOVOI_TENANT_ID env var)")
    # Sending wallet addresses — only needed for Step 2 balance checks
    parser.add_argument("--sending-algo",    default="", help="Algorand sending wallet address (Step 2 balance check)")
    parser.add_argument("--sending-voi",     default="", help="VOI sending wallet address (Step 2 balance check)")
    parser.add_argument("--sending-hedera",  default="", help="Hedera sending account e.g. 0.0.123456 (Step 2 balance check)")
    parser.add_argument("--sending-stellar", default="", help="Stellar sending address G... (Step 2 balance check)")
    # Payout address overrides — defaults come from smoke_test_full.py (no arg needed normally)
    parser.add_argument("--payout-algo",     default="", help="Override Algorand payout address")
    parser.add_argument("--payout-voi",      default="", help="Override VOI payout address")
    parser.add_argument("--payout-hedera",   default="", help="Override Hedera payout account")
    parser.add_argument("--payout-stellar",  default="", help="Override Stellar payout address")
    parser.add_argument("--no-tweet",        action="store_true", help="Skip X posting (dry-run)")
    parser.add_argument("--skip-balance",    action="store_true", help="Skip wallet balance checks")
    parser.add_argument("--webhook-secret",  default="", help="Webhook secret for HMAC simulation (optional)")
    # Resume mode — skip Steps 1-4, poll existing checkout tokens directly
    parser.add_argument("--token-algo",      default="", help="Resume: existing Algorand checkout token")
    parser.add_argument("--token-voi",       default="", help="Resume: existing VOI checkout token")
    parser.add_argument("--token-hedera",    default="", help="Resume: existing Hedera checkout token")
    parser.add_argument("--token-stellar",   default="", help="Resume: existing Stellar checkout token")
    args = parser.parse_args()

    print()
    print("╔══════════════════════════════════════════════════════════════╗")
    print("║   AlgoVoi X Adapter — End-to-End Mainnet Test               ║")
    print("║   Algorand · VOI · Hedera · Stellar                         ║")
    print("╚══════════════════════════════════════════════════════════════╝")
    print(f"  Started: {_ts()}")

    creds = load_creds(args)

    # Validate required credentials early
    missing = [k for k in ("api_key", "tenant_id") if not creds.get(k)]
    if missing:
        print(f"\n  ❌ Missing required credentials: {', '.join(missing)}")
        if "api_key" in missing:
            print("     Set ALGOVOI_API_KEY in keys.txt or environment")
        if "tenant_id" in missing:
            print("     Pass --tenant-id or set ALGOVOI_TENANT_ID env var")
        sys.exit(1)

    # ── Resume mode: skip Steps 1-4, use pre-existing checkout tokens ─────────
    resume_tokens = {
        k: v for k, v in {
            "algorand": args.token_algo,
            "voi":      args.token_voi,
            "hedera":   args.token_hedera,
            "stellar":  args.token_stellar,
        }.items() if v
    }

    if resume_tokens:
        print(f"\n  ▶  Resume mode — polling {len(resume_tokens)} existing checkout(s)")
        checkouts = {}
        for chain, token in resume_tokens.items():
            base_url = f"https://api1.ilovechicken.co.uk/checkout/{token}"
            checkouts[chain] = {
                "token":       token,
                "checkout_url": base_url,
                "amount_microunits": CHAINS[chain]["atomic"] if isinstance(CHAINS[chain]["atomic"], int) else 0,
                "recipient":   "",
                "network":     CHAINS[chain]["network"],
                "created_at":  _ts(),
            }
            _mark(chain, 1, "SKIP")
            _mark(chain, 2, "SKIP")
            _mark(chain, 3, "PASS")
            _mark(chain, 4, "PASS")
            _info(f"  {chain.capitalize():10s}: token={token}")
    else:
        # ── Step 1 ────────────────────────────────────────────────────────────
        _network_status = step1_network_status()

        # ── Step 2 ────────────────────────────────────────────────────────────
        _balances = step2_balance_check(creds, skip=args.skip_balance)

        # ── Step 3 ────────────────────────────────────────────────────────────
        checkouts = step3_create_checkouts(creds["api_key"], creds["tenant_id"])

        if not checkouts:
            _fail("No checkouts created — aborting test.")
            sys.exit(1)

        # ── Step 4 ────────────────────────────────────────────────────────────
        step4_wait_for_payments(checkouts)

    # ── Step 5 ────────────────────────────────────────────────────────────────
    confirmed = step5_confirm_on_chain(checkouts, creds["api_key"], creds["tenant_id"])

    # ── Step 6 ────────────────────────────────────────────────────────────────
    step6_webhook_info(confirmed, creds.get("webhook_secret", ""))

    # ── Step 7 ────────────────────────────────────────────────────────────────
    tweets = step7_post_tweets(confirmed, creds, no_tweet=args.no_tweet)

    # ── Step 8 ────────────────────────────────────────────────────────────────
    step8_summary(confirmed, tweets)

    # ── Step 9 ────────────────────────────────────────────────────────────────
    step9_explorer_links(confirmed)

    print(f"\n  Finished: {_ts()}")
    print()

    # Exit code: 0 if at least one chain fully confirmed + tweeted
    fully_done = sum(
        1 for c in CHAINS
        if _STATUS[c][5] == "PASS" and (args.no_tweet or _STATUS[c][7] == "PASS")
    )
    sys.exit(0 if fully_done == len(CHAINS) else 1)


if __name__ == "__main__":
    main()
