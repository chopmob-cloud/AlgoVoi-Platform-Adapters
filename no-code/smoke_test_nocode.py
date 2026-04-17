"""
AlgoVoi No-Code Adapters — Smoke Test
======================================

Phase 1 — Offline checks (no API calls, no credentials needed):
  01  Zapier: init + list networks (16 networks, correct keys)
  02  Zapier: webhook HMAC validation (valid + invalid)
  03  Zapier: generate MPP challenge
  04  Zapier: generate x402 challenge
  05  Zapier: generate AP2 mandate
  06  Zapier: schema rejection (bad amount, bad network, missing label)
  07  Make: init + list networks (16 networks, correct keys)
  08  Make: webhook HMAC validation (valid + invalid)
  09  Make: generate MPP challenge
  10  Make: generate x402 challenge
  11  Make: generate AP2 mandate
  12  Make: schema rejection (bad amount, bad network, missing label)
  13  n8n: init + list networks (16 networks, correct keys)
  14  n8n: webhook HMAC validation (valid + invalid)
  15  n8n: generate MPP challenge
  16  n8n: generate x402 challenge
  17  n8n: generate AP2 mandate
  18  n8n: schema rejection (bad amount, bad network, missing label)

Phase 2 — Live API round-trip (requires ALGOVOI_API_KEY / ALGOVOI_TENANT_ID /
          at least one ALGOVOI_PAYOUT_* address):
  19  Zapier: create payment link → returns checkout_url + token
  20  Make:   create payment link → returns checkout_url + token
  21  n8n:    create payment link → returns checkout_url + token

Usage:
    # Phase 1 only (no credentials needed):
    python no-code/smoke_test_nocode.py

    # Phase 2 as well:
    ALGOVOI_API_KEY=algv_... ALGOVOI_TENANT_ID=... ALGOVOI_PAYOUT_ALGORAND=... \\
        python no-code/smoke_test_nocode.py --live

Run from the repo root: C:\\algo\\platform-adapters
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import hmac as _hmac
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT / "zapier"))
sys.path.insert(0, str(ROOT / "make"))
sys.path.insert(0, str(ROOT / "n8n"))

from zapier_algovoi import AlgoVoiZapier  # noqa: E402
from make_algovoi   import AlgoVoiMake    # noqa: E402
from n8n_algovoi    import AlgoVoiN8n     # noqa: E402

_PASS = "  PASS  "
_FAIL = "  FAIL  "
_SKIP = "  SKIP  "

def ok(msg: str)   -> None: print(f"{_PASS}{msg}")
def fail(msg: str) -> None: print(f"{_FAIL}{msg}")
def skip(msg: str) -> None: print(f"{_SKIP}{msg}")


def _make_sig(body: str, secret: str) -> str:
    return _hmac.new(secret.encode(), body.encode(), hashlib.sha256).hexdigest()


# ── Shared fixture ─────────────────────────────────────────────────────────────

_SECRET    = "test_webhook_secret_abc123"
_PAYOUT    = "ZVLRVYQSLJNVFMOIOKT35XH5SNQG45IVFMLLRFLHDQJQA5TO5H3SO4TVDQ"
_FAKE_KEY  = "algv_" + "x" * 40  # fake key for offline tests
_FAKE_TID  = "00000000-0000-0000-0000-000000000000"

_EXPECTED_NETWORKS = {
    "algorand_mainnet", "voi_mainnet", "hedera_mainnet", "stellar_mainnet",
    "algorand_mainnet_algo", "voi_mainnet_voi", "hedera_mainnet_hbar", "stellar_mainnet_xlm",
    "algorand_testnet", "voi_testnet", "hedera_testnet", "stellar_testnet",
    "algorand_testnet_algo", "voi_testnet_voi", "hedera_testnet_hbar", "stellar_testnet_xlm",
}

WEBHOOK_BODY = json.dumps({
    "event_id": "evt_001",
    "event_type": "payment.received",
    "status": "paid",
    "token": "tok_abc123",
    "amount": 5.00,
    "currency": "USD",
    "network": "algorand_mainnet",
    "tx_id": "TXABC123",
    "order_id": "ORD-001",
})

failures = 0


# ── Phase 1 helpers ────────────────────────────────────────────────────────────

def _check_networks_zapier(z: AlgoVoiZapier, label: str) -> None:
    global failures
    res = z.action_list_networks()
    nets = res.data.get("networks", [])
    keys = {n["key"] for n in nets}
    if len(nets) == 16 and _EXPECTED_NETWORKS <= keys:
        ok(f"[{label}] list networks — 16 networks, all keys present")
    else:
        fail(f"[{label}] list networks — got {len(nets)} networks, keys={keys - _EXPECTED_NETWORKS}")
        failures += 1


def _check_networks_make(m: AlgoVoiMake, label: str) -> None:
    global failures
    bundle = m.module_list_networks()
    nets = bundle.get("data", {}).get("networks", [])
    keys = {n["key"] for n in nets}
    if len(nets) == 16 and _EXPECTED_NETWORKS <= keys:
        ok(f"[{label}] list networks — 16 networks, all keys present")
    else:
        fail(f"[{label}] list networks — got {len(nets)} networks")
        failures += 1


def _check_networks_n8n(n: AlgoVoiN8n, label: str) -> None:
    global failures
    item = n.execute_list_networks()
    nets = item["json"].get("networks", [])
    keys = {net["key"] for net in nets}
    if len(nets) == 16 and _EXPECTED_NETWORKS <= keys:
        ok(f"[{label}] list networks — 16 networks, all keys present")
    else:
        fail(f"[{label}] list networks — got {len(nets)} networks")
        failures += 1


# ── Phase 1: Zapier ────────────────────────────────────────────────────────────

def phase1_zapier() -> None:
    global failures
    print("\n── Zapier ──")

    z = AlgoVoiZapier(
        algovoi_key=_FAKE_KEY, tenant_id=_FAKE_TID,
        payout_algorand=_PAYOUT, webhook_secret=_SECRET,
    )

    # 01 init + list networks
    _check_networks_zapier(z, "Zapier")

    # 02 webhook HMAC
    sig_ok  = _make_sig(WEBHOOK_BODY, _SECRET)
    res_ok  = z.receive_and_forward(WEBHOOK_BODY, sig_ok)
    res_bad = z.receive_and_forward(WEBHOOK_BODY, "badsig")
    if res_ok.success and res_ok.http_status == 200:
        ok("[Zapier] 02a webhook valid HMAC → 200 OK")
    else:
        fail(f"[Zapier] 02a webhook valid HMAC failed: {res_ok}")
        failures += 1
    if not res_bad.success and res_bad.http_status == 401:
        ok("[Zapier] 02b webhook invalid HMAC → 401")
    else:
        fail(f"[Zapier] 02b webhook bad HMAC: {res_bad}")
        failures += 1

    # 03 MPP challenge
    res = z.action_generate_challenge({
        "protocol": "mpp", "resource_id": "/premium",
        "amount_microunits": 1_000_000, "network": "algorand_mainnet",
    })
    if res.success and "WWW-Authenticate" in res.data.get("header_name",""):
        ok("[Zapier] 03 generate MPP challenge — WWW-Authenticate returned")
    else:
        fail(f"[Zapier] 03 MPP challenge failed: {res.error}")
        failures += 1

    # 04 x402 challenge
    res = z.action_generate_challenge({
        "protocol": "x402", "resource_id": "/api/data",
        "amount_microunits": 500_000, "network": "stellar_mainnet",
    })
    if res.success and res.data.get("header_name") == "X-Payment-Required":
        try:
            decoded = json.loads(base64.b64decode(res.data["header_value"] + "==").decode())
            assert decoded["network"] == "stellar_mainnet"
            ok("[Zapier] 04 generate x402 challenge — X-Payment-Required, decodable")
        except Exception as e:
            fail(f"[Zapier] 04 x402 decode error: {e}")
            failures += 1
    else:
        fail(f"[Zapier] 04 x402 challenge failed: {res.error}")
        failures += 1

    # 05 AP2 mandate
    res = z.action_generate_challenge({
        "protocol": "ap2", "resource_id": "/service",
        "amount_microunits": 2_000_000, "network": "hedera_mainnet",
    })
    if res.success and res.data.get("mandate_id") and len(res.data["mandate_id"]) == 16:
        try:
            decoded = json.loads(base64.b64decode(res.data["mandate_b64"] + "==").decode())
            assert decoded["network"] == "hedera_mainnet"
            ok("[Zapier] 05 generate AP2 mandate — mandate_id=16 chars, b64 round-trips")
        except Exception as e:
            fail(f"[Zapier] 05 AP2 decode error: {e}")
            failures += 1
    else:
        fail(f"[Zapier] 05 AP2 failed: {res.error}")
        failures += 1

    # 06 schema rejection
    r1 = z.action_create_payment_link({"amount": -5, "currency": "USD", "label": "Test", "network": "algorand_mainnet"})
    r2 = z.action_create_payment_link({"amount": 5, "currency": "USD", "label": "Test", "network": "bad_network"})
    r3 = z.action_create_payment_link({"amount": 5, "currency": "USD", "label": "", "network": "algorand_mainnet"})
    if not r1.success and not r2.success and not r3.success:
        ok("[Zapier] 06 schema rejection — bad amount, bad network, missing label all rejected")
    else:
        fail(f"[Zapier] 06 schema rejection: r1={r1.success} r2={r2.success} r3={r3.success}")
        failures += 1


# ── Phase 1: Make ──────────────────────────────────────────────────────────────

def phase1_make() -> None:
    global failures
    print("\n── Make ──")

    m = AlgoVoiMake(
        algovoi_key=_FAKE_KEY, tenant_id=_FAKE_TID,
        payout_algorand=_PAYOUT, webhook_secret=_SECRET,
    )

    # 07 init + list networks
    _check_networks_make(m, "Make")

    # 08 webhook HMAC
    sig_ok  = _make_sig(WEBHOOK_BODY, _SECRET)
    b_ok    = m.receive_webhook(WEBHOOK_BODY, sig_ok)
    b_bad   = m.receive_webhook(WEBHOOK_BODY, "badsig")
    if b_ok.get("data") and b_ok["data"].get("event_type"):
        ok("[Make] 08a webhook valid HMAC → data bundle returned")
    else:
        fail(f"[Make] 08a webhook valid: {b_ok}")
        failures += 1
    if b_bad.get("error", {}).get("code") == "INVALID_SIGNATURE":
        ok("[Make] 08b webhook invalid HMAC → INVALID_SIGNATURE error")
    else:
        fail(f"[Make] 08b bad HMAC: {b_bad}")
        failures += 1

    # 09 MPP challenge
    b = m.module_generate_challenge({
        "protocol": "mpp", "resource_id": "/premium",
        "amount_microunits": 1_000_000, "network": "algorand_mainnet",
    })
    if b.get("data") and b["data"].get("header_name") == "WWW-Authenticate":
        ok("[Make] 09 generate MPP challenge — WWW-Authenticate returned")
    else:
        fail(f"[Make] 09 MPP: {b}")
        failures += 1

    # 10 x402 challenge
    b = m.module_generate_challenge({
        "protocol": "x402", "resource_id": "/api",
        "amount_microunits": 500_000, "network": "voi_mainnet",
    })
    if b.get("data") and b["data"].get("header_name") == "X-Payment-Required":
        try:
            decoded = json.loads(base64.b64decode(b["data"]["header_value"] + "==").decode())
            assert decoded["network"] == "voi_mainnet"
            ok("[Make] 10 generate x402 challenge — X-Payment-Required, decodable")
        except Exception as e:
            fail(f"[Make] 10 x402 decode: {e}")
            failures += 1
    else:
        fail(f"[Make] 10 x402: {b}")
        failures += 1

    # 11 AP2 mandate
    b = m.module_generate_challenge({
        "protocol": "ap2", "resource_id": "/service",
        "amount_microunits": 2_000_000, "network": "stellar_mainnet",
    })
    if b.get("data") and len(b["data"].get("mandate_id","")) == 16:
        ok("[Make] 11 generate AP2 mandate — mandate_id=16 chars")
    else:
        fail(f"[Make] 11 AP2: {b}")
        failures += 1

    # 12 schema rejection
    r1 = m.module_create_payment_link({"amount": -1, "currency":"USD","label":"T","network":"algorand_mainnet"})
    r2 = m.module_create_payment_link({"amount":  5, "currency":"USD","label":"T","network":"bad_net"})
    r3 = m.module_create_payment_link({"amount":  5, "currency":"USD","label":"", "network":"algorand_mainnet"})
    if all(b.get("error") for b in [r1, r2, r3]):
        ok("[Make] 12 schema rejection — bad amount, bad network, missing label all rejected")
    else:
        fail(f"[Make] 12 schema: {r1} {r2} {r3}")
        failures += 1


# ── Phase 1: n8n ───────────────────────────────────────────────────────────────

def phase1_n8n() -> None:
    global failures
    print("\n── n8n ──")

    n = AlgoVoiN8n(
        algovoi_key=_FAKE_KEY, tenant_id=_FAKE_TID,
        payout_algorand=_PAYOUT, webhook_secret=_SECRET,
    )

    # 13 init + list networks
    _check_networks_n8n(n, "n8n")

    # 14 webhook HMAC
    sig_ok  = _make_sig(WEBHOOK_BODY, _SECRET)
    i_ok    = n.receive_webhook(WEBHOOK_BODY, sig_ok)
    i_bad   = n.receive_webhook(WEBHOOK_BODY, "badsig")
    if i_ok["json"].get("success") and i_ok["json"].get("event_type"):
        ok("[n8n] 14a webhook valid HMAC → item returned")
    else:
        fail(f"[n8n] 14a: {i_ok}")
        failures += 1
    if i_bad["json"].get("error"):
        ok("[n8n] 14b webhook invalid HMAC → error item")
    else:
        fail(f"[n8n] 14b: {i_bad}")
        failures += 1

    # 15 MPP challenge
    i = n.execute_generate_mpp_challenge({
        "resource_id": "/premium", "amount_microunits": 1_000_000, "network": "algorand_mainnet",
    })
    if i["json"].get("success") and i["json"].get("header_name") == "WWW-Authenticate":
        ok("[n8n] 15 generate MPP challenge — WWW-Authenticate returned")
    else:
        fail(f"[n8n] 15 MPP: {i}")
        failures += 1

    # 16 x402 challenge
    i = n.execute_generate_x402_challenge({
        "resource_id": "/api", "amount_microunits": 500_000, "network": "hedera_mainnet",
    })
    if i["json"].get("success") and i["json"].get("header_name") == "X-Payment-Required":
        try:
            decoded = json.loads(base64.b64decode(i["json"]["header_value"] + "==").decode())
            assert decoded["network"] == "hedera_mainnet"
            ok("[n8n] 16 generate x402 challenge — X-Payment-Required, decodable")
        except Exception as e:
            fail(f"[n8n] 16 x402 decode: {e}")
            failures += 1
    else:
        fail(f"[n8n] 16 x402: {i}")
        failures += 1

    # 17 AP2 mandate
    i = n.execute_generate_ap2_mandate({
        "resource_id": "/svc", "amount_microunits": 2_000_000, "network": "algorand_mainnet_algo",
    })
    if i["json"].get("success") and len(i["json"].get("mandate_id","")) == 16:
        try:
            decoded = json.loads(base64.b64decode(i["json"]["mandate_b64"] + "==").decode())
            assert decoded["network"] == "algorand_mainnet_algo"
            ok("[n8n] 17 generate AP2 mandate — mandate_id=16 chars, b64 round-trips")
        except Exception as e:
            fail(f"[n8n] 17 AP2 decode: {e}")
            failures += 1
    else:
        fail(f"[n8n] 17 AP2: {i}")
        failures += 1

    # 18 schema rejection
    r1 = n.execute_create_payment_link({"amount": -1, "currency":"USD","label":"T","network":"algorand_mainnet"})
    r2 = n.execute_create_payment_link({"amount":  5, "currency":"USD","label":"T","network":"bad_net"})
    r3 = n.execute_create_payment_link({"amount":  5, "currency":"USD","label":"", "network":"algorand_mainnet"})
    if all(item["json"].get("error") for item in [r1, r2, r3]):
        ok("[n8n] 18 schema rejection — bad amount, bad network, missing label all rejected")
    else:
        fail(f"[n8n] 18: {r1} {r2} {r3}")
        failures += 1


# ── Phase 2: live API ──────────────────────────────────────────────────────────

def phase2_live(creds: dict) -> None:
    global failures
    print("\n── Phase 2: Live API ──")

    common = dict(
        algovoi_key=creds["api_key"],
        tenant_id=creds["tenant_id"],
        payout_algorand=creds.get("payout_algorand", ""),
        payout_voi=creds.get("payout_voi", ""),
        payout_hedera=creds.get("payout_hedera", ""),
        payout_stellar=creds.get("payout_stellar", ""),
    )

    for adapter_name, adapter_cls, create_fn in [
        ("Zapier", AlgoVoiZapier, lambda a: a.action_create_payment_link({
            "amount": 1.00, "currency": "USD",
            "label": "Smoke Test — Zapier", "network": "algorand_mainnet",
        })),
        ("Make", AlgoVoiMake, lambda a: (lambda b: type("R", (), {
            "success": "data" in b, "data": b.get("data", {}), "error": b.get("error", {}).get("message")
        })())(a.module_create_payment_link({
            "amount": 1.00, "currency": "USD",
            "label": "Smoke Test — Make", "network": "algorand_mainnet",
        }))),
        ("n8n", AlgoVoiN8n, lambda a: (lambda i: type("R", (), {
            "success": i["json"].get("success", False),
            "data": i["json"], "error": i["json"].get("error"),
        })())(a.execute_create_payment_link({
            "amount": 1.00, "currency": "USD",
            "label": "Smoke Test — n8n", "network": "algorand_mainnet",
        }))),
    ]:
        try:
            adapter = adapter_cls(**common)
            res = create_fn(adapter)
            if res.success and res.data.get("checkout_url") and res.data.get("token"):
                ok(f"[{adapter_name}] create_payment_link — checkout_url + token returned ✓")
            else:
                fail(f"[{adapter_name}] create_payment_link failed: {res.error}")
                failures += 1
        except Exception as exc:
            fail(f"[{adapter_name}] create_payment_link exception: {exc}")
            failures += 1


# ── Credential loader ──────────────────────────────────────────────────────────

def _load_creds() -> dict | None:
    api_key    = os.environ.get("ALGOVOI_API_KEY", "")
    tenant_id  = os.environ.get("ALGOVOI_TENANT_ID", "")

    if not api_key:
        repo_root = Path(__file__).parent.parent
        for fname in ("keys.txt",):
            p = repo_root / fname
            if not p.exists():
                continue
            for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
                line = line.strip()
                if line.startswith("algv_"):
                    api_key = line
                    break

    payouts = {
        "payout_algorand": os.environ.get("ALGOVOI_PAYOUT_ALGORAND", ""),
        "payout_voi":      os.environ.get("ALGOVOI_PAYOUT_VOI", ""),
        "payout_hedera":   os.environ.get("ALGOVOI_PAYOUT_HEDERA", ""),
        "payout_stellar":  os.environ.get("ALGOVOI_PAYOUT_STELLAR", ""),
    }
    has_payout = any(payouts.values())

    if not api_key or not tenant_id or not has_payout:
        return None
    return {"api_key": api_key, "tenant_id": tenant_id, **payouts}


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="AlgoVoi no-code adapter smoke tests")
    parser.add_argument("--live", action="store_true", help="Run Phase 2 live API tests")
    args = parser.parse_args()

    print("=" * 60)
    print("  AlgoVoi No-Code Adapters — Smoke Test")
    print("=" * 60)
    print("\n── Phase 1: Offline ──")

    phase1_zapier()
    phase1_make()
    phase1_n8n()

    if args.live:
        creds = _load_creds()
        if creds:
            phase2_live(creds)
        else:
            skip("Phase 2 skipped — missing ALGOVOI_API_KEY / ALGOVOI_TENANT_ID / payout address")

    print("\n" + "=" * 60)
    if failures == 0:
        print("  ALL SMOKE TESTS PASSED")
    else:
        print(f"  {failures} FAILURE(S) — see above")
    print("=" * 60)
    sys.exit(0 if failures == 0 else 1)


if __name__ == "__main__":
    main()
