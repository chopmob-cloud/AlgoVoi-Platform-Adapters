"""
MCP A2A two-agent smoke test
============================

Demonstrates the fetch_agent_card + send_a2a_message MCP tools
communicating with the live AlgoVoi A2A server.

  Agent A = AlgoVoi MCP server tools (this script, acting as client)
  Agent B = https://api1.ilovechicken.co.uk  (live A2A payment-gated server)

Phase 1 — discovery + challenge (no payment needed):
    python smoke_mcp_a2a.py

Phase 2 — full authenticated round-trip (requires API key + on-chain TX):
    ALGOVOI_KEY=algv_...  TENANT_ID=...  PAYOUT_ADDRESS=<algo-addr> \\
        python smoke_mcp_a2a.py --phase 2 --tx <ALGORAND_TX_ID>

Usage notes:
    Phase 1 runs without any credentials and shows the agent card,
    the challenge headers returned on an unpaid request, and the
    generate_mpp_challenge output that a paying client would use.

    Phase 2 additionally performs a full authenticated + paid round-trip
    using a real on-chain transaction ID.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, "python"))
sys.path.insert(0, os.path.join(_HERE, "..", "mpp-adapter"))

from algovoi_mcp.client import AlgoVoiClient
from algovoi_mcp.schemas import (
    FetchAgentCardInput,
    GenerateMppChallengeInput,
    SendA2aMessageInput,
)
from algovoi_mcp import server as mcp_server

AGENT_URL   = "https://api1.ilovechicken.co.uk"
SEPARATOR   = "─" * 60

OK   = "\033[32m✓\033[0m"
FAIL = "\033[31m✗\033[0m"
INFO = "\033[36m·\033[0m"

_passes = 0
_fails  = 0


def check(label: str, condition: bool, detail: str = "") -> bool:
    global _passes, _fails
    if condition:
        _passes += 1
        print(f"  {OK}  {label}")
    else:
        _fails += 1
        print(f"  {FAIL}  {label}")
    if detail:
        print(f"       {detail}")
    return condition


def section(title: str) -> None:
    print(f"\n{SEPARATOR}")
    print(f"  {title}")
    print(SEPARATOR)


def make_client(api_key: str = "algv_smoke_test",
                tenant_id: str = "smoke-tenant",
                payout: str = "SMOKE_PAYOUT") -> AlgoVoiClient:
    return AlgoVoiClient(
        api_base         = "https://cloud.algovoi.co.uk",
        api_key          = api_key,
        tenant_id        = tenant_id,
        payout_addresses = {
            "algorand_mainnet": payout,
            "voi_mainnet":      payout,
            "hedera_mainnet":   payout,
            "stellar_mainnet":  payout,
        },
    )


# ── Phase 1a: Agent card discovery ───────────────────────────────────────────

def phase1_fetch_agent_card() -> dict:
    section("Phase 1a — Agent A calls fetch_agent_card on Agent B")
    print(f"  {INFO}  GET {AGENT_URL}/.well-known/agent.json\n")

    out = mcp_server.tool_fetch_agent_card(
        FetchAgentCardInput(agent_url=AGENT_URL)
    )

    check("tool returned without exception",     True)
    check("agent_url matches",                   out.get("agent_url") == AGENT_URL)
    check("error is None",                       out.get("error") is None,
          f"error={out.get('error')}")

    card = out.get("card") or {}
    check("card.name present",                   bool(card.get("name")),
          f"name={card.get('name')!r}")
    check("card.description present",            bool(card.get("description")))
    check("card.url present",                    bool(card.get("url")))
    check("card has skills list",                isinstance(card.get("skills"), list))
    check("card has securitySchemes",            bool(card.get("securitySchemes")))

    if card:
        print(f"\n  {INFO}  Agent B identity:")
        print(f"       name        : {card.get('name')}")
        print(f"       description : {card.get('description', '')[:80]}…")
        print(f"       url         : {card.get('url')}")
        print(f"       version     : {card.get('version')}")
        skills = card.get("skills", [])
        print(f"       skills      : {[s.get('id') for s in skills]}")
        sec = list(card.get("securitySchemes", {}).keys())
        print(f"       security    : {sec}")

    return card


# ── Phase 1b: Send message without payment → expect 401/402 ──────────────────

def phase1_send_unpaid() -> dict | None:
    section("Phase 1b — Agent A sends message with no payment proof (expect 401/402)")
    print(f"  {INFO}  POST {AGENT_URL}/message:send  (no Authorization)\n")

    out = mcp_server.tool_send_a2a_message(
        SendA2aMessageInput(agent_url=AGENT_URL, text="What is the price of ALGO?")
    )

    check("tool returned without exception", True)

    # Server returns 401 (unauthenticated) — tool should surface this as an error
    payment_required = out.get("payment_required", False)
    error            = out.get("error")

    if payment_required:
        # 402 path — ideal
        check("payment_required=True",  True)
        check("challenge_headers present",
              bool(out.get("challenge_headers")),
              f"headers={list(out.get('challenge_headers', {}).keys())}")
        print(f"\n  {INFO}  Challenge headers from Agent B:")
        for k, v in (out.get("challenge_headers") or {}).items():
            print(f"       {k}: {v[:80]}{'…' if len(v) > 80 else ''}")
        return out
    elif error and ("401" in str(error) or "Unauthorized" in str(error)):
        # 401 path — also valid: server requires auth before payment check
        check("401 Unauthorized returned (auth required before payment)",
              True, f"error={error!r}")
        print(f"\n  {INFO}  Agent B requires authentication before payment check.")
        print(f"       This is expected — provide ALGOVOI_KEY for Phase 2.")
        return None
    else:
        check("unexpected response", False,
              f"payment_required={payment_required}, error={error!r}, task={out.get('task')}")
        return None


# ── Phase 1c: Show what a challenge looks like (local generation) ─────────────

def phase1_show_challenge() -> None:
    section("Phase 1c — Agent A generates MPP challenge (what Agent B would send)")
    print(f"  {INFO}  Demonstrating generate_mpp_challenge for the resource\n")

    client = make_client()
    out = mcp_server.tool_generate_mpp_challenge(
        client,
        GenerateMppChallengeInput(
            resource_id="a2a-message",
            amount_microunits=10_000,
            networks=["algorand_mainnet", "voi_mainnet", "hedera_mainnet", "stellar_mainnet"],
        ),
    )

    check("status_code == 402",     out.get("status_code") == 402)
    check("WWW-Authenticate set",   bool(out.get("headers", {}).get("WWW-Authenticate")))
    check("accepts has 4 networks", len(out.get("accepts", [])) == 4)

    print(f"\n  {INFO}  What Agent B would send back to Agent A on 402:")
    print(f"       HTTP 402 Payment Required")
    for k, v in out.get("headers", {}).items():
        print(f"       {k}: {v[:80]}{'…' if len(v) > 80 else ''}")
    print(f"\n  {INFO}  Payment options for Agent A:")
    for a in out.get("accepts", []):
        print(f"       {a['network']:25s}  {int(a['amount'])/1_000_000:.4f} {a.get('asset','USDC')}  →  {a['receiver'][:20]}…")
    print(f"\n  {INFO}  Agent A flow after receiving 402:")
    print(f"       1. Read WWW-Authenticate / X-Payment-Required header")
    print(f"       2. Choose network (e.g. algorand_mainnet)")
    print(f"       3. Send {out['accepts'][0]['amount']} micro-units on-chain")
    print(f"       4. Retry send_a2a_message with payment_proof=<tx_id>")


# ── Phase 2: Full authenticated round-trip ────────────────────────────────────

def phase2_full_roundtrip(api_key: str, tenant_id: str,
                           payout: str, tx_id: str) -> None:
    section("Phase 2 — Full authenticated + paid round-trip")
    print(f"  {INFO}  Agent A → Agent B with payment proof\n")

    client = make_client(api_key=api_key, tenant_id=tenant_id, payout=payout)

    # Step 1: send with payment_proof=tx_id
    print(f"  {INFO}  POST {AGENT_URL}/message:send  (payment_proof={tx_id[:16]}…)\n")
    out = mcp_server.tool_send_a2a_message(
        SendA2aMessageInput(
            agent_url=AGENT_URL,
            text="Verify my payment and tell me the status.",
            payment_proof=tx_id,
        )
    )

    check("tool returned without exception", True)
    check("payment_required=False",         out.get("payment_required") is False,
          f"payment_required={out.get('payment_required')}")

    task = out.get("task") or {}
    check("task returned",                  bool(task),
          f"task={json.dumps(task)[:120]}")
    check("task.status present",            bool(task.get("status")),
          f"status={task.get('status')!r}")

    if task:
        print(f"\n  {INFO}  Agent B task result:")
        print(f"       status   : {task.get('status')}")
        artifacts = task.get("artifacts", [])
        for art in artifacts:
            for part in art.get("parts", []):
                if part.get("type") == "text":
                    text = part.get("text", "")[:200]
                    print(f"       response : {text}{'…' if len(part.get('text','')) > 200 else ''}")

    # Step 2: verify mpp receipt on-chain
    print(f"\n  {INFO}  verify_mpp_receipt on-chain (direct indexer)\n")
    receipt_out = mcp_server.tool_verify_mpp_receipt(
        client,
        __import__("algovoi_mcp.schemas", fromlist=["VerifyMppReceiptInput"])
        .VerifyMppReceiptInput(
            resource_id="a2a-message",
            tx_id=tx_id,
            network="algorand_mainnet",
        ),
    )
    check("verified=True", receipt_out.get("verified") is True,
          f"verified={receipt_out.get('verified')}")


# ── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="MCP A2A two-agent smoke test")
    parser.add_argument("--phase", type=int, default=1, choices=[1, 2])
    parser.add_argument("--tx",    default="", help="On-chain TX ID for Phase 2")
    args = parser.parse_args()

    print(f"\n{'═' * 60}")
    print(f"  MCP A2A Two-Agent Smoke Test")
    print(f"  Agent A: AlgoVoi MCP tools (this script)")
    print(f"  Agent B: {AGENT_URL}")
    print(f"{'═' * 60}")

    # Phase 1 always runs
    phase1_fetch_agent_card()
    phase1_send_unpaid()
    phase1_show_challenge()

    # Phase 2 requires credentials
    if args.phase == 2:
        api_key   = os.environ.get("ALGOVOI_KEY", "").strip()
        tenant_id = os.environ.get("TENANT_ID",   "").strip()
        payout    = os.environ.get("PAYOUT_ADDRESS", "").strip()
        tx_id     = args.tx.strip()

        missing = []
        if not api_key:   missing.append("ALGOVOI_KEY")
        if not tenant_id: missing.append("TENANT_ID")
        if not payout:    missing.append("PAYOUT_ADDRESS")
        if not tx_id:     missing.append("--tx <TX_ID>")

        if missing:
            print(f"\n  Phase 2 skipped — missing: {', '.join(missing)}")
        else:
            phase2_full_roundtrip(api_key, tenant_id, payout, tx_id)

    # Summary
    total = _passes + _fails
    print(f"\n{'═' * 60}")
    status = "PASS" if _fails == 0 else "FAIL"
    color  = "\033[32m" if _fails == 0 else "\033[31m"
    print(f"  {color}{status}\033[0m  {_passes}/{total} checks passed")
    print(f"{'═' * 60}\n")
    sys.exit(0 if _fails == 0 else 1)


if __name__ == "__main__":
    main()
