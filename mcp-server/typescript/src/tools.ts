/**
 * All 8 MCP tools exposed by the AlgoVoi MCP server.
 *
 * Each tool is a pure async function receiving a typed args object and
 * returning a JSON-serialisable result. `index.ts` wraps these into MCP
 * tool responses with the correct content format.
 */

import { createHmac, randomBytes, timingSafeEqual } from "node:crypto";
import { Buffer } from "node:buffer";
import { AlgoVoiClient } from "./client.js";
import { NETWORKS, NETWORK_INFO, PROTOCOLS, type Network } from "./networks.js";

const MAX_TOKEN_LEN = 200;
const MAX_TX_ID_LEN = 200;
const MAX_WEBHOOK_BODY = 64 * 1024;

// ── 1. create_payment_link ────────────────────────────────────────────────────

export interface CreatePaymentLinkArgs {
  amount: number;
  currency: string;
  label: string;
  network: string;
  redirect_url?: string;
}

export async function createPaymentLink(
  client: AlgoVoiClient,
  args: CreatePaymentLinkArgs
) {
  if (!NETWORKS.includes(args.network as Network)) {
    throw new Error(
      `network must be one of: ${NETWORKS.join(", ")} — got "${args.network}"`
    );
  }
  const link = await client.createPaymentLink({
    amount: args.amount,
    currency: args.currency,
    label: args.label,
    network: args.network,
    redirectUrl: args.redirect_url,
  });
  return {
    checkout_url: link.checkout_url,
    token: link.token,
    chain: link.chain,
    amount_microunits: link.amount_microunits,
    amount_display: `${args.amount.toFixed(2)} ${args.currency.toUpperCase()}`,
  };
}

// ── 2. verify_payment ─────────────────────────────────────────────────────────

export interface VerifyPaymentArgs {
  token: string;
  tx_id?: string;
}

export async function verifyPayment(
  client: AlgoVoiClient,
  args: VerifyPaymentArgs
) {
  if (!args.token || args.token.length > MAX_TOKEN_LEN) {
    throw new Error(
      `token must be a non-empty string up to ${MAX_TOKEN_LEN} chars`
    );
  }
  // If a tx_id is given, verify the on-chain transaction. Otherwise fall
  // back to the hosted-return status endpoint.
  if (args.tx_id) {
    if (args.tx_id.length > MAX_TX_ID_LEN) {
      throw new Error(`tx_id must be ≤ ${MAX_TX_ID_LEN} chars`);
    }
    const resp = await client.verifyExtensionPayment(args.token, args.tx_id);
    return {
      paid: resp.success === true,
      status: resp.success ? "verified" : "unverified",
      error: (resp.error as string) ?? null,
      raw: resp,
    };
  }
  const resp = await client.verifyHostedReturn(args.token);
  return {
    paid: resp.paid,
    status: resp.status,
    raw: resp.raw,
  };
}

// ── 3. prepare_extension_payment ──────────────────────────────────────────────

export interface PrepareExtensionPaymentArgs {
  amount: number;
  currency: string;
  label: string;
  network: string;
}

export async function prepareExtensionPayment(
  client: AlgoVoiClient,
  args: PrepareExtensionPaymentArgs
) {
  if (!["algorand_mainnet", "voi_mainnet"].includes(args.network)) {
    throw new Error(
      'extension payments require network "algorand_mainnet" or "voi_mainnet"'
    );
  }
  const link = await client.createPaymentLink({
    amount: args.amount,
    currency: args.currency,
    label: args.label,
    network: args.network,
  });
  const info = NETWORK_INFO[args.network as Network];
  return {
    token: link.token,
    checkout_url: link.checkout_url,
    chain: link.chain,
    amount_microunits: link.amount_microunits,
    asset_id: info.asset_id,
    ticker: info.asset,
    instructions:
      "Use the returned token with your client-side wallet flow, then call verify_payment " +
      "with the tx_id once the on-chain transfer is submitted.",
  };
}

// ── 4. verify_webhook ─────────────────────────────────────────────────────────

export interface VerifyWebhookArgs {
  raw_body: string;
  signature: string;
  webhook_secret?: string;
}

