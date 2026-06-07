"""
AutoGen Adapter — two-phase smoke test
=======================================

Phase 1 — Challenge render (no live AlgoVoi API needed)
    Verifies that each protocol / network combination returns the correct
    402 challenge without a payment proof, and that the callable tool returns
    challenge JSON when no proof is supplied.

Phase 2 — Full on-chain round-trip + initiate_chat
    Requires real TX IDs from the 4 supported chains.

Usage:
    python smoke_test_autogen.py                                      # Phase 1
    python smoke_test_autogen.py ALGO_TX VOI_TX HEDERA_TX STELLAR_TX  # Phase 2

Credentials loaded from (in order):
    OPENAI_KEY / OPENAI_API_KEY  env var  — or 'OpenAI: <key>' in keys.txt
    ALGOVOI_KEY                  env var  — or first 'algv_' line in keys.txt
    TENANT_ID                    env var  — defaults to placeholder
"""

from __future__ import annotations

import base64
import argparse
import json
import os
import sys
import traceback
import types
from unittest.mock import MagicMock

# ── path setup ────────────────────────────────────────────────────────────────
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)


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
    root = os.path.join(_HERE, "..", "..")
    for fname in ("keys.txt", "openai.txt"):
        v = _load_labelled("openai", os.path.join(root, fname))
        if v and v.startswith("sk-"):
            return v
    txt = os.path.join(root, "openai.txt")
    try:
        with open(txt, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith("sk-"):
                    return line
    except FileNotFoundError:
        pass
    return ""


def _load_algovoi_key() -> str:
    k = os.environ.get("ALGOVOI_KEY")
    if k:
        return k
    root = os.path.join(_HERE, "..", "..")
    for fname in ("openai.txt", "keys.txt"):
        v = _load_line_prefix("algv_", os.path.join(root, fname))
        if v:
            return v
    return ""


PAYOUT_ADDRS = {
    "algorand-mainnet": "ZVLRVYQSLJNVFMOIOKT35XH5SNQG45IVFMLLRFLHDQJQA5TO5H3SO4TVDQ",
    "voi-mainnet":      "THDLWTJ7RB4OJWFZCLL5IME7FHBSJ3SONBRWHIVQE3BEGTY2BWUEUVEOQY",
    "hedera-mainnet":   "0.0.1317927",
    "stellar-mainnet":  "GD45SH4TC4TMJOJWJJSLGAXODAIO36POCACT2MWS7I6CTJORMFKEP3HR",
}


def _mpp_proof(network: str, tx_id: str) -> str:
    return base64.b64encode(json.dumps({
        "network": network,
        "payload": {"txId": tx_id},
    }).encode()).decode()


# ── stub gate modules for phase-1 tests ──────────────────────────────────────

def _make_challenge_gate(protocol: str, network: str) -> MagicMock:
    gate = MagicMock()
    result = MagicMock()
    result.requires_payment = True
    result.error = "Payment proof required"

    if protocol == "mpp":
        body = json.dumps({
            "error": "payment_required",
            "www_authenticate": (
                f'Payment resource="ai-conversation", network="{network}", '
                f'amount="10000", currency="USDC"'
            ),
        }).encode()
    elif protocol == "ap2":
        body = json.dumps({
            "error": "payment_required",
            "ap2_challenge": json.dumps({
                "protocol": "ap2", "network": network,
                "amount_microunits": 10000, "currency": "USDC",
            }),
        }).encode()
    else:  # x402
        body = json.dumps({
            "error": "payment_required",
            "x_payment_required": json.dumps({
                "x402Version": 1, "network": network,
                "amount": "10000", "currency": "USDC",
            }),
        }).encode()

    result.as_wsgi_response.return_value = (402, [], body)
    mock_resp = MagicMock()
    mock_resp.status_code = 402
    mock_resp.data = body
    result.as_flask_response.return_value = mock_resp
    gate.check.return_value = result
    return gate


def _stub_protocol(protocol: str, gate: MagicMock) -> None:
    if protocol == "mpp":
        mod = types.ModuleType("mpp")
        mod.MppGate = MagicMock(return_value=gate)
        sys.modules["mpp"] = mod
    elif protocol == "ap2":
        mod = types.ModuleType("ap2")
        mod.Ap2Gate = MagicMock(return_value=gate)
        sys.modules["ap2"] = mod
    else:
        mod = types.ModuleType("openai_algovoi")
        mod._X402Gate = MagicMock(return_value=gate)
        sys.modules["openai_algovoi"] = mod


from autogen_algovoi import AlgoVoiAutoGen, AlgoVoiPaymentTool  # noqa: E402


# ── colour helpers ─────────────────────────────────────────────────────────────

def _ok(msg: str) -> None:
    print(f"  \033[92mPASS\033[0m  {msg}")

def _fail(msg: str) -> None:
    print(f"  \033[91mFAIL\033[0m  {msg}")

def _head(msg: str) -> None:
    print(f"\n\033[1m{msg}\033[0m")


# ══════════════════════════════════════════════════════════════════════════════
# Phase 1 — challenge render
# ══════════════════════════════════════════════════════════════════════════════

PHASE1_CASES = [
    ("mpp",  "algorand-mainnet"),
    ("mpp",  "voi-mainnet"),
    ("ap2",  "algorand-mainnet"),
    ("ap2",  "hedera-mainnet"),
    ("x402", "algorand-mainnet"),
    ("x402", "stellar-mainnet"),
]


def run_phase1() -> int:
    _head("Phase 1 — challenge render (6 cases)")
    failures = 0

    for protocol, network in PHASE1_CASES:
        label = f"{protocol} / {network}"
        try:
            gate = _make_challenge_gate(protocol, network)
            _stub_protocol(protocol, gate)

            adapter = AlgoVoiAutoGen(
                algovoi_key="algv_smoke",
                tenant_id="smoke-tid",
                payout_address="SMOKE_ADDR",
                protocol=protocol,
                network=network,
                amount_microunits=10_000,
            )

            result = adapter.check({}, {})
            assert result.requires_payment, "requires_payment should be True"

            status, _headers, body = result.as_wsgi_response()
            assert status == 402, f"expected 402, got {status}"
            data = json.loads(body)
            assert "error" in data, f"no 'error' in body: {data}"

            _ok(label)
        except Exception as exc:
            _fail(f"{label}: {exc}")
            traceback.print_exc()
            failures += 1

    return failures


def run_phase1_tool() -> int:
    _head("Phase 1 — callable tool challenge (2 cases)")
    failures = 0

    for protocol in ("mpp", "ap2"):
        label = f"tool / {protocol}"
        try:
            gate = _make_challenge_gate(protocol, "algorand-mainnet")
            _stub_protocol(protocol, gate)

            adapter = AlgoVoiAutoGen(
                algovoi_key="algv_smoke",
                tenant_id="smoke-tid",
                payout_address="SMOKE_ADDR",
                protocol=protocol,
                network="algorand-mainnet",
            )
            tool = adapter.as_tool(resource_fn=lambda q: "premium content")

            out = tool(query="test question", payment_proof="")
            data = json.loads(out)
            assert data["error"] == "payment_required", f"unexpected: {data}"

            _ok(label)
        except Exception as exc:
            _fail(f"{label}: {exc}")
            traceback.print_exc()
            failures += 1

    return failures


def run_phase1_llm_config() -> int:
    _head("Phase 1 — llm_config property (1 case)")
    failures = 0
    try:
        gate = _make_challenge_gate("mpp", "algorand-mainnet")
        _stub_protocol("mpp", gate)
        adapter = AlgoVoiAutoGen(
            algovoi_key="algv_smoke",
            tenant_id="smoke-tid",
            payout_address="SMOKE_ADDR",
            openai_key="sk-smoke",
            model="gpt-4o",
        )
        cfg = adapter.llm_config
        assert "config_list" in cfg
        assert cfg["config_list"][0]["model"] == "gpt-4o"
        assert cfg["config_list"][0]["api_key"] == "sk-smoke"
        _ok("llm_config shape correct")
    except Exception as exc:
        _fail(f"llm_config: {exc}")
        traceback.print_exc()
        failures += 1
    return failures


# ══════════════════════════════════════════════════════════════════════════════
# Phase 2 — live on-chain verification via real TX IDs
# ══════════════════════════════════════════════════════════════════════════════

def verify_payments(algo_tx: str, voi_tx: str, hedera_tx: str, stellar_tx: str) -> int:
    algovoi_key = _load_algovoi_key()
    openai_key  = _load_openai_key()
    tenant_id   = os.environ.get("TENANT_ID", "YOUR_TENANT_ID")

    if not algovoi_key:
        print("\n\033[91mALGOVOI_KEY not found — cannot run Phase 2\033[0m")
        return 1

    # Remove phase-1 stubs so real modules are imported
    for k in ("mpp", "ap2", "openai_algovoi"):
        sys.modules.pop(k, None)

    print("\n" + "=" * 60)
    print("PHASE 2 — On-chain Verification + AutoGen initiate_chat")
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
        if tx_id == "skip":
            print("  [WARN] skipped")
            continue
        print(f"  TX: {tx_id}")

        try:
            adapter = AlgoVoiAutoGen(
                algovoi_key=algovoi_key,
                tenant_id=tenant_id,
                payout_address=PAYOUT_ADDRS[network],
                openai_key=openai_key,
                protocol="mpp",
                network=network,
                amount_microunits=10_000,
            )

            # Step 1 — challenge
            result = adapter.check({}, {})
            assert result.requires_payment, "should require payment on first call"

            # Step 2 — build proof from TX ID
            proof = _mpp_proof(network, tx_id)

            # Step 3 — verify
            result2 = adapter.check({"Authorization": f"Payment {proof}"}, {})
            assert not result2.requires_payment, f"payment rejected: {getattr(result2, 'error', '')}"

            print("  [PASS] Payment verified")
            if hasattr(result2, "receipt") and result2.receipt:
                print(f"         payer  : {result2.receipt.payer}")
                print(f"         amount : {result2.receipt.amount} microunits")
                print(f"         tx_id  : {result2.receipt.tx_id}")
            passed += 1

        except Exception as exc:
            print(f"  [FAIL] {type(exc).__name__}: {exc}")
            traceback.print_exc()
            failed += 1

    # initiate_chat smoke — mock conversation (no live AutoGen install required)
    print(f"\n-- initiate_chat (AutoGen 0.2.x mock conversation) ---------")
    try:
        from unittest.mock import MagicMock as _MM
        cr = _MM()
        cr.summary = "AutoGen says: Hello from AlgoVoi"
        cr.chat_history = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "AutoGen says: Hello from AlgoVoi"},
        ]
        sender = _MM()
        sender.initiate_chat.return_value = cr
        recipient = _MM()

        adapter = AlgoVoiAutoGen(
            algovoi_key=algovoi_key,
            tenant_id=tenant_id,
            payout_address=PAYOUT_ADDRS["algorand-mainnet"],
            openai_key=openai_key,
            protocol="mpp",
            network="algorand-mainnet",
        )

        output = adapter.initiate_chat(recipient, sender, "Hello agent", max_turns=3)
        assert isinstance(output, str) and len(output) > 0
        print(f"  [PASS] initiate_chat result: {output[:80]}")
        passed += 1
    except Exception as exc:
        print(f"  [FAIL] initiate_chat: {type(exc).__name__}: {exc}")
        traceback.print_exc()
        failed += 1

    # callable tool — verified path using algo_tx proof
    print(f"\n-- callable tool (as_tool) on algorand-mainnet ---------------")
    try:
        if algo_tx != "skip":
            adapter = AlgoVoiAutoGen(
                algovoi_key=algovoi_key,
                tenant_id=tenant_id,
                payout_address=PAYOUT_ADDRS["algorand-mainnet"],
                protocol="mpp",
                network="algorand-mainnet",
            )
            proof = _mpp_proof("algorand-mainnet", algo_tx)
            tool = adapter.as_tool(resource_fn=lambda q: f"Answer to: {q}")
            out = tool(query="What is AlgoVoi?", payment_proof=proof)
            assert "Answer to" in out, f"unexpected: {out}"
            print(f"  [PASS] tool output: {out[:80]}")
            passed += 1
        else:
            print("  [WARN] skipped (algo_tx == skip)")
    except Exception as exc:
        print(f"  [FAIL] {type(exc).__name__}: {exc}")
        traceback.print_exc()
        failed += 1

    print(f"\n{'=' * 60}")
    print(f"Results: {passed}/{passed + failed} passed",
          "PASS" if failed == 0 else "FAIL")
    return 1 if failed else 0


# ══════════════════════════════════════════════════════════════════════════════
# Entry point
# ══════════════════════════════════════════════════════════════════════════════

def main() -> None:
    total = 0
    total += run_phase1()
    total += run_phase1_tool()
    total += run_phase1_llm_config()

    if total == 0:
        print(f"\n\033[92mAll smoke tests passed.\033[0m\n")
        sys.exit(0)
    else:
        print(f"\n\033[91m{total} smoke test(s) failed.\033[0m\n")
        sys.exit(1)


if __name__ == "__main__":
    if len(sys.argv) == 5:
        sys.exit(verify_payments(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]))
    elif len(sys.argv) == 1:
        main()
    else:
        print("Usage:")
        print("  python smoke_test_autogen.py                              # Phase 1")
        print("  python smoke_test_autogen.py ALGO VOI HEDERA STELLAR     # Phase 2")
        sys.exit(1)
