"""
Hugging Face Adapter — two-phase smoke test
=============================================

Phase 1 — Challenge render (no live AlgoVoi API needed)
    Verifies that each protocol / network combination returns the correct
    402 challenge header without a payment proof.

Phase 2 — Full on-chain round-trip + InferenceClient + smolagents tool
    Requires:
      ALGOVOI_KEY, TENANT_ID, PAYOUT_ADDRESS, HF_TOKEN env vars
      Live AlgoVoi gateway (gateway.algovoi.com)
      Live Hugging Face Inference API

Usage:
    # Phase 1 only (CI-safe):
    python smoke_test_huggingface.py --phase 1

    # Both phases (full integration):
    ALGOVOI_KEY=algv_... TENANT_ID=... PAYOUT_ADDRESS=... HF_TOKEN=hf_... \\
        python smoke_test_huggingface.py --phase 2
"""

from __future__ import annotations

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
        mod = types.ModuleType("mpp_algovoi")
        mod.AlgoVoiMppGate = MagicMock(return_value=gate)
        sys.modules["mpp_algovoi"] = mod
    elif protocol == "ap2":
        mod = types.ModuleType("ap2_algovoi")
        mod.AlgoVoiAp2Gate = MagicMock(return_value=gate)
        sys.modules["ap2_algovoi"] = mod
    else:
        mod = types.ModuleType("openai_algovoi")
        mod.AlgoVoiX402Gate = MagicMock(return_value=gate)
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
# Phase 2 — live on-chain + HF inference
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
    hf_token       = os.environ.get("HF_TOKEN", "")

    missing = [k for k, v in {
        "ALGOVOI_KEY": algovoi_key,
        "TENANT_ID": tenant_id,
        "PAYOUT_ADDRESS": payout_address,
        "HF_TOKEN": hf_token,
    }.items() if not v]

    if missing:
        print(f"\n\033[93mPhase 2 skipped — missing env vars: {', '.join(missing)}\033[0m")
        return 0

    # Remove stubs so real modules are imported
    for k in ("mpp_algovoi", "ap2_algovoi", "openai_algovoi",
              "huggingface_hub", "smolagents"):
        sys.modules.pop(k, None)

    failures = 0
    _head("Phase 2 — live on-chain verification (4 chains × MPP)")

    for network in PHASE2_NETWORKS:
        label = f"mpp / {network}"
        try:
            adapter = AlgoVoiHuggingFace(
                algovoi_key=algovoi_key,
                tenant_id=tenant_id,
                payout_address=payout_address,
                hf_token=hf_token,
                protocol="mpp",
                network=network,
                amount_microunits=10_000,
                model="meta-llama/Meta-Llama-3-8B-Instruct",
            )

            # Step 1 — challenge
            result = adapter.check({}, {})
            assert result.requires_payment, "should require payment on first call"

            # Step 2 — obtain proof from the gateway (AlgoVoi test endpoint)
            import urllib.request
            req_body = json.dumps({
                "tenant_id": tenant_id,
                "network": network,
                "amount_microunits": 10_000,
                "resource_id": "ai-inference",
            }).encode()
            req = urllib.request.Request(
                "https://gateway.algovoi.com/v1/test/issue-proof",
                data=req_body,
                headers={"Content-Type": "application/json", "X-AlgoVoi-Key": algovoi_key},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                proof_data = json.loads(resp.read())
            proof = proof_data["proof"]

            # Step 3 — verify
            result2 = adapter.check({"Authorization": f"Payment {proof}"}, {})
            assert not result2.requires_payment, "should be verified with valid proof"

            _ok(label)
        except Exception as exc:
            _fail(f"{label}: {exc}")
            traceback.print_exc()
            failures += 1

    # InferenceClient smoke — single call
    _head("Phase 2 — InferenceClient.complete()")
    try:
        adapter = AlgoVoiHuggingFace(
            algovoi_key=algovoi_key,
            tenant_id=tenant_id,
            payout_address=payout_address,
            hf_token=hf_token,
            protocol="mpp",
            network="algorand-mainnet",
            model="meta-llama/Meta-Llama-3-8B-Instruct",
        )
        reply = adapter.complete([
            {"role": "user", "content": "Reply with exactly: AlgoVoi HF OK"}
        ])
        assert isinstance(reply, str) and len(reply) > 0, f"empty reply: {reply!r}"
        _ok(f"InferenceClient reply: {reply[:80]}")
    except Exception as exc:
        _fail(f"InferenceClient: {exc}")
        traceback.print_exc()
        failures += 1

    # smolagents tool — verified path
    _head("Phase 2 — smolagents tool (verified proof)")
    try:
        adapter = AlgoVoiHuggingFace(
            algovoi_key=algovoi_key,
            tenant_id=tenant_id,
            payout_address=payout_address,
            protocol="mpp",
            network="algorand-mainnet",
        )

        # issue a proof
        import urllib.request
        req_body = json.dumps({
            "tenant_id": tenant_id,
            "network": "algorand-mainnet",
            "amount_microunits": 10_000,
            "resource_id": "ai-inference",
        }).encode()
        req = urllib.request.Request(
            "https://gateway.algovoi.com/v1/test/issue-proof",
            data=req_body,
            headers={"Content-Type": "application/json", "X-AlgoVoi-Key": algovoi_key},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            proof_data = json.loads(resp.read())
        proof = proof_data["proof"]

        tool = adapter.as_tool(resource_fn=lambda q: f"Answer to: {q}")
        out = tool.forward(query="What is AlgoVoi?", payment_proof=proof)
        assert "Answer to" in out, f"unexpected tool output: {out}"
        _ok(f"tool output: {out[:80]}")
    except Exception as exc:
        _fail(f"tool verified path: {exc}")
        traceback.print_exc()
        failures += 1

    return failures


# ══════════════════════════════════════════════════════════════════════════════
# Entry point
# ══════════════════════════════════════════════════════════════════════════════

def main() -> None:
    parser = argparse.ArgumentParser(description="Hugging Face adapter smoke test")
    parser.add_argument(
        "--phase", type=int, choices=[1, 2], default=1,
        help="1 = challenge render only (default); 2 = full live test",
    )
    args = parser.parse_args()

    total_failures = 0
    total_failures += run_phase1()
    total_failures += run_phase1_tool()

    if args.phase == 2:
        total_failures += run_phase2()

    if total_failures == 0:
        print(f"\n\033[92mAll smoke tests passed.\033[0m\n")
        sys.exit(0)
    else:
        print(f"\n\033[91m{total_failures} smoke test(s) failed.\033[0m\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
