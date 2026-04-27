"""
AlgoVoi MCP server — exposes 16 tools via stdio transport to any MCP client
(Claude Desktop, Claude Code, Cursor, Windsurf).

Tool families:
- 1-13: AlgoVoi platform ops (payment links, MPP/x402/AP2, A2A discovery)
- 14-16: bridge_send / bridge_read / bridge_wait — file-based message channel
         for two collaborating Claude sessions on the same machine to relay
         requests/replies (see bridge.py).

Runtime pipeline (per tool call)::

    raw dict args
       ├─► schemas.py    (Pydantic v2 strict validation)   §4.1
       ├─► tool_*()      (business logic; returns dict)
       ├─► redact.scrub  (strip secrets + truncate strings) §4.2/4.4
       └─► audit.log_call (structured JSON on stderr)       §10

Sections cited above refer to ALGOVOI_MCP.md.
"""

from __future__ import annotations

import base64
import hashlib
import hmac as _hmac
import json
import os
import secrets
import ssl
import sys
import time
from time import monotonic
from typing import Any, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import mcp.types as mcp_types
from mcp.server.lowlevel import Server
from mcp.server.stdio import stdio_server
from pydantic import BaseModel, ValidationError

from . import bridge as _bridge
from .audit import log_call
from .client import AlgoVoiClient
from .idempotency import IdempotencyCache
from .networks import CAIP2, NETWORK_INFO, NETWORKS, PROTOCOLS
from .redact import scrub
from .schemas import (
    BridgeReadInput,
    BridgeSendInput,
    BridgeWaitInput,
    CreatePaymentLinkInput,
    FetchAgentCardInput,
    GenerateAp2MandateInput,
    GenerateMppChallengeInput,
    GenerateX402ChallengeInput,
    ListNetworksInput,
    PrepareExtensionPaymentInput,
    SCHEMAS_BY_TOOL,
    SendA2aMessageInput,
    VerifyAp2PaymentInput,
    VerifyMppReceiptInput,
    VerifyPaymentInput,
    VerifyWebhookInput,
    VerifyX402ProofInput,
)

MAX_WEBHOOK_BODY = 64 * 1024

# Process-wide idempotency cache — stdio server runs per-client, so this is
# per Claude Desktop / Cursor session.
_IDEMPOTENCY = IdempotencyCache()


# ── Tool implementations (accept validated Pydantic models) ───────────────────

def tool_create_payment_link(client: AlgoVoiClient, args: CreatePaymentLinkInput) -> dict:
    # §6.4 — cached replay for the same idempotency key
    if args.idempotency_key:
        cached = _IDEMPOTENCY.get(args.idempotency_key)
        if cached is not None:
            return cached

    link = client.create_payment_link(
        amount          = args.amount,
        currency        = args.currency,
        label           = args.label,
        network         = args.network,
        redirect_url    = args.redirect_url,
        idempotency_key = args.idempotency_key,
    )
    result = {
        "checkout_url":      link["checkout_url"],
        "token":             client.extract_token(link["checkout_url"]),
        "chain":             link.get("chain", "algorand-mainnet"),
        "amount_microunits": int(link.get("amount_microunits", 0)),
        "amount_display":    f"{args.amount:.2f} {args.currency.upper()}",
    }
    if args.idempotency_key:
        _IDEMPOTENCY.set(args.idempotency_key, result)
    return result


def tool_verify_payment(client: AlgoVoiClient, args: VerifyPaymentInput) -> dict:
    if args.tx_id:
        resp = client.verify_extension_payment(args.token, args.tx_id)
        verified = resp.get("success") is True
        return {
            "paid":   verified,
            "status": "verified" if verified else "unverified",
            "error":  resp.get("error") if not verified else None,
        }
    hosted = client.verify_hosted_return(args.token)
    return {"paid": hosted["paid"], "status": hosted["status"]}


def tool_prepare_extension_payment(
    client: AlgoVoiClient, args: PrepareExtensionPaymentInput
) -> dict:
    link = client.create_payment_link(
        amount   = args.amount,
        currency = args.currency,
        label    = args.label,
        network  = args.network,
    )
    info = NETWORK_INFO[args.network]
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


