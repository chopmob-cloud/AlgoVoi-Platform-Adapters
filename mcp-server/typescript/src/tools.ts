/**
 * All 21 MCP tools exposed by the AlgoVoi MCP server.
 *
 * Each tool is a pure async function — the dispatcher in `index.ts` calls
 * the matching parser from `schemas.ts` first, so every function below
 * receives a validated, typed argument object.
 *
 * Tools are grouped:
 *   1-5   one-shot payments + webhooks (Tier 1)
 *   6-9   MPP / x402 (machine-payable agent flows)
 *   10-11 AP2 (Google Agent Payments Protocol)
 *   12-13 A2A (Agent-to-Agent)
 *   14-21 Tier 2 — Standing-authority recurring payments (subscriptions,
 *         agent-bound spending authorities) — added in MCP v1.2.0.
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
  ConfirmAuthorityInput,
  CreatePaymentLinkInput,
  CreateRecurringAuthorityInput,
  FetchAgentCardInput,
  GenerateAp2MandateInput,
  GenerateMppChallengeInput,
  GenerateX402ChallengeInput,
  GetAuthorityInput,
  ListAuthoritiesInput,
  ManualPullInput,
  PauseAuthorityInput,
  PrepareExtensionPaymentInput,
  ResumeAuthorityInput,
  RevokeAuthorityInput,
  DiscoverResourcesInput,
  GetComplianceAttestationInput,
  ScreenRecipientInput,
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

// ── 14-21. Tier 2 — Standing-Authority Recurring Payments ────────────────────
//
// Eight tools the agent calls to manage subscriptions:
//
//   create_recurring_authority  — open a new standing authority
//   get_authority               — read current state
//   list_authorities            — list this tenant's authorities
//   confirm_authority           — mark active after on-chain landing
//   revoke_authority            — chain-side revocation (customer signs)
//   pause_authority             — off-chain pause
//   resume_authority            — off-chain resume
//   manual_pull                 — tenant-initiated catch-up pull
//
// All write tools (create / confirm / revoke / pause / resume / pull) hit
// the AlgoVoi gateway and return shaped responses for the LLM. The
// `customer_signing_payload` from create_recurring_authority is returned
// verbatim — the agent hands it to a wallet UI.

export async function createRecurringAuthority(
  client: AlgoVoiClient,
  args: CreateRecurringAuthorityInput,
): Promise<unknown> {
  const resp = await client.createRecurringAuthority({
    subscription_id:        args.subscription_id,
    chain:                  args.chain,
    customer_wallet_address: args.customer_wallet_address,
    cap_amount_minor:       args.cap_amount_minor,
    cap_period_seconds:     args.cap_period_seconds,
    per_cycle_amount_minor: args.per_cycle_amount_minor,
    asset:                  args.asset,
    metadata:               args.metadata,
  });
  return {
    authority_id:    resp.authority.id,
    status:          resp.authority.status,
    chain:           resp.authority.chain,
    cap_amount_minor: resp.authority.cap_amount_minor,
    /** Hand this to the customer's wallet UI — chain-specific signing template. */
    customer_signing_payload: resp.customer_signing_payload,
    authorisation_url: resp.authorisation_url,
    /** Next step for the agent: route the customer to wallet signing, then call confirm_authority. */
    next_step: "Pass customer_signing_payload to the customer's wallet (Pera/Defly/MetaMask/Phantom/HashPack/Freighter) for signing. After the on-chain transaction lands, call confirm_authority(authority_id, on_chain_address).",
  };
}

export async function getAuthority(
  client: AlgoVoiClient,
  args: GetAuthorityInput,
): Promise<unknown> {
  return client.getAuthority(args.authority_id);
}

export async function listAuthorities(
  client: AlgoVoiClient,
  args: ListAuthoritiesInput,
): Promise<unknown> {
  const list = await client.listAuthorities({
    subscription_id: args.subscription_id,
    status:          args.status,
    limit:           args.limit,
    offset:          args.offset,
  });
  return { authorities: list, count: list.length };
}

export async function confirmAuthority(
  client: AlgoVoiClient,
  args: ConfirmAuthorityInput,
): Promise<unknown> {
  return client.confirmAuthority(
    args.authority_id,
    args.on_chain_address,
    args.first_cycle_due_at,
  );
}

