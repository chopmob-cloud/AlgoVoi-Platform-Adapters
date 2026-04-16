"""
AlgoVoi MCP server — exposes 8 tools via stdio transport to any MCP client
(Claude Desktop, Claude Code, Cursor, Windsurf).

Uses the modern `mcp.server.lowlevel.Server` API — the same surface the
official SDK's FastMCP and decorator-based servers compile down to — so this
module stays readable even without the FastMCP DSL.
"""

from __future__ import annotations

import base64
import hashlib
import hmac as _hmac
import json
import os
import secrets
import time
from typing import Any, Optional

import mcp.types as mcp_types
from mcp.server.lowlevel import Server
from mcp.server.stdio import stdio_server

from .client import AlgoVoiClient
from .networks import CAIP2, NETWORK_INFO, NETWORKS, PROTOCOLS

MAX_TOKEN_LEN    = 200
MAX_TX_ID_LEN    = 200
MAX_WEBHOOK_BODY = 64 * 1024


# ── Tool implementations ──────────────────────────────────────────────────────

def tool_create_payment_link(client: AlgoVoiClient, args: dict) -> dict:
    network = args.get("network")
    if network not in NETWORKS:
        raise ValueError(f"network must be one of {list(NETWORKS)} — got {network!r}")
    link = client.create_payment_link(
        amount       = args["amount"],
        currency     = args["currency"],
        label        = args["label"],
        network      = network,
        redirect_url = args.get("redirect_url"),
    )
    return {
        "checkout_url":      link["checkout_url"],
        "token":             client.extract_token(link["checkout_url"]),
        "chain":             link.get("chain", "algorand-mainnet"),
        "amount_microunits": int(link.get("amount_microunits", 0)),
        "amount_display":    f"{float(args['amount']):.2f} {args['currency'].upper()}",
    }


def tool_verify_payment(client: AlgoVoiClient, args: dict) -> dict:
    token = args.get("token", "")
    if not token or len(token) > MAX_TOKEN_LEN:
        raise ValueError(f"token must be a non-empty string up to {MAX_TOKEN_LEN} chars")
    tx_id = args.get("tx_id")
    if tx_id:
        if len(tx_id) > MAX_TX_ID_LEN:
            raise ValueError(f"tx_id must be ≤ {MAX_TX_ID_LEN} chars")
        resp = client.verify_extension_payment(token, tx_id)
        return {
            "paid":   resp.get("success") is True,
            "status": "verified" if resp.get("success") else "unverified",
            "error":  resp.get("error"),
            "raw":    resp,
        }
    return client.verify_hosted_return(token)


def tool_prepare_extension_payment(client: AlgoVoiClient, args: dict) -> dict:
    network = args.get("network")
    if network not in ("algorand_mainnet", "voi_mainnet"):
        raise ValueError('extension payments require network "algorand_mainnet" or "voi_mainnet"')
    link = client.create_payment_link(
        amount   = args["amount"],
        currency = args["currency"],
        label    = args["label"],
        network  = network,
    )
    info = NETWORK_INFO[network]
    return {
        "token":             client.extract_token(link["checkout_url"]),
        "checkout_url":      link["checkout_url"],
        "chain":             link.get("chain", "algorand-mainnet"),
        "amount_microunits": int(link.get("amount_microunits", 0)),
        "asset_id":          info["asset_id"],
        "ticker":            info["asset"],
        "instructions": (
            "Use the returned token with your client-side wallet flow, then call "
            "verify_payment with the tx_id once the on-chain transfer is submitted."
        ),
    }