def tool_verify_webhook(
    webhook_secret_env: Optional[str], args: VerifyWebhookInput
) -> dict:
    # webhook_secret never flows through tool arguments — only env var.
    secret = webhook_secret_env
    if not secret:
        return {
            "valid":   False,
            "payload": None,
            "error":   "webhook_secret not configured (ALGOVOI_WEBHOOK_SECRET env var)",
        }
    body_bytes = args.raw_body.encode("utf-8")
    if len(body_bytes) > MAX_WEBHOOK_BODY:
        return {"valid": False, "payload": None, "error": "body exceeds 64 KiB cap"}

    expected = base64.b64encode(
        _hmac.new(secret.encode(), body_bytes, hashlib.sha256).digest()
    ).decode()
    if not _hmac.compare_digest(expected, args.signature):
        return {"valid": False, "payload": None, "error": "signature mismatch"}
    try:
        return {"valid": True, "payload": json.loads(args.raw_body), "error": None}
    except json.JSONDecodeError:
        return {"valid": False, "payload": None, "error": "body is not valid JSON"}


def tool_list_networks(_: ListNetworksInput) -> dict:
    return {
        "networks":  [{"key": k, **v} for k, v in NETWORK_INFO.items()],
        "protocols": list(PROTOCOLS),
        "note":      "Use `key` as the `network` argument for other AlgoVoi tools.",
    }


def tool_generate_mpp_challenge(
    client: AlgoVoiClient, args: GenerateMppChallengeInput
) -> dict:
    nets       = list(args.networks or ["algorand_mainnet"])
    expires_in = args.expires_in_seconds or 300
    expires_at = time.strftime(
        "%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() + expires_in)
    )

    accepts = [
        {
            "scheme":   "algovoi",
            "network":  CAIP2[n],
            "asset":    NETWORK_INFO[n]["asset_id"],
            "receiver": client.payout_address_for(n),
            "amount":   str(args.amount_microunits),
            "decimals": NETWORK_INFO[n]["decimals"],
        }
        for n in nets
    ]

    request_b64 = base64.b64encode(
        json.dumps({
            "intent":   "charge",
            "resource": args.resource_id,
            "accepts":  accepts,
            "expires":  expires_at,
        }).encode()
    ).decode()

    # Challenge ID: HMAC(random_key, tenant|resource|expires)[:16]
    id_key    = secrets.token_hex(16)
    id_input  = f"{client.tenant_id}|{args.resource_id}|{expires_at}"
    challenge_id = _hmac.new(
        id_key.encode(), id_input.encode(), hashlib.sha256
    ).hexdigest()[:16]

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
            "WWW-Authenticate":   www_authenticate,
            "X-Payment-Required": x_payment_required,
        },
        "challenge_id": challenge_id,
        "accepts":      accepts,
        "expires":      expires_at,
        "note": (
            "Return this 402 response from your API. The client must pay on-chain "
            "and re-send with Authorization: Payment <token>."
        ),
    }


def tool_verify_mpp_receipt(
    client: AlgoVoiClient, args: VerifyMppReceiptInput
) -> dict:
    resp = client.verify_mpp_receipt(args.resource_id, args.tx_id, args.network)
    return {"verified": bool(resp.get("verified") or resp.get("valid"))}


def tool_verify_x402_proof(
    client: AlgoVoiClient, args: VerifyX402ProofInput
) -> dict:
    resp = client.verify_x402_proof(args.proof, args.network)
    return {"verified": bool(resp.get("verified") or resp.get("valid"))}


# ── 9. generate_x402_challenge ────────────────────────────────────────────────

def tool_generate_x402_challenge(
    client: AlgoVoiClient, args: GenerateX402ChallengeInput
) -> dict:
    network    = args.network or "algorand_mainnet"
    net_info   = NETWORK_INFO[network]
    expires_in = args.expires_in_seconds or 300
    expires_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() + expires_in))

    payload = {
        "version":           "1",
        "scheme":            "exact",
        "networkId":         CAIP2[network],
        "maxAmountRequired": str(args.amount_microunits),
        "resource":          args.resource,
        "description":       args.description or "",
        "mimeType":          "application/json",
        "payTo":             client.payout_address_for(network),
        "maxTimeoutSeconds": expires_in,
        "asset":             net_info["asset_id"],
        "decimals":          net_info["decimals"],
        "extra":             {},
    }
    x_payment_required = base64.b64encode(json.dumps(payload).encode()).decode()

    return {
        "status_code": 402,
        "headers": {
            "X-Payment-Required": x_payment_required,
        },
        "payload": payload,
        "expires": expires_at,
        "note": (
            "Return this 402 response from your API. The client must pay on-chain "
            "and re-send with X-Payment: <base64-proof>, then verify with verify_x402_proof."
        ),
    }


