"""
MPP Smoke Test — live 0.01 USDC payments across all 4 chains.

Run:   python smoke_test_mpp.py
Then:  python smoke_test_mpp.py verify <algorand_tx> <voi_tx> <hedera_tx> <stellar_tx>

AlgoVoi docs: https://github.com/chopmob-cloud/AlgoVoi-Platform-Adapters
Copyright (c) 2026 Christopher Hopley (ilovechicken.co.uk). BSL 1.1.
"""

import base64
import json
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))
from mpp import MppGate

# ── Payout addresses (confirmed from prior smoke tests) ──────────────────────
PAYOUT = {
    "algorand_mainnet": "ZVLRVYQSLJNVFMOIOKT35XH5SNQG45IVFMLLRFLHDQJQA5TO5H3SO4TVDQ",
    "voi_mainnet":      "THDLWTJ7RB4OJWFZCLL5IME7FHBSJ3SONBRWHIVQE3BEGTY2BWUEUVEOQY",
    "hedera_mainnet":   "0.0.1317927",
    "stellar_mainnet":  "GD45SH4TC4TMJOJWJJSLGAXODAIO36POCACT2MWS7I6CTJORMFKEP3HR",
}

AMOUNT = 10000  # 0.01 USDC (6 decimals)

GATES = {
    net: MppGate(
        api_base="https://api1.ilovechicken.co.uk",
        api_key="smoke-test",
        tenant_id="YOUR_TENANT_ID",
        resource_id=f"mpp-smoke-{net.replace('_', '-')}",
        amount_microunits=AMOUNT,
        networks=[net],
        realm="MPP Smoke Test",
        payout_address=PAYOUT[net],
        method=net.split("_")[0],  # e.g. "algorand", "voi", "hedera", "stellar"
    )
    for net in PAYOUT
}

CHAIN_LABELS = {
    "algorand_mainnet": "Algorand mainnet  (USDC ASA 31566704)",
    "voi_mainnet":      "VOI mainnet       (aUSDC ARC200 302190)",
    "hedera_mainnet":   "Hedera mainnet    (USDC HTS 0.0.456858)",
    "stellar_mainnet":  "Stellar pubnet    (USDC Circle)",
}


def show_challenges():
    print("\nMPP Smoke Test — Payment Challenges")
    print("=" * 60)
    print(f"Amount: 0.01 USDC on each chain\n")

    for net, gate in GATES.items():
        result = gate.check({})
        challenge = result.challenge
        accepts = challenge.accepts[0] if challenge and challenge.accepts else {}

        print(f"  Chain : {CHAIN_LABELS[net]}")
        print(f"  Pay to: {accepts.get('payTo', '')}")
        print(f"  Amount: {accepts.get('amount', '')} microunits (0.01 USDC)")
        print(f"  Asset : {accepts.get('asset', '')}")
        print(f"  method: {challenge.method}  intent: charge")
        print()

    print("Send 0.01 USDC on each chain to the address above, then run:")
    print("  python smoke_test_mpp.py verify <algo_tx> <voi_tx> <hedera_tx> <stellar_tx>")
    print()


def verify_payments(algo_tx, voi_tx, hedera_tx, stellar_tx):
    txs = {
        "algorand_mainnet": algo_tx,
        "voi_mainnet":      voi_tx,
        "hedera_mainnet":   hedera_tx,
        "stellar_mainnet":  stellar_tx,
    }

    print("\nMPP Smoke Test — Verification")
    print("=" * 60)

    passed = failed = 0

    for net, tx_id in txs.items():
        gate = GATES[net]
        network_wire = gate.NETWORKS[net]["network"]

        proof = base64.b64encode(json.dumps({
            "network": network_wire,
            "payload": {"txId": tx_id},
        }).encode()).decode()

        result = gate.check({"Authorization": f"Payment {proof}"})

        label = CHAIN_LABELS[net]
        if not result.requires_payment and result.receipt:
            r = result.receipt
            print(f"  [PASS] {label}")
            print(f"         tx={tx_id[:30]}...")
            print(f"         payer={r.payer[:30]}  amount={r.amount}")
            passed += 1
        else:
            print(f"  [FAIL] {label}")
            print(f"         tx={tx_id}")
            print(f"         error={result.error}")
            failed += 1

    print(f"\nResults: {passed} passed, {failed} failed")
    return failed == 0


if __name__ == "__main__":
    if len(sys.argv) == 6 and sys.argv[1] == "verify":
        ok = verify_payments(sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5])
        sys.exit(0 if ok else 1)
    else:
        show_challenges()