def tool_verify_webhook(webhook_secret_env: Optional[str], args: dict) -> dict:
    secret = args.get("webhook_secret") or webhook_secret_env
    if not secret:
        return {"valid": False, "payload": None,
                "error": "webhook_secret not configured in env or passed as argument"}
    raw_body  = args.get("raw_body", "")
    signature = args.get("signature", "")
    if not signature or not isinstance(signature, str):
        return {"valid": False, "payload": None, "error": "missing signature"}
    body_bytes = raw_body.encode("utf-8") if isinstance(raw_body, str) else bytes(raw_body)
    if len(body_bytes) > MAX_WEBHOOK_BODY:
        return {"valid": False, "payload": None, "error": "body exceeds 64 KiB cap"}

    expected = base64.b64encode(
        _hmac.new(secret.encode(), body_bytes, hashlib.sha256).digest()
    ).decode()
    if not _hmac.compare_digest(expected, signature):
        return {"valid": False, "payload": None, "error": "signature mismatch"}
    try:
        return {"valid": True, "payload": json.loads(raw_body), "error": None}
    except json.JSONDecodeError:
        return {"valid": False, "payload": None, "error": "body is not valid JSON"}


def tool_list_networks(args: dict) -> dict:
    return {
        "networks":  [{"key": k, **v} for k, v in NETWORK_INFO.items()],
        "protocols": list(PROTOCOLS),
        "note":      "Use `key` as the `network` argument for other AlgoVoi tools.",
    }


def tool_generate_mpp_challenge(client: AlgoVoiClient, args: dict) -> dict:
    resource_id       = args["resource_id"]
    amount_microunits = int(args["amount_microunits"])
    nets              = args.get("networks") or ["algorand_mainnet"]
    expires_in        = int(args.get("expires_in_seconds", 300))

    for n in nets:
        if n not in NETWORKS:
            raise ValueError(f"unsupported network in networks[]: {n}")

    expires_at = time.strftime(
        "%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() + expires_in)
    )

    accepts = [
        {
            "scheme":   "algovoi",
            "network":  CAIP2[n],
            "asset":    NETWORK_INFO[n]["asset_id"],
            "receiver": client.payout_address,
            "amount":   str(amount_microunits),
            "decimals": NETWORK_INFO[n]["decimals"],
        }
        for n in nets
    ]

    request_b64 = base64.b64encode(
        json.dumps({
            "intent":   "charge",
            "resource": resource_id,
            "accepts":  accepts,
            "expires":  expires_at,
        }).encode()
    ).decode()

    # Challenge ID = truncated HMAC of (tenant | resource | expires) with a
    # per-challenge random key — mirrors MppGate's id-construction pattern.
    id_key    = secrets.token_hex(16)
    id_input  = f"{client.tenant_id}|{resource_id}|{expires_at}"
    challenge_id = _hmac.new(id_key.encode(), id_input.encode(), hashlib.sha256).hexdigest()[:16]

    www_authenticate = (
        f'Payment realm="AlgoVoi", id="{challenge_id}", method="algovoi", '
        f'intent="charge", request="{request_b64}", expires="{expires_at}"'
    )
    x_payment_required = base64.b64encode(
        json.dumps({"accepts": accepts, "expires": expires_at}).encode()
    ).decode()

    return {
        "status_code": 402,
        "headers": {
            "WWW-Authenticate":    www_authenticate,
            "X-Payment-Required":  x_payment_required,
        },
        "challenge_id": challenge_id,
        "accepts":      accepts,
        "expires":      expires_at,
        "note": (
            "Return this 402 response from your API. The client must pay on-chain "
            "and re-send with Authorization: Payment <token>."
        ),
    }


def tool_verify_mpp_receipt(client: AlgoVoiClient, args: dict) -> dict:
    resource_id = args.get("resource_id")
    tx_id       = args.get("tx_id")
    network     = args.get("network")
    if not resource_id or not tx_id:
        raise ValueError("resource_id and tx_id are required")
    if network not in NETWORKS:
        raise ValueError(f"unsupported network: {network}")
    resp = client.verify_mpp_receipt(resource_id, tx_id, network)
    return {
        "verified": bool(resp.get("verified") or resp.get("valid")),
        "raw":      resp,
    }


def tool_verify_x402_proof(client: AlgoVoiClient, args: dict) -> dict:
    proof   = args.get("proof")
    network = args.get("network")
    if not proof:
        raise ValueError("proof is required (base64-encoded x402 payment payload)")
    if network not in NETWORKS:
        raise ValueError(f"unsupported network: {network}")
    resp = client.verify_x402_proof(proof, network)
    return {
        "verified": bool(resp.get("verified") or resp.get("valid")),
        "raw":      resp,
    }