# ── 10. generate_ap2_mandate ──────────────────────────────────────────────────

def tool_generate_ap2_mandate(
    client: AlgoVoiClient, args: GenerateAp2MandateInput
) -> dict:
    network    = args.network or "algorand_mainnet"
    net_info   = NETWORK_INFO[network]
    expires_in = args.expires_in_seconds or 300
    expires_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() + expires_in))

    id_key     = secrets.token_hex(16)
    id_input   = f"{client.tenant_id}|{args.resource_id}|{expires_at}"
    mandate_id = _hmac.new(
        id_key.encode(), id_input.encode(), hashlib.sha256
    ).hexdigest()[:16]

    mandate = {
        "version":    "0.1",
        "type":       "PaymentMandate",
        "mandate_id": mandate_id,
        "payee": {
            "address":  client.payout_address_for(network),
            "network":  CAIP2[network],
            "asset_id": net_info["asset_id"],
        },
        "amount": {
            "value":    str(args.amount_microunits),
            "decimals": net_info["decimals"],
        },
        "resource":    args.resource_id,
        "description": args.description or "",
        "expires":     expires_at,
        "protocol":    "algovoi-ap2/0.1",
    }
    mandate_b64 = base64.b64encode(json.dumps(mandate).encode()).decode()

    return {
        "mandate_id":  mandate_id,
        "mandate":     mandate,
        "mandate_b64": mandate_b64,
        "expires":     expires_at,
        "note": (
            "Include mandate_b64 in the AP2-Payment-Required header. "
            "The paying agent submits on-chain, then call verify_ap2_payment "
            "with the mandate_id and tx_id."
        ),
    }


# ── 11. verify_ap2_payment ────────────────────────────────────────────────────

def tool_verify_ap2_payment(
    client: AlgoVoiClient, args: VerifyAp2PaymentInput
) -> dict:
    resp = client.verify_ap2_payment(args.mandate_id, args.tx_id, args.network)
    return {"verified": bool(resp.get("verified") or resp.get("valid"))}


# ── 12. fetch_agent_card ─────────────────────────────────────────────────────

def tool_fetch_agent_card(args: FetchAgentCardInput) -> dict:
    url = args.agent_url.rstrip("/") + "/.well-known/agent.json"
    try:
        req = Request(
            url,
            headers={"Accept": "application/json", "User-Agent": "algovoi-mcp/1.3.0"},
        )
        with urlopen(req, timeout=5) as resp:
            body = resp.read(64 * 1024)
        card = json.loads(body)
        return {"agent_url": args.agent_url, "card": card, "error": None}
    except Exception as exc:
        return {"agent_url": args.agent_url, "card": None, "error": str(exc)}


# ── 13. send_a2a_message ──────────────────────────────────────────────────────

def tool_send_a2a_message(args: SendA2aMessageInput) -> dict:
    url        = args.agent_url.rstrip("/") + "/message:send"
    message_id = args.message_id or secrets.token_hex(16)
    payload    = json.dumps({
        "message": {
            "role":      "user",
            "parts":     [{"type": "text", "text": args.text}],
            "messageId": message_id,
        },
    }).encode()
    headers = {
        "Content-Type": "application/json",
        "Accept":       "application/json",
        "User-Agent":   "algovoi-mcp/1.3.0",
    }
    if args.payment_proof:
        headers["Authorization"] = f"Payment {args.payment_proof}"

    try:
        req = Request(url, data=payload, headers=headers, method="POST")
        with urlopen(req, timeout=30) as resp:
            body = resp.read(256 * 1024)
        task = json.loads(body)
        return {"payment_required": False, "agent_url": args.agent_url, "task": task}
    except HTTPError as exc:
        if exc.code == 402:
            challenge_headers = dict(exc.headers)
            body402: dict = {}
            try:
                body402 = json.loads(exc.read(64 * 1024))
            except Exception:
                pass
            return {
                "payment_required":  True,
                "challenge_headers": challenge_headers,
                "request_id":        body402.get("request_id"),
                "agent_url":         args.agent_url,
                "note": (
                    "Pay on-chain then retry with payment_proof set. "
                    "Inspect challenge_headers — WWW-Authenticate = MPP, "
                    "X-Payment-Required = x402, X-AP2-Cart-Mandate = AP2."
                ),
            }
        return {
            "payment_required": False,
            "agent_url":        args.agent_url,
            "task":             None,
            "error":            f"HTTP {exc.code}: {exc.reason}",
        }
    except Exception as exc:
        return {
            "payment_required": False,
            "agent_url":        args.agent_url,
            "task":             None,
            "error":            str(exc),
        }


