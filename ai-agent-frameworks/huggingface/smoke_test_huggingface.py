"""
Hugging Face Adapter — two-phase smoke test
=============================================

Phase 1 — Challenge render (no live AlgoVoi API needed)
    Verifies that each protocol / network combination returns the correct
    402 challenge header without a payment proof.

Phase 2 — Full on-chain round-trip + InferenceClient + smolagents tool
    Requires real TX IDs from the 4 supported chains.

Usage:
    python smoke_test_huggingface.py                                      # Phase 1
    python smoke_test_huggingface.py ALGO_TX VOI_TX HEDERA_TX STELLAR_TX  # Phase 2

Credentials loaded from (in order):
    ALGOVOI_KEY  env var  — or first 'algv_' line in keys.txt
    HF_TOKEN     env var  — or "" (HF calls will warn if absent)
    TENANT_ID    env var  — defaults to placeholder
"""

from __future__ import annotations

import base64
import argparse
import json
import os
import sys
import traceback
import types
import unittest
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
    """Return a mock gate that emits a realistic 402 challenge."""
    gate = MagicMock()
    result = MagicMock()
    result.requires_payment = True
    result.error = "Payment proof required"

    if protocol == "mpp":
        challenge_hdr = (
            f'Payment resource="ai-inference", '
            f'network="{network}", amount="10000", currency="USDC"'
        )
        flask_body = json.dumps({
            "error": "payment_required",
            "www_authenticate": challenge_hdr,
        }).encode()
    elif protocol == "ap2":
        challenge_hdr = json.dumps({
            "protocol": "ap2",
            "network": network,
            "amount_microunits": 10000,
            "currency": "USDC",
        })
        flask_body = json.dumps({
            "error": "payment_required",
            "ap2_challenge": challenge_hdr,
        }).encode()
    else:  # x402
        challenge_hdr = json.dumps({
            "x402Version": 1,
            "network": network,
            "amount": "10000",
            "currency": "USDC",
        })
        flask_body = json.dumps({
            "error": "payment_required",
            "x_payment_required": challenge_hdr,
        }).encode()

    import flask as _flask
    mock_resp = MagicMock()
    mock_resp.status_code = 402
    mock_resp.data = flask_body
    result.as_flask_response.return_value = mock_resp
    result.as_wsgi_response.return_value = (402, [], flask_body)

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


# stub smolagents + huggingface_hub for phase-1
_smolagents_mod = types.ModuleType("smolagents")
class _FakeTool:
    name: str = ""
    description: str = ""
    inputs: dict = {}
    output_type: str = "string"
    def __init__(self) -> None: pass
    def forward(self, **kwargs): raise NotImplementedError
_smolagents_mod.Tool = _FakeTool
sys.modules.setdefault("smolagents", _smolagents_mod)

_hfhub_mod = types.ModuleType("huggingface_hub")
_hfhub_mod.InferenceClient = MagicMock()
sys.modules.setdefault("huggingface_hub", _hfhub_mod)

from huggingface_algovoi import AlgoVoiHuggingFace, AlgoVoiPaymentTool  # noqa: E402

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

            adapter = AlgoVoiHuggingFace(
                algovoi_key="algv_smoke",
                tenant_id="smoke-tid",
                payout_address="SMOKE_ADDR",
                hf_token="hf_smoke",
                protocol=protocol,
                network=network,
                amount_microunits=10_000,
            )

            result = adapter.check({}, {})
            assert result.requires_payment, "requires_payment should be True"

            # Verify as_wsgi_response shape
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
    _head("Phase 1 — smolagents tool challenge (2 cases)")
    failures = 0

    for protocol in ("mpp", "ap2"):
        label = f"tool / {protocol}"
        try:
            gate = _make_challenge_gate(protocol, "algorand-mainnet")
            _stub_protocol(protocol, gate)

            adapter = AlgoVoiHuggingFace(
                algovoi_key="algv_smoke",
                tenant_id="smoke-tid",
                payout_address="SMOKE_ADDR",
                protocol=protocol,
                network="algorand-mainnet",
            )
            tool = adapter.as_tool(resource_fn=lambda q: "premium content")

            # No proof → challenge JSON
            out = tool.forward(query="test question", payment_proof="")
            data = json.loads(out)
            assert data["error"] == "payment_required", f"unexpected: {data}"

            _ok(label)
        except Exception as exc:
            _fail(f"{label}: {exc}")
            traceback.print_exc()
            failures += 1

    return failures


