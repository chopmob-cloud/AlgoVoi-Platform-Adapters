"""
AlgoVoi LangGraph Adapter -- two-phase smoke test
===================================================

Phase 1 -- Challenge render (no live API needed)
    Verifies that each protocol / network combination returns the correct
    402 challenge without a payment proof, the payment tool returns challenge
    JSON, invoke_graph / stream_graph run after gate passes, and the Flask
    guard returns 402.

Phase 2 -- Full on-chain round-trip
    Requires:
      ALGOVOI_KEY, TENANT_ID env vars
      Real on-chain TX IDs for each network (use "skip" to skip a chain)

Usage:
    # Phase 1 only (CI-safe):
    python smoke_test_langgraph.py --phase 1

    # Both phases (full integration):
    ALGOVOI_KEY=algv_... TENANT_ID=... \\
        python smoke_test_langgraph.py --phase 2 \\
            --algo-tx  <ALGORAND_TX_ID> \\
            --voi-tx   <VOI_TX_ID> \\
            --hedera-tx <HEDERA_TX_ID> \\
            --stellar-tx <STELLAR_TX_ID>

    Use "skip" for any chain not yet funded.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import traceback
from unittest.mock import MagicMock, patch

# ── path setup ────────────────────────────────────────────────────────────────
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)


# ── helpers ───────────────────────────────────────────────────────────────────

def ok(msg: str)   -> None: print(f"  PASS  {msg}")
def fail(msg: str) -> None: print(f"  FAIL  {msg}")
def head(msg: str) -> None: print(f"\n{msg}")


def b64(obj: object) -> str:
    import base64
    return base64.b64encode(json.dumps(obj).encode()).decode()


# ── mock gate factory ─────────────────────────────────────────────────────────

def _make_gate(protocol: str, network: str, *, requires_payment: bool = True) -> MagicMock:
    gate   = MagicMock()
    result = MagicMock()
    result.requires_payment = requires_payment
    result.error = "Payment proof required" if requires_payment else None

    if protocol == "mpp":
        www_auth = (
            f'Payment realm="API Access", id="smoke-{network}", '
            f'intent="charge", request="{b64({"network": network})}", '
            f'expires="9999999999"'
        )
        result.as_wsgi_response.return_value = (
            "402 Payment Required",
            [("WWW-Authenticate", www_auth)],
            json.dumps({"error": "payment_required"}).encode(),
        )
    elif protocol == "ap2":
        mandate = b64({"type": "CartMandate", "ap2_version": "0.1", "network": network})
        result.as_wsgi_response.return_value = (
            "402 Payment Required",
            [("X-AP2-Cart-Mandate", mandate)],
            json.dumps({"error": "payment_required"}).encode(),
        )
    else:  # x402
        challenge = b64({
            "x402Version": 1,
            "accepts": [{"network": network, "asset": "USDC", "amount": "10000"}],
        })
        result.as_wsgi_response.return_value = (
            "402 Payment Required",
            [("X-PAYMENT-REQUIRED", challenge)],
            json.dumps({"error": "payment_required"}).encode(),
        )

    gate.check.return_value = result
    return gate


def _make_adapter(protocol: str = "mpp", network: str = "algorand-mainnet",
                  gate: MagicMock | None = None):
    from langgraph_algovoi import AlgoVoiLangGraph
    mock_gate = gate or _make_gate(protocol, network)
    with patch("langgraph_algovoi._build_gate", return_value=mock_gate):
        adapter = AlgoVoiLangGraph(
            algovoi_key="algv_smoke",
            tenant_id="smoke-tid",
            payout_address="SMOKE_ADDR",
            protocol=protocol,
            network=network,
            amount_microunits=10_000,
        )
    adapter._gate = mock_gate
    return adapter


# ── Phase 1 cases ─────────────────────────────────────────────────────────────

PHASE1_CASES = [
    ("mpp",  "algorand-mainnet", "WWW-Authenticate"),
    ("mpp",  "voi-mainnet",      "WWW-Authenticate"),
    ("ap2",  "algorand-mainnet", "X-AP2-Cart-Mandate"),
    ("ap2",  "stellar-mainnet",  "X-AP2-Cart-Mandate"),
    ("x402", "algorand-mainnet", "X-PAYMENT-REQUIRED"),
    ("x402", "hedera-mainnet",   "X-PAYMENT-REQUIRED"),
]


def run_phase1_challenge() -> int:
    head("Phase 1 -- challenge render (6 cases)")
    failures = 0

    for protocol, network, expected_header in PHASE1_CASES:
        label = f"{protocol} / {network}"
        try:
            adapter = _make_adapter(protocol, network)

            result = adapter.check({})
            if not result.requires_payment:
                raise AssertionError("Expected requires_payment=True")

            status, headers, _ = result.as_wsgi_response()
            if "402" not in str(status):
                raise AssertionError(f"Expected 402, got {status}")

            hdr_keys = {k for k, _ in headers}
            if expected_header not in hdr_keys:
                raise AssertionError(f"Missing {expected_header} header")

            hdr_val = next(v for k, v in headers if k == expected_header)

            if protocol == "mpp":
                if not hdr_val.startswith("Payment "):
                    raise AssertionError("WWW-Authenticate must start with 'Payment '")
                if "realm=" not in hdr_val:
                    raise AssertionError("Missing realm= in WWW-Authenticate")
                if "intent=" not in hdr_val:
                    raise AssertionError("Missing intent= in WWW-Authenticate")
            else:
                import base64
                decoded = json.loads(base64.b64decode(hdr_val))
                if protocol == "x402":
                    if decoded.get("x402Version") != 1:
                        raise AssertionError("Missing x402Version=1")
                    if not isinstance(decoded.get("accepts"), list):
                        raise AssertionError("Missing accepts array")
                else:  # ap2
                    if decoded.get("type") != "CartMandate":
                        raise AssertionError("Missing type=CartMandate")
                    if decoded.get("ap2_version") != "0.1":
                        raise AssertionError("Missing ap2_version=0.1")

            ok(label)
        except Exception as exc:
            fail(f"{label}: {exc}")
            failures += 1

    return failures


def run_phase1_tool() -> int:
    head("Phase 1 -- tool challenge (3 cases)")
    failures = 0

    for protocol in ("mpp", "x402", "ap2"):
        label = f"tool / {protocol}"
        try:
            adapter = _make_adapter(protocol, "algorand-mainnet")
            tool    = adapter.as_tool(lambda q: "premium content", tool_name="kb")
            out     = json.loads(tool._run(query="anything", payment_proof=""))
            if out.get("error") != "payment_required":
                raise AssertionError(f"Expected payment_required, got {out}")
            ok(label)
        except Exception as exc:
            fail(f"{label}: {exc}")
            failures += 1

    return failures


def run_phase1_invoke_graph() -> int:
    head("Phase 1 -- invoke_graph / stream_graph (2 cases)")
    failures = 0

    # invoke_graph: mock graph, gate passes
    try:
        ok_gate  = _make_gate("mpp", "algorand-mainnet", requires_payment=False)
        adapter  = _make_adapter(gate=ok_gate)
        mock_g   = MagicMock()
        mock_g.invoke.return_value = {"messages": [{"role": "ai", "content": "hello"}]}

        output = adapter.invoke_graph(mock_g, {"messages": []})
        assert output["messages"][0]["content"] == "hello"
        mock_g.invoke.assert_called_once_with({"messages": []}, config=None)
        ok("invoke_graph delegates to graph.invoke")
    except Exception as exc:
        fail(f"invoke_graph: {exc}")
        failures += 1

    # stream_graph: mock graph, gate passes
    try:
        ok_gate  = _make_gate("mpp", "algorand-mainnet", requires_payment=False)
        adapter  = _make_adapter(gate=ok_gate)
        mock_g   = MagicMock()
        mock_g.stream.return_value = iter([{"step": 0}, {"step": 1}])

        chunks = list(adapter.stream_graph(mock_g, {"messages": []},
                                           stream_mode="updates"))
        assert len(chunks) == 2
        assert chunks[1]["step"] == 1
        mock_g.stream.assert_called_once_with(
            {"messages": []}, config=None, stream_mode="updates"
        )
        ok("stream_graph delegates to graph.stream")
    except Exception as exc:
        fail(f"stream_graph: {exc}")
        failures += 1

    return failures


def run_phase1_flask_guard() -> int:
    head("Phase 1 -- flask_guard returns 402 (1 case)")
    failures = 0

    try:
        pytest_mod = sys.modules.get("pytest")
        try:
            import flask  # noqa: F401
        except ImportError:
            ok("flask_guard (flask not installed — skipped)")
            return 0

        from flask import Flask
        adapter = _make_adapter("mpp", "algorand-mainnet")

        app = Flask(__name__)

        @app.route("/agent", methods=["POST"])
        def agent():
            guard = adapter.flask_guard()
            if guard is not None:
                return guard
            return "OK", 200

        with app.test_client() as c:
            resp = c.post("/agent", json={"messages": []})

        if resp.status_code != 402:
            raise AssertionError(f"Expected 402, got {resp.status_code}")
        ok("flask_guard returns 402 without payment")
    except Exception as exc:
        fail(f"flask_guard: {exc}")
        failures += 1

    return failures


# ── Phase 2 ───────────────────────────────────────────────────────────────────

# Payout addresses per network (receives MPP payment)
_PAYOUT = {
    "algorand-mainnet": "ZVLRVYQSLJNVFMOIOKT35XH5SNQG45IVFMLLRFLHDQJQA5TO5H3SO4TVDQ",
    "voi-mainnet":      "THDLWTJ7RB4OJWFZCLL5IME7FHBSJ3SONBRWHIVQE3BEGTY2BWUEUVEOQY",
    "hedera-mainnet":   "0.0.1317927",
    "stellar-mainnet":  "GD45SH4TC4TMJOJWJJSLGAXODAIO36POCACT2MWS7I6CTJORMFKEP3HR",
}

# Wire network names (passed in MPP proof payload)
_WIRE_NETWORK = {
    "algorand-mainnet": "algorand-mainnet",
    "voi-mainnet":      "voi-mainnet",
    "hedera-mainnet":   "hedera-mainnet",
    "stellar-mainnet":  "stellar-mainnet",
}

PHASE2_ENTRIES = [
    # (network_key,       argparse_dest)
    ("algorand-mainnet",  "algo_tx"),
    ("voi-mainnet",       "voi_tx"),
    ("hedera-mainnet",    "hedera_tx"),
    ("stellar-mainnet",   "stellar_tx"),
]


def _mpp_proof(network: str, tx_id: str) -> str:
    import base64
    return base64.b64encode(json.dumps({
        "network": _WIRE_NETWORK[network],
        "payload": {"txId": tx_id},
    }).encode()).decode()


def run_phase2(tx_ids: dict[str, str]) -> int:
    algovoi_key = os.environ.get("ALGOVOI_KEY", "")
    tenant_id   = os.environ.get("TENANT_ID", "")

    missing = [k for k, v in {
        "ALGOVOI_KEY": algovoi_key,
        "TENANT_ID":   tenant_id,
    }.items() if not v]

    if missing:
        print(f"\nPhase 2 skipped — missing env vars: {', '.join(missing)}")
        return 0

    from langgraph_algovoi import AlgoVoiLangGraph
    failures = skipped = 0

    head("Phase 2 -- live on-chain verification (4 chains × MPP)")
    first_verified_network: str | None = None

    for network, arg_dest in PHASE2_ENTRIES:
        tx_id = tx_ids.get(arg_dest, "skip")
        label = f"mpp / {network}"

        if tx_id.lower() == "skip":
            print(f"  SKIP  {label}")
            skipped += 1
            continue

        print(f"\n  {label}")
        print(f"    TX: {tx_id}")

        try:
            gate = AlgoVoiLangGraph(
                algovoi_key=algovoi_key,
                tenant_id=tenant_id,
                payout_address=_PAYOUT[network],
                protocol="mpp",
                network=network,
                amount_microunits=10_000,
            )

            # 1. No proof → should require payment
            r1 = gate.check({})
            if not r1.requires_payment:
                raise AssertionError("Expected 402 before payment")

            # 2. With proof → should verify on-chain
            proof = _mpp_proof(network, tx_id)
            r2 = gate.check({"Authorization": f"Payment {proof}"})
            if r2.requires_payment:
                raise AssertionError(f"Payment rejected — {r2.error}")

            receipt = r2.receipt
            if receipt:
                print(f"    [PASS] Verified — payer: {receipt.payer}  "
                      f"amount: {receipt.amount}  tx: {receipt.tx_id[:40]}…")
            else:
                print(f"    [PASS] Verified (no receipt object)")

            ok(label)
            if first_verified_network is None:
                first_verified_network = network

        except Exception as exc:
            fail(f"{label}: {exc}")
            traceback.print_exc()
            failures += 1

    # invoke_graph round-trip using first successfully verified network
    head("Phase 2 -- invoke_graph round-trip")
    if first_verified_network is None:
        print("  SKIP  no verified network available for invoke_graph test")
    else:
        arg_dest = next(d for n, d in PHASE2_ENTRIES if n == first_verified_network)
        tx_id    = tx_ids[arg_dest]
        network  = first_verified_network
        try:
            gate = AlgoVoiLangGraph(
                algovoi_key=algovoi_key,
                tenant_id=tenant_id,
                payout_address=_PAYOUT[network],
                protocol="mpp",
                network=network,
                amount_microunits=10_000,
            )

            proof = _mpp_proof(network, tx_id)
            r = gate.check({"Authorization": f"Payment {proof}"})
            if r.requires_payment:
                raise AssertionError("Gate should pass with valid proof")

            mock_g = MagicMock()
            mock_g.invoke.return_value = {"messages": [{"role": "ai", "content": "live-ok"}]}
            output = gate.invoke_graph(mock_g, {"messages": []})
            assert output["messages"][0]["content"] == "live-ok"
            ok(f"invoke_graph ({network}): {output['messages'][0]['content']}")
        except Exception as exc:
            fail(f"invoke_graph live: {exc}")
            traceback.print_exc()
            failures += 1

    if skipped == 4:
        print("\nPhase 2: all chains skipped (no TX IDs provided)")
    return failures


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", type=int, default=1)
    parser.add_argument("--algo-tx",    default="skip", metavar="TX_ID",
                        help="Algorand mainnet TX ID (use 'skip' to skip)")
    parser.add_argument("--voi-tx",     default="skip", metavar="TX_ID",
                        help="VOI mainnet TX ID")
    parser.add_argument("--hedera-tx",  default="skip", metavar="TX_ID",
                        help="Hedera mainnet TX ID")
    parser.add_argument("--stellar-tx", default="skip", metavar="TX_ID",
                        help="Stellar mainnet TX ID")
    args = parser.parse_args()

    total = 0
    total += run_phase1_challenge()
    total += run_phase1_tool()
    total += run_phase1_invoke_graph()
    total += run_phase1_flask_guard()

    if args.phase == 2:
        tx_ids = {
            "algo_tx":    args.algo_tx,
            "voi_tx":     args.voi_tx,
            "hedera_tx":  args.hedera_tx,
            "stellar_tx": args.stellar_tx,
        }
        total += run_phase2(tx_ids)

    if total == 0:
        print("\nAll smoke tests passed.\n")
        sys.exit(0)
    else:
        print(f"\n{total} smoke test(s) failed.\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