# ── 14-16. Bridge tools (cross-Claude-session messaging) ──────────────────────

def tool_bridge_send(args: BridgeSendInput) -> dict:
    return _bridge.send(args.channel, args.body, getattr(args, "from_", None))


def tool_bridge_read(args: BridgeReadInput) -> dict:
    return _bridge.read(args.channel, args.since or None, args.limit)


def tool_bridge_wait(args: BridgeWaitInput) -> dict:
    return _bridge.wait(args.channel, args.since or None, args.timeout_seconds)


# ── Tool schemas (MCP wire format — JSON Schema) ──────────────────────────────

TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "name": "create_payment_link",
        "description": (
            "Create a hosted AlgoVoi checkout URL for a given amount and chain. "
            "Returns a short token and public URL the customer can visit to pay in USDC "
            "or native tokens (Algorand / VOI / Hedera / Stellar)."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "amount":          {"type": "number",  "description": "Payment amount in fiat units (e.g. 5.00 for $5.00)."},
                "currency":        {"type": "string",  "description": "ISO currency code — e.g. USD, GBP, EUR."},
                "label":           {"type": "string",  "description": 'Short order label (e.g. "Order #123").'},
                "network":         {"type": "string",  "enum": list(NETWORKS), "description": "Preferred blockchain network."},
                "redirect_url":    {"type": "string", "description": "https URL to return the customer to after payment (optional)."},
                "idempotency_key": {"type": "string", "description": "16–64 char token — duplicate calls within 24h return the same checkout URL."},
            },
            "required":             ["amount", "currency", "label", "network"],
            "additionalProperties": False,
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
            "required":             ["token"],
            "additionalProperties": False,
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
                "network":  {"type": "string", "enum": ["algorand_mainnet", "voi_mainnet", "algorand_mainnet_algo", "voi_mainnet_voi", "algorand_testnet", "voi_testnet", "algorand_testnet_algo", "voi_testnet_voi"]},
            },
            "required":             ["amount", "currency", "label", "network"],
            "additionalProperties": False,
        },
    },
    {
        "name": "verify_webhook",
        "description": (
            "Verify an AlgoVoi webhook HMAC-SHA256 signature. Returns {valid: true, payload: "
            "<parsed-json>} if the signature matches the server's configured webhook secret "
            "(ALGOVOI_WEBHOOK_SECRET env var — never passed as a tool argument)."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "raw_body":  {"type": "string", "description": "Raw webhook POST body as a UTF-8 string."},
                "signature": {"type": "string", "description": "Base64 signature from the X-AlgoVoi-Signature header."},
            },
            "required":             ["raw_body", "signature"],
            "additionalProperties": False,
        },
    },
    {
        "name": "list_networks",
        "description": (
            "List the blockchain networks AlgoVoi supports, with asset IDs, decimals, and "
            "CAIP-2 identifiers. Offline tool — no API call."
        ),
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
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
            "required":             ["resource_id", "amount_microunits"],
            "additionalProperties": False,
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
            "required":             ["resource_id", "tx_id", "network"],
            "additionalProperties": False,
        },
    },
    {
        "name": "verify_x402_proof",
        "description": (
            "Verify an x402 on-chain payment for a resource — returns {verified: true} if the "
            "transaction paid the correct amount to the tenant's payout address on the given network."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "proof":   {"type": "string", "description": "Base64 payment payload from X-Payment header."},
                "network": {"type": "string", "enum": list(NETWORKS)},
            },
            "required":             ["proof", "network"],
            "additionalProperties": False,
        },
    },
    {
        "name": "generate_x402_challenge",
        "description": (
            "Generate an x402 (spec v1) 402 Payment Required response for gating a resource. "
            "Returns the X-Payment-Required header value and full payload. The client must pay "
            "on-chain and re-send with X-Payment: <base64-proof>, then verify with verify_x402_proof."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "resource":          {"type": "string",  "description": "Resource URL or identifier being gated."},
                "amount_microunits": {"type": "integer", "description": "Amount in asset micro-units (1 USDC = 1_000_000)."},
                "network":           {"type": "string",  "enum": list(NETWORKS), "description": "Network to accept. Defaults to algorand_mainnet."},
                "expires_in_seconds": {"type": "integer", "description": "Challenge TTL in seconds; default 300."},
                "description":       {"type": "string",  "description": "Optional human-readable description shown in the payment prompt."},
            },
            "required":             ["resource", "amount_microunits"],
            "additionalProperties": False,
        },
    },
    {
        "name": "generate_ap2_mandate",
        "description": (
            "Generate an AP2 v0.1 PaymentMandate for agent-to-agent payment. Returns the mandate "
            "object and its base64 encoding for the AP2-Payment-Required header. After the paying "
            "agent submits on-chain, call verify_ap2_payment to confirm."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "resource_id":       {"type": "string",  "description": "Logical resource or task identifier."},
                "amount_microunits": {"type": "integer", "description": "Amount in asset micro-units (1 USDC = 1_000_000)."},
                "network":           {"type": "string",  "enum": list(NETWORKS), "description": "Network to accept. Defaults to algorand_mainnet."},
                "expires_in_seconds": {"type": "integer", "description": "Mandate TTL in seconds; default 300."},
                "description":       {"type": "string",  "description": "Optional description of the resource or task."},
            },
            "required":             ["resource_id", "amount_microunits"],
            "additionalProperties": False,
        },
    },
    {
        "name": "verify_ap2_payment",
        "description": (
            "Confirm an AP2 on-chain payment — returns {verified: true} if the transaction "
            "satisfies the mandate's amount and recipient. Call after the paying agent submits on-chain."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "mandate_id": {"type": "string", "description": "mandate_id returned by generate_ap2_mandate."},
                "tx_id":      {"type": "string", "description": "On-chain transaction ID submitted by the paying agent."},
                "network":    {"type": "string", "enum": list(NETWORKS)},
            },
            "required":             ["mandate_id", "tx_id", "network"],
            "additionalProperties": False,
        },
    },
    {
        "name": "fetch_agent_card",
        "description": (
            "Fetch an A2A agent's public discovery card from {agent_url}/.well-known/agent.json. "
            "Returns the agent's name, capabilities, skills, and supported payment schemes. "
            "Use this before send_a2a_message to understand what the agent does and what it costs."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "agent_url": {
                    "type":        "string",
                    "description": "Base HTTPS URL of the A2A agent (e.g. https://api1.example.com). Must start with https://.",
                },
            },
            "required":             ["agent_url"],
            "additionalProperties": False,
        },
    },
    {
        "name": "send_a2a_message",
        "description": (
            "Send a message to a payment-gated A2A v1.0 agent (POST {agent_url}/message:send). "
            "First call with no payment_proof — if the agent requires payment it returns "
            "payment_required=true with challenge_headers (MPP / x402 / AP2). "
            "Inspect the challenge, pay on-chain using the matching generate_*_challenge tool, "
            "then retry with the payment_proof. On success returns the task result."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "agent_url": {
                    "type":        "string",
                    "description": "Base HTTPS URL of the A2A agent. Must start with https://.",
                },
                "text": {
                    "type":        "string",
                    "description": "Message text to send (max 4096 chars).",
                },
                "payment_proof": {
                    "type":        "string",
                    "description": (
                        "Optional payment proof to include as Authorization: Payment <proof>. "
                        "Obtain after paying on-chain following a 402 challenge."
                    ),
                },
                "message_id": {
                    "type":        "string",
                    "description": "Optional idempotency ID for the message (max 64 chars). Auto-generated if omitted.",
                },
            },
            "required":             ["agent_url", "text"],
            "additionalProperties": False,
        },
    },
    # ── 14. bridge_send ───────────────────────────────────────────────────────
    {
        "name":        "bridge_send",
        "description": (
            "Append a message to a shared channel readable by another collaborating "
            "Claude session on the same machine. Storage is a JSONL file per channel "
            "under ~/.algovoi-bridge/. Channel names use [a-z0-9_-]. Returns the "
            "stored record id, timestamp, channel and storage path."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "channel": {"type": "string", "description": "Channel name — [a-z0-9_-]+, max 64 chars."},
                "body":    {"type": "string", "description": "Message body (max 64KB)."},
                "from":    {"type": "string", "description": "Optional sender label, e.g. 'shopify-worker'."},
            },
            "required":             ["channel", "body"],
            "additionalProperties": False,
        },
    },
    # ── 15. bridge_read ───────────────────────────────────────────────────────
    {
        "name":        "bridge_read",
        "description": (
            "Read messages from a shared channel. If 'since' is omitted, returns "
            "the most recent batch (up to 'limit'). If 'since' is a message id, "
            "returns only newer messages (sortable lexicographically by id). "
            "Use the returned 'next_since' to poll incrementally."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "channel": {"type": "string", "description": "Channel name (same as bridge_send)."},
                "since":   {"type": "string", "description": "Message id from a previous read, or empty for recent batch."},
                "limit":   {"type": "integer", "description": "Max messages to return (1–500). Default 50."},
            },
            "required":             ["channel"],
            "additionalProperties": False,
        },
    },
    # ── 16. bridge_wait ───────────────────────────────────────────────────────
    {
        "name":        "bridge_wait",
        "description": (
            "Long-poll: block until a new message appears on the channel after "
            "'since' (or any new message if 'since' is empty), or the timeout "
            "expires. Returns the same shape as bridge_read; 'messages' is empty "
            "iff the timeout was hit."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "channel":         {"type": "string",  "description": "Channel name."},
                "since":           {"type": "string",  "description": "Watermark id; only return messages strictly after this."},
                "timeout_seconds": {"type": "integer", "description": "Max seconds to wait (1–120). Default 30."},
            },
            "required":             ["channel"],
            "additionalProperties": False,
        },
    },
]


