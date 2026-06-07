"""
OpenAI Adapter Smoke Test — live 0.01 USDC payments across all 4 chains.

Phase 1 (show challenges):
    python smoke_test_openai.py

Phase 2 (verify + call AI):
    python smoke_test_openai.py verify <algo_tx> <voi_tx> <hedera_tx> <stellar_tx>

Env vars:
    ALGOVOI_KEY    AlgoVoi API key   (default: smoke-test)
    OPENAI_KEY     OpenAI API key    (default: reads ../../../openai.txt)
    TENANT_ID      AlgoVoi tenant UUID

AlgoVoi docs: https://github.com/chopmob-cloud/AlgoVoi-Platform-Adapters
Licensed under the Business Source License 1.1 — see LICENSE for details.
"""

import base64
import json
import os
import sys

# ── resolve paths ────────────────────────────────────────────────────────────
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))   # platform-adapters/

sys.path.insert(0, _HERE)
from openai_algovoi import AlgoVoiOpenAI, _CAIP2, _ASSET_ID

# ── credentials ──────────────────────────────────────────────────────────────

def _load_openai_key() -> str:
    key = os.environ.get("OPENAI_KEY", "")
    if key:
        return key.strip()
    txt = os.path.join(_ROOT, "openai.txt")
    if os.path.exists(txt):
        with open(txt) as f:
            for line in f:
                line = line.strip()
                if line and line.startswith("sk-"):
                    return line
    raise SystemExit("OPENAI_KEY not set and no sk- key found in openai.txt")

ALGOVOI_KEY = os.environ.get("ALGOVOI_KEY", "smoke-test")
TENANT_ID   = os.environ.get("TENANT_ID",   "YOUR_TENANT_ID")
OPENAI_KEY  = _load_openai_key()

# ── payout addresses (same as MPP/AP2 smoke tests) ───────────────────────────
PAYOUT = {
    "algorand-mainnet": "ZVLRVYQSLJNVFMOIOKT35XH5SNQG45IVFMLLRFLHDQJQA5TO5H3SO4TVDQ",
    "voi-mainnet":      "THDLWTJ7RB4OJWFZCLL5IME7FHBSJ3SONBRWHIVQE3BEGTY2BWUEUVEOQY",
    "hedera-mainnet":   "0.0.1317927",
    "stellar-mainnet":  "GD45SH4TC4TMJOJWJJSLGAXODAIO36POCACT2MWS7I6CTJORMFKEP3HR",
}

CHAIN_LABELS = {
    "algorand-mainnet": "Algorand mainnet  (USDC ASA 31566704)",
    "voi-mainnet":      "VOI mainnet       (aUSDC ARC200 302190)",
    "hedera-mainnet":   "Hedera mainnet    (USDC HTS 0.0.456858)",
    "stellar-mainnet":  "Stellar pubnet    (USDC Circle)",
}

AMOUNT = 10000   # 0.01 USDC

# ── gate factory ─────────────────────────────────────────────────────────────

def make_gate(network: str) -> AlgoVoiOpenAI:
    return AlgoVoiOpenAI(
        openai_key        = OPENAI_KEY,
        algovoi_key       = ALGOVOI_KEY,
        tenant_id         = TENANT_ID,
        payout_address    = PAYOUT[network],
        protocol          = "x402",
        network           = network,
        amount_microunits = AMOUNT,
        model             = "gpt-4o-mini",
    )


# ── Phase 1: show challenges ──────────────────────────────────────────────────

def show_challenges() -> None:
    print("\nOpenAI Adapter Smoke Test — x402 Payment Challenges")
    print("=" * 60)
    print(f"  Amount : 0.01 USDC per chain\n")

    for network, label in CHAIN_LABELS.items():
        gate   = make_gate(network)
        result = gate.check({})
        body, status, headers = result.as_flask_response()
        raw    = headers.get("X-PAYMENT-REQUIRED", "")
        try:
            challenge = json.loads(base64.b64decode(raw))
            acc = challenge["accepts"][0]
        except Exception:
            acc = {}

        print(f"  Chain  : {label}")
        print(f"  Pay to : {PAYOUT[network]}")
        print(f"  Amount : {acc.get('amount', AMOUNT)} microunits (0.01 USDC)")
        print(f"  Asset  : {acc.get('asset', _ASSET_ID[network])}")
        print(f"  Network: {acc.get('network', _CAIP2[network])}")
        print(f"  Status : {status}")
        print()

    print("Send 0.01 USDC on each chain to the address shown, then run:")
    print("  python smoke_test_openai.py verify <algo_tx> <voi_tx> <hedera_tx> <stellar_tx>")
    print()


# ── Phase 2: verify + call AI ─────────────────────────────────────────────────

def _build_x402_proof(network: str, tx_id: str) -> str:
    """
    Construct the X-PAYMENT header value for a confirmed on-chain TX.

    x402 spec v1 proof format:
      { "x402Version": 1, "network": "<caip2>", "payload": { "signature": "<tx_id>" } }
    """
    obj = {
        "x402Version": 1,
        "network": _CAIP2[network],
        "payload": {
            "signature": tx_id,
            "tx_id":     tx_id,
        },
    }
    return base64.b64encode(json.dumps(obj).encode()).decode()


def verify_payments(algo_tx: str, voi_tx: str, hedera_tx: str, stellar_tx: str) -> bool:
    txs = {
        "algorand-mainnet": algo_tx,
        "voi-mainnet":      voi_tx,
        "hedera-mainnet":   hedera_tx,
        "stellar-mainnet":  stellar_tx,
    }

    print("\nOpenAI Adapter Smoke Test — Verification + AI Call")
    print("=" * 60)

    passed = failed = 0

    for network, tx_id in txs.items():
        label = CHAIN_LABELS[network]
        proof = _build_x402_proof(network, tx_id)
        gate  = make_gate(network)

        print(f"\n  Chain : {label}")
        print(f"  TX    : {tx_id[:50]}{'...' if len(tx_id) > 50 else ''}")

        # Step 1: submit proof
        result = gate.check({"X-PAYMENT": proof})

        if result.requires_payment:
            print(f"  [FAIL] Payment not verified — {result.error or 'rejected'}")
            failed += 1
            continue

        print(f"  [PASS] Payment verified")

        # Step 2: call AI
        try:
            reply = gate.complete([
                {"role": "user", "content": f"Say 'Payment verified on {network}' in one sentence."}
            ])
            print(f"  [PASS] AI responded: {reply.strip()}")
            passed += 1
        except Exception as exc:
            print(f"  [FAIL] AI call failed — {exc}")
            failed += 1

    print(f"\n{'=' * 60}")
    print(f"Results: {passed} passed, {failed} failed")
    return failed == 0


# ── entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) == 6 and sys.argv[1] == "verify":
        ok = verify_payments(sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5])
        sys.exit(0 if ok else 1)
    else:
        show_challenges()
