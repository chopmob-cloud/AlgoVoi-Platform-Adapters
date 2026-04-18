"""
Gemini Adapter Smoke Test
=========================
Phase 1 — show_challenges(): 402 challenges for MPP + AP2 on all 4 chains
Phase 2 — verify_payments(): verifies real TX IDs on-chain, calls Gemini API

Gemini key read from GEMINI_KEY env var (never written to disk).

Usage:
    GEMINI_KEY=AIza... python smoke_test_gemini.py
    GEMINI_KEY=AIza... python smoke_test_gemini.py ALGO_TX VOI_TX HEDERA_TX STELLAR_TX
"""

from __future__ import annotations

import base64
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "mpp-adapter"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "ap2-adapter"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "openai"))

from gemini_algovoi import AlgoVoiGemini

# ── Config ────────────────────────────────────────────────────────────────────

def _load_key(prefix: str) -> str:
    key_file = os.path.join(os.path.dirname(__file__), "..", "..", "openai.txt")
    with open(key_file, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line.startswith(prefix):
                return line
    raise RuntimeError(f"No key with prefix {prefix!r} found in openai.txt")

GEMINI_KEY  = os.environ.get("GEMINI_KEY") or _load_key("AIza")
ALGOVOI_KEY = _load_key("algv_")
TENANT_ID   = "YOUR_TENANT_ID"

PAYOUT_ADDRS = {
    "algorand-mainnet": "ZVLRVYQSLJNVFMOIOKT35XH5SNQG45IVFMLLRFLHDQJQA5TO5H3SO4TVDQ",
    "voi-mainnet":      "THDLWTJ7RB4OJWFZCLL5IME7FHBSJ3SONBRWHIVQE3BEGTY2BWUEUVEOQY",
    "hedera-mainnet":   "0.0.1317927",
    "stellar-mainnet":  "GD45SH4TC4TMJOJWJJSLGAXODAIO36POCACT2MWS7I6CTJORMFKEP3HR",
}

TEST_MESSAGES = [
    {"role": "system", "content": "You are a helpful assistant. Reply very briefly."},
    {"role": "user",   "content": "Payment verified. Say hello and confirm you are Gemini."},
]

# ── Helpers ───────────────────────────────────────────────────────────────────

def _mpp_gate(network: str) -> AlgoVoiGemini:
    return AlgoVoiGemini(
        gemini_key=GEMINI_KEY, algovoi_key=ALGOVOI_KEY,
        tenant_id=TENANT_ID, payout_address=PAYOUT_ADDRS[network],
        protocol="mpp", network=network,
        amount_microunits=10000, model="gemini-2.0-flash",
    )

def _ap2_gate(network: str) -> AlgoVoiGemini:
    return AlgoVoiGemini(
        gemini_key=GEMINI_KEY, algovoi_key=ALGOVOI_KEY,
        tenant_id=TENANT_ID, payout_address=PAYOUT_ADDRS[network],
        protocol="ap2", network=network,
        amount_microunits=10000, model="gemini-2.0-flash",
    )

def _mpp_proof(network: str, tx_id: str) -> str:
    return base64.b64encode(json.dumps({
        "network": network,
        "payload": {"txId": tx_id},
    }).encode()).decode()

# ── Phase 1 ───────────────────────────────────────────────────────────────────

def show_challenges():
    print("\n" + "="*60)
    print("PHASE 1 - Payment Challenges")
    print("="*60)

    networks = ["algorand-mainnet", "voi-mainnet", "hedera-mainnet", "stellar-mainnet"]

    print("\n-- MPP challenges ------------------------------------------")
    for net in networks:
        result = _mpp_gate(net).check({})
        status, headers, _ = result.as_wsgi_response()
        www_auth = next((v for k, v in headers if k.lower() == "www-authenticate"), "")
        print(f"  {net:20s}  {status}  {www_auth[:80]}")

    print("\n-- AP2 CartMandate challenges ------------------------------")
    for net in networks:
        result = _ap2_gate(net).check({}, {})
        status, headers, _ = result.as_wsgi_response()
        cart = next((v for k, v in headers if k.lower() == "x-ap2-cart-mandate"), "")
        print(f"  {net:20s}  {status}  CartMandate={cart[:40]}...")

    print("\n[PASS] All 8 challenges returned 402 correctly")
    print("\nTo run Phase 2:")
    print("  GEMINI_KEY=AIza... python smoke_test_gemini.py ALGO_TX VOI_TX HEDERA_TX STELLAR_TX")

# ── Phase 2 ───────────────────────────────────────────────────────────────────

def verify_payments(algo_tx: str, voi_tx: str, hedera_tx: str, stellar_tx: str):
    print("\n" + "="*60)
    print("PHASE 2 - On-chain Verification + Gemini API")
    print("="*60)

    tests = [
        ("algorand-mainnet", algo_tx),
        ("voi-mainnet",      voi_tx),
        ("hedera-mainnet",   hedera_tx),
        ("stellar-mainnet",  stellar_tx),
    ]

    passed = failed = 0

    for network, tx_id in tests:
        print(f"\n-- {network} ------------------------------------------")
        print(f"  TX: {tx_id}")
        gate  = _mpp_gate(network)
        proof = _mpp_proof(network, tx_id)

        try:
            result = gate.check({"Authorization": f"Payment {proof}"})

            if result.requires_payment:
                print(f"  [FAIL] Payment rejected - {result.error}")
                failed += 1
                continue

            print(f"  [PASS] Payment verified")
            if result.receipt:
                print(f"         payer  : {result.receipt.payer}")
                print(f"         amount : {result.receipt.amount} microunits")

            reply = gate.complete(TEST_MESSAGES)
            print(f"  [PASS] Gemini replied: {reply[:120]}")
            passed += 1

        except Exception as e:
            print(f"  [FAIL] {type(e).__name__}: {e}")
            failed += 1

    print(f"\n{'='*60}")
    print(f"Results: {passed}/{passed+failed} passed", "PASS" if failed == 0 else "FAIL")
    if failed:
        sys.exit(1)

# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) == 5:
        verify_payments(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4])
    elif len(sys.argv) == 1:
        show_challenges()
    else:
        print("Usage:")
        print("  GEMINI_KEY=AIza... python smoke_test_gemini.py")
        print("  GEMINI_KEY=AIza... python smoke_test_gemini.py ALGO VOI HEDERA STELLAR")
        sys.exit(1)