# ── Tool filtering (MCP_ENABLED_TOOLS env var) ────────────────────────────────

def _parse_enabled_tools(raw: Optional[str]) -> Optional[set[str]]:
    """Parse the comma-separated allow-list. ``None`` / empty = all tools."""
    if not raw or not raw.strip():
        return None
    names = {t.strip() for t in raw.split(",") if t.strip()}
    known = {t["name"] for t in TOOL_SCHEMAS}
    unknown = names - known
    if unknown:
        sys.stderr.write(
            f"[algovoi-mcp] warning: MCP_ENABLED_TOOLS contains unknown "
            f"tools: {sorted(unknown)} — ignoring\n"
        )
    return names & known


_BRIDGE_TOOLS = {"bridge_send", "bridge_read", "bridge_wait"}


# ── Dispatch (validate → run → redact → audit) ────────────────────────────────

def _dispatch(
    client: Optional[AlgoVoiClient],
    webhook_secret_env: Optional[str],
    name: str,
    raw_args: dict,
) -> dict:
    """Validate args against the schema, run the tool, and redact output."""
    schema_cls = SCHEMAS_BY_TOOL.get(name)
    if schema_cls is None:
        raise ValueError(f"unknown tool: {name}")

    # Bridge tools are pure filesystem ops — no AlgoVoi client needed.
    if name in _BRIDGE_TOOLS:
        args: BaseModel = schema_cls.model_validate(raw_args)
        if name == "bridge_send":
            return scrub(tool_bridge_send(args))   # type: ignore[arg-type]
        if name == "bridge_read":
            return scrub(tool_bridge_read(args))   # type: ignore[arg-type]
        if name == "bridge_wait":
            return scrub(tool_bridge_wait(args))   # type: ignore[arg-type]

    if client is None:
        raise ValueError(
            f"tool '{name}' requires AlgoVoi credentials (running in bridge-only mode)"
        )

    args: BaseModel = schema_cls.model_validate(raw_args)

    if name == "create_payment_link":
        result = tool_create_payment_link(client, args)         # type: ignore[arg-type]
    elif name == "verify_payment":
        result = tool_verify_payment(client, args)              # type: ignore[arg-type]
    elif name == "prepare_extension_payment":
        result = tool_prepare_extension_payment(client, args)   # type: ignore[arg-type]
    elif name == "verify_webhook":
        result = tool_verify_webhook(webhook_secret_env, args)  # type: ignore[arg-type]
    elif name == "list_networks":
        result = tool_list_networks(args)                       # type: ignore[arg-type]
    elif name == "generate_mpp_challenge":
        result = tool_generate_mpp_challenge(client, args)      # type: ignore[arg-type]
    elif name == "verify_mpp_receipt":
        result = tool_verify_mpp_receipt(client, args)          # type: ignore[arg-type]
    elif name == "verify_x402_proof":
        result = tool_verify_x402_proof(client, args)              # type: ignore[arg-type]
    elif name == "generate_x402_challenge":
        result = tool_generate_x402_challenge(client, args)        # type: ignore[arg-type]
    elif name == "generate_ap2_mandate":
        result = tool_generate_ap2_mandate(client, args)           # type: ignore[arg-type]
    elif name == "verify_ap2_payment":
        result = tool_verify_ap2_payment(client, args)             # type: ignore[arg-type]
    elif name == "fetch_agent_card":
        result = tool_fetch_agent_card(args)                       # type: ignore[arg-type]
    elif name == "send_a2a_message":
        result = tool_send_a2a_message(args)                       # type: ignore[arg-type]
    elif name == "bridge_send":
        result = tool_bridge_send(args)                            # type: ignore[arg-type]
    elif name == "bridge_read":
        result = tool_bridge_read(args)                            # type: ignore[arg-type]
    elif name == "bridge_wait":
        result = tool_bridge_wait(args)                            # type: ignore[arg-type]
    else:
        raise ValueError(f"unknown tool: {name}")

    # §4.2 / §4.4 — redact sensitive keys + truncate long strings
    return scrub(result)


