/**
 * All 8 MCP tools exposed by the AlgoVoi MCP server.
 *
 * Each tool is a pure async function — the dispatcher in `index.ts` calls
 * the matching parser from `schemas.ts` first, so every function below
 * receives a validated, typed argument object.
 */

import { createHmac, timingSafeEqual, randomBytes, randomUUID } from "node:crypto";
import { Buffer } from "node:buffer";
import { AlgoVoiClient } from "./client.js";
import { IdempotencyCache } from "./idempotency.js";
import {
  NETWORKS,
  NETWORK_INFO,
  PROTOCOLS,
  type Network,
} from "./networks.js";
import type {
  CreatePaymentLinkInput,
  FetchAgentCardInput,
  GenerateAp2MandateInput,
  GenerateMppChallengeInput,
  GenerateX402ChallengeInput,
  PrepareExtensionPaymentInput,
  SendA2aMessageInput,
  VerifyAp2PaymentInput,
  VerifyMppReceiptInput,
  VerifyPaymentInput,
  VerifyWebhookInput,
  VerifyX402ProofInput,
} from "./schemas.js";

const MAX_WEBHOOK_BODY = 64 * 1024;

// Process-wide cache for create_payment_link idempotency.
const IDEMPOTENCY = new IdempotencyCache<Record<string, unknown>>();

// Exported for tests that want to clear cache state between runs.
export function _resetIdempotencyCacheForTests() {
  // `IDEMPOTENCY` is a const, but we can clear via Map semantics exposed
  // indirectly.  Set TTL-expired state by reconstructing — use a test-only
  // hook through the module's closure.
  (IDEMPOTENCY as unknown as { store: Map<string, unknown> }).store?.clear?.();
}

// ── 1. create_payment_link ────────────────────────────────────────────────────

export async function createPaymentLink(
  client: AlgoVoiClient,
  args: CreatePaymentLinkInput
) {
  if (args.idempotency_key) {
    const cached = IDEMPOTENCY.get(args.idempotency_key);
    if (cached) return cached;
  }
  const link = await client.createPaymentLink({
    amount:         args.amount,
    currency:       args.currency,
    label:          args.label,
    network:        args.network,
    redirectUrl:    args.redirect_url,
    idempotencyKey: args.idempotency_key,
  });
  const result = {
    checkout_url:      link.checkout_url,
    token:             link.token,
    chain:             link.chain,
    amount_microunits: link.amount_microunits,
    amount_display:    `${args.amount.toFixed(2)} ${args.currency.toUpperCase()}`,
  };
  if (args.idempotency_key) {
    IDEMPOTENCY.set(args.idempotency_key, result);
  }
  return result;
}

// ── 2. verify_payment ─────────────────────────────────────────────────────────

export async function verifyPayment(
  client: AlgoVoiClient,
  args: VerifyPaymentInput
) {
  if (args.tx_id) {
    const resp     = await client.verifyExtensionPayment(args.token, args.tx_id);
    const verified = resp.success === true;
    return {
      paid:   verified,
      status: verified ? "verified" : "unverified",
      error:  verified ? null : ((resp.error as string) ?? null),
    };
  }
  const resp = await client.verifyHostedReturn(args.token);
  return { paid: resp.paid, status: resp.status };
}

// ── 3. prepare_extension_payment ──────────────────────────────────────────────

export async function prepareExtensionPayment(
  client: AlgoVoiClient,
  args: PrepareExtensionPaymentInput
) {
  const link = await client.createPaymentLink({
    amount:   args.amount,
    currency: args.currency,
    label:    args.label,
    network:  args.network,
  });
  const info = NETWORK_INFO[args.network as Network];
  return {
    token:             link.token,
    checkout_url:      link.checkout_url,
    chain:             link.chain,
    amount_microunits: link.amount_microunits,
    asset_id:          info.asset_id,
    ticker:            info.asset,
    instructions:
      "Use the returned token with your client-side wallet flow, then call verify_payment " +
      "with the tx_id once the on-chain transfer is submitted.",
  };
}

// ── 4. verify_webhook ─────────────────────────────────────────────────────────

