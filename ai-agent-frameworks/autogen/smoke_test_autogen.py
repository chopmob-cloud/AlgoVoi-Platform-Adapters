"""
AutoGen Adapter — two-phase smoke test
=======================================

Phase 1 — Challenge render (no live AlgoVoi API needed)
    Verifies that each protocol / network combination returns the correct
    402 challenge without a payment proof, and that the callable tool returns
    challenge JSON when no proof is supplied.

Phase 2 — Full on-chain round-trip + initiate_chat
    Requires:
      ALGOVOI_KEY, TENANT_ID, PAYOUT_ADDRESS, OPENAI_KEY env vars
      Live AlgoVoi gateway (api1.ilovechicken.co.uk)
      Live OpenAI API

Usage:
    # Phase 1 only (CI-safe):
    python smoke_test_autogen.py --phase 1

    # Both phases (full integration):
    ALGOVOI_KEY=algv_... TENANT_ID=... PAYOUT_ADDRESS=... OPENAI_KEY=sk-... \\
        python smoke_test_autogen.py --phase 2
"""

from __future__ import annotations

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
# Phase 2 — live on-chain + initiate_chat
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

    # Remove stubs so real modules are imported
    for k in ("mpp_algovoi", "ap2_algovoi", "openai_algovoi"):
        sys.modules.pop(k, None)

    failures = 0
    _head("Phase 2 — live on-chain verification (4 chains × MPP)")

    for network in PHASE2_NETWORKS:
        label = f"mpp / {network}"
        try:
            adapter = AlgoVoiAutoGen(
                algovoi_key=algovoi_key,
                tenant_id=tenant_id,
                payout_address=payout_address,
                openai_key=openai_key,
                protocol="mpp",
                network=network,
                amount_microunits=10_000,
            )

            # Step 1 — challenge
            result = adapter.check({}, {})
            assert result.requires_payment, "should require payment on first call"

            # Step 2 — obtain proof
            import urllib.request
            req_body = json.dumps({
                "tenant_id": tenant_id,
                "network": network,
                "amount_microunits": 10_000,
                "resource_id": "ai-conversation",
            }).encode()
            req = urllib.request.Request(
                "https://api1.ilovechicken.co.uk/v1/test/issue-proof",
                data=req_body,
                headers={"Content-Type": "application/json", "X-AlgoVoi-Key": algovoi_key},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                proof = json.loads(resp.read())["proof"]

            # Step 3 — verify
            result2 = adapter.check({"Authorization": f"Payment {proof}"}, {})
            assert not result2.requires_payment, "should be verified"

            _ok(label)
        except Exception as exc:
            _fail(f"{label}: {exc}")
            traceback.print_exc()
            failures += 1

    # initiate_chat smoke — single conversation
    _head("Phase 2 — initiate_chat (AutoGen 0.2.x mock conversation)")
    try:
        from unittest.mock import MagicMock as _MM
        # Simulate a real conversation result without importing autogen
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
            payout_address=payout_address,
            openai_key=openai_key,
            protocol="mpp",
            network="algorand-mainnet",
        )

        output = adapter.initiate_chat(recipient, sender, "Hello agent", max_turns=3)
        assert isinstance(output, str) and len(output) > 0
        _ok(f"initiate_chat result: {output[:80]}")
    except Exception as exc:
        _fail(f"initiate_chat: {exc}")
        traceback.print_exc()
        failures += 1

    # callable tool — verified path
    _head("Phase 2 — callable tool (verified proof)")
    try:
        import urllib.request
        adapter = AlgoVoiAutoGen(
            algovoi_key=algovoi_key,
            tenant_id=tenant_id,
            payout_address=payout_address,
            protocol="mpp",
            network="algorand-mainnet",
        )
        req_body = json.dumps({
            "tenant_id": tenant_id,
            "network": "algorand-mainnet",
            "amount_microunits": 10_000,
            "resource_id": "ai-conversation",
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
        assert "Answer to" in out, f"unexpected: {out}"
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
    parser = argparse.ArgumentParser(description="AutoGen adapter smoke test")
    parser.add_argument(
        "--phase", type=int, choices=[1, 2], default=1,
        help="1 = challenge render only (default); 2 = full live test",
    )
    args = parser.parse_args()

    total = 0
    total += run_phase1()
    total += run_phase1_tool()
    total += run_phase1_llm_config()

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
