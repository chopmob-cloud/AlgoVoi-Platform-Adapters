"""
Stdio smoke test for both AlgoVoi MCP servers (TypeScript + Python).

Starts each server as a subprocess with fake env vars, speaks the MCP JSON-RPC
2.0 protocol over stdin/stdout, and asserts all 11 tools are listed on each side.

Run:
    python smoke_stdio.py
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path


EXPECTED_TOOLS = {
    "create_payment_link",
    "verify_payment",
    "prepare_extension_payment",
    "verify_webhook",
    "list_networks",
    "generate_mpp_challenge",
    "verify_mpp_receipt",
    "verify_x402_proof",
    "generate_x402_challenge",
    "generate_ap2_mandate",
    "verify_ap2_payment",
}


def ok(msg):   print(f"  PASS  {msg}")
def fail(msg): print(f"  FAIL  {msg}")


def speak_mcp(proc: subprocess.Popen) -> dict:
    """Initialize + list tools over stdio. Returns the tools/list response."""
    def send(req: dict) -> None:
        line = (json.dumps(req) + "\n").encode()
        proc.stdin.write(line)
        proc.stdin.flush()

    def recv() -> dict:
        line = proc.stdout.readline()
        return json.loads(line)

    # 1) initialize
    send({
        "jsonrpc": "2.0", "id": 1, "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "smoke-client", "version": "1.0.0"},
        },
    })
    init_resp = recv()
    assert "result" in init_resp, f"initialize failed: {init_resp}"

    # 2) notifications/initialized (required by MCP spec — no response)
    send({"jsonrpc": "2.0", "method": "notifications/initialized"})

    # 3) tools/list
    send({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
    return recv()


def run_ts() -> int:
    print("\nTypeScript server (node dist/index.js)")
    ts_dir = Path(__file__).parent / "typescript"
    dist = ts_dir / "dist" / "index.js"
    if not dist.exists():
        fail(f"dist/index.js not found — did you run `npm run build`? ({dist})")
        return 1

    env = os.environ.copy()
    env.update({
        "ALGOVOI_API_KEY":         "algv_smoke",
        "ALGOVOI_TENANT_ID":       "tenant-smoke",
        "ALGOVOI_PAYOUT_ALGORAND": "SMOKE_ALGO_ADDR",
        "ALGOVOI_PAYOUT_VOI":      "SMOKE_VOI_ADDR",
        "ALGOVOI_PAYOUT_HEDERA":   "0.0.999999",
        "ALGOVOI_PAYOUT_STELLAR":  "GSMOKESMOKESMOKESMOKESMOKESMOKESMOKESMOKESMOKESMOKESMOKE",
    })
    proc = subprocess.Popen(
        ["node", str(dist)],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        env=env, cwd=str(ts_dir),
    )
    try:
        resp = speak_mcp(proc)
        tools = {t["name"] for t in resp["result"]["tools"]}
        missing = EXPECTED_TOOLS - tools
        if missing:
            fail(f"missing tools: {missing}")
            return 1
        extra = tools - EXPECTED_TOOLS
        if extra:
            fail(f"unexpected extra tools: {extra}")
            return 1
        ok(f"all 11 tools listed: {sorted(tools)}")
        return 0
    except Exception as exc:
        fail(f"{exc}")
        try:
            stderr = proc.stderr.read().decode(errors="replace")
            if stderr:
                print("  stderr:")
                for ln in stderr.splitlines():
                    print(f"    {ln}")
        except Exception:
            pass
        return 1
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


def run_py() -> int:
    print("\nPython server (python -m algovoi_mcp)")
    env = os.environ.copy()
    env.update({
        "ALGOVOI_API_KEY":         "algv_smoke",
        "ALGOVOI_TENANT_ID":       "tenant-smoke",
        "ALGOVOI_PAYOUT_ALGORAND": "SMOKE_ALGO_ADDR",
        "ALGOVOI_PAYOUT_VOI":      "SMOKE_VOI_ADDR",
        "ALGOVOI_PAYOUT_HEDERA":   "0.0.999999",
        "ALGOVOI_PAYOUT_STELLAR":  "GSMOKESMOKESMOKESMOKESMOKESMOKESMOKESMOKESMOKESMOKESMOKE",
        "PYTHONUNBUFFERED":        "1",
    })
    proc = subprocess.Popen(
        [sys.executable, "-m", "algovoi_mcp"],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        env=env,
    )
    try:
        resp = speak_mcp(proc)
        tools = {t["name"] for t in resp["result"]["tools"]}
        missing = EXPECTED_TOOLS - tools
        if missing:
            fail(f"missing tools: {missing}")
            return 1
        extra = tools - EXPECTED_TOOLS
        if extra:
            fail(f"unexpected extra tools: {extra}")
            return 1
        ok(f"all 11 tools listed: {sorted(tools)}")
        return 0
    except Exception as exc:
        fail(f"{exc}")
        try:
            stderr = proc.stderr.read().decode(errors="replace")
            if stderr:
                print("  stderr:")
                for ln in stderr.splitlines():
                    print(f"    {ln}")
        except Exception:
            pass
        return 1
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


def main() -> None:
    failures = run_ts() + run_py()
    if failures:
        print(f"\n{failures} smoke test(s) failed.\n")
        sys.exit(1)
    print("\nAll stdio smoke tests passed.\n")


if __name__ == "__main__":
    main()