export function verifyWebhook(
  webhookSecretFromEnv: string | undefined,
  args: VerifyWebhookInput
) {
  if (!webhookSecretFromEnv) {
    return {
      valid:   false,
      payload: null,
      error:   "webhook_secret not configured (ALGOVOI_WEBHOOK_SECRET env var)",
    };
  }
  const bodyBytes = Buffer.from(args.raw_body, "utf8");
  if (bodyBytes.length > MAX_WEBHOOK_BODY) {
    return { valid: false, payload: null, error: "body exceeds 64 KiB cap" };
  }
  const expected = createHmac("sha256", webhookSecretFromEnv)
    .update(bodyBytes)
    .digest("base64");
  const given = Buffer.from(args.signature, "utf8");
  const exp   = Buffer.from(expected, "utf8");
  if (given.length !== exp.length || !timingSafeEqual(given, exp)) {
    return { valid: false, payload: null, error: "signature mismatch" };
  }
  try {
    return { valid: true, payload: JSON.parse(args.raw_body), error: null };
  } catch {
    return { valid: false, payload: null, error: "body is not valid JSON" };
  }
}

// ── 5. list_networks ──────────────────────────────────────────────────────────

export function listNetworks() {
  return {
    networks: Object.entries(NETWORK_INFO).map(([key, info]) => ({
      key,
      ...info,
    })),
    protocols: [...PROTOCOLS],
    note:      "Use `key` as the `network` argument for other AlgoVoi tools.",
  };
}

// ── 6. generate_mpp_challenge ─────────────────────────────────────────────────

const CAIP2: Record<string, string> = {
  // Mainnet
  algorand_mainnet:      "algorand:mainnet",
  voi_mainnet:           "voi:mainnet",
  hedera_mainnet:        "hedera:mainnet",
  stellar_mainnet:       "stellar:pubnet",
  algorand_mainnet_algo: "algorand:mainnet",
  voi_mainnet_voi:       "voi:mainnet",
  hedera_mainnet_hbar:   "hedera:mainnet",
  stellar_mainnet_xlm:   "stellar:pubnet",
  // Testnet
  algorand_testnet:      "algorand:testnet",
  voi_testnet:           "voi:testnet",
  hedera_testnet:        "hedera:testnet",
  stellar_testnet:       "stellar:testnet",
  algorand_testnet_algo: "algorand:testnet",
  voi_testnet_voi:       "voi:testnet",
  hedera_testnet_hbar:   "hedera:testnet",
  stellar_testnet_xlm:   "stellar:testnet",
};

export function generateMppChallenge(
  client: AlgoVoiClient,
  args: GenerateMppChallengeInput
) {
  const nets      = args.networks ?? ["algorand_mainnet"];
  const expiresIn = args.expires_in_seconds ?? 300;
  const expiresAt = new Date(Date.now() + expiresIn * 1000).toISOString();

  const accepts = nets.map((n) => ({
    scheme:   "algovoi",
    network:  CAIP2[n],
    asset:    NETWORK_INFO[n as Network].asset_id,
    receiver: client.payoutAddressFor(n),
    amount:   String(args.amount_microunits),
    decimals: NETWORK_INFO[n as Network].decimals,
  }));

  const requestB64 = Buffer.from(
    JSON.stringify({
      intent:   "charge",
      resource: args.resource_id,
      accepts,
      expires:  expiresAt,
    }),
    "utf8"
  ).toString("base64");

  const idInput     = `${client.tenantId}|${args.resource_id}|${expiresAt}`;
  const challengeId = createHmac("sha256", randomBytes(16).toString("hex"))
    .update(idInput)
    .digest("hex")
    .slice(0, 16);

  const wwwAuthenticate =
    `Payment realm="AlgoVoi", id="${challengeId}", method="algovoi", ` +
    `intent="charge", request="${requestB64}", expires="${expiresAt}"`;

  const xPaymentRequired = Buffer.from(
    JSON.stringify({ accepts, expires: expiresAt }),
    "utf8"
  ).toString("base64");

  return {
    status_code: 402,
    headers: {
      "WWW-Authenticate":   wwwAuthenticate,
      "X-Payment-Required": xPaymentRequired,
    },
    challenge_id: challengeId,
    accepts,
    expires: expiresAt,
    note:
      "Return this 402 response from your API. The client must pay on-chain " +
      "and re-send with Authorization: Payment <token>.",
  };
}