# ══════════════════════════════════════════════════════════════════════════════
# Phase 2 — live on-chain verification via real TX IDs
# ══════════════════════════════════════════════════════════════════════════════

def verify_payments(algo_tx: str, voi_tx: str, hedera_tx: str, stellar_tx: str) -> int:
    algovoi_key = _load_algovoi_key()
    hf_token    = os.environ.get("HF_TOKEN", "")
    tenant_id   = os.environ.get("TENANT_ID", "YOUR_TENANT_ID")

    if not algovoi_key:
        print("\n\033[91mALGOVOI_KEY not found — cannot run Phase 2\033[0m")
        return 1

    # Remove phase-1 stubs so real modules are imported
    for k in ("mpp", "ap2", "openai_algovoi", "huggingface_hub", "smolagents"):
        sys.modules.pop(k, None)

    print("\n" + "=" * 60)
    print("PHASE 2 — On-chain Verification + HuggingFace InferenceClient")
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
            adapter = AlgoVoiHuggingFace(
                algovoi_key=algovoi_key,
                tenant_id=tenant_id,
                payout_address=PAYOUT_ADDRS[network],
                hf_token=hf_token,
                protocol="mpp",
                network=network,
                amount_microunits=10_000,
                model="meta-llama/Meta-Llama-3-8B-Instruct",
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

    # InferenceClient.complete() — warn if HF token absent
    print(f"\n-- InferenceClient.complete() ------------------------------")
    try:
        if not hf_token:
            print("  [WARN] HF_TOKEN not set — skipping live InferenceClient call")
        else:
            adapter = AlgoVoiHuggingFace(
                algovoi_key=algovoi_key,
                tenant_id=tenant_id,
                payout_address=PAYOUT_ADDRS["algorand-mainnet"],
                hf_token=hf_token,
                protocol="mpp",
                network="algorand-mainnet",
                model="meta-llama/Meta-Llama-3-8B-Instruct",
            )
            reply = adapter.complete([
                {"role": "user", "content": "Reply with exactly: AlgoVoi HF OK"}
            ])
            assert isinstance(reply, str) and len(reply) > 0, f"empty reply: {reply!r}"
            print(f"  [PASS] InferenceClient reply: {reply[:80]}")
            passed += 1
    except (ImportError, NotImplementedError) as exc:
        print(f"  [WARN] InferenceClient not available: {exc}")
    except Exception as exc:
        print(f"  [FAIL] {type(exc).__name__}: {exc}")
        traceback.print_exc()
        failed += 1

    # smolagents tool — verified path using algo_tx proof
    print(f"\n-- smolagents tool (as_tool) on algorand-mainnet -----------")
    try:
        if algo_tx != "skip":
            adapter = AlgoVoiHuggingFace(
                algovoi_key=algovoi_key,
                tenant_id=tenant_id,
                payout_address=PAYOUT_ADDRS["algorand-mainnet"],
                protocol="mpp",
                network="algorand-mainnet",
            )
            proof = _mpp_proof("algorand-mainnet", algo_tx)
            tool = adapter.as_tool(resource_fn=lambda q: f"Answer to: {q}")
            out = tool.forward(query="What is AlgoVoi?", payment_proof=proof)
            assert "Answer to" in out, f"unexpected tool output: {out}"
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
    total_failures = 0
    total_failures += run_phase1()
    total_failures += run_phase1_tool()

    if total_failures == 0:
        print(f"\n\033[92mAll smoke tests passed.\033[0m\n")
        sys.exit(0)
    else:
        print(f"\n\033[91m{total_failures} smoke test(s) failed.\033[0m\n")
        sys.exit(1)


if __name__ == "__main__":
    if len(sys.argv) == 5:
        sys.exit(verify_payments(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]))
    elif len(sys.argv) == 1:
        main()
    else:
        print("Usage:")
        print("  python smoke_test_huggingface.py                              # Phase 1")
        print("  python smoke_test_huggingface.py ALGO VOI HEDERA STELLAR     # Phase 2")
        sys.exit(1)
