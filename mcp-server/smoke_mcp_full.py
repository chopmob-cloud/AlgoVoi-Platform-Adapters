"""
AlgoVoi MCP Server — Thorough Smoke Test
=========================================

Phase 1 — Offline tool calls (no network to AlgoVoi API):
  01  tools/list — all 11 tools present
  02  list_networks — 4 networks, correct CAIP-2 + asset IDs
  03  generate_mpp_challenge — 402 + WWW-Authenticate shape
  04  generate_x402_challenge — 402 + X-Payment-Required decodable
  05  generate_ap2_mandate — mandate_id len 16, mandate_b64 round-trips
  06  verify_webhook (valid sig) — valid=true, payload parsed
  07  verify_webhook (bad sig) — valid=false, mismatch error
  08  verify_webhook (unconfigured) — graceful error, no crash
  09  Schema rejection — bad args return isError / error field
  10  MCP_ENABLED_TOOLS — subset listing + disabled tool rejection

Phase 2 — Live API round-trip (requires ALGOVOI_API_KEY / ALGOVOI_TENANT_ID /
          ALGOVOI_PAYOUT_ADDRESS):
  11  create_payment_link — returns checkout_url + token
  12  verify_payment — polls the token just created

Usage:
    # Phase 1 only (TypeScript + Python, no credentials needed):
    python smoke_mcp_full.py

    # Phase 2 as well (needs real credentials in env or keys.txt):
    ALGOVOI_API_KEY=algv_... ALGOVOI_TENANT_ID=... ALGOVOI_PAYOUT_ADDRESS=... \\
        python smoke_mcp_full.py --live

Run from the mcp-server/ directory.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import hmac as _hmac
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

# --Colours / output helpers --────────────────────────────────────────────────

_PASS  = "  PASS  "
_FAIL  = "  FAIL  "
_SKIP  = "  SKIP  "

def ok(msg: str)   -> None: print(f"{_PASS}{msg}")
def fail(msg: str) -> None: print(f"{_FAIL}{msg}")
def skip(msg: str) -> None: print(f"{_SKIP}{msg}")

# --Credential loading --──────────────────────────────────────────────────────

def _load_algovoi_creds() -> dict[str, str] | None:
    """Try env vars first, then keys.txt in repo root."""
    api_key  = os.environ.get("ALGOVOI_API_KEY", "")
    tenant   = os.environ.get("ALGOVOI_TENANT_ID", "")
    payout   = os.environ.get("ALGOVOI_PAYOUT_ADDRESS", "")

    if not api_key:
        repo_root = Path(__file__).parent.parent
        for fname in ("keys.txt", "openai.txt"):
            p = repo_root / fname
            if not p.exists():
                continue
            for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
                line = line.strip()
                if line.lower().startswith("algovoi:") or line.startswith("algv_"):
                    api_key = line.split(":", 1)[-1].strip() if ":" in line else line
                    break
            if api_key:
                break

    if not (api_key and tenant and payout):
        return None
    return {
        "ALGOVOI_API_KEY":        api_key,
        "ALGOVOI_TENANT_ID":      tenant,
        "ALGOVOI_PAYOUT_ADDRESS": payout,
    }

# --MCP session (stdio JSON-RPC helper) --─────────────────────────────────────

class McpSession:
    """Manages a running MCP server subprocess and speaks JSON-RPC over stdio."""

    def __init__(self, proc: subprocess.Popen) -> None:
        self._proc    = proc
        self._next_id = 3  # 1 = initialize, 2 = tools/list reserved

    # --low-level send/recv --─────────────────────────────────────────────────

    def _send(self, req: dict) -> None:
        line = (json.dumps(req) + "\n").encode()
        self._proc.stdin.write(line)   # type: ignore[union-attr]
        self._proc.stdin.flush()       # type: ignore[union-attr]

    def _recv(self) -> dict:
        line = self._proc.stdout.readline()  # type: ignore[union-attr]
        if not line:
            raise RuntimeError("server closed stdout unexpectedly")
        return json.loads(line)

    # --protocol handshake --──────────────────────────────────────────────────

    def initialize(self) -> None:
        self._send({
            "jsonrpc": "2.0", "id": 1, "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities":    {},
                "clientInfo":      {"name": "smoke-full", "version": "1.0.0"},
            },
        })
        resp = self._recv()
        if "error" in resp:
            raise RuntimeError(f"initialize error: {resp['error']}")
        self._send({"jsonrpc": "2.0", "method": "notifications/initialized"})

    # --public API --──────────────────────────────────────────────────────────

    def list_tools(self) -> list[dict]:
        self._send({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        resp = self._recv()
        return resp["result"]["tools"]

    def call_tool(self, name: str, arguments: dict | None = None) -> dict:
        req_id = self._next_id
        self._next_id += 1
        self._send({
            "jsonrpc": "2.0", "id": req_id, "method": "tools/call",
            "params": {"name": name, "arguments": arguments or {}},
        })
        resp = self._recv()
        if "error" in resp:
            # JSON-RPC level error (e.g. method not found)
            return {"_rpc_error": resp["error"]}
        # MCP tool results are in result.content[0].text
        content = resp.get("result", {}).get("content", [])
        if content:
            try:
                return json.loads(content[0]["text"])
            except (KeyError, json.JSONDecodeError):
                return {"_raw": content[0].get("text", "")}
        return resp.get("result", {})

    def stderr_lines(self) -> list[str]:
        try:
            raw = self._proc.stderr.read()  # type: ignore[union-attr]
            return raw.decode(errors="replace").splitlines() if raw else []
        except Exception:
            return []


# --Server launcher --─────────────────────────────────────────────────────────

def _launch_ts(extra_env: dict | None = None) -> subprocess.Popen:
    ts_dir  = Path(__file__).parent / "typescript"
    dist    = ts_dir / "dist" / "index.js"
    if not dist.exists():
        raise FileNotFoundError(
            f"dist/index.js not found — run `npm run build` in {ts_dir}"
        )
    env = os.environ.copy()
    env.update({
        "ALGOVOI_API_KEY":        "algv_smoke",
        "ALGOVOI_TENANT_ID":      "tenant-smoke",
        "ALGOVOI_PAYOUT_ADDRESS": "SMOKE_PAYOUT_ADDR",
        "ALGOVOI_WEBHOOK_SECRET": "whsec_smoke",
    })
    if extra_env:
        env.update(extra_env)
    return subprocess.Popen(
        ["node", str(dist)],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        env=env, cwd=str(ts_dir),
    )


def _launch_py(extra_env: dict | None = None) -> subprocess.Popen:
    env = os.environ.copy()
    env.update({
        "ALGOVOI_API_KEY":        "algv_smoke",
        "ALGOVOI_TENANT_ID":      "tenant-smoke",
        "ALGOVOI_PAYOUT_ADDRESS": "SMOKE_PAYOUT_ADDR",
        "ALGOVOI_WEBHOOK_SECRET": "whsec_smoke",
        "PYTHONUNBUFFERED":       "1",
    })
    if extra_env:
        env.update(extra_env)
    return subprocess.Popen(
        [sys.executable, "-m", "algovoi_mcp"],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        env=env,
    )


def _kill(proc: subprocess.Popen) -> None:
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()


# --HMAC helper for webhook tests --───────────────────────────────────────────

def _sign(secret: str, body: str) -> str:
    return base64.b64encode(
        _hmac.new(secret.encode(), body.encode(), hashlib.sha256).digest()
    ).decode()


# --Phase 1 test suite --──────────────────────────────────────────────────────

def run_phase1(session: McpSession, label: str) -> int:
    """Run all offline tests against an already-initialized McpSession.
    Returns number of failures."""
    failures = 0

    # 01 — tools/list
    tools = session.list_tools()
    names = {t["name"] for t in tools}
    EXPECTED = {
        "create_payment_link", "verify_payment", "prepare_extension_payment",
        "verify_webhook", "list_networks", "generate_mpp_challenge",
        "verify_mpp_receipt", "verify_x402_proof", "generate_x402_challenge",
        "generate_ap2_mandate", "verify_ap2_payment",
    }
    if names == EXPECTED:
        ok(f"[{label}] 01 tools/list — all 11 tools present")
    else:
        fail(f"[{label}] 01 tools/list — expected {sorted(EXPECTED)}, got {sorted(names)}")
        failures += 1

    # 02 — list_networks
    out = session.call_tool("list_networks")
    nets = out.get("networks", [])
    if len(nets) == 4 and all("caip2" in n and "asset_id" in n for n in nets):
        algo = next((n for n in nets if n["key"] == "algorand_mainnet"), None)
        if algo and algo["asset_id"] == "31566704" and algo["caip2"] == "algorand:mainnet":
            ok(f"[{label}] 02 list_networks — 4 networks, correct CAIP-2 + asset IDs")
        else:
            fail(f"[{label}] 02 list_networks — algorand_mainnet fields wrong: {algo}")
            failures += 1
    else:
        fail(f"[{label}] 02 list_networks — unexpected shape: {out}")
        failures += 1

    # 03 — generate_mpp_challenge
    out = session.call_tool("generate_mpp_challenge", {
        "resource_id": "smoke-kb", "amount_microunits": 1_000_000,
    })
    h = out.get("headers", {}).get("WWW-Authenticate", "")
    if (
        out.get("status_code") == 402
        and h.startswith("Payment ")
        and 'intent="charge"' in h
        and len(out.get("challenge_id", "")) == 16
        and out.get("accepts", [{}])[0].get("receiver") == "SMOKE_PAYOUT_ADDR"
    ):
        ok(f"[{label}] 03 generate_mpp_challenge — 402 + correct WWW-Authenticate")
    else:
        fail(f"[{label}] 03 generate_mpp_challenge — bad output: {out}")
        failures += 1

    # 04 — generate_x402_challenge
    out = session.call_tool("generate_x402_challenge", {
        "resource": "https://api.example.com/premium",
        "amount_microunits": 500_000,
        "description": "Smoke test access",
    })
    header_b64 = out.get("headers", {}).get("X-Payment-Required", "")
    try:
        decoded = json.loads(base64.b64decode(header_b64))
        assert decoded["version"] == "1"
        assert decoded["payTo"]   == "SMOKE_PAYOUT_ADDR"
        assert decoded["maxAmountRequired"] == "500000"
        assert decoded["networkId"] == "algorand:mainnet"
        ok(f"[{label}] 04 generate_x402_challenge — 402 + X-Payment-Required decodes correctly")
    except Exception as exc:
        fail(f"[{label}] 04 generate_x402_challenge — {exc} | raw: {out}")
        failures += 1

    # 05 — generate_ap2_mandate
    out = session.call_tool("generate_ap2_mandate", {
        "resource_id": "smoke-task-42", "amount_microunits": 2_000_000,
        "description": "Smoke test task",
    })
    mandate_id  = out.get("mandate_id", "")
    mandate_b64 = out.get("mandate_b64", "")
    try:
        assert len(mandate_id) == 16, f"mandate_id length {len(mandate_id)}"
        mandate = json.loads(base64.b64decode(mandate_b64))
        assert mandate["type"]              == "PaymentMandate"
        assert mandate["version"]           == "0.1"
        assert mandate["protocol"]          == "algovoi-ap2/0.1"
        assert mandate["payee"]["address"]  == "SMOKE_PAYOUT_ADDR"
        assert mandate["amount"]["value"]   == "2000000"
        assert mandate["mandate_id"]        == mandate_id
        ok(f"[{label}] 05 generate_ap2_mandate — mandate_id={mandate_id}, b64 round-trips OK")
    except Exception as exc:
        fail(f"[{label}] 05 generate_ap2_mandate — {exc} | raw: {out}")
        failures += 1

    # 06 — verify_webhook valid sig
    body   = json.dumps({"order_id": "123", "status": "paid"})
    sig    = _sign("whsec_smoke", body)
    out    = session.call_tool("verify_webhook", {"raw_body": body, "signature": sig})
    if out.get("valid") is True and out.get("payload", {}).get("order_id") == "123":
        ok(f"[{label}] 06 verify_webhook (valid) — valid=true, payload parsed")
    else:
        fail(f"[{label}] 06 verify_webhook (valid) — {out}")
        failures += 1

    # 07 — verify_webhook bad sig
    out = session.call_tool("verify_webhook", {"raw_body": body, "signature": "AAAA"})
    if out.get("valid") is False and "mismatch" in str(out.get("error", "")):
        ok(f"[{label}] 07 verify_webhook (bad sig) — valid=false, mismatch")
    else:
        fail(f"[{label}] 07 verify_webhook (bad sig) — {out}")
        failures += 1

    # 08 — verify_webhook non-JSON body (valid sig on non-JSON)
    bad_body = "not-json-payload"
    bad_sig  = _sign("whsec_smoke", bad_body)
    out = session.call_tool("verify_webhook", {"raw_body": bad_body, "signature": bad_sig})
    if out.get("valid") is False and "JSON" in str(out.get("error", "")):
        ok(f"[{label}] 08 verify_webhook (non-JSON) — valid=false, JSON error")
    else:
        fail(f"[{label}] 08 verify_webhook (non-JSON) — {out}")
        failures += 1

    def _is_rejected(r: dict) -> bool:
        # Our own error dict, MCP SDK JSON-Schema rejection (_raw), or RPC error
        return "error" in r or r.get("_rpc_error") or (
            "_raw" in r and (
                "error" in r["_raw"].lower()
                or "not allowed" in r["_raw"].lower()
                or "not of type" in r["_raw"].lower()
                or "is not one of" in r["_raw"].lower()
            )
        )

    # 09a — schema rejection: extra field
    out = session.call_tool("create_payment_link", {
        "amount": 5, "currency": "USD", "label": "x",
        "network": "algorand_mainnet", "bogus_field": "injected",
    })
    if _is_rejected(out):
        ok(f"[{label}] 09a schema rejection (extra field) — rejected correctly")
    else:
        fail(f"[{label}] 09a schema rejection (extra field) — expected error, got: {out}")
        failures += 1

    # 09b — schema rejection: bad network enum
    out = session.call_tool("create_payment_link", {
        "amount": 5, "currency": "USD", "label": "x", "network": "solana_mainnet",
    })
    if _is_rejected(out):
        ok(f"[{label}] 09b schema rejection (bad network) — rejected correctly")
    else:
        fail(f"[{label}] 09b schema rejection (bad network) — expected error, got: {out}")
        failures += 1

    # 09c — schema rejection: string amount in strict mode
    out = session.call_tool("create_payment_link", {
        "amount": "5.00", "currency": "USD", "label": "x", "network": "algorand_mainnet",
    })
    if _is_rejected(out):
        ok(f"[{label}] 09c schema rejection (string amount) — rejected correctly")
    else:
        fail(f"[{label}] 09c schema rejection (string amount) — expected error, got: {out}")
        failures += 1

    return failures


def run_enabled_tools_test(launcher: Any, label: str) -> int:
    """10 — MCP_ENABLED_TOOLS: subset listing + disabled tool rejection."""
    failures = 0
    proc = launcher(extra_env={"MCP_ENABLED_TOOLS": "list_networks,generate_mpp_challenge"})
    try:
        sess = McpSession(proc)
        sess.initialize()

        tools = sess.list_tools()
        names = {t["name"] for t in tools}
        if names == {"list_networks", "generate_mpp_challenge"}:
            ok(f"[{label}] 10a MCP_ENABLED_TOOLS — only 2 tools listed")
        else:
            fail(f"[{label}] 10a MCP_ENABLED_TOOLS — expected 2 tools, got {sorted(names)}")
            failures += 1

        out = sess.call_tool("create_payment_link", {
            "amount": 5, "currency": "USD", "label": "x", "network": "algorand_mainnet",
        })
        if "error" in out:
            ok(f"[{label}] 10b MCP_ENABLED_TOOLS — disabled tool returns error")
        else:
            fail(f"[{label}] 10b MCP_ENABLED_TOOLS — disabled tool should be rejected: {out}")
            failures += 1
    except Exception as exc:
        fail(f"[{label}] 10 MCP_ENABLED_TOOLS — {exc}")
        failures += 1
    finally:
        _kill(proc)
    return failures


# --Phase 2 live API (all 4 chains) --─────────────────────────────────────────

# Networks to test in Phase 2 — same order as list_networks output.
_NETWORKS = [
    "algorand_mainnet",
    "voi_mainnet",
    "hedera_mainnet",
    "stellar_mainnet",
]
# Only Algorand + VOI support the browser-extension wallet flow.
_EXT_NETWORKS = ["algorand_mainnet", "voi_mainnet"]


def run_phase2(
    session: McpSession,
    label: str,
    tx_ids: dict[str, str],   # network → on-chain TX ID (optional, for verify tools)
) -> int:
    """
    Phase 2: live API round-trip on all 4 chains.

    Tests numbered 11–18:
      11a–d  create_payment_link on each chain
      12a–d  verify_payment (unpaid is fine — proves the token is valid)
      13a–b  prepare_extension_payment (algorand + voi only)
      14     verify_mpp_receipt   (if --algo-tx provided)
      15     verify_x402_proof    (if --algo-tx provided)
      16     verify_ap2_payment   (if --algo-tx provided)
    """
    failures  = 0
    tokens: dict[str, str] = {}   # network → checkout token

    # 11 — create_payment_link on all 4 chains
    print(f"\n  [{label}] -- create_payment_link (all 4 chains) --")
    for i, net in enumerate(_NETWORKS, start=1):
        out = session.call_tool("create_payment_link", {
            "amount":   0.01,
            "currency": "USD",
            "label":    f"MCP smoke {label} {net}",
            "network":  net,
        })
        token = out.get("token", "")
        url   = out.get("checkout_url", "")
        chain = out.get("chain", "")
        if url.startswith("https://") and token:
            tokens[net] = token
            ok(f"[{label}] 11{chr(96+i)} create_payment_link ({net}) — token={token} chain={chain}")
        else:
            fail(f"[{label}] 11{chr(96+i)} create_payment_link ({net}) — {out}")
            failures += 1

    # 12 — verify_payment on each token just created (will be pending/unpaid)
    print(f"\n  [{label}] -- verify_payment (all 4 chains) --")
    for i, net in enumerate(_NETWORKS, start=1):
        token = tokens.get(net)
        if not token:
            skip(f"[{label}] 12{chr(96+i)} verify_payment ({net}) — skipped (no token)")
            continue
        out = session.call_tool("verify_payment", {"token": token})
        if "paid" in out and "status" in out:
            ok(f"[{label}] 12{chr(96+i)} verify_payment ({net}) — paid={out['paid']}, status={out['status']}")
        else:
            fail(f"[{label}] 12{chr(96+i)} verify_payment ({net}) — {out}")
            failures += 1

    # 13 — prepare_extension_payment (Algorand + VOI only)
    print(f"\n  [{label}] -- prepare_extension_payment (algorand + voi) --")
    for i, net in enumerate(_EXT_NETWORKS, start=1):
        out = session.call_tool("prepare_extension_payment", {
            "amount": 0.01, "currency": "USD",
            "label":  f"MCP ext smoke {net}", "network": net,
        })
        if out.get("token") and out.get("asset_id") and out.get("ticker"):
            ok(
                f"[{label}] 13{chr(96+i)} prepare_extension_payment ({net})"
                f" — ticker={out['ticker']} asset_id={out['asset_id']}"
            )
        else:
            fail(f"[{label}] 13{chr(96+i)} prepare_extension_payment ({net}) — {out}")
            failures += 1

    # 14 — verify_mpp_receipt (requires a real paid TX ID)
    print(f"\n  [{label}] -- protocol verification (TX IDs) --")
    algo_tx = tx_ids.get("algorand_mainnet")
    if algo_tx:
        out = session.call_tool("verify_mpp_receipt", {
            "resource_id": "smoke-resource",
            "tx_id":       algo_tx,
            "network":     "algorand_mainnet",
        })
        if "verified" in out:
            ok(f"[{label}] 14 verify_mpp_receipt (algorand) — verified={out['verified']}")
        else:
            fail(f"[{label}] 14 verify_mpp_receipt — {out}")
            failures += 1

        # 15 — verify_x402_proof (needs a base64 proof, use TX ID as stand-in)
        proof_b64 = base64.b64encode(json.dumps({"tx_id": algo_tx}).encode()).decode()
        out = session.call_tool("verify_x402_proof", {
            "proof": proof_b64, "network": "algorand_mainnet",
        })
        if "verified" in out:
            ok(f"[{label}] 15 verify_x402_proof (algorand) — verified={out['verified']}")
        else:
            fail(f"[{label}] 15 verify_x402_proof — {out}")
            failures += 1

        # 16 — verify_ap2_payment
        out = session.call_tool("verify_ap2_payment", {
            "mandate_id": "a" * 16,
            "tx_id":      algo_tx,
            "network":    "algorand_mainnet",
        })
        if "verified" in out:
            ok(f"[{label}] 16 verify_ap2_payment (algorand) — verified={out['verified']}")
        else:
            fail(f"[{label}] 16 verify_ap2_payment — {out}")
            failures += 1
    else:
        skip(f"[{label}] 14-16 verify_mpp_receipt/x402/ap2 — pass --algo-tx TX_ID to test")

    # Per-chain TX verification (VOI / Hedera / Stellar)
    for net, flag in [
        ("voi_mainnet",     "voi_mainnet"),
        ("hedera_mainnet",  "hedera_mainnet"),
        ("stellar_mainnet", "stellar_mainnet"),
    ]:
        tx = tx_ids.get(net)
        if not tx:
            continue
        out = session.call_tool("verify_mpp_receipt", {
            "resource_id": "smoke-resource", "tx_id": tx, "network": net,
        })
        if "verified" in out:
            ok(f"[{label}] verify_mpp_receipt ({net}) — verified={out['verified']}")
        else:
            fail(f"[{label}] verify_mpp_receipt ({net}) — {out}")
            failures += 1

    return failures


# --Per-server runner --───────────────────────────────────────────────────────

def run_server(
    launcher_fn: Any,
    label: str,
    live: bool,
    live_env: dict | None,
    tx_ids: dict[str, str],
) -> int:
    """Spin up a server, run all phases, return total failure count."""
    print(f"\n{'=' * 60}")
    print(f"  {label}")
    print(f"{'=' * 60}")

    failures = 0

    # --Phase 1 --─────────────────────────────────────────────────────────────
    print("\n--Phase 1: offline tools --")
    proc = launcher_fn()
    try:
        sess = McpSession(proc)
        sess.initialize()
        failures += run_phase1(sess, label)
    except Exception as exc:
        fail(f"[{label}] Phase 1 session error: {exc}")
        failures += 1
        for ln in sess.stderr_lines() if 'sess' in dir() else []:
            print(f"    stderr: {ln}")
    finally:
        _kill(proc)

    # --MCP_ENABLED_TOOLS test (separate process) --───────────────────────────
    print("\n--MCP_ENABLED_TOOLS filtering --")
    failures += run_enabled_tools_test(launcher_fn, label)

    # --Phase 2 --─────────────────────────────────────────────────────────────
    if live and live_env:
        print("\n--Phase 2: live API (all 4 chains) --")
        proc2 = launcher_fn(extra_env=live_env)
        try:
            sess2 = McpSession(proc2)
            sess2.initialize()
            failures += run_phase2(sess2, label, tx_ids)
        except Exception as exc:
            fail(f"[{label}] Phase 2 session error: {exc}")
            failures += 1
        finally:
            _kill(proc2)
    elif live:
        skip(f"[{label}] Phase 2 — no credentials found (set ALGOVOI_API_KEY / ALGOVOI_TENANT_ID / ALGOVOI_PAYOUT_ADDRESS)")

    return failures


# --Entry point --─────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="AlgoVoi MCP Server full smoke test",
        epilog=(
            "Phase 2 usage:\n"
            "  ALGOVOI_API_KEY=algv_... ALGOVOI_TENANT_ID=... ALGOVOI_PAYOUT_ADDRESS=... \\\n"
            "      python smoke_mcp_full.py --live\n\n"
            "With TX ID verification (all 4 chains):\n"
            "  python smoke_mcp_full.py --live \\\n"
            "      --algo-tx ABCD1234... --voi-tx EFGH5678... \\\n"
            "      --hedera-tx 0.0.12345@... --stellar-tx abc123..."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--live",      action="store_true", help="Run Phase 2 live API tests")
    parser.add_argument("--ts-only",   action="store_true")
    parser.add_argument("--py-only",   action="store_true")
    parser.add_argument("--algo-tx",   default="", metavar="TX_ID", help="Algorand TX ID for verify tools")
    parser.add_argument("--voi-tx",    default="", metavar="TX_ID", help="VOI TX ID for verify tools")
    parser.add_argument("--hedera-tx", default="", metavar="TX_ID", help="Hedera TX ID for verify tools")
    parser.add_argument("--stellar-tx",default="", metavar="TX_ID", help="Stellar TX ID for verify tools")
    args = parser.parse_args()

    live_env = _load_algovoi_creds() if args.live else None

    tx_ids: dict[str, str] = {
        k: v for k, v in {
            "algorand_mainnet": args.algo_tx,
            "voi_mainnet":      args.voi_tx,
            "hedera_mainnet":   args.hedera_tx,
            "stellar_mainnet":  args.stellar_tx,
        }.items() if v
    }

    ts_dir = Path(__file__).parent / "typescript"
    dist   = ts_dir / "dist" / "index.js"

    total_failures = 0

    if not args.py_only:
        if not dist.exists():
            print(f"\nSkipping TypeScript — dist/index.js not found (run `npm run build`)")
        else:
            total_failures += run_server(
                launcher_fn = _launch_ts,
                label       = "TypeScript",
                live        = args.live,
                live_env    = live_env,
                tx_ids      = tx_ids,
            )

    if not args.ts_only:
        total_failures += run_server(
            launcher_fn = _launch_py,
            label       = "Python",
            live        = args.live,
            live_env    = live_env,
            tx_ids      = tx_ids,
        )

    print(f"\n{'=' * 60}")
    if total_failures == 0:
        print("  ALL SMOKE TESTS PASSED")
    else:
        print(f"  {total_failures} SMOKE TEST(S) FAILED")
    print(f"{'=' * 60}\n")

    sys.exit(0 if total_failures == 0 else 1)


if __name__ == "__main__":
    main()