// ── 7. verify_mpp_receipt ─────────────────────────────────────────────────────

export async function verifyMppReceipt(
  client: AlgoVoiClient,
  args: VerifyMppReceiptInput
) {
  const resp = await client.verifyMppReceipt(
    args.resource_id,
    args.tx_id,
    args.network
  );
  return {
    verified: Boolean((resp as any).verified ?? (resp as any).valid),
  };
}

// ── 8. verify_x402_proof ──────────────────────────────────────────────────────

export async function verifyX402Proof(
  client: AlgoVoiClient,
  args: VerifyX402ProofInput
) {
  const resp = await client.verifyX402Proof(args.proof, args.network);
  return {
    verified: Boolean((resp as any).verified ?? (resp as any).valid),
  };
}

// ── 9. generate_x402_challenge ────────────────────────────────────────────────

export function generateX402Challenge(
  client: AlgoVoiClient,
  args: GenerateX402ChallengeInput
) {
  const network    = args.network ?? "algorand_mainnet";
  const info       = NETWORK_INFO[network as Network];
  const expiresIn  = args.expires_in_seconds ?? 300;
  const expiresAt  = new Date(Date.now() + expiresIn * 1000).toISOString();

  const payload = {
    version:           "1",
    scheme:            "exact",
    networkId:         CAIP2[network],
    maxAmountRequired: String(args.amount_microunits),
    resource:          args.resource,
    description:       args.description ?? "",
    mimeType:          "application/json",
    payTo:             client.payoutAddressFor(network),
    maxTimeoutSeconds: expiresIn,
    asset:             info.asset_id,
    decimals:          info.decimals,
    extra:             {},
  };

  const xPaymentRequired = Buffer.from(JSON.stringify(payload), "utf8").toString("base64");

  return {
    status_code: 402,
    headers: {
      "X-Payment-Required": xPaymentRequired,
    },
    payload,
    expires: expiresAt,
    note:
      "Return this 402 response from your API. The client must pay on-chain " +
      "and re-send with X-Payment: <base64-proof>, then verify with verify_x402_proof.",
  };
}

// ── 10. generate_ap2_mandate ──────────────────────────────────────────────────

export function generateAp2Mandate(
  client: AlgoVoiClient,
  args: GenerateAp2MandateInput
) {
  const network    = args.network ?? "algorand_mainnet";
  const info       = NETWORK_INFO[network as Network];
  const expiresIn  = args.expires_in_seconds ?? 300;
  const expiresAt  = new Date(Date.now() + expiresIn * 1000).toISOString();

  const idInput  = `${client.tenantId}|${args.resource_id}|${expiresAt}`;
  const mandateId = createHmac("sha256", randomBytes(16).toString("hex"))
    .update(idInput)
    .digest("hex")
    .slice(0, 16);

  const mandate = {
    version:     "0.1",
    type:        "PaymentMandate",
    mandate_id:  mandateId,
    payee: {
      address:  client.payoutAddressFor(network),
      network:  CAIP2[network],
      asset_id: info.asset_id,
    },
    amount: {
      value:    String(args.amount_microunits),
      decimals: info.decimals,
    },
    resource:    args.resource_id,
    description: args.description ?? "",
    expires:     expiresAt,
    protocol:    "algovoi-ap2/0.1",
  };

  const mandateB64 = Buffer.from(JSON.stringify(mandate), "utf8").toString("base64");

  return {
    mandate_id:  mandateId,
    mandate,
    mandate_b64: mandateB64,
    expires:     expiresAt,
    note:
      "Include mandate_b64 in the AP2-Payment-Required header. " +
      "The paying agent submits on-chain, then call verify_ap2_payment " +
      "with the mandate_id and tx_id.",
  };
}

// ── 11. verify_ap2_payment ────────────────────────────────────────────────────