# ── Server factory ────────────────────────────────────────────────────────────

def build_server(
    client: Optional[AlgoVoiClient],
    webhook_secret_env: Optional[str],
    enabled_tools: Optional[set[str]] = None,
) -> Server:
    """Construct an MCP ``Server`` with the permitted subset of tools."""
    server  = Server("algovoi-mcp-server")
    allowed = enabled_tools if enabled_tools is not None else {t["name"] for t in TOOL_SCHEMAS}
    schemas = [t for t in TOOL_SCHEMAS if t["name"] in allowed]

    @server.list_tools()
    async def _list_tools() -> list[mcp_types.Tool]:
        return [
            mcp_types.Tool(
                name        = t["name"],
                description = t["description"],
                inputSchema = t["inputSchema"],
            )
            for t in schemas
        ]

    @server.call_tool()
    async def _call_tool(name: str, arguments: dict) -> list[mcp_types.TextContent]:
        if name not in allowed:
            err = json.dumps(
                {"error": f"tool '{name}' is not enabled (MCP_ENABLED_TOOLS)"},
                indent=2,
            )
            log_call(
                tool_name   = name,
                args        = arguments or {},
                status      = "rejected",
                duration_ms = 0.0,
                error_code  = "ToolDisabled",
            )
            return [mcp_types.TextContent(type="text", text=err)]

        start = monotonic()
        try:
            result = _dispatch(client, webhook_secret_env, name, arguments or {})
            log_call(
                tool_name   = name,
                args        = arguments or {},
                status      = "ok",
                duration_ms = (monotonic() - start) * 1000,
            )
            payload = json.dumps(result, indent=2, default=str)
            return [mcp_types.TextContent(type="text", text=payload)]
        except ValidationError as exc:
            log_call(
                tool_name   = name,
                args        = arguments or {},
                status      = "rejected",
                duration_ms = (monotonic() - start) * 1000,
                error_code  = "ValidationError",
            )
            err = json.dumps(
                {"error": "invalid arguments", "detail": exc.errors()},
                indent=2,
                default=str,
            )
            return [mcp_types.TextContent(type="text", text=err)]
        except Exception as exc:
            log_call(
                tool_name   = name,
                args        = arguments or {},
                status      = "error",
                duration_ms = (monotonic() - start) * 1000,
                error_code  = type(exc).__name__,
            )
            err = json.dumps({"error": str(exc)}, indent=2)
            return [mcp_types.TextContent(type="text", text=err)]

    return server