# ── Tool schemas (mirrors typescript/src/tools.ts) ────────────────────────────

TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "name": "create_payment_link",
        "description": (
            "Create a hosted AlgoVoi checkout URL for a given amount and chain. "
            "Returns a short token and public URL the customer can visit to pay in USDC "
            "(Algorand / VOI / Hedera / Stellar)."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "amount":   {"type": "number",  "description": "Payment amount in fiat units (e.g. 5.00 for $5.00)."},
                "currency": {"type": "string",  "description": "ISO currency code — e.g. USD, GBP, EUR."},
                "label":    {"type": "string",  "description": 'Short order label (e.g. "Order #123").'},
                "network":  {"type": "string",  "enum": list(NETWORKS), "description": "Preferred blockchain network."},
                "redirect_url": {"type": "string", "description": "https URL to return the customer to after payment (optional)."},
            },
            "required": ["amount", "currency", "label", "network"],
        },
    },
    {
        "name": "verify_payment",
        "description": (
            "Verify that a payment for a given checkout token has settled. Returns paid/unpaid "
            "status. If tx_id is supplied, verifies that specific on-chain transaction; "
            "otherwise uses hosted-checkout status."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "token": {"type": "string", "description": "Short token returned by create_payment_link."},
                "tx_id": {"type": "string", "description": "Optional on-chain transaction ID to verify against the token."},
            },
            "required": ["token"],
        },
    },
    {
        "name": "prepare_extension_payment",
        "description": (
            "Prepare an in-page wallet-extension payment (Algorand / VOI only). Returns the token "
            "and chain parameters a frontend can use to ask a browser wallet to sign and submit "
            "the transfer, then verify with verify_payment + tx_id."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "amount":   {"type": "number"},
                "currency": {"type": "string"},
                "label":    {"type": "string"},
                "network":  {"type": "string", "enum": ["algorand_mainnet", "voi_mainnet"]},
            },
            "required": ["amount", "currency", "label", "network"],
        },
    },
    {
        "name": "verify_webhook",
        "description": (
            "Verify an AlgoVoi webhook HMAC-SHA256 signature. Returns {valid: true, payload: "
            "<parsed-json>} if the signature matches the configured webhook secret. Never passes "
            "the secret through the transcript."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "raw_body":  {"type": "string", "description": "Raw webhook POST body as a UTF-8 string."},
                "signature": {"type": "string", "description": "Base64 signature from the X-AlgoVoi-Signature header."},
            },
            "required": ["raw_body", "signature"],
        },
    },
    {
        "name": "list_networks",
        "description": (
            "List the blockchain networks AlgoVoi supports, with asset IDs, decimals, and "
            "CAIP-2 identifiers. Offline tool — no API call."
        ),
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "generate_mpp_challenge",
        "description": (
            "Generate an IETF MPP (draft-ryan-httpauth-payment) 402 challenge that an API server "
            "can return to gate a resource. Produces the WWW-Authenticate and X-Payment-Required "
            "headers plus the challenge_id to echo."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "resource_id":       {"type": "string",  "description": 'Logical resource identifier (e.g. "premium-kb").'},
                "amount_microunits": {"type": "integer", "description": "Amount in asset micro-units (1 USDC = 1_000_000)."},
                "networks": {
                    "type": "array",
                    "items": {"type": "string", "enum": list(NETWORKS)},
                    "description": 'Networks to accept. Defaults to ["algorand_mainnet"] if omitted.',
                },
                "expires_in_seconds": {"type": "integer", "description": "Challenge TTL; default 300."},
            },
            "required": ["resource_id", "amount_microunits"],
        },
    },
    {
        "name": "verify_mpp_receipt",
        "description": (
            "Verify an MPP receipt (on-chain transaction ID) for a given resource — returns "
            "{verified: true} if the transaction paid the resource's declared amount to the "
            "tenant's payout address."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "resource_id": {"type": "string"},
                "tx_id":       {"type": "string"},
                "network":     {"type": "string", "enum": list(NETWORKS)},
            },
            "required": ["resource_id", "tx_id", "network"],
        },
    },
    {
        "name": "verify_x402_proof",
        "description": (
            "Verify a base64-encoded x402 payment proof against a given network — returns "
            "{verified: true} if the proof corresponds to a confirmed on-chain transfer to the "
            "tenant's payout address."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "proof":   {"type": "string", "description": "Base64 payment payload from X-Payment header."},
                "network": {"type": "string", "enum": list(NETWORKS)},
            },
            "required": ["proof", "network"],
        },
    },
]