export async function revokeAuthority(
  client: AlgoVoiClient,
  args: RevokeAuthorityInput,
): Promise<unknown> {
  return client.revokeAuthority(args.authority_id);
}

export async function pauseAuthority(
  client: AlgoVoiClient,
  args: PauseAuthorityInput,
): Promise<unknown> {
  return client.pauseAuthority(args.authority_id);
}

export async function resumeAuthority(
  client: AlgoVoiClient,
  args: ResumeAuthorityInput,
): Promise<unknown> {
  return client.resumeAuthority(args.authority_id, args.next_cycle_due_at);
}

export async function manualPull(
  client: AlgoVoiClient,
  args: ManualPullInput,
): Promise<unknown> {
  return client.manualPull({
    authority_id:    args.authority_id,
    amount_minor:    args.amount_minor,
    idempotency_key: args.idempotency_key,
  });
}

export async function discoverResources(
  client: AlgoVoiClient,
  _args: DiscoverResourcesInput,
): Promise<unknown> {
  const res = await fetch(`${client.apiBase}/discovery/resources`, {
    headers: { Accept: "application/json" },
  });
  if (!res.ok) {
    return { error: "discovery_unavailable", status: res.status };
  }
  return res.json();
}

export async function screenRecipient(
  client: AlgoVoiClient,
  args: ScreenRecipientInput,
): Promise<unknown> {
  const body: Record<string, unknown> = {
    recipient_address: args.recipient_address,
    network:           args.network,
  };
  if (args.amount_microunits !== undefined) body.amount_microunits = args.amount_microunits;
  if (args.asset !== undefined) body.asset = args.asset;
  const res = await fetch(`${client.apiBase}/compliance/screen`, {
    method:  "POST",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body:    JSON.stringify(body),
  });
  if (!res.ok) {
    const detail = await res.text().catch(() => "");
    return { error: "screen_failed", status: res.status, detail: detail.slice(0, 200) };
  }
  return res.json();
}

export async function getComplianceAttestation(
  client: AlgoVoiClient,
  _args: GetComplianceAttestationInput,
): Promise<unknown> {
  const res = await fetch(`${client.apiBase}/compliance/attestation`, {
    headers: { Accept: "application/json" },
  });
  if (!res.ok) {
    return { error: "attestation_unavailable", status: res.status };
  }
  return res.json();
}

// ── Tool schemas (MCP wire — JSON Schema) ─────────────────────────────────────

