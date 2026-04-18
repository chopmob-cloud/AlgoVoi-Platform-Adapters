"""
Semantic Kernel Adapter — two-phase smoke test
================================================

Phase 1 — Challenge render (no live AlgoVoi API needed)
    Verifies that each protocol / network combination returns the correct
    402 challenge without a payment proof, and that the plugin gate() method
    returns challenge JSON when no proof is supplied.

Phase 2 — Full on-chain round-trip + SK chat completion
    Requires real TX IDs from the 4 supported chains.

Usage:
    python smoke_test_semantic_kernel.py                                      # Phase 1
    python smoke_test_semantic_kernel.py ALGO_TX VOI_TX HEDERA_TX STELLAR_TX  # Phase 2

Credentials loaded from (in order):
    OPENAI_KEY / OPENAI_API_KEY  env var  — or 'OpenAI: <key>' in keys.txt
    ALGOVOI_KEY                  env var  — or first 'algv_' line in keys.txt
    TENANT_ID                    env var  — defaults to placeholder
"""

from __future__ import annotations

import base64
import argparse
import asyncio
import json
import os
import sys
import traceback
import types
from unittest.mock import MagicMock, AsyncMock, patch

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


# ── stub gate modules for phase-1 ────────────────────────────────────────────

def _make_challenge_gate(protocol: str, network: str) -> MagicMock:
    gate = MagicMock()
    result = MagicMock()
    result.requires_payment = True
    result.error = "Payment proof required"

    if protocol == "mpp":
        body = json.dumps({
            "error": "payment_required",
            "www_authenticate": (
                f'Payment resource="ai-function", network="{network}", '
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
    else:
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


import semantic_kernel_algovoi as sk_mod  # noqa: E402
from semantic_kernel_algovoi import AlgoVoiSemanticKernel, AlgoVoiPaymentPlugin  # noqa: E402


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
    ("ap2",  "stellar-mainnet"),
    ("x402", "algorand-mainnet"),
    ("x402", "hedera-mainnet"),
]


def run_phase1() -> int:
    _head("Phase 1 — challenge render (6 cases)")
    failures = 0

    for protocol, network in PHASE1_CASES:
        label = f"{protocol} / {network}"
        try:
            gate = _make_challenge_gate(protocol, network)
            _stub_protocol(protocol, gate)

            adapter = AlgoVoiSemanticKernel(
                algovoi_key="algv_smoke",
                tenant_id="smoke-tid",
                payout_address="SMOKE_ADDR",
                protocol=protocol,
                network=network,
                amount_microunits=10_000,
            )

            result = adapter.check({}, {})
            assert result.requires_payment
            status, _headers, body = result.as_wsgi_response()
            assert status == 402
            data = json.loads(body)
            assert "error" in data

            _ok(label)
        except Exception as exc:
            _fail(f"{label}: {exc}")
            traceback.print_exc()
            failures += 1

    return failures


def run_phase1_plugin() -> int:
    _head("Phase 1 — plugin gate() challenge (2 cases)")
    failures = 0

    for protocol in ("mpp", "ap2"):
        label = f"plugin / {protocol}"
        try:
            gate = _make_challenge_gate(protocol, "algorand-mainnet")
            _stub_protocol(protocol, gate)

            adapter = AlgoVoiSemanticKernel(
                algovoi_key="algv_smoke",
                tenant_id="smoke-tid",
                payout_address="SMOKE_ADDR",
                protocol=protocol,
                network="algorand-mainnet",
            )
            plugin = adapter.as_plugin(resource_fn=lambda q: "premium content")

            out = plugin.gate(query="test question", payment_proof="")
            data = json.loads(out)
            assert data["error"] == "payment_required"

            _ok(label)
        except Exception as exc:
            _fail(f"{label}: {exc}")
            traceback.print_exc()
            failures += 1

    return failures


def run_phase1_invoke() -> int:
    _head("Phase 1 — invoke_function() mock (1 case)")
    failures = 0
    try:
        gate = _make_challenge_gate("mpp", "algorand-mainnet")
        _stub_protocol("mpp", gate)

        adapter = AlgoVoiSemanticKernel(
            algovoi_key="algv_smoke",
            tenant_id="smoke-tid",
            payout_address="SMOKE_ADDR",
            protocol="mpp",
            network="algorand-mainnet",
        )

        mock_kernel = MagicMock()
        mock_fn = MagicMock()
        mock_kernel.invoke = AsyncMock(return_value="function result")

        with patch.object(sk_mod, "asyncio") as mock_asyncio:
            mock_asyncio.run.return_value = "function result"
            out = adapter.invoke_function(mock_kernel, mock_fn, input="hello")
        assert out == "function result"
        _ok("invoke_function shape correct")
    except Exception as exc:
        _fail(f"invoke_function: {exc}")
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
    print("PHASE 2 — On-chain Verification + Semantic Kernel complete()")
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
            adapter = AlgoVoiSemanticKernel(
                algovoi_key=algovoi_key,
                tenant_id=tenant_id,
                payout_address=PAYOUT_ADDRS[network],
                openai_key=openai_key,
                protocol="mpp",
                network=network,
                amount_microunits=10_000,
                model="gpt-4o",
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

    # SK chat completion — warn if semantic_kernel not installed
    print(f"\n-- SK complete() on algorand-mainnet -----------------------")
    try:
        adapter = AlgoVoiSemanticKernel(
            algovoi_key=algovoi_key,
            tenant_id=tenant_id,
            payout_address=PAYOUT_ADDRS["algorand-mainnet"],
            openai_key=openai_key,
            protocol="mpp",
            network="algorand-mainnet",
            model="gpt-4o",
        )
        reply = adapter.complete([{"role": "user", "content": "Reply with exactly: AlgoVoi SK OK"}])
        assert isinstance(reply, str) and len(reply) > 0
        print(f"  [PASS] complete() reply: {reply[:80]}")
        passed += 1
    except ModuleNotFoundError as exc:
        print(f"  [WARN] semantic_kernel not installed — skipping: {exc}")
    except Exception as exc:
        print(f"  [FAIL] {type(exc).__name__}: {exc}")
        traceback.print_exc()
        failed += 1

    # Plugin verified path using algo_tx proof
    print(f"\n-- plugin gate() on algorand-mainnet -----------------------")
    try:
        if algo_tx != "skip":
            adapter = AlgoVoiSemanticKernel(
                algovoi_key=algovoi_key,
                tenant_id=tenant_id,
                payout_address=PAYOUT_ADDRS["algorand-mainnet"],
                protocol="mpp",
                network="algorand-mainnet",
            )
            proof = _mpp_proof("algorand-mainnet", algo_tx)
            plugin = adapter.as_plugin(resource_fn=lambda q: f"Answer to: {q}")
            out = plugin.gate(query="What is AlgoVoi?", payment_proof=proof)
            assert "Answer to" in out
            print(f"  [PASS] plugin gate output: {out[:80]}")
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
    total += run_phase1_plugin()
    total += run_phase1_invoke()

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
        print("  python smoke_test_semantic_kernel.py                              # Phase 1")
        print("  python smoke_test_semantic_kernel.py ALGO VOI HEDERA STELLAR     # Phase 2")
        sys.exit(1)