# ── Stdio entry ───────────────────────────────────────────────────────────────

async def run_stdio() -> None:
    """Read env vars, build server, and run stdio transport.

    Bridge-only mode: if MCP_ENABLED_TOOLS restricts to bridge_* tools (or
    ALGOVOI_API_KEY is unset), the AlgoVoi client is not constructed and
    no payout addresses are required — the bridge tools are pure file I/O.
    """
    enabled_tools  = _parse_enabled_tools(os.environ.get("MCP_ENABLED_TOOLS"))
    api_base       = os.environ.get("ALGOVOI_API_BASE", "https://api1.ilovechicken.co.uk")
    webhook_secret = os.environ.get("ALGOVOI_WEBHOOK_SECRET")

    # Bridge-only if the user explicitly limited to bridge tools, OR if no
    # AlgoVoi API key is configured at all.
    bridge_only = (
        (enabled_tools is not None and enabled_tools.issubset(_BRIDGE_TOOLS))
        or not os.environ.get("ALGOVOI_API_KEY", "").strip()
    )

    client: Optional[AlgoVoiClient] = None

    if bridge_only:
        # Default to bridge-only tool set if the user didn't explicitly pick one
        if enabled_tools is None:
            enabled_tools = set(_BRIDGE_TOOLS)
    else:
        api_key   = _require_env("ALGOVOI_API_KEY")
        tenant_id = _require_env("ALGOVOI_TENANT_ID")

        # Per-chain payout addresses. Per-chain vars take priority;
        # ALGOVOI_PAYOUT_ADDRESS acts as a universal fallback.
        payout_fallback = os.environ.get("ALGOVOI_PAYOUT_ADDRESS", "").strip() or None
        chain_env = [
            ("algorand_mainnet", "ALGOVOI_PAYOUT_ALGORAND"),
            ("voi_mainnet",      "ALGOVOI_PAYOUT_VOI"),
            ("hedera_mainnet",   "ALGOVOI_PAYOUT_HEDERA"),
            ("stellar_mainnet",  "ALGOVOI_PAYOUT_STELLAR"),
        ]
        payout_addresses: dict[str, str] = {}
        for key, env_var in chain_env:
            v = (os.environ.get(env_var, "").strip() or None) or payout_fallback
            if v:
                payout_addresses[key] = v
        if not payout_addresses:
            sys.stderr.write(
                "\n[algovoi-mcp] no payout address configured.\n"
                "Set ALGOVOI_PAYOUT_ALGORAND, ALGOVOI_PAYOUT_VOI, ALGOVOI_PAYOUT_HEDERA,\n"
                "ALGOVOI_PAYOUT_STELLAR (or ALGOVOI_PAYOUT_ADDRESS as a universal fallback).\n"
                "(Or run in bridge-only mode by unsetting ALGOVOI_API_KEY or setting\n"
                " MCP_ENABLED_TOOLS=bridge_send,bridge_read,bridge_wait.)\n\n"
            )
            raise SystemExit(2)

        client = AlgoVoiClient(
            api_base         = api_base,
            api_key          = api_key,
            tenant_id        = tenant_id,
            payout_addresses = payout_addresses,
        )

    server = build_server(client, webhook_secret, enabled_tools)

    count = len(enabled_tools) if enabled_tools is not None else len(TOOL_SCHEMAS)
    sys.stderr.write(
        f"[algovoi-mcp] connected on stdio — {count} tools ready, "
        f"webhook_secret={'set' if webhook_secret else 'unset'}\n"
    )

    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())


def _require_env(name: str) -> str:
    v = os.environ.get(name, "").strip()
    if not v:
        sys.stderr.write(
            f"\n[algovoi-mcp] missing required env var: {name}\n"
            "Set ALGOVOI_API_KEY, ALGOVOI_TENANT_ID, and at least one payout address.\n\n"
        )
        raise SystemExit(2)
    return v
