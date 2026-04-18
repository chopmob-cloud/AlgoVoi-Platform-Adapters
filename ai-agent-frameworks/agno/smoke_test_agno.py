"""
AlgoVoi Agno Adapter -- two-phase smoke test
=============================================

Phase 1 -- Challenge render (no live API needed)
    Verifies that each protocol / network combination returns the correct
    402 challenge without a payment proof, the pre-hook raises
    AgnoPaymentRequired, run_agent raises on unpaid requests, ASGI
    middleware returns 402, and the Flask guard returns 402.

Phase 2 -- Full on-chain round-trip
    Requires:
      ALGOVOI_KEY, TENANT_ID env vars
      Real on-chain TX IDs for each network (use "skip" to skip a chain)

Usage:
    # Phase 1 only (CI-safe):
    python smoke_test_agno.py --phase 1

    # Both phases (full integration):
    ALGOVOI_KEY=algv_... TENANT_ID=... \\
        python smoke_test_agno.py --phase 2 \\
            --algo-tx  <ALGORAND_TX_ID> \\
            --voi-tx   <VOI_TX_ID> \\
            --hedera-tx <HEDERA_TX_ID> \\
            --stellar-tx <STELLAR_TX_ID>

    Use "skip" for any chain not yet funded.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import traceback
from unittest.mock import AsyncMock, MagicMock, patch

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
    from agno_algovoi import AlgoVoiAgno
    mock_gate = gate or _make_gate(protocol, network)
    with patch("agno_algovoi._build_gate", return_value=mock_gate):
        adapter = AlgoVoiAgno(
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


def run_phase1_pre_hook() -> int:
    head("Phase 1 -- pre-hook raises AgnoPaymentRequired (3 cases)")
    from agno_algovoi import AgnoPaymentRequired
    failures = 0

    for protocol in ("mpp", "x402", "ap2"):
        label = f"pre_hook / {protocol}"
        try:
            adapter = _make_adapter(protocol, "algorand-mainnet")
            hook    = adapter.make_pre_hook(headers={})
            try:
                hook()
                raise AssertionError("Expected AgnoPaymentRequired")
            except AgnoPaymentRequired as exc:
                if not exc.result.requires_payment:
                    raise AssertionError("result.requires_payment must be True")
            ok(label)
        except Exception as exc:
            fail(f"{label}: {exc}")
            failures += 1

    return failures


def run_phase1_run_agent() -> int:
    head("Phase 1 -- run_agent raises on no proof (2 cases)")
    from agno_algovoi import AgnoPaymentRequired
    failures = 0

    # Sync run_agent
    try:
        adapter    = _make_adapter("mpp", "algorand-mainnet")
        mock_agent = MagicMock()
        try:
            adapter.run_agent(mock_agent, "test", headers={})
            fail("run_agent (sync): expected AgnoPaymentRequired")
            failures += 1
        except AgnoPaymentRequired:
            ok("run_agent (sync) raises AgnoPaymentRequired")
        if mock_agent.run.called:
            raise AssertionError("agent.run should not have been called")
    except Exception as exc:
        fail(f"run_agent sync: {exc}")
        failures += 1

    # Async arun_agent
    try:
        adapter    = _make_adapter("mpp", "algorand-mainnet")
        mock_agent = AsyncMock()
        try:
            asyncio.get_event_loop().run_until_complete(
                adapter.arun_agent(mock_agent, "test", headers={})
            )
            fail("arun_agent: expected AgnoPaymentRequired")
            failures += 1
        except AgnoPaymentRequired:
            ok("arun_agent (async) raises AgnoPaymentRequired")
        if mock_agent.arun.called:
            raise AssertionError("agent.arun should not have been called")
    except Exception as exc:
        fail(f"arun_agent: {exc}")
        failures += 1

    return failures


def run_phase1_asgi_middleware() -> int:
    head("Phase 1 -- ASGI middleware returns 402 (1 case)")
    from agno_algovoi import _AgnoPaymentMiddleware
    failures = 0

    try:
        adapter   = _make_adapter("mpp", "algorand-mainnet")
        inner_app = AsyncMock()
        mw        = _AgnoPaymentMiddleware(inner_app, adapter)

        sent = []

        async def fake_send(msg):
            sent.append(msg)

        scope = {"type": "http", "headers": []}
        asyncio.get_event_loop().run_until_complete(
            mw(scope, MagicMock(), fake_send)
        )

        if inner_app.called:
            raise AssertionError("Inner app should not have been called")
        status_msgs = [m for m in sent if m.get("type") == "http.response.start"]
        if not status_msgs:
            raise AssertionError("No http.response.start sent")
        if status_msgs[0].get("status") != 402:
            raise AssertionError(f"Expected 402, got {status_msgs[0].get('status')}")

        ok("ASGI middleware returns 402")
    except Exception as exc:
        fail(f"asgi_middleware: {exc}")
        failures += 1

    return failures


def run_phase1_flask_guard() -> int:
    head("Phase 1 -- flask_guard returns 402 (1 case)")
    failures = 0

    try:
        try:
            import flask  # noqa: F401
        except ImportError:
            ok("flask_guard (flask not installed — skipped)")
            return 0

        from flask import Flask
        adapter = _make_adapter("mpp", "algorand-mainnet")

        app = Flask(__name__)

        @app.route("/agent", methods=["POST"])
        def agent_route():
            guard = adapter.flask_guard()
            if guard is not None:
                return guard
            return "OK", 200

        with app.test_client() as c:
            resp = c.post("/agent", json={"message": "hello"})

        if resp.status_code != 402:
            raise AssertionError(f"Expected 402, got {resp.status_code}")
        ok("flask_guard returns 402 without payment")
    except Exception as exc:
        fail(f"flask_guard: {exc}")
        failures += 1

    return failures


# ── Phase 2 ───────────────────────────────────────────────────────────────────

_PAYOUT_AGNO = {
    "algorand-mainnet": "ZVLRVYQSLJNVFMOIOKT35XH5SNQG45IVFMLLRFLHDQJQA5TO5H3SO4TVDQ",
    "voi-mainnet":      "THDLWTJ7RB4OJWFZCLL5IME7FHBSJ3SONBRWHIVQE3BEGTY2BWUEUVEOQY",
    "hedera-mainnet":   "0.0.1317927",
    "stellar-mainnet":  "GD45SH4TC4TMJOJWJJSLGAXODAIO36POCACT2MWS7I6CTJORMFKEP3HR",
}

PHASE2_ENTRIES_AGNO = [
    ("algorand-mainnet", "algo_tx"),
    ("voi-mainnet",      "voi_tx"),
    ("hedera-mainnet",   "hedera_tx"),
    ("stellar-mainnet",  "stellar_tx"),
]


def _mpp_proof_agno(network: str, tx_id: str) -> str:
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

    from agno_algovoi import AgnoPaymentRequired, AlgoVoiAgno
    failures = skipped = 0
    first_verified: tuple[str, str] | None = None

    head("Phase 2 -- live on-chain verification (4 chains × MPP)")
    for network, arg_dest in PHASE2_ENTRIES_AGNO:
        tx_id = tx_ids.get(arg_dest, "skip")
        label = f"mpp / {network}"

        if tx_id.lower() == "skip":
            print(f"  SKIP  {label}")
            skipped += 1
            continue

        print(f"\n  {label}")
        print(f"    TX: {tx_id}")

        try:
            gate = AlgoVoiAgno(
                algovoi_key=algovoi_key,
                tenant_id=tenant_id,
                payout_address=_PAYOUT_AGNO[network],
                protocol="mpp",
                network=network,
                amount_microunits=10_000,
            )

            r1 = gate.check({})
            if not r1.requires_payment:
                raise AssertionError("Expected 402 before payment")

            proof = _mpp_proof_agno(network, tx_id)
            r2 = gate.check({"Authorization": f"Payment {proof}"})
            if r2.requires_payment:
                raise AssertionError(f"Payment rejected — {r2.error}")

            receipt = getattr(r2, "receipt", None)
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

    head("Phase 2 -- run_agent round-trip")
    if first_verified is None:
        print("  SKIP  no verified network available for run_agent test")
    else:
        network, tx_id = first_verified
        try:
            gate = AlgoVoiAgno(
                algovoi_key=algovoi_key,
                tenant_id=tenant_id,
                payout_address=_PAYOUT_AGNO[network],
                protocol="mpp",
                network=network,
                amount_microunits=10_000,
            )

            proof = _mpp_proof_agno(network, tx_id)
            mock_agent = MagicMock()
            mock_agent.run.return_value = MagicMock(content="live-ok")
            output = gate.run_agent(
                mock_agent, "What is 2+2?",
                headers={"Authorization": f"Payment {proof}"},
            )
            assert output.content == "live-ok"
            ok(f"run_agent ({network}): {output.content}")
        except Exception as exc:
            fail(f"run_agent live: {exc}")
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
    total += run_phase1_pre_hook()
    total += run_phase1_run_agent()
    total += run_phase1_asgi_middleware()
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