export function verifyWebhook(
  webhookSecretFromEnv: string | undefined,
  args: VerifyWebhookArgs
) {
  const secret = args.webhook_secret || webhookSecretFromEnv;
  if (!secret) {
    return {
      valid: false,
      payload: null,
      error: "webhook_secret not configured in env or passed as argument",
    };
  }
  if (!args.signature || typeof args.signature !== "string") {
    return { valid: false, payload: null, error: "missing signature" };
  }
  const bodyBytes = Buffer.from(args.raw_body, "utf8");
  if (bodyBytes.length > MAX_WEBHOOK_BODY) {
    return { valid: false, payload: null, error: "body exceeds 64 KiB cap" };
  }
  const expected = createHmac("sha256", secret)
    .update(bodyBytes)
    .digest("base64");
  const given = Buffer.from(args.signature, "utf8");
  const exp = Buffer.from(expected, "utf8");
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
    note: "Use `key` as the `network` argument for other AlgoVoi tools.",
  };
}

// ── 6. generate_mpp_challenge ─────────────────────────────────────────────────

export interface GenerateMppChallengeArgs {
  resource_id: string;
  amount_microunits: number;
  networks?: string[];
  expires_in_seconds?: number;
}

const CAIP2: Record<string, string> = {
  algorand_mainnet: "algorand:mainnet",
  voi_mainnet: "voi:mainnet",
  hedera_mainnet: "hedera:mainnet",
  stellar_mainnet: "stellar:pubnet",
};

export function generateMppChallenge(
  client: AlgoVoiClient,
  args: GenerateMppChallengeArgs
) {
  const nets = args.networks ?? ["algorand_mainnet"];
  for (const n of nets) {
    if (!NETWORKS.includes(n as Network)) {
      throw new Error(`unsupported network in networks[]: ${n}`);
    }
  }
  const expiresIn = args.expires_in_seconds ?? 300;
  const expiresAt = new Date(Date.now() + expiresIn * 1000).toISOString();

  const accepts = nets.map((n) => {
    const info = NETWORK_INFO[n as Network];
    return {
      scheme: "algovoi",
      network: CAIP2[n],
      asset: info.asset_id,
      receiver: client.payoutAddress,
      amount: String(args.amount_microunits),
      decimals: info.decimals,
    };
  });

  const requestObj = {
    intent: "charge" as const,
    resource: args.resource_id,
    accepts,
    expires: expiresAt,
  };
  const requestB64 = Buffer.from(JSON.stringify(requestObj), "utf8").toString(
    "base64"
  );
  // Challenge ID = HMAC-SHA256(tenantId + resourceId + expiresAt) — mirrors
  // the server-side MppGate pattern so the echo check succeeds.
  const idInput = `${client.tenantId}|${args.resource_id}|${expiresAt}`;
  const challengeId = createHmac(
    "sha256",
    randomBytes(16).toString("hex")
  )
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
      "WWW-Authenticate": wwwAuthenticate,
      "X-Payment-Required": xPaymentRequired,
    },
    challenge_id: challengeId,
    accepts,
    expires: expiresAt,
    note: "Return this 402 response from your API. The client must pay on-chain and re-send with Authorization: Payment <token>.",
  };
}

// ── 7. verify_mpp_receipt ─────────────────────────────────────────────────────

export interface VerifyMppReceiptArgs {
  resource_id: string;
  tx_id: string;
  network: string;
}

export async function verifyMppReceipt(
  client: AlgoVoiClient,
  args: VerifyMppReceiptArgs
) {
  if (!args.resource_id || !args.tx_id) {
    throw new Error("resource_id and tx_id are required");
  }
  if (!NETWORKS.includes(args.network as Network)) {
    throw new Error(`unsupported network: ${args.network}`);
  }
  const resp = await client.verifyMppReceipt(
    args.resource_id,
    args.tx_id,
    args.network
  );
  return {
    verified: Boolean((resp as any).verified ?? (resp as any).valid),
    raw: resp,
  };
}

// ── 8. verify_x402_proof ──────────────────────────────────────────────────────

export interface VerifyX402ProofArgs {
  proof: string;
  network: string;
}

export async function verifyX402Proof(
  client: AlgoVoiClient,
  args: VerifyX402ProofArgs
) {
  if (!args.proof) {
    throw new Error("proof is required (base64-encoded x402 payment payload)");
  }
  if (!NETWORKS.includes(args.network as Network)) {
    throw new Error(`unsupported network: ${args.network}`);
  }
  const resp = await client.verifyX402Proof(args.proof, args.network);
  return {
    verified: Boolean((resp as any).verified ?? (resp as any).valid),
    raw: resp,
  };
}

// ── Tool schemas for MCP ListTools response ───────────────────────────────────