export const TOOL_SCHEMAS = [
  {
    name: "create_payment_link",
    description:
      "Create a hosted AlgoVoi checkout URL for a given amount and chain. " +
      "Returns {checkout_url, token, chain, amount_microunits} — the customer visits checkout_url to pay in USDC or native tokens (ALGO, VOI, HBAR, XLM). " +
      "Use this when the customer will pay via a hosted checkout page (redirect or iframe). " +
      "For in-page browser-wallet payments (AVM chains only) use prepare_extension_payment instead. " +
      "For server-to-server agent payments use generate_mpp_challenge, generate_x402_challenge, or generate_ap2_mandate instead. " +
      "Authentication: requires ALGOVOI_API_KEY and ALGOVOI_TENANT_ID env vars (set once at server startup — never passed as tool args). " +
      "Errors: throws if amount <= 0, currency is unrecognised, or network is unsupported. " +
      "Rate limits: subject to tenant plan limits; use idempotency_key to avoid duplicate links on retry.",
    inputSchema: {
      type: "object",
      properties: {
        amount:   { type: "number", description: "Payment amount in fiat major units (e.g. 5.00 for $5.00 USD). AlgoVoi converts to on-chain micro-units automatically." },
        currency: { type: "string", description: "ISO 4217 currency code — e.g. USD, GBP, EUR. Determines the fiat amount denominated on the checkout page." },
        label:    { type: "string", description: 'Short human-readable order label shown on the checkout page (e.g. "Order #123" or "1-month subscription").' },
        network:  { type: "string", enum: [...NETWORKS], description: "Preferred blockchain network. The customer may pay in USDC or the chain's native token (ALGO, VOI, HBAR, XLM). Use algorand_mainnet or voi_mainnet for USDC on AVM chains." },
        redirect_url:    { type: "string", description: "HTTPS URL to redirect the customer to after a successful payment. Must start with https://." },
        idempotency_key: { type: "string", description: "16–64 character idempotency token. Duplicate calls with the same key within 24 hours return the cached checkout URL instead of creating a new one." },
      },
      required: ["amount", "currency", "label", "network"],
      additionalProperties: false,
    },
  },
  {
    name: "verify_payment",
    description:
      "Verify that a hosted checkout payment has settled on-chain. " +
      "Returns {paid: bool, status: 'verified'|'unverified'|'pending'|'expired'}. " +
      "If tx_id is supplied, verifies that specific on-chain transaction against the token; otherwise polls hosted-checkout status. " +
      "Use this after create_payment_link (for hosted checkout) or after prepare_extension_payment + tx_id (for browser-wallet flows). " +
      "For MPP 402-challenge flows use verify_mpp_receipt; for x402 use verify_x402_proof; for AP2 use verify_ap2_payment. " +
      "Authentication: requires ALGOVOI_API_KEY env var. " +
      "Errors: returns {paid: false, error: '...'} if the token is unknown or the transaction does not match.",
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
      "Prepare an in-page wallet-extension payment for Algorand or VOI chains. " +
      "Returns {token, chain, amount_microunits, recipient, asset_id} — pass these to the browser wallet (e.g. Pera, Defly) to sign and submit. " +
      "After the user signs and the transaction confirms, call verify_payment with the returned token and the on-chain tx_id to confirm settlement. " +
      "Use this for browser-based dApp flows where the user's wallet is in the browser. " +
      "For hosted redirect checkout use create_payment_link. " +
      "For server-to-server API flows use generate_mpp_challenge or generate_x402_challenge. " +
      "Authentication: requires ALGOVOI_API_KEY env var. " +
      "Errors: throws if network is not an AVM chain (Algorand or VOI only) or if amount <= 0.",
    inputSchema: {
      type: "object",
      properties: {
        amount:   { type: "number",  description: "Payment amount in fiat major units (e.g. 5.00 for $5.00 USD). Converted to on-chain micro-units automatically." },
        currency: { type: "string",  description: "ISO 4217 currency code — e.g. USD, GBP, EUR." },
        label:    { type: "string",  description: "Short human-readable label for the payment (e.g. 'Order #42'). Shown in the wallet signing dialog." },
        network:  { type: "string",  enum: ["algorand_mainnet", "voi_mainnet", "algorand_mainnet_algo", "voi_mainnet_voi", "algorand_testnet", "voi_testnet", "algorand_testnet_algo", "voi_testnet_voi"], description: "AVM network to pay on. Use algorand_mainnet or voi_mainnet for USDC; use algorand_mainnet_algo / voi_mainnet_voi for native tokens." },
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
      "Verify an MPP (IETF draft-ryan-httpauth-payment) payment receipt submitted by a paying agent. " +
      "Returns {verified: true, access_token: '...'} on success; {verified: false, error: 'amount_mismatch'|'recipient_mismatch'|'tx_not_found'|'expired'} on failure. " +
      "Call this after generate_mpp_challenge, once the paying agent sends its Payment header containing the on-chain tx_id. " +
      "The access_token in the response can be passed back to the agent as proof of payment for protected resources. " +
      "For x402 proof-of-payment flows use verify_x402_proof instead. " +
      "For AP2 mandate flows use verify_ap2_payment instead. " +
      "Authentication: requires ALGOVOI_API_KEY env var. " +
      "Errors: returns verified=false (never throws) so payment failures can be communicated back to the paying agent without a server error.",
    inputSchema: {
      type: "object",
      properties: {
        resource_id: { type: "string", description: "Resource identifier from the original generate_mpp_challenge call." },
        tx_id:       { type: "string", description: "On-chain transaction ID submitted by the paying agent in the Payment header." },
        network:     { type: "string", enum: [...NETWORKS], description: "Blockchain network the payment was submitted on — must match the network in the original challenge." },
      },
      required: ["resource_id", "tx_id", "network"],
      additionalProperties: false,
    },
  },
  {
    name: "verify_x402_proof",
    description:
      "Verify a base64-encoded x402 (spec v1) payment proof submitted by a client in the X-Payment header. " +
      "Returns {verified: true} if the proof decodes to a confirmed on-chain transfer matching the tenant's payout address and amount. " +
      "Returns {verified: false, error: 'invalid_proof'|'amount_mismatch'|'recipient_mismatch'|'tx_not_found'} on failure. " +
      "Call this after generate_x402_challenge, once the client re-submits the request with X-Payment: <base64-proof>. " +
      "For MPP payment-header flows use verify_mpp_receipt instead. " +
      "For AP2 mandate flows use verify_ap2_payment instead. " +
      "Authentication: requires ALGOVOI_API_KEY env var. " +
      "Errors: always returns {verified: bool} — never throws on proof format errors.",
    inputSchema: {
      type: "object",
      properties: {
        proof:   { type: "string", description: "Base64-encoded payment payload extracted from the X-Payment request header." },
        network: { type: "string", enum: [...NETWORKS], description: "Blockchain network the payment was submitted on — must match the network in the original x402 challenge." },
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
      "Verify an AP2 v0.1 agent-to-agent payment against an existing mandate. " +
      "Returns {verified: true} if the on-chain transaction satisfies the mandate's declared amount and recipient. " +
      "Returns {verified: false, error: 'mandate_not_found'|'mandate_expired'|'amount_mismatch'|'tx_not_found'} on failure. " +
      "Call this after generate_ap2_mandate once the paying agent submits its on-chain tx_id. " +
      "For MPP payment-header flows use verify_mpp_receipt instead. " +
      "For x402 proof-of-payment flows use verify_x402_proof instead. " +
      "Authentication: requires ALGOVOI_API_KEY env var. " +
      "Errors: always returns {verified: bool} — never throws on unknown mandate IDs.",
    inputSchema: {
      type: "object",
      properties: {
        mandate_id: { type: "string", description: "mandate_id returned by generate_ap2_mandate." },
        tx_id:      { type: "string", description: "On-chain transaction ID submitted by the paying agent." },
        network:    { type: "string", enum: [...NETWORKS], description: "Blockchain network the payment was submitted on — must match the network in the original AP2 mandate." },
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
  // ── Tier 2 — Standing-Authority Recurring Payments ────────────────────────
  {
    name: "create_recurring_authority",
    description:
      "Create a Tier 2 standing authority for an existing AlgoVoi subscription. " +
      "Tier 2 = 'customer signs ONCE, AlgoVoi auto-pulls per cycle' — the subscription / " +
      "agent-bound spending pattern (vs Tier 1's pay-on-every-invoice). " +
      "Returns {authority_id, status, customer_signing_payload, next_step}. " +
      "The customer_signing_payload is a chain-specific template (Algorand " +
      "SpendingCapVault 6-action group, EVM ERC-20 approve, Solana SPL Approve, " +
      "Hedera HTS allowance, or Stellar Soroban auth_entry) — hand it to the " +
      "customer's wallet (Pera/Defly/MetaMask/Phantom/HashPack/Freighter) for signing. " +
      "After the on-chain transaction lands, call confirm_authority to mark the " +
      "authority active. AlgoVoi's cycle reaper then auto-pulls per cap_period_seconds. " +
      "Stellar uses 7-decimal precision for USDC; every other chain uses 6 — pass " +
      "cap_amount_minor in chain-native atomic units. " +
      "Authentication: requires ALGOVOI_API_KEY and ALGOVOI_TENANT_ID env vars. " +
      "Errors: throws if chain is unsupported, period < 86400, or per_cycle_amount_minor > cap_amount_minor.",
    inputSchema: {
      type: "object",
      properties: {
        subscription_id: {
          type:        "string",
          description: "UUID of the Tier 1 subscription this authority is bound to. Create one via the dashboard or POST /v1/subscriptions first.",
        },
        chain: {
          type:        "string",
          enum: [
            "algorand_mainnet", "algorand_testnet",
            "voi_mainnet",      "voi_testnet",
            "base_mainnet",     "base_sepolia",
            "tempo_mainnet",    "tempo_testnet",
            "solana_mainnet",   "solana_devnet",
            "hedera_mainnet",   "hedera_testnet",
            "stellar_mainnet",  "stellar_testnet",
          ],
          description: "Blockchain network to authorise on. Each chain uses its native primitive (SpendingCapVault, ERC-20 approve, SPL Approve, HTS allowance, Soroban auth_entry).",
        },
        customer_wallet_address: {
          type:        "string",
          description: "Customer's chain-native address (Algorand 58-char base32, EVM 0x-prefixed hex, Solana base58, Hedera 0.0.X, Stellar G-address).",
        },
        cap_amount_minor: {
          type:        "integer",
          description: "Total spend cap over cap_period_seconds, in chain-native atomic units. e.g. for 12 × $10 USDC on Algorand: 120_000_000 (6 decimals). For Stellar: 1_200_000_000 (7 decimals).",
        },
        cap_period_seconds: {
          type:        "integer",
          description: "Cap window length in seconds. Must be >= 86400 (1 day). Typical: 365 * 86400 = 31_536_000 for annual.",
        },
        per_cycle_amount_minor: {
          type:        "integer",
          description: "Per-pull cap, in atomic units. Each cycle pulls at most this much. Must be <= cap_amount_minor.",
        },
        asset: {
          type:        "string",
          description: "Asset symbol — defaults to USDC. Native coins (VOI/HBAR/XLM/ETH/SOL) supported per chain.",
        },
        metadata: {
          type:        "object",
          description: "Free-form tenant metadata, forwarded on every webhook event.",
          additionalProperties: true,
        },
      },
      required:             ["subscription_id", "chain", "customer_wallet_address", "cap_amount_minor", "cap_period_seconds", "per_cycle_amount_minor"],
      additionalProperties: false,
    },
  },
  {
    name: "get_authority",
    description:
      "Fetch the current state of a Tier 2 recurring authority by id. " +
      "Returns {id, status, on_chain_address, cap_remaining_minor, cycles_pulled, " +
      "cycles_failed, last_error, ...}. status transitions: pending → active (after " +
      "confirm_authority) → revoking → revoked, or paused/resumed mid-life, or " +
      "expired when the cap_amount or auth lifetime is exhausted.",
    inputSchema: {
      type: "object",
      properties: {
        authority_id: { type: "string", description: "UUID returned by create_recurring_authority." },
      },
      required:             ["authority_id"],
      additionalProperties: false,
    },
  },
  {
    name: "list_authorities",
    description:
      "List Tier 2 recurring authorities for this tenant. Returns {authorities: [...], count}. " +
      "Optionally filter by subscription_id or status (pending/active/paused/revoking/revoked/expired). " +
      "Default limit 50, max 200.",
    inputSchema: {
      type: "object",
      properties: {
        subscription_id: { type: "string", description: "Filter to authorities for one subscription." },
        status:          { type: "string", description: "Filter by status: pending / active / paused / revoking / revoked / expired." },
        limit:           { type: "integer", description: "Max results (1-200, default 50)." },
        offset:          { type: "integer", description: "Pagination offset (default 0)." },
      },
      additionalProperties: false,
    },
  },
  {
    name: "confirm_authority",
    description:
      "Mark a pending Tier 2 authority active after on-chain landing. Most flows " +
      "use AlgoVoi's hosted widget which calls this automatically via webhook — " +
      "surfaced here for self-hosted wallet UIs. on_chain_address format depends on " +
      "the chain: Algorand/VOI 'app:<application_id>', EVM '0x<tx_hash>', Solana " +
      "'<base58 tx signature>', Hedera '<account_id>@<seconds>.<nanos>', Stellar " +
      "'<64-char hex tx hash>'.",
    inputSchema: {
      type: "object",
      properties: {
        authority_id:     { type: "string", description: "UUID returned by create_recurring_authority." },
        on_chain_address: { type: "string", description: "Chain-native handle of the landed authorisation transaction." },
        first_cycle_due_at: { type: "string", description: "Optional ISO8601 first-cycle due-at; gateway computes one if omitted." },
      },
      required:             ["authority_id", "on_chain_address"],
      additionalProperties: false,
    },
  },
  {
    name: "revoke_authority",
    description:
      "Revoke an active Tier 2 authority. Gateway constructs the chain-specific " +
      "revocation transaction (Algorand vault owner_withdraw + remove_agent, EVM " +
      "approve(0), Solana SPL revoke, Hedera approve(amount=0), Stellar Soroban " +
      "auth-entry expiry); the customer's wallet signs it. Authority transitions to " +
      "'revoking' until on-chain landing, then 'revoked'.",
    inputSchema: {
      type: "object",
      properties: {
        authority_id: { type: "string", description: "UUID of the authority to revoke." },
      },
      required:             ["authority_id"],
      additionalProperties: false,
    },
  },
  {
    name: "pause_authority",
    description:
      "Pause an active Tier 2 authority — no on-chain action. Stops cycle pulls until " +
      "resume_authority is called. Useful for billing holds, manual review, or " +
      "customer-initiated 'pause my subscription' flows.",
    inputSchema: {
      type: "object",
      properties: {
        authority_id: { type: "string", description: "UUID of the authority to pause." },
      },
      required:             ["authority_id"],
      additionalProperties: false,
    },
  },
  {
    name: "resume_authority",
    description:
      "Resume a paused Tier 2 authority. Optionally specify next_cycle_due_at " +
      "(ISO8601) to delay the first post-resume pull; otherwise pulls resume " +
      "immediately on the existing schedule.",
    inputSchema: {
      type: "object",
      properties: {
        authority_id:      { type: "string", description: "UUID of the authority to resume." },
        next_cycle_due_at: { type: "string", description: "Optional ISO8601 timestamp for the next cycle pull." },
      },
      required:             ["authority_id"],
      additionalProperties: false,
    },
  },
  {
    name: "manual_pull",
    description:
      "Manually trigger a one-off Tier 2 pull (catch-up after dunning, prorated " +
      "mid-cycle billing). Most pulls fire automatically via the cycle reaper — " +
      "only use this for proration or catch-up flows. amount_minor must be <= " +
      "the authority's per_cycle_amount_minor. Returns the updated authority row " +
      "with cycles_pulled incremented on success.",
    inputSchema: {
      type: "object",
      properties: {
        authority_id:    { type: "string",  description: "UUID of an active authority." },
        amount_minor:    { type: "integer", description: "Pull amount in atomic units. Must be <= per_cycle_amount_minor." },
        idempotency_key: { type: "string",  description: "Optional client-supplied key for retry safety (max 128 chars)." },
      },
      required:             ["authority_id", "amount_minor"],
      additionalProperties: false,
    },
  },
  // ── Discovery & Compliance ────────────────────────────────────────────────
  {
    name: "discover_resources",
    description:
      "Fetch the public AlgoVoi Bazaar catalog — all x402 and MPP payable resources " +
      "listed by active tenants, including the agent-trust-bench endpoints. Each entry " +
      "includes resource_id, price, accepted networks, and payment protocol details. " +
      "Mirrors `npx agentcash try https://api.algovoi.co.uk` — no API key required.",
    inputSchema: {
      type:                 "object",
      properties:           {},
      additionalProperties: false,
    },
  },
  {
    name: "screen_recipient",
    description:
      "Pre-payment compliance screen: checks a recipient wallet address against " +
      "OFSI / OFAC SDN / EU Consolidated sanctions lists plus AlgoVoi KYB status. " +
      "Returns verdict ('allow' | 'block' | 'flag'), sanctions_clear, risk_tier, and " +
      "reasons. Operates under SAMLA 2018 s.20 — reasons are intentionally generic; " +
      "specific list matches are never disclosed. No API key required; rate-limited " +
      "60/min. Call this before submitting any payment to an unknown counterparty.",
    inputSchema: {
      type: "object",
      properties: {
        recipient_address: {
          type:        "string",
          description: "On-chain wallet address of the payment recipient (4–128 chars).",
        },
        network: {
          type:        "string",
          description: "Network key (e.g. 'algorand_mainnet', 'base_mainnet', 'solana_mainnet').",
        },
        amount_microunits: {
          type:        "integer",
          description: "Optional: payment amount in atomic units — used for risk-tier calculation.",
        },
        asset: {
          type:        "string",
          description: "Optional: asset identifier (e.g. '31566704' for Algorand USDC).",
        },
      },
      required:             ["recipient_address", "network"],
      additionalProperties: false,
    },
  },
  {
    name: "get_compliance_attestation",
    description:
      "Fetch the operator's public compliance posture: active regulatory frameworks " +
      "(UK MLRs 2017, SAMLA 2018 s.20, UK GDPR), live sanctions sources (OFSI, OFAC, " +
      "EU), KYB gate status, audit chain heads (SHA-256 hash-chained ledger), and " +
      "off-VM Object Lock shipment status. No API key required. Use to verify the " +
      "platform's compliance state before processing high-value or regulated payments.",
    inputSchema: {
      type:                 "object",
      properties:           {},
      additionalProperties: false,
    },
  },
] as const;
