"""
AlgoVoi Google A2A Adapter -- two-phase smoke test
====================================================

Phase 1 -- Challenge render (no live API needed)
    Verifies that each protocol / network combination returns the correct
    402 challenge without a payment proof, the payment tool returns challenge
    JSON, handle_request routes correctly, and agent_card is well-formed.

Phase 2 -- Full on-chain round-trip
    Requires:
      ALGOVOI_KEY, TENANT_ID env vars
      Real on-chain TX IDs for each network (use "skip" to skip a chain)

Usage:
    # Phase 1 only (CI-safe):
    python smoke_test_a2a.py --phase 1

    # Both phases (full integration):
    ALGOVOI_KEY=algv_... TENANT_ID=... \\
        python smoke_test_a2a.py --phase 2 \\
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

def _make_gate(protocol: str, network: str) -> MagicMock:
    gate   = MagicMock()
    result = MagicMock()
    result.requires_payment = True
    result.error = "Payment proof required"

    if protocol == "mpp":
        www_auth = (
            f'Payment realm="API Access", id="smoke-{network}", '
            f'intent="charge", request="{b64({"network": network})}", '
            f'expires="9999999999"'
        )
        result.as_wsgi_response.return_value = (
            402,
            [("WWW-Authenticate", www_auth)],
            json.dumps({"error": "payment_required"}).encode(),
        )
    elif protocol == "ap2":
        mandate = b64({"type": "CartMandate", "ap2_version": "0.1", "network": network})
        result.as_wsgi_response.return_value = (
            402,
            [("X-AP2-Cart-Mandate", mandate)],
            json.dumps({"error": "payment_required"}).encode(),
        )
    else:  # x402
        challenge = b64({
            "x402Version": 1,
            "accepts": [{"network": network, "asset": "USDC", "amount": "10000"}],
        })
        result.as_wsgi_response.return_value = (
            402,
            [("X-PAYMENT-REQUIRED", challenge)],
            json.dumps({"error": "payment_required"}).encode(),
        )

    gate.check.return_value = result
    return gate


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
    from a2a_algovoi import AlgoVoiA2A

    head("Phase 1 -- challenge render (6 cases)")
    failures = 0

    for protocol, network, expected_header in PHASE1_CASES:
        label = f"{protocol} / {network}"
        try:
            mock_gate = _make_gate(protocol, network)
            with patch.object(AlgoVoiA2A, "_build_gate", return_value=mock_gate):
                gate = AlgoVoiA2A(
                    algovoi_key="algv_smoke",
                    tenant_id="smoke-tid",
                    payout_address="SMOKE_ADDR",
                    protocol=protocol,
                    network=network,
                    amount_microunits=10_000,
                )
            gate._gate = mock_gate

            result = gate.check({})
            if not result.requires_payment:
                raise AssertionError("Expected requires_payment=True")

            status, headers, _ = result.as_wsgi_response()
            if status != 402:
                raise AssertionError(f"Expected 402, got {status}")

            hdr_keys = {k for k, v in headers}
            if expected_header not in hdr_keys:
                raise AssertionError(f"Missing {expected_header} header")

            hdr_val = next(v for k, v in headers if k == expected_header)

            # Protocol-specific content checks
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
    from a2a_algovoi import AlgoVoiA2A

    head("Phase 1 -- tool challenge (3 cases)")
    failures = 0

    for protocol in ("mpp", "x402", "ap2"):
        label = f"tool / {protocol}"
        try:
            mock_gate = _make_gate(protocol, "algorand-mainnet")
            with patch.object(AlgoVoiA2A, "_build_gate", return_value=mock_gate):
                gate = AlgoVoiA2A(
                    algovoi_key="algv_smoke",
                    tenant_id="smoke-tid",
                    payout_address="SMOKE_ADDR",
                    protocol=protocol,
                    network="algorand-mainnet",
                )
            gate._gate = mock_gate

            tool = gate.as_tool(lambda q: "premium content", tool_name="kb")
            out  = json.loads(tool(query="anything", payment_proof=""))
            if out.get("error") != "payment_required":
                raise AssertionError(f"Expected payment_required, got {out}")

            ok(label)
        except Exception as exc:
            fail(f"{label}: {exc}")
            failures += 1

    return failures


def run_phase1_handle_request() -> int:
    from a2a_algovoi import AlgoVoiA2A

    head("Phase 1 -- handle_request routing (2 cases)")
    failures = 0

    # message/send
    try:
        mock_gate = _make_gate("mpp", "algorand-mainnet")
        with patch.object(AlgoVoiA2A, "_build_gate", return_value=mock_gate):
            gate = AlgoVoiA2A(
                algovoi_key="algv_smoke",
                tenant_id="smoke-tid",
                payout_address="SMOKE_ADDR",
            )
        gate._gate = mock_gate

        body = {
            "jsonrpc": "2.0",
            "method":  "message/send",
            "params":  {"message": {"role": "user", "parts": [{"type": "text", "text": "ping"}]}},
            "id":      "r1",
        }
        resp = gate.handle_request(body, lambda text: f"pong:{text}")
        assert resp["jsonrpc"]                                          == "2.0"
        assert resp["result"]["status"]["state"]                        == "completed"
        assert "pong:ping" in resp["result"]["artifacts"][0]["parts"][0]["text"]
        ok("message/send routing")
    except Exception as exc:
        fail(f"message/send routing: {exc}")
        failures += 1

    # tasks/get after message/send
    try:
        mock_gate = _make_gate("mpp", "algorand-mainnet")
        with patch.object(AlgoVoiA2A, "_build_gate", return_value=mock_gate):
            gate = AlgoVoiA2A(
                algovoi_key="algv_smoke",
                tenant_id="smoke-tid",
                payout_address="SMOKE_ADDR",
            )
        gate._gate = mock_gate

        send = gate.handle_request(
            {"jsonrpc": "2.0", "method": "message/send",
             "params": {"message": {"parts": [{"type": "text", "text": "q"}]}}, "id": "s1"},
            lambda t: "answer",
        )
        task_id = send["result"]["id"]
        get_resp = gate.handle_request(
            {"jsonrpc": "2.0", "method": "tasks/get", "params": {"id": task_id}, "id": "g1"},
            lambda t: "",
        )
        assert get_resp["result"]["id"]              == task_id
        assert get_resp["result"]["status"]["state"] == "completed"
        ok("tasks/get routing")
    except Exception as exc:
        fail(f"tasks/get routing: {exc}")
        failures += 1

    return failures


def run_phase1_agent_card() -> int:
    from a2a_algovoi import AlgoVoiA2A

    head("Phase 1 -- agent_card structure (1 case)")
    failures = 0

    try:
        mock_gate = _make_gate("mpp", "algorand-mainnet")
        with patch.object(AlgoVoiA2A, "_build_gate", return_value=mock_gate):
            gate = AlgoVoiA2A(
                algovoi_key="algv_smoke",
                tenant_id="smoke-tid",
                payout_address="SMOKE_ADDR",
                agent_name="SmokeBot",
                agent_description="Smoke test agent",
                agent_version="0.1.0",
            )
        gate._gate = mock_gate

        card = gate.agent_card(
            "https://smoke.example.com/a2a",
            skills=[{"id": "kb", "name": "Knowledge Base", "description": "Premium KB"}],
            supports_streaming=True,
        )
        assert card["name"]                              == "SmokeBot"
        assert card["url"]                               == "https://smoke.example.com/a2a"
        assert card["version"]                           == "0.1.0"
        assert card["capabilities"]["streaming"]         is True
        assert card["capabilities"]["pushNotifications"] is False
        assert card["skills"][0]["id"]                   == "kb"
        assert "text/plain" in card["defaultInputModes"]
        ok("agent_card structure valid")
    except Exception as exc:
        fail(f"agent_card: {exc}")
        failures += 1

    return failures


# ── Phase 2 ───────────────────────────────────────────────────────────────────

_PAYOUT_A2A = {
    "algorand-mainnet": "ZVLRVYQSLJNVFMOIOKT35XH5SNQG45IVFMLLRFLHDQJQA5TO5H3SO4TVDQ",
    "voi-mainnet":      "THDLWTJ7RB4OJWFZCLL5IME7FHBSJ3SONBRWHIVQE3BEGTY2BWUEUVEOQY",
    "hedera-mainnet":   "0.0.1317927",
    "stellar-mainnet":  "GD45SH4TC4TMJOJWJJSLGAXODAIO36POCACT2MWS7I6CTJORMFKEP3HR",
}

PHASE2_ENTRIES_A2A = [
    ("algorand-mainnet", "algo_tx"),
    ("voi-mainnet",      "voi_tx"),
    ("hedera-mainnet",   "hedera_tx"),
    ("stellar-mainnet",  "stellar_tx"),
]


def _mpp_proof_a2a(network: str, tx_id: str) -> str:
    import base64
    return base64.b64encode(json.dumps({
        "network": network,
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

    from a2a_algovoi import AlgoVoiA2A
    failures = skipped = 0
    first_verified: tuple[str, str] | None = None  # (network, tx_id)

    head("Phase 2 -- live on-chain verification (4 chains × MPP)")
    for network, arg_dest in PHASE2_ENTRIES_A2A:
        tx_id = tx_ids.get(arg_dest, "skip")
        label = f"mpp / {network}"

        if tx_id.lower() == "skip":
            print(f"  SKIP  {label}")
            skipped += 1
            continue

        print(f"\n  {label}")
        print(f"    TX: {tx_id}")

        try:
            gate = AlgoVoiA2A(
                algovoi_key=algovoi_key,
                tenant_id=tenant_id,
                payout_address=_PAYOUT_A2A[network],
                protocol="mpp",
                network=network,
                amount_microunits=10_000,
            )

            # No proof → 402
            r1 = gate.check({})
            if not r1.requires_payment:
                raise AssertionError("Expected 402 before payment")

            # With proof → verified on-chain
            proof = _mpp_proof_a2a(network, tx_id)
            r2 = gate.check({"Authorization": f"Payment {proof}"})
            if r2.requires_payment:
                raise AssertionError(f"Payment rejected — {r2.error}")

            # Receipt lives on the wrapped gate result
            receipt = getattr(r2._gate_result, "receipt", None)
            if receipt:
                print(f"    [PASS] Verified — payer: {receipt.payer}  "
                      f"amount: {receipt.amount}  tx: {receipt.tx_id[:40]}…")
            else:
                print(f"    [PASS] Verified (no receipt object)")

            ok(label)
            if first_verified is None:
                first_verified = (network, tx_id)

        except Exception as exc:
            fail(f"{label}: {exc}")
            traceback.print_exc()
            failures += 1

    # handle_request round-trip with live verification
    head("Phase 2 -- handle_request with live payment proof")
    if first_verified is None:
        print("  SKIP  no verified network available for handle_request test")
    else:
        network, tx_id = first_verified
        try:
            gate = AlgoVoiA2A(
                algovoi_key=algovoi_key,
                tenant_id=tenant_id,
                payout_address=_PAYOUT_A2A[network],
                protocol="mpp",
                network=network,
                amount_microunits=10_000,
            )

            proof = _mpp_proof_a2a(network, tx_id)
            body = {
                "jsonrpc": "2.0",
                "method":  "message/send",
                "params":  {"message": {"parts": [{"type": "text", "text": "ping"}]}},
                "id":      "live-1",
            }
            resp_dict = gate.handle_request(
                body,
                lambda text: f"pong:{text}",
                headers={"Authorization": f"Payment {proof}"},
            )
            assert resp_dict["result"]["status"]["state"] == "completed"
            ok(f"handle_request live ({network}): "
               f"{resp_dict['result']['artifacts'][0]['parts'][0]['text'][:60]}")
        except Exception as exc:
            fail(f"handle_request live: {exc}")
            traceback.print_exc()
            failures += 1

    if skipped == 4:
        print("\nPhase 2: all chains skipped (no TX IDs provided)")
    return failures


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", type=int, default=1)
    parser.add_argument("--algo-tx",    default="skip", metavar="TX_ID")
    parser.add_argument("--voi-tx",     default="skip", metavar="TX_ID")
    parser.add_argument("--hedera-tx",  default="skip", metavar="TX_ID")
    parser.add_argument("--stellar-tx", default="skip", metavar="TX_ID")
    args = parser.parse_args()

    total = 0
    total += run_phase1_challenge()
    total += run_phase1_tool()
    total += run_phase1_handle_request()
    total += run_phase1_agent_card()

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
