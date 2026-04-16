"""
LangChain Adapter Smoke Test
=============================
Phase 1 — show_challenges(): renders the 402 payment challenges for MPP + AP2
           on all 4 chains (no live money moved).
Phase 2 — verify_payments(): takes real TX IDs, verifies on-chain, then calls
           ChatOpenAI via LangChain.

Usage:
    python smoke_test_langchain.py                                     # Phase 1
    python smoke_test_langchain.py ALGO_TX VOI_TX HEDERA_TX STELLAR_TX  # Phase 2

Credentials loaded from (in order):
    OPENAI_KEY / OPENAI_API_KEY  env var  — or 'OpenAI: <key>' in keys.txt
    ALGOVOI_KEY                  env var  — or first 'algv_' line in keys.txt
    TENANT_ID                    env var  — defaults to placeholder
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

from langchain_algovoi import AlgoVoiLangChain

# ── Credential loading ────────────────────────────────────────────────────────

def _load_labelled(label: str, path: str) -> str | None:
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.lower().startswith(label.lower() + ":"):
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
                    return line.split()[0]
    except FileNotFoundError:
        pass
    return None


def _load_openai_key() -> str:
    k = os.environ.get("OPENAI_KEY") or os.environ.get("OPENAI_API_KEY")
    if k:
        return k
    root = os.path.join(os.path.dirname(__file__), "..", "..")
    # Try labelled form first ("OpenAI: sk-...")
    for fname in ("keys.txt", "openai.txt"):
        v = _load_labelled("openai", os.path.join(root, fname))
        if v and v.startswith("sk-"):
            return v
    # Fall back to first bare sk- line in openai.txt
    txt = os.path.join(root, "openai.txt")
    try:
        with open(txt, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith("sk-"):
                    return line
    except FileNotFoundError:
        pass
    raise RuntimeError(
        "OPENAI_KEY not set. Export OPENAI_KEY=sk-... or add a 'sk-...' line to openai.txt."
    )


def _load_algovoi_key() -> str:
    k = os.environ.get("ALGOVOI_KEY")
    if k:
        return k
    root = os.path.join(os.path.dirname(__file__), "..", "..")
    for fname in ("openai.txt", "keys.txt"):
        v = _load_line_prefix("algv_", os.path.join(root, fname))
        if v:
            return v
    raise RuntimeError("ALGOVOI_KEY not found in env / openai.txt / keys.txt.")


OPENAI_KEY  = _load_openai_key()
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
    {"role": "user",   "content": "Payment verified. Say hello and confirm you are ChatGPT via LangChain."},
]

# ── Gate helpers ──────────────────────────────────────────────────────────────

def _mpp_gate(network: str) -> AlgoVoiLangChain:
    return AlgoVoiLangChain(
        openai_key        = OPENAI_KEY,
        algovoi_key       = ALGOVOI_KEY,
        tenant_id         = TENANT_ID,
        payout_address    = PAYOUT_ADDRS[network],
        protocol          = "mpp",
        network           = network,
        amount_microunits = 10000,
        model             = "gpt-4o",
    )


def _ap2_gate(network: str) -> AlgoVoiLangChain:
    return AlgoVoiLangChain(
        openai_key        = OPENAI_KEY,
        algovoi_key       = ALGOVOI_KEY,
        tenant_id         = TENANT_ID,
        payout_address    = PAYOUT_ADDRS[network],
        protocol          = "ap2",
        network           = network,
        amount_microunits = 10000,
        model             = "gpt-4o",
    )


def _mpp_proof(network: str, tx_id: str) -> str:
    return base64.b64encode(json.dumps({
        "network": network,
        "payload": {"txId": tx_id},
    }).encode()).decode()


# ── Phase 1 ───────────────────────────────────────────────────────────────────

def show_challenges():
    print("\n" + "=" * 60)
    print("PHASE 1 — Payment Challenges (LangChain / ChatOpenAI)")
    print("=" * 60)

    networks = ["algorand-mainnet", "voi-mainnet", "hedera-mainnet", "stellar-mainnet"]

    print("\n-- MPP challenges ------------------------------------------")
    for net in networks:
        gate   = _mpp_gate(net)
        result = gate.check({})
        _, status, headers = result.as_flask_response()
        www_auth = next((v for k, v in headers.items() if k.lower() == "www-authenticate"), "")
        print(f"  {net:20s}  {status}  {www_auth[:80]}")

    print("\n-- AP2 CartMandate challenges ------------------------------")
    for net in networks:
        gate   = _ap2_gate(net)
        result = gate.check({}, {})
        _, status, headers = result.as_flask_response()
        cart = next((v for k, v in headers.items() if k.lower() == "x-ap2-cart-mandate"), "")
        print(f"  {net:20s}  {status}  CartMandate={cart[:40]}...")

    print("\n[PASS] All 8 challenges returned 402 correctly")
    print("\nTo run Phase 2, send 0.01 USDC on each chain then:")
    print("  python smoke_test_langchain.py ALGO_TX VOI_TX HEDERA_TX STELLAR_TX")
    print(f"\n  Algorand payout : {PAYOUT_ADDRS['algorand-mainnet']}")
    print(f"  VOI payout      : {PAYOUT_ADDRS['voi-mainnet']}")
    print(f"  Hedera payout   : {PAYOUT_ADDRS['hedera-mainnet']}")
    print(f"  Stellar payout  : {PAYOUT_ADDRS['stellar-mainnet']}")


# ── Phase 2 ───────────────────────────────────────────────────────────────────

def verify_payments(algo_tx: str, voi_tx: str, hedera_tx: str, stellar_tx: str):
    print("\n" + "=" * 60)
    print("PHASE 2 — On-chain Verification + LangChain ChatOpenAI")
    print("=" * 60)

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
                print(f"  [FAIL] Payment rejected — {result.error}")
                failed += 1
                continue

            print("  [PASS] Payment verified")
            if result.receipt:
                print(f"         payer  : {result.receipt.payer}")
                print(f"         amount : {result.receipt.amount} microunits")
                print(f"         tx_id  : {result.receipt.tx_id}")

            reply = gate.complete(TEST_MESSAGES)
            print(f"  [PASS] LangChain replied: {reply[:120]}")
            passed += 1

        except Exception as e:
            print(f"  [FAIL] {type(e).__name__}: {e}")
            failed += 1

    # ── Agent tool phase ──────────────────────────────────────────────────────
    print(f"\n-- Agent tool (as_tool) on algorand-mainnet ----------------")
    try:
        gate  = _mpp_gate("algorand-mainnet")
        proof = _mpp_proof("algorand-mainnet", algo_tx)

        resource_fn = lambda q: f"Protected answer to: {q}"
        tool = gate.as_tool(resource_fn=resource_fn, tool_name="demo_gate")

        tool_input_no_proof = json.dumps({"query": "hello"})
        challenge_output    = tool._run(tool_input_no_proof)
        challenge_data      = json.loads(challenge_output)
        assert challenge_data.get("error") == "payment_required", (
            f"Expected payment_required challenge, got: {challenge_data}"
        )
        print("  [PASS] Tool returns challenge JSON when proof absent")

        tool_input_with_proof = json.dumps({"query": "hello", "payment_proof": proof})
        resource_output       = tool._run(tool_input_with_proof)
        assert resource_output == "Protected answer to: hello", (
            f"Unexpected resource output: {resource_output}"
        )
        print(f"  [PASS] Tool returned resource response: {resource_output}")
        passed += 1

    except Exception as e:
        print(f"  [FAIL] {type(e).__name__}: {e}")
        failed += 1

    print(f"\n{'=' * 60}")
    print(f"Results: {passed}/{passed + failed} passed",
          "PASS" if failed == 0 else "FAIL")
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
        print("  python smoke_test_langchain.py                              # Phase 1")
        print("  python smoke_test_langchain.py ALGO VOI HEDERA STELLAR     # Phase 2")
        sys.exit(1)