export const TOOL_SCHEMAS = [
  {
    name: "create_payment_link",
    description:
      "Create a hosted AlgoVoi checkout URL for a given amount and chain. Returns a short token and public URL the customer can visit to pay in USDC (Algorand / VOI / Hedera / Stellar).",
    inputSchema: {
      type: "object",
      properties: {
        amount: {
          type: "number",
          description: "Payment amount in fiat units (e.g. 5.00 for $5.00).",
        },
        currency: {
          type: "string",
          description: "ISO currency code — e.g. USD, GBP, EUR.",
        },
        label: {
          type: "string",
          description: 'Short order label (e.g. "Order #123").',
        },
        network: {
          type: "string",
          enum: [...NETWORKS],
          description: "Preferred blockchain network.",
        },
        redirect_url: {
          type: "string",
          description:
            "https URL to return the customer to after payment (optional).",
        },
      },
      required: ["amount", "currency", "label", "network"],
    },
  },
  {
    name: "verify_payment",
    description:
      "Verify that a payment for a given checkout token has settled. Returns paid/unpaid status. If tx_id is supplied, verifies that specific on-chain transaction; otherwise uses hosted-checkout status.",
    inputSchema: {
      type: "object",
      properties: {
        token: {
          type: "string",
          description: "Short token returned by create_payment_link.",
        },
        tx_id: {
          type: "string",
          description:
            "Optional on-chain transaction ID to verify against the token.",
        },
      },
      required: ["token"],
    },
  },
  {
    name: "prepare_extension_payment",
    description:
      "Prepare an in-page wallet-extension payment (Algorand / VOI only). Returns the token and chain parameters a frontend can use to ask a browser wallet to sign and submit the transfer, then verify with verify_payment + tx_id.",
    inputSchema: {
      type: "object",
      properties: {
        amount: { type: "number" },
        currency: { type: "string" },
        label: { type: "string" },
        network: {
          type: "string",
          enum: ["algorand_mainnet", "voi_mainnet"],
        },
      },
      required: ["amount", "currency", "label", "network"],
    },
  },
  {
    name: "verify_webhook",
    description:
      "Verify an AlgoVoi webhook HMAC-SHA256 signature. Returns {valid: true, payload: <parsed-json>} if the signature matches the configured webhook secret. Never passes the secret through the transcript.",
    inputSchema: {
      type: "object",
      properties: {
        raw_body: {
          type: "string",
          description: "Raw webhook POST body as a UTF-8 string.",
        },
        signature: {
          type: "string",
          description: "Base64 signature from the X-AlgoVoi-Signature header.",
        },
      },
      required: ["raw_body", "signature"],
    },
  },
  {
    name: "list_networks",
    description:
      "List the blockchain networks AlgoVoi supports, with asset IDs, decimals, and CAIP-2 identifiers. Offline tool — no API call.",
    inputSchema: {
      type: "object",
      properties: {},
    },
  },
  {
    name: "generate_mpp_challenge",
    description:
      "Generate an IETF MPP (draft-ryan-httpauth-payment) 402 challenge that an API server can return to gate a resource. Produces the WWW-Authenticate and X-Payment-Required headers plus the challenge_id to echo.",
    inputSchema: {
      type: "object",
      properties: {
        resource_id: {
          type: "string",
          description: 'Logical resource identifier (e.g. "premium-kb").',
        },
        amount_microunits: {
          type: "integer",
          description: "Amount in asset micro-units (1 USDC = 1_000_000).",
        },
        networks: {
          type: "array",
          items: { type: "string", enum: [...NETWORKS] },
          description:
            'Networks to accept. Defaults to ["algorand_mainnet"] if omitted.',
        },
        expires_in_seconds: {
          type: "integer",
          description: "Challenge TTL; default 300.",
        },
      },
      required: ["resource_id", "amount_microunits"],
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
        tx_id: { type: "string" },
        network: {
          type: "string",
          enum: [...NETWORKS],
        },
      },
      required: ["resource_id", "tx_id", "network"],
    },
  },
  {
    name: "verify_x402_proof",
    description:
      "Verify a base64-encoded x402 payment proof against a given network — returns {verified: true} if the proof corresponds to a confirmed on-chain transfer to the tenant's payout address.",
    inputSchema: {
      type: "object",
      properties: {
        proof: {
          type: "string",
          description: "Base64 payment payload from X-Payment header.",
        },
        network: {
          type: "string",
          enum: [...NETWORKS],
        },
      },
      required: ["proof", "network"],
    },
  },
] as const;
