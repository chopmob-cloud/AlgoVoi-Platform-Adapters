"""
AlgoVoi Full Multi-Chain Smoke Test
====================================
Tests all 4 chains × 2 tokens each (stablecoin + native) via the MPP gate.

Networks covered (8 mainnet):
  algorand_mainnet       Algorand  USDC   (ASA 31566704)
  algorand_mainnet_algo  Algorand  ALGO   (native)
  voi_mainnet            VOI       aUSDC  (ARC-200 302190)
  voi_mainnet_voi        VOI       VOI    (native)
  hedera_mainnet         Hedera    USDC   (HTS 0.0.456858)
  hedera_mainnet_hbar    Hedera    HBAR   (native, 8 decimals)
  stellar_mainnet        Stellar   USDC   (Circle trust-line)
  stellar_mainnet_xlm    Stellar   XLM    (native)

Phase 1 — challenge render (no live payments, offline):
    python smoke_test_full.py

Phase 2 — on-chain TX verification (provide real confirmed TX IDs):
    python smoke_test_full.py verify \\
        <algo_usdc_tx>  <algo_algo_tx>  \\
        <voi_usdc_tx>   <voi_voi_tx>   \\
        <hedera_usdc_tx> <hedera_hbar_tx> \\
        <stellar_usdc_tx> <stellar_xlm_tx>

    Use "skip" for any network you have not yet funded.

Credentials loaded from env vars or keys.txt / openai.txt in the repo root.

AlgoVoi docs: https://github.com/chopmob-cloud/AlgoVoi-Platform-Adapters
"""

from __future__ import annotations

import base64
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from mpp import MppGate

# ── Credential loading ────────────────────────────────────────────────────────

def _load_line_prefix(prefix: str, path: str) -> str | None:
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                stripped = line.strip()
                if stripped.startswith(prefix):
                    return stripped.split()[0]
    except FileNotFoundError:
        pass
    return None


def _load_key() -> str:
    k = (os.environ.get("ALGOVOI_API_KEY")
         or os.environ.get("ALGOVOI_KEY"))
    if k:
        return k
    root = os.path.join(os.path.dirname(__file__), "..")
    for fname in ("keys.txt", "openai.txt"):
        v = _load_line_prefix("algv_", os.path.join(root, fname))
        if v:
            return v
    raise RuntimeError(
        "ALGOVOI_API_KEY not set and not found in keys.txt / openai.txt"
    )


ALGOVOI_KEY = _load_key()
TENANT_ID   = os.environ.get("ALGOVOI_TENANT_ID", os.environ.get("TENANT_ID", "YOUR_TENANT_ID"))

# ── Payout addresses ──────────────────────────────────────────────────────────
# Same wallet per chain — receives both stablecoin AND native token.
# Algorand and VOI wallets are Algorand-format addresses; Hedera is 0.0.X;
# Stellar is a G-address.

PAYOUT = {
    "algorand_mainnet":      "ZVLRVYQSLJNVFMOIOKT35XH5SNQG45IVFMLLRFLHDQJQA5TO5H3SO4TVDQ",
    "algorand_mainnet_algo": "ZVLRVYQSLJNVFMOIOKT35XH5SNQG45IVFMLLRFLHDQJQA5TO5H3SO4TVDQ",
    "voi_mainnet":           "THDLWTJ7RB4OJWFZCLL5IME7FHBSJ3SONBRWHIVQE3BEGTY2BWUEUVEOQY",
    "voi_mainnet_voi":       "THDLWTJ7RB4OJWFZCLL5IME7FHBSJ3SONBRWHIVQE3BEGTY2BWUEUVEOQY",
    "hedera_mainnet":        "0.0.1317927",
    "hedera_mainnet_hbar":   "0.0.1317927",
    "stellar_mainnet":       "GD45SH4TC4TMJOJWJJSLGAXODAIO36POCACT2MWS7I6CTJORMFKEP3HR",
    "stellar_mainnet_xlm":   "GD45SH4TC4TMJOJWJJSLGAXODAIO36POCACT2MWS7I6CTJORMFKEP3HR",
}

# ── Network display metadata ──────────────────────────────────────────────────

CHAINS = [
    # (net_key, chain, ticker, asset_label, amount_display, decimals, native)
    ("algorand_mainnet",      "Algorand", "USDC",  "ASA 31566704",                    "0.01 USDC",   6, False),
    ("algorand_mainnet_algo", "Algorand", "ALGO",  "native",                          "0.01 ALGO",   6, True),
    ("voi_mainnet",           "VOI",      "aUSDC", "ARC-200 302190",                  "0.01 aUSDC",  6, False),
    ("voi_mainnet_voi",       "VOI",      "VOI",   "native",                          "0.01 VOI",    6, True),
    ("hedera_mainnet",        "Hedera",   "USDC",  "HTS 0.0.456858",                  "0.01 USDC",   6, False),
    ("hedera_mainnet_hbar",   "Hedera",   "HBAR",  "native (tinybars)",               "10000 tinybars",  8, True),
    ("stellar_mainnet",       "Stellar",  "USDC",  "USDC:GA5ZS… (Circle trust-line)", "0.01 USDC",   7, False),
    ("stellar_mainnet_xlm",   "Stellar",  "XLM",   "native (stroops)",                "10000 stroops", 7, True),
]

# Phase 2 argument order matches CHAINS order above
AMOUNT = 10_000  # 0.01 USDC/ALGO/VOI; 0.0001 HBAR; 0.001 XLM


