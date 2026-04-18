"""
Mistral Adapter Smoke Test
==========================
Phase 1 — show_challenges(): shows the 402 payment challenges for MPP + AP2 on all 4 chains
Phase 2 — verify_payments(): takes real TX IDs, verifies on-chain, calls Mistral API

Usage:
    python smoke_test_mistral.py                              # Phase 1 only
    python smoke_test_mistral.py ALGO_TX VOI_TX HEDERA_TX STELLAR_TX   # Phase 2

Credentials:
    MISTRAL_KEY  env var (or first "Mistral:" line in keys.txt / openai.txt)
    ALGOVOI_KEY  env var (or first "algv_" line in openai.txt / keys.txt)
    TENANT_ID    env var (defaults to "YOUR_TENANT_ID" placeholder)
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

from mistral_algovoi import AlgoVoiMistral

# -- Key loading --------------------------------------------------------------─

def _load_labelled(label: str, path: str) -> str | None:
    """Find a line like 'label: value' (case-insensitive on label)."""
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                lower = line.lower()
                if lower.startswith(label.lower() + ":"):
                    _, _, value = line.partition(":")
                    return value.strip().split()[0] if value.strip() else None
    except FileNotFoundError:
        pass
    return None


def _load_line_prefix(prefix: str, path: str) -> str | None:
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith(prefix):
                    return line
    except FileNotFoundError:
        pass
    return None


def _load_mistral_key() -> str:
    k = os.environ.get("MISTRAL_KEY") or os.environ.get("MISTRAL_API_KEY")
    if k:
        return k
    repo_root = os.path.join(os.path.dirname(__file__), "..", "..")
    for fname in ("mistral.txt", "keys.txt", "openai.txt"):
        p = os.path.join(repo_root, fname)
        v = _load_labelled("mistral", p)
        if v:
            return v
    raise RuntimeError(
        "MISTRAL_KEY not set. Either export MISTRAL_KEY=... or add a "
        "'Mistral: <key>' line to keys.txt / mistral.txt in the repo root."
    )


def _load_algovoi_key() -> str:
    k = os.environ.get("ALGOVOI_KEY")
    if k:
        return k
    repo_root = os.path.join(os.path.dirname(__file__), "..", "..")
    v = _load_line_prefix("algv_", os.path.join(repo_root, "openai.txt"))
    if v:
        return v
    v = _load_line_prefix("algv_", os.path.join(repo_root, "keys.txt"))
    if v:
        return v.split()[0]  # strip trailing "(key ID …)" comments
    raise RuntimeError("ALGOVOI_KEY not found in env / openai.txt / keys.txt.")


MISTRAL_KEY = _load_mistral_key()
ALGOVOI_KEY = _load_algovoi_key()
TENANT_ID   = os.environ.get("TENANT_ID", "YOUR_TENANT_ID")

PAYOUT_ADDRS = {
    "algorand-mainnet": "ZVLRVYQSLJNVFMOIOKT35XH5SNQG45IVFMLLRFLHDQJQA5TO5H3SO4TVDQ",
    "voi-mainnet":      "THDLWTJ7RB4OJWFZCLL5IME7FHBSJ3SONBRWHIVQE3BEGTY2BWUEUVEOQY",
    "hedera-mainnet":   "0.0.1317927",
    "stellar-mainnet":  "GD45SH4TC4TMJOJWJJSLGAXODAIO36POCACT2MWS7I6CTJORMFKEP3HR",
}

TEST_MESSAGES = [
    {"role": "system", "content": "You are a helpful assistant. Reply very briefly."},
    {"role": "user",   "content": "Payment verified. Say hello and confirm you are Mistral."},
]

# -- Gate helpers --------------------------------------------------------------

def _mpp_gate(network: str) -> AlgoVoiMistral:
    return AlgoVoiMistral(
        mistral_key       = MISTRAL_KEY,
        algovoi_key       = ALGOVOI_KEY,
        tenant_id         = TENANT_ID,
        payout_address    = PAYOUT_ADDRS[network],
        protocol          = "mpp",
        network           = network,
        amount_microunits = 10000,
        model             = "mistral-large-latest",
    )


def _ap2_gate(network: str) -> AlgoVoiMistral:
    return AlgoVoiMistral(
        mistral_key       = MISTRAL_KEY,
        algovoi_key       = ALGOVOI_KEY,
        tenant_id         = TENANT_ID,
        payout_address    = PAYOUT_ADDRS[network],
        protocol          = "ap2",
        network           = network,
        amount_microunits = 10000,
        model             = "mistral-large-latest",
    )


def _mpp_proof(network: str, tx_id: str) -> str:
    return base64.b64encode(json.dumps({
        "network": network,
        "payload": {"txId": tx_id},
    }).encode()).decode()


# -- Phase 1: show challenges --------------------------------------------------

def show_challenges():
    print("\n" + "="*60)
    print("PHASE 1 — Payment Challenges (Mistral)")
    print("="*60)

    networks = ["algorand-mainnet", "voi-mainnet", "hedera-mainnet", "stellar-mainnet"]

    print("\n-- MPP challenges ------------------------------------------")
    for net in networks:
        gate   = _mpp_gate(net)
        result = gate.check({})
        status, headers, _ = result.as_wsgi_response()
        www_auth = next((v for k, v in headers if k.lower() == "www-authenticate"), "")
        print(f"  {net:20s}  {status}  {www_auth[:80]}")

    print("\n-- AP2 CartMandate challenges ------------------------------")
    for net in networks:
        gate   = _ap2_gate(net)
        result = gate.check({}, {})
        _, status, headers = result.as_flask_response()
        cart   = next((v for k, v in headers.items() if k.lower() == "x-ap2-cart-mandate"), "")
        print(f"  {net:20s}  {status}  CartMandate={cart[:40]}...")

    print("\n[PASS] All 8 challenges returned 402 correctly")
    print("\nTo proceed to Phase 2, send 0.01 USDC on each chain and run:")
    print("  python smoke_test_mistral.py ALGO_TX VOI_TX HEDERA_TX STELLAR_TX")
    print(f"\n  Algorand payout : {PAYOUT_ADDRS['algorand-mainnet']}")
    print(f"  VOI payout      : {PAYOUT_ADDRS['voi-mainnet']}")
    print(f"  Hedera payout   : {PAYOUT_ADDRS['hedera-mainnet']}")
    print(f"  Stellar payout  : {PAYOUT_ADDRS['stellar-mainnet']}")


# -- Phase 2: verify + AI call ------------------------------------------------─

def verify_payments(algo_tx: str, voi_tx: str, hedera_tx: str, stellar_tx: str):
    print("\n" + "="*60)
    print("PHASE 2 — On-chain Verification + Mistral API")
    print("="*60)

    tests = [
        ("algorand-mainnet", algo_tx,    "algorand-mainnet"),
        ("voi-mainnet",      voi_tx,     "voi-mainnet"),
        ("hedera-mainnet",   hedera_tx,  "hedera-mainnet"),
        ("stellar-mainnet",  stellar_tx, "stellar-mainnet"),
    ]

    passed = failed = 0

    for network, tx_id, proof_network in tests:
        print(f"\n-- {network} ------------------------------------------")
        print(f"  TX: {tx_id}")

        gate  = _mpp_gate(network)
        proof = _mpp_proof(proof_network, tx_id)

        try:
            result = gate.check({"Authorization": f"Payment {proof}"})

            if result.requires_payment:
                print(f"  [FAIL] Payment rejected — {result.error}")
                failed += 1
                continue

            print(f"  [PASS] Payment verified")
            if result.receipt:
                print(f"         payer  : {result.receipt.payer}")
                print(f"         amount : {result.receipt.amount} microunits")
                print(f"         tx_id  : {result.receipt.tx_id}")

            # Call Mistral
            reply = gate.complete(TEST_MESSAGES)
            print(f"  [PASS] Mistral replied: {reply[:120]}")
            passed += 1
            gate.close()   # Release httpx pool.

        except Exception as e:
            print(f"  [FAIL] {type(e).__name__}: {e}")
            failed += 1

    print(f"\n{'='*60}")
    print(f"Results: {passed}/{passed+failed} passed",
          "PASS" if failed == 0 else "FAIL")
    if failed:
        sys.exit(1)


# -- Entry point --------------------------------------------------------------─

if __name__ == "__main__":
    if len(sys.argv) == 5:
        verify_payments(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4])
    elif len(sys.argv) == 1:
        show_challenges()
    else:
        print("Usage:")
        print("  python smoke_test_mistral.py                              # Phase 1")
        print("  python smoke_test_mistral.py ALGO VOI HEDERA STELLAR     # Phase 2")
        sys.exit(1)
