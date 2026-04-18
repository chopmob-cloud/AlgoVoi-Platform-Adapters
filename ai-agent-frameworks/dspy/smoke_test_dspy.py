"""
DSPy Adapter -- two-phase smoke test
======================================

Phase 1 -- Challenge render (no live AlgoVoi API needed)
    Verifies that each protocol / network combination returns the correct
    402 challenge without a payment proof, and that the payment tool returns
    challenge JSON when no proof is supplied.

Phase 2 -- Full on-chain round-trip + DSPy Predict run
    Requires:
      ALGOVOI_KEY, TENANT_ID, PAYOUT_ADDRESS, OPENAI_KEY env vars
      Live AlgoVoi gateway (api1.ilovechicken.co.uk)
      Live OpenAI API + dspy installed (pip install dspy)

Usage:
    # Phase 1 only (CI-safe):
    python smoke_test_dspy.py --phase 1

    # Both phases (full integration):
    ALGOVOI_KEY=algv_... TENANT_ID=... PAYOUT_ADDRESS=... OPENAI_KEY=sk-... \\
        python smoke_test_dspy.py --phase 2
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import traceback
import types
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

# ── path setup ────────────────────────────────────────────────────────────────
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)


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


# ── stub dspy for phase-1 ─────────────────────────────────────────────────────

def _stub_dspy_for_phase1() -> None:
    dspy = types.ModuleType("dspy")

    class _Signature:
        pass

    dspy.Signature = _Signature
    dspy.InputField = MagicMock(return_value=None)
    dspy.OutputField = MagicMock(return_value=None)

    class _MockPredict:
        def __init__(self, sig):
            self.sig = sig
        def __call__(self, **kwargs):
            return SimpleNamespace(response="Smoke test DSPy response")

    dspy.Predict = _MockPredict

    class _MockLM:
        def __init__(self, model, **kwargs):
            self.model = model

    dspy.LM = _MockLM

    @contextmanager
    def _context(**kwargs):
        yield

    dspy.context = _context
    dspy.configure = MagicMock()
    sys.modules["dspy"] = dspy


_stub_dspy_for_phase1()

import dspy_algovoi as dspy_mod  # noqa: E402
from dspy_algovoi import AlgoVoiDSPy, AlgoVoiPaymentTool  # noqa: E402


# ── colour helpers ────────────────────────────────────────────────────────────

def _ok(msg: str) -> None:
    print(f"  PASS  {msg}")

def _fail(msg: str) -> None:
    print(f"  FAIL  {msg}")

def _head(msg: str) -> None:
    print(f"\n{msg}")


# ══════════════════════════════════════════════════════════════════════════════
# Phase 1 -- challenge render
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
    _head("Phase 1 -- challenge render (6 cases)")
    failures = 0

    for protocol, network in PHASE1_CASES:
        label = f"{protocol} / {network}"
        try:
            gate = _make_challenge_gate(protocol, network)
            _stub_protocol(protocol, gate)

            adapter = AlgoVoiDSPy(
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


def run_phase1_tool() -> int:
    _head("Phase 1 -- tool challenge (2 cases)")
    failures = 0

    for protocol in ("mpp", "ap2"):
        label = f"tool / {protocol}"
        try:
            gate = _make_challenge_gate(protocol, "algorand-mainnet")
            _stub_protocol(protocol, gate)

            adapter = AlgoVoiDSPy(
                algovoi_key="algv_smoke",
                tenant_id="smoke-tid",
                payout_address="SMOKE_ADDR",
                protocol=protocol,
                network="algorand-mainnet",
            )
            tool = adapter.as_tool(resource_fn=lambda q: "premium content")

            out = tool(query="test question", payment_proof="")
            data = json.loads(out)
            assert data["error"] == "payment_required"

            _ok(label)
        except Exception as exc:
            _fail(f"{label}: {exc}")
            traceback.print_exc()
            failures += 1

    return failures


def run_phase1_run_module() -> int:
    _head("Phase 1 -- run_module() mock shape (1 case)")
    failures = 0
    try:
        gate = _make_challenge_gate("mpp", "algorand-mainnet")
        _stub_protocol("mpp", gate)

        adapter = AlgoVoiDSPy(
            algovoi_key="algv_smoke",
            tenant_id="smoke-tid",
            payout_address="SMOKE_ADDR",
            protocol="mpp",
            network="algorand-mainnet",
        )

        mock_module = MagicMock(return_value=SimpleNamespace(answer="Module output"))
        result = adapter.run_module(mock_module, question="What is 2+2?")
        assert result == "Module output"
        _ok("run_module shape correct")
    except Exception as exc:
        _fail(f"run_module: {exc}")
        traceback.print_exc()
        failures += 1
    return failures


# ══════════════════════════════════════════════════════════════════════════════
# Phase 2 -- live on-chain + DSPy Predict run
# ══════════════════════════════════════════════════════════════════════════════

PHASE2_NETWORKS = [
    "algorand-mainnet",
    "voi-mainnet",
    "hedera-mainnet",
    "stellar-mainnet",
]


def run_phase2() -> int:
    algovoi_key    = os.environ.get("ALGOVOI_KEY", "")
    tenant_id      = os.environ.get("TENANT_ID", "")
    payout_address = os.environ.get("PAYOUT_ADDRESS", "")
    openai_key     = os.environ.get("OPENAI_KEY", "")

    missing = [k for k, v in {
        "ALGOVOI_KEY": algovoi_key,
        "TENANT_ID": tenant_id,
        "PAYOUT_ADDRESS": payout_address,
        "OPENAI_KEY": openai_key,
    }.items() if not v]

    if missing:
        print(f"\nPhase 2 skipped -- missing env vars: {', '.join(missing)}")
        return 0

    # Remove phase-1 stubs so live modules load
    for k in ("mpp_algovoi", "ap2_algovoi", "openai_algovoi", "dspy"):
        sys.modules.pop(k, None)

    failures = 0
    _head("Phase 2 -- live on-chain verification (4 chains x MPP)")

    for network in PHASE2_NETWORKS:
        label = f"mpp / {network}"
        try:
            adapter = AlgoVoiDSPy(
                algovoi_key=algovoi_key,
                tenant_id=tenant_id,
                payout_address=payout_address,
                openai_key=openai_key,
                protocol="mpp",
                network=network,
                amount_microunits=10_000,
                model="openai/gpt-4o",
            )

            result = adapter.check({}, {})
            assert result.requires_payment

            import urllib.request
            req_body = json.dumps({
                "tenant_id": tenant_id,
                "network": network,
                "amount_microunits": 10_000,
                "resource_id": "ai-function",
            }).encode()
            req = urllib.request.Request(
                "https://api1.ilovechicken.co.uk/v1/test/issue-proof",
                data=req_body,
                headers={"Content-Type": "application/json", "X-AlgoVoi-Key": algovoi_key},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                proof = json.loads(resp.read())["proof"]

            result2 = adapter.check({"Authorization": f"Payment {proof}"}, {})
            assert not result2.requires_payment

            _ok(label)
        except Exception as exc:
            _fail(f"{label}: {exc}")
            traceback.print_exc()
            failures += 1

    # DSPy Predict complete()
    _head("Phase 2 -- DSPy complete() via Predict module")
    try:
        adapter = AlgoVoiDSPy(
            algovoi_key=algovoi_key,
            tenant_id=tenant_id,
            payout_address=payout_address,
            openai_key=openai_key,
            protocol="mpp",
            network="algorand-mainnet",
            model="openai/gpt-4o",
        )
        reply = adapter.complete([{"role": "user", "content": "Reply with exactly: AlgoVoi DSPy OK"}])
        assert isinstance(reply, str) and len(reply) > 0
        _ok(f"complete() reply: {reply[:80]}")
    except Exception as exc:
        _fail(f"complete(): {exc}")
        traceback.print_exc()
        failures += 1

    # Tool verified path
    _head("Phase 2 -- tool gate() verified proof")
    try:
        adapter = AlgoVoiDSPy(
            algovoi_key=algovoi_key,
            tenant_id=tenant_id,
            payout_address=payout_address,
            protocol="mpp",
            network="algorand-mainnet",
        )
        import urllib.request
        req_body = json.dumps({
            "tenant_id": tenant_id,
            "network": "algorand-mainnet",
            "amount_microunits": 10_000,
            "resource_id": "ai-function",
        }).encode()
        req = urllib.request.Request(
            "https://api1.ilovechicken.co.uk/v1/test/issue-proof",
            data=req_body,
            headers={"Content-Type": "application/json", "X-AlgoVoi-Key": algovoi_key},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            proof = json.loads(resp.read())["proof"]

        tool = adapter.as_tool(resource_fn=lambda q: f"Answer to: {q}")
        out = tool(query="What is AlgoVoi?", payment_proof=proof)
        assert "Answer to" in out
        _ok(f"tool output: {out[:80]}")
    except Exception as exc:
        _fail(f"tool verified: {exc}")
        traceback.print_exc()
        failures += 1

    return failures


# ══════════════════════════════════════════════════════════════════════════════
# Entry point
# ══════════════════════════════════════════════════════════════════════════════

def main() -> None:
    parser = argparse.ArgumentParser(description="DSPy adapter smoke test")
    parser.add_argument(
        "--phase", type=int, choices=[1, 2], default=1,
        help="1 = challenge render only (default); 2 = full live test",
    )
    args = parser.parse_args()

    total = 0
    total += run_phase1()
    total += run_phase1_tool()
    total += run_phase1_run_module()

    if args.phase == 2:
        total += run_phase2()

    if total == 0:
        print(f"\nAll smoke tests passed.\n")
        sys.exit(0)
    else:
        print(f"\n{total} smoke test(s) failed.\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