export async function verifyAp2Payment(
  client: AlgoVoiClient,
  args: VerifyAp2PaymentInput
) {
  const resp = await client.verifyAp2Payment(args.mandate_id, args.tx_id, args.network);
  return {
    verified: Boolean((resp as any).verified ?? (resp as any).valid),
  };
}

// ── 12. fetch_agent_card ──────────────────────────────────────────────────────

export async function fetchAgentCard(args: FetchAgentCardInput): Promise<unknown> {
  const url = `${args.agent_url.replace(/\/$/, "")}/.well-known/agent.json`;
  try {
    const resp = await fetch(url, {
      method:  "GET",
      headers: { Accept: "application/json", "User-Agent": "algovoi-mcp/1.2.0" },
      signal:  AbortSignal.timeout(5_000),
    });
    if (!resp.ok) {
      return { agent_url: args.agent_url, card: null, error: `HTTP ${resp.status}` };
    }
    const card = await resp.json();
    return { agent_url: args.agent_url, card, error: null };
  } catch (err) {
    return {
      agent_url: args.agent_url,
      card:      null,
      error:     err instanceof Error ? err.message : String(err),
    };
  }
}

// ── 13. send_a2a_message ──────────────────────────────────────────────────────

export async function sendA2aMessage(args: SendA2aMessageInput): Promise<unknown> {
  const url     = `${args.agent_url.replace(/\/$/, "")}/message:send`;
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    Accept:          "application/json",
    "User-Agent":    "algovoi-mcp/1.2.0",
  };
  if (args.payment_proof) {
    headers["Authorization"] = `Payment ${args.payment_proof}`;
  }
  const body = JSON.stringify({
    message: {
      role:      "user",
      parts:     [{ type: "text", text: args.text }],
      messageId: args.message_id ?? randomUUID(),
    },
  });

  let resp: Response;
  try {
    resp = await fetch(url, {
      method:  "POST",
      headers,
      body,
      signal:  AbortSignal.timeout(30_000),
    });
  } catch (err) {
    return {
      payment_required: false,
      agent_url:        args.agent_url,
      task:             null,
      error:            err instanceof Error ? err.message : String(err),
    };
  }

  if (resp.status === 402) {
    const challengeHeaders: Record<string, string> = {};
    resp.headers.forEach((v, k) => { challengeHeaders[k] = v; });
    let body402: Record<string, unknown> = {};
    try { body402 = (await resp.json()) as Record<string, unknown>; } catch { /* empty */ }
    return {
      payment_required:  true,
      challenge_headers: challengeHeaders,
      request_id:        body402["request_id"] ?? null,
      agent_url:         args.agent_url,
      note:
        "Pay on-chain then retry with payment_proof set. " +
        "Inspect challenge_headers — WWW-Authenticate = MPP, " +
        "X-Payment-Required = x402, X-AP2-Cart-Mandate = AP2.",
    };
  }

  if (!resp.ok) {
    return {
      payment_required: false,
      agent_url:        args.agent_url,
      task:             null,
      error:            `HTTP ${resp.status}`,
    };
  }

  const task = await resp.json();
  return { payment_required: false, agent_url: args.agent_url, task };
}

// ── Tool schemas (MCP wire — JSON Schema) ─────────────────────────────────────