# ── Server factory ────────────────────────────────────────────────────────────

def build_server(client: AlgoVoiClient, webhook_secret_env: Optional[str]) -> Server:
    """Construct an MCP ``Server`` with all 8 tools wired up."""
    server = Server("algovoi-mcp-server")

    @server.list_tools()
    async def _list_tools() -> list[mcp_types.Tool]:
        return [
            mcp_types.Tool(
                name=t["name"],
                description=t["description"],
                inputSchema=t["inputSchema"],
            )
            for t in TOOL_SCHEMAS
        ]

    @server.call_tool()
    async def _call_tool(name: str, arguments: dict) -> list[mcp_types.TextContent]:
        try:
            result = _dispatch(client, webhook_secret_env, name, arguments or {})
            payload = json.dumps(result, indent=2, default=str)
            return [mcp_types.TextContent(type="text", text=payload)]
        except Exception as exc:
            err = json.dumps({"error": str(exc)}, indent=2)
            return [mcp_types.TextContent(type="text", text=err)]

    return server


def _dispatch(
    client: AlgoVoiClient,
    webhook_secret_env: Optional[str],
    name: str,
    args: dict,
) -> dict:
    if name == "create_payment_link":
        return tool_create_payment_link(client, args)
    if name == "verify_payment":
        return tool_verify_payment(client, args)
    if name == "prepare_extension_payment":
        return tool_prepare_extension_payment(client, args)
    if name == "verify_webhook":
        return tool_verify_webhook(webhook_secret_env, args)
    if name == "list_networks":
        return tool_list_networks(args)
    if name == "generate_mpp_challenge":
        return tool_generate_mpp_challenge(client, args)
    if name == "verify_mpp_receipt":
        return tool_verify_mpp_receipt(client, args)
    if name == "verify_x402_proof":
        return tool_verify_x402_proof(client, args)
    raise ValueError(f"unknown tool: {name}")


# ── Stdio entry ───────────────────────────────────────────────────────────────

async def run_stdio() -> None:
    """Read env vars, build server, and run stdio transport."""
    api_key        = _require_env("ALGOVOI_API_KEY")
    tenant_id      = _require_env("ALGOVOI_TENANT_ID")
    payout_address = _require_env("ALGOVOI_PAYOUT_ADDRESS")
    api_base       = os.environ.get("ALGOVOI_API_BASE", "https://api1.ilovechicken.co.uk")
    webhook_secret = os.environ.get("ALGOVOI_WEBHOOK_SECRET")

    client = AlgoVoiClient(
        api_base       = api_base,
        api_key        = api_key,
        tenant_id      = tenant_id,
        payout_address = payout_address,
    )
    server = build_server(client, webhook_secret)

    import sys
    sys.stderr.write(
        f"[algovoi-mcp] connected on stdio — {len(TOOL_SCHEMAS)} tools ready, "
        f"api_base={api_base}\n"
    )

    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())


def _require_env(name: str) -> str:
    v = os.environ.get(name, "").strip()
    if not v:
        import sys
        sys.stderr.write(
            f"\n[algovoi-mcp] missing required env var: {name}\n"
            "Set ALGOVOI_API_KEY, ALGOVOI_TENANT_ID, and ALGOVOI_PAYOUT_ADDRESS.\n\n"
        )
        raise SystemExit(2)
    return v