# ── Gate factory ─────────────────────────────────────────────────────────────

def _gate(net_key: str) -> MppGate:
    ticker = MppGate.NETWORKS[net_key]["ticker"]
    return MppGate(
        api_base="https://api1.ilovechicken.co.uk",
        api_key=ALGOVOI_KEY,
        tenant_id=TENANT_ID,
        resource_id=f"smoke-full-{net_key.replace('_', '-')}",
        amount_microunits=AMOUNT,
        networks=[net_key],
        realm="AlgoVoi Full Smoke",
        payout_address=PAYOUT[net_key],
        method=net_key.split("_")[0],   # "algorand", "voi", "hedera", "stellar"
    )


def _mpp_proof(net_key: str, tx_id: str) -> str:
    wire_network = MppGate.NETWORKS[net_key]["network"]
    return base64.b64encode(json.dumps({
        "network": wire_network,
        "payload": {"txId": tx_id},
    }).encode()).decode()


# ── Phase 1 — challenge render ────────────────────────────────────────────────

def show_challenges() -> None:
    print("\n" + "=" * 70)
    print("AlgoVoi Full Smoke — Phase 1: Payment Challenges (8 networks)")
    print("=" * 70)
    print(f"  Amount per test : {AMOUNT} microunits")
    print(f"  API key         : {ALGOVOI_KEY[:12]}…")
    print()

    all_pass = True
    for net_key, chain, ticker, asset_label, amount_disp, decimals, native in CHAINS:
        gate   = _gate(net_key)
        result = gate.check({})

        if not result.requires_payment:
            print(f"  [FAIL] {chain} {ticker:5s} — expected 402, got pass-through")
            all_pass = False
            continue

        ch = result.challenge
        accepts = ch.accepts[0] if ch and ch.accepts else {}

        print(f"  {chain:8s} {ticker:6s}  ({asset_label})")
        print(f"    Pay to : {accepts.get('payTo', '')}")
        print(f"    Amount : {accepts.get('amount', '')} ({amount_disp})")
        print(f"    Asset  : {accepts.get('asset', 'native')}")
        print(f"    Ticker : {accepts.get('ticker', ticker)}")
        print(f"    Method : {ch.method}  intent: charge")
        print()

    if all_pass:
        print("[PASS] All 8 networks returned HTTP 402 correctly.")
    else:
        print("[FAIL] One or more networks did not return 402.")
        sys.exit(1)

    print("\nTo run Phase 2, send the amounts above on each chain then:")
    print("  python smoke_test_full.py verify \\")
    print("      <algo_usdc_tx>  <algo_algo_tx>  \\")
    print("      <voi_usdc_tx>   <voi_voi_tx>   \\")
    print("      <hedera_usdc_tx> <hedera_hbar_tx> \\")
    print("      <stellar_usdc_tx> <stellar_xlm_tx>")
    print()
    print("  Use 'skip' for any network not yet funded.")
    print()
    print(f"  Known Algorand USDC TX (reusable for testing):")
    print(f"    DF2PQUPY6TVX3DD7GQSY7LEZNVGOEYC24NBIIHLKYM5RIA3UN4AQ")


# ── Phase 2 — on-chain verification ──────────────────────────────────────────

def verify_payments(tx_ids: list[str]) -> None:
    if len(tx_ids) != 8:
        print(f"ERROR: expected 8 TX IDs (use 'skip' for untested networks), got {len(tx_ids)}")
        sys.exit(1)

    print("\n" + "=" * 70)
    print("AlgoVoi Full Smoke — Phase 2: On-Chain Verification (8 networks)")
    print("=" * 70)

    passed = failed = skipped = 0

    for (net_key, chain, ticker, asset_label, amount_disp, decimals, native), tx_id in zip(CHAINS, tx_ids):

        label = f"{chain:8s} {ticker:6s}  ({asset_label})"

        if tx_id.lower() == "skip":
            print(f"  [SKIP] {label}")
            skipped += 1
            continue

        print(f"\n  {label}")
        print(f"    TX: {tx_id}")

        gate  = _gate(net_key)
        proof = _mpp_proof(net_key, tx_id)

        try:
            result = gate.check({"Authorization": f"Payment {proof}"})

            if result.requires_payment:
                print(f"    [FAIL] Payment rejected — {result.error}")
                failed += 1
                continue

            r = result.receipt
            print(f"    [PASS] Verified on-chain")
            if r:
                print(f"           payer  : {r.payer}")
                print(f"           amount : {r.amount} ({amount_disp})")
                print(f"           tx_id  : {r.tx_id[:52]}{'…' if len(r.tx_id) > 52 else ''}")
            passed += 1

        except Exception as exc:
            print(f"    [FAIL] {type(exc).__name__}: {exc}")
            failed += 1

    print(f"\n{'=' * 70}")
    print(f"Results: {passed} passed  {failed} failed  {skipped} skipped"
          f"  ({passed + failed + skipped}/8 networks)")
    if failed:
        print("OVERALL: FAIL")
        sys.exit(1)
    else:
        print("OVERALL: PASS")


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    args = sys.argv[1:]

    if not args:
        show_challenges()

    elif args[0] == "verify":
        verify_payments(args[1:])

    else:
        # Convenience: allow passing 8 TX IDs directly without "verify" keyword
        if len(args) == 8:
            verify_payments(args)
        else:
            print(__doc__)
            sys.exit(1)