export const TOOL_SCHEMAS = [
  {
    name: "create_payment_link",
    description:
      "Create a hosted AlgoVoi checkout URL for a given amount and chain. Returns a short token and public URL the customer can visit to pay in USDC or native tokens (Algorand / VOI / Hedera / Stellar).",
    inputSchema: {
      type: "object",
      properties: {
        amount:   { type: "number", description: "Payment amount in fiat units (e.g. 5.00 for $5.00)." },
        currency: { type: "string", description: "ISO currency code — e.g. USD, GBP, EUR." },
        label:    { type: "string", description: 'Short order label (e.g. "Order #123").' },
        network:  { type: "string", enum: [...NETWORKS], description: "Preferred blockchain network." },
        redirect_url:    { type: "string", description: "https URL to return the customer to after payment (optional)." },
        idempotency_key: { type: "string", description: "16–64 char token — duplicate calls within 24h return the same checkout URL." },
      },
      required: ["amount", "currency", "label", "network"],
      additionalProperties: false,
    },
  },
  {
    name: "verify_payment",
    description:
      "Verify that a payment for a given checkout token has settled. Returns paid/unpaid status. If tx_id is supplied, verifies that specific on-chain transaction; otherwise uses hosted-checkout status.",
    inputSchema: {
      type: "object",
      properties: {
        token: { type: "string", description: "Short token returned by create_payment_link." },
        tx_id: { type: "string", description: "Optional on-chain transaction ID to verify against the token." },
      },
      required: ["token"],
      additionalProperties: false,
    },
  },
  {
    name: "prepare_extension_payment",
    description:
      "Prepare an in-page wallet-extension payment (Algorand / VOI only). Returns the token and chain parameters a frontend can use to ask a browser wallet to sign and submit the transfer, then verify with verify_payment + tx_id.",
    inputSchema: {
      type: "object",
      properties: {
        amount:   { type: "number" },
        currency: { type: "string" },
        label:    { type: "string" },
        network:  { type: "string", enum: ["algorand_mainnet", "voi_mainnet", "algorand_mainnet_algo", "voi_mainnet_voi", "algorand_testnet", "voi_testnet", "algorand_testnet_algo", "voi_testnet_voi"] },
      },
      required: ["amount", "currency", "label", "network"],
      additionalProperties: false,
    },
  },
  {
    name: "verify_webhook",
    description:
      "Verify an AlgoVoi webhook HMAC-SHA256 signature. Returns {valid: true, payload: <parsed-json>} if the signature matches the server's configured webhook secret (ALGOVOI_WEBHOOK_SECRET env var — never passed as a tool argument).",
    inputSchema: {
      type: "object",
      properties: {
        raw_body:  { type: "string", description: "Raw webhook POST body as a UTF-8 string." },
        signature: { type: "string", description: "Base64 signature from the X-AlgoVoi-Signature header." },
      },
      required: ["raw_body", "signature"],
      additionalProperties: false,
    },
  },
  {
    name: "list_networks",
    description:
      "List the blockchain networks AlgoVoi supports, with asset IDs, decimals, and CAIP-2 identifiers. Offline tool — no API call.",
    inputSchema: { type: "object", properties: {}, additionalProperties: false },
  },
  {
    name: "generate_mpp_challenge",
    description:
      "Generate an IETF MPP (draft-ryan-httpauth-payment) 402 challenge that an API server can return to gate a resource. Produces the WWW-Authenticate and X-Payment-Required headers plus the challenge_id to echo.",
    inputSchema: {
      type: "object",
      properties: {
        resource_id:       { type: "string",  description: 'Logical resource identifier (e.g. "premium-kb").' },
        amount_microunits: { type: "integer", description: "Amount in asset micro-units (1 USDC = 1_000_000)." },
        networks: {
          type: "array",
          items: { type: "string", enum: [...NETWORKS] },
          description: 'Networks to accept. Defaults to ["algorand_mainnet"] if omitted.',
        },
        expires_in_seconds: { type: "integer", description: "Challenge TTL; default 300." },
      },
      required: ["resource_id", "amount_microunits"],
      additionalProperties: false,
    },
  },
  {
    name: "verify_mpp_receipt",
    description:
      "Verify an MPP receipt (on-chain transaction ID) for a given resource — returns {verified: true} if the transaction paid the resource's declared amount to the tenant's payout address.",
    inputSchema: {
      type: "object",
      properties: {
        resource_id: { type: "string" },
        tx_id:       { type: "string" },
        network:     { type: "string", enum: [...NETWORKS] },
      },
      required: ["resource_id", "tx_id", "network"],
      additionalProperties: false,
    },
  },
  {
    name: "verify_x402_proof",
    description:
      "Verify a base64-encoded x402 payment proof against a given network — returns {verified: true} if the proof corresponds to a confirmed on-chain transfer to the tenant's payout address.",
    inputSchema: {
      type: "object",
      properties: {
        proof:   { type: "string", description: "Base64 payment payload from X-Payment header." },
        network: { type: "string", enum: [...NETWORKS] },
      },
      required: ["proof", "network"],
      additionalProperties: false,
    },
  },
  {
    name: "generate_x402_challenge",
    description:
      "Generate an x402 (spec v1) 402 Payment Required response for gating a resource. Returns the X-Payment-Required header value and full payload. The client must pay on-chain and re-send with X-Payment: <base64-proof>, then verify with verify_x402_proof.",
    inputSchema: {
      type: "object",
      properties: {
        resource:           { type: "string",  description: "Resource URL or identifier being gated." },
        amount_microunits:  { type: "integer", description: "Amount in asset micro-units (1 USDC = 1_000_000)." },
        network:            { type: "string",  enum: [...NETWORKS], description: "Network to accept. Defaults to algorand_mainnet." },
        expires_in_seconds: { type: "integer", description: "Challenge TTL in seconds; default 300." },
        description:        { type: "string",  description: "Optional human-readable description shown in the payment prompt." },
      },
      required: ["resource", "amount_microunits"],
      additionalProperties: false,
    },
  },
  {
    name: "generate_ap2_mandate",
    description:
      "Generate an AP2 v0.1 PaymentMandate for agent-to-agent payment. Returns the mandate object and its base64 encoding for the AP2-Payment-Required header. After the paying agent submits on-chain, call verify_ap2_payment to confirm.",
    inputSchema: {
      type: "object",
      properties: {
        resource_id:        { type: "string",  description: "Logical resource or task identifier." },
        amount_microunits:  { type: "integer", description: "Amount in asset micro-units (1 USDC = 1_000_000)." },
        network:            { type: "string",  enum: [...NETWORKS], description: "Network to accept. Defaults to algorand_mainnet." },
        expires_in_seconds: { type: "integer", description: "Mandate TTL in seconds; default 300." },
        description:        { type: "string",  description: "Optional description of the resource or task." },
      },
      required: ["resource_id", "amount_microunits"],
      additionalProperties: false,
    },
  },
  {
    name: "verify_ap2_payment",
    description:
      "Verify an AP2 payment — returns {verified: true} if the on-chain transaction satisfies the mandate's amount and recipient.",
    inputSchema: {
      type: "object",
      properties: {
        mandate_id: { type: "string", description: "mandate_id returned by generate_ap2_mandate." },
        tx_id:      { type: "string", description: "On-chain transaction ID submitted by the paying agent." },
        network:    { type: "string", enum: [...NETWORKS] },
      },
      required: ["mandate_id", "tx_id", "network"],
      additionalProperties: false,
    },
  },
  {
    name: "fetch_agent_card",
    description:
      "Fetch an A2A agent's public discovery card from {agent_url}/.well-known/agent.json. " +
      "Returns the agent's name, capabilities, skills, and supported payment schemes. " +
      "Use this before send_a2a_message to understand what the agent does and what it costs.",
    inputSchema: {
      type: "object",
      properties: {
        agent_url: {
          type:        "string",
          description: "Base HTTPS URL of the A2A agent (e.g. https://api1.example.com). Must start with https://.",
        },
      },
      required: ["agent_url"],
      additionalProperties: false,
    },
  },
  {
    name: "send_a2a_message",
    description:
      "Send a message to a payment-gated A2A v1.0 agent (POST {agent_url}/message:send). " +
      "First call with no payment_proof — if the agent requires payment it returns " +
      "payment_required=true with challenge_headers (MPP / x402 / AP2). " +
      "Inspect the challenge, pay on-chain using the matching generate_*_challenge tool, " +
      "then retry with the payment_proof. On success returns the task result.",
    inputSchema: {
      type: "object",
      properties: {
        agent_url: {
          type:        "string",
          description: "Base HTTPS URL of the A2A agent. Must start with https://.",
        },
        text: {
          type:        "string",
          description: "Message text to send (max 4096 chars).",
        },
        payment_proof: {
          type:        "string",
          description:
            "Optional payment proof to include as Authorization: Payment <proof>. " +
            "Obtain after paying on-chain following a 402 challenge.",
        },
        message_id: {
          type:        "string",
          description: "Optional idempotency ID for the message (max 64 chars). Auto-generated if omitted.",
        },
      },
      required:             ["agent_url", "text"],
      additionalProperties: false,
    },
  },
] as const;
