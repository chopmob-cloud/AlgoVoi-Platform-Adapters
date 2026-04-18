"""
Semantic Kernel Adapter — two-phase smoke test
================================================

Phase 1 — Challenge render (no live AlgoVoi API needed)
    Verifies that each protocol / network combination returns the correct
    402 challenge without a payment proof, and that the plugin gate() method
    returns challenge JSON when no proof is supplied.

Phase 2 — Full on-chain round-trip + SK chat completion
    Requires:
      ALGOVOI_KEY, TENANT_ID, PAYOUT_ADDRESS, OPENAI_KEY env vars
      Live AlgoVoi gateway (api1.ilovechicken.co.uk)
      Live OpenAI API + semantic-kernel installed (pip install semantic-kernel)

Usage:
    # Phase 1 only (CI-safe):
    python smoke_test_semantic_kernel.py --phase 1

    # Both phases (full integration):
    ALGOVOI_KEY=algv_... TENANT_ID=... PAYOUT_ADDRESS=... OPENAI_KEY=sk-... \\
        python smoke_test_semantic_kernel.py --phase 2
"""

from __future__ import annotations

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
# Phase 2 — live on-chain + SK chat completion
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
        print(f"\n\033[93mPhase 2 skipped — missing env vars: {', '.join(missing)}\033[0m")
        return 0

    for k in ("mpp_algovoi", "ap2_algovoi", "openai_algovoi"):
        sys.modules.pop(k, None)

    failures = 0
    _head("Phase 2 — live on-chain verification (4 chains × MPP)")

    for network in PHASE2_NETWORKS:
        label = f"mpp / {network}"
        try:
            adapter = AlgoVoiSemanticKernel(
                algovoi_key=algovoi_key,
                tenant_id=tenant_id,
                payout_address=payout_address,
                openai_key=openai_key,
                protocol="mpp",
                network=network,
                amount_microunits=10_000,
                model="gpt-4o",
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

    # SK chat completion
    _head("Phase 2 — SK chat completion via complete()")
    try:
        adapter = AlgoVoiSemanticKernel(
            algovoi_key=algovoi_key,
            tenant_id=tenant_id,
            payout_address=payout_address,
            openai_key=openai_key,
            protocol="mpp",
            network="algorand-mainnet",
            model="gpt-4o",
        )
        reply = adapter.complete([{"role": "user", "content": "Reply with exactly: AlgoVoi SK OK"}])
        assert isinstance(reply, str) and len(reply) > 0
        _ok(f"complete() reply: {reply[:80]}")
    except Exception as exc:
        _fail(f"complete(): {exc}")
        traceback.print_exc()
        failures += 1

    # Plugin verified path
    _head("Phase 2 — plugin gate() verified proof")
    try:
        adapter = AlgoVoiSemanticKernel(
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

        plugin = adapter.as_plugin(resource_fn=lambda q: f"Answer to: {q}")
        out = plugin.gate(query="What is AlgoVoi?", payment_proof=proof)
        assert "Answer to" in out
        _ok(f"plugin gate output: {out[:80]}")
    except Exception as exc:
        _fail(f"plugin verified: {exc}")
        traceback.print_exc()
        failures += 1

    return failures


# ══════════════════════════════════════════════════════════════════════════════
# Entry point
# ══════════════════════════════════════════════════════════════════════════════

def main() -> None:
    parser = argparse.ArgumentParser(description="Semantic Kernel adapter smoke test")
    parser.add_argument(
        "--phase", type=int, choices=[1, 2], default=1,
        help="1 = challenge render only (default); 2 = full live test",
    )
    args = parser.parse_args()

    total = 0
    total += run_phase1()
    total += run_phase1_plugin()
    total += run_phase1_invoke()

    if args.phase == 2:
        total += run_phase2()

    if total == 0:
        print(f"\n\033[92mAll smoke tests passed.\033[0m\n")
        sys.exit(0)
    else:
        print(f"\n\033[91m{total} smoke test(s) failed.\033[0m\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
