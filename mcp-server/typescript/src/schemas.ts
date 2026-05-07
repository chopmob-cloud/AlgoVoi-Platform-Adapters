/**
 * Strict runtime validators for all 8 tool inputs.
 *
 * Mirrors §4.1 of ALGOVOI_MCP.md: every handler re-validates its arguments
 * before business logic runs, with `extra='forbid'` semantics — unknown
 * keys are rejected.  We implement this by hand (no Zod dep) because:
 *
 *   - the MCP wire already advertises `additionalProperties: false`
 *   - hand-written validators give precise error messages
 *   - keeps the package dep surface minimal (only @modelcontextprotocol/sdk)
 *
 * Each `parseX()` function throws `ValidationError` on the first violation
 * and returns the typed object on success.  The dispatcher in `index.ts`
 * catches `ValidationError` and reports it as a rejected tool call.
 */

import { NETWORKS, type Network } from "./networks.js";

export class ValidationError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "ValidationError";
  }
}

const EXT_NETWORKS = new Set<string>([
  "algorand_mainnet", "voi_mainnet", "algorand_mainnet_algo", "voi_mainnet_voi",
  "algorand_testnet", "voi_testnet", "algorand_testnet_algo", "voi_testnet_voi",
]);

// ── shared helpers ────────────────────────────────────────────────────────────

function assertKeys(
  obj: Record<string, unknown>,
  allowed: readonly string[]
): void {
  for (const k of Object.keys(obj)) {
    if (!allowed.includes(k)) {
      throw new ValidationError(`unexpected field: "${k}"`);
    }
  }
}

function requireString(
  obj: Record<string, unknown>,
  key: string,
  opts: { min?: number; max?: number; optional?: boolean } = {}
): string | undefined {
  const v = obj[key];
  if (v === undefined || v === null) {
    if (opts.optional) return undefined;
    throw new ValidationError(`missing required field: "${key}"`);
  }
  if (typeof v !== "string") {
    throw new ValidationError(`"${key}" must be a string`);
  }
  const min = opts.min ?? 0;
  const max = opts.max ?? Infinity;
  if (v.length < min) throw new ValidationError(`"${key}" must be ≥ ${min} chars`);
  if (v.length > max) throw new ValidationError(`"${key}" must be ≤ ${max} chars`);
  return v;
}

function requireNumber(
  obj: Record<string, unknown>,
  key: string,
  opts: {
    gt?: number;
    ge?: number;
    le?: number;
    integer?: boolean;
    optional?: boolean;
  } = {}
): number | undefined {
  const v = obj[key];
  if (v === undefined || v === null) {
    if (opts.optional) return undefined;
    throw new ValidationError(`missing required field: "${key}"`);
  }
  if (typeof v !== "number" || !Number.isFinite(v)) {
    throw new ValidationError(`"${key}" must be a finite number`);
  }
  if (opts.integer && !Number.isInteger(v)) {
    throw new ValidationError(`"${key}" must be an integer`);
  }
  if (opts.gt !== undefined && v <= opts.gt) {
    throw new ValidationError(`"${key}" must be > ${opts.gt}`);
  }
  if (opts.ge !== undefined && v < opts.ge) {
    throw new ValidationError(`"${key}" must be ≥ ${opts.ge}`);
  }
  if (opts.le !== undefined && v > opts.le) {
    throw new ValidationError(`"${key}" must be ≤ ${opts.le}`);
  }
  return v;
}

/** Convenience wrapper around requireNumber that asserts integer. */
function requireInt(
  obj: Record<string, unknown>,
  key: string,
  opts: { gt?: number; ge?: number; le?: number; optional?: boolean } = {},
): number | undefined {
  return requireNumber(obj, key, { ...opts, integer: true });
}

function requireEnum<T extends string>(
  obj: Record<string, unknown>,
  key: string,
  allowed: readonly T[],
  opts: { optional?: boolean } = {}
): T | undefined {
  const v = obj[key];
  if (v === undefined || v === null) {
    if (opts.optional) return undefined;
    throw new ValidationError(`missing required field: "${key}"`);
  }
  if (typeof v !== "string" || !allowed.includes(v as T)) {
    throw new ValidationError(
      `"${key}" must be one of: ${allowed.join(", ")} — got ${JSON.stringify(v)}`
    );
  }
  return v as T;
}

function requireStringArray<T extends string>(
  obj: Record<string, unknown>,
  key: string,
  allowed: readonly T[],
  opts: { min?: number; max?: number; optional?: boolean } = {}
): T[] | undefined {
  const v = obj[key];
  if (v === undefined || v === null) {
    if (opts.optional) return undefined;
    throw new ValidationError(`missing required field: "${key}"`);
  }
  if (!Array.isArray(v)) {
    throw new ValidationError(`"${key}" must be an array`);
  }
  if (opts.min !== undefined && v.length < opts.min) {
    throw new ValidationError(`"${key}" must have at least ${opts.min} items`);
  }
  if (opts.max !== undefined && v.length > opts.max) {
    throw new ValidationError(`"${key}" must have at most ${opts.max} items`);
  }
  for (const item of v) {
    if (typeof item !== "string" || !allowed.includes(item as T)) {
      throw new ValidationError(
        `"${key}" contains invalid value ${JSON.stringify(item)} ` +
          `— must be one of: ${allowed.join(", ")}`
      );
    }
  }
  return v as T[];
}

export interface GenerateX402ChallengeInput {
  resource: string;
  amount_microunits: number;
  network?: Network;
  expires_in_seconds?: number;
  description?: string;
}

export interface GenerateAp2MandateInput {
  resource_id: string;
  amount_microunits: number;
  network?: Network;
  expires_in_seconds?: number;
  description?: string;
}

export interface VerifyAp2PaymentInput {
  mandate_id: string;
  tx_id: string;
  network: Network;
}

// ── parsed shapes ─────────────────────────────────────────────────────────────

export interface CreatePaymentLinkInput {
  amount: number;
  currency: string;
  label: string;
  network: Network;
  redirect_url?: string;
  idempotency_key?: string;
}

export interface VerifyPaymentInput {
  token: string;
  tx_id?: string;
}

export interface PrepareExtensionPaymentInput {
  amount: number;
  currency: string;
  label: string;
  network: "algorand_mainnet" | "voi_mainnet" | "algorand_mainnet_algo" | "voi_mainnet_voi"
         | "algorand_testnet" | "voi_testnet" | "algorand_testnet_algo" | "voi_testnet_voi";
}

export interface VerifyWebhookInput {
  raw_body: string;
  signature: string;
}

export interface GenerateMppChallengeInput {
  resource_id: string;
  amount_microunits: number;
  networks?: Network[];
  expires_in_seconds?: number;
}

export interface VerifyMppReceiptInput {
  resource_id: string;
  tx_id: string;
  network: Network;
}

export interface VerifyX402ProofInput {
  proof: string;
  network: Network;
}

// ── parsers ───────────────────────────────────────────────────────────────────

const MAX_WEBHOOK_BODY = 64 * 1024;

export function parseCreatePaymentLink(raw: unknown): CreatePaymentLinkInput {
  const obj = expectObject(raw);
  assertKeys(obj, [
    "amount",
    "currency",
    "label",
    "network",
    "redirect_url",
    "idempotency_key",
  ]);
  return {
    amount:   requireNumber(obj, "amount",  { gt: 0, le: 10_000_000 })!,
    currency: requireString(obj, "currency", { min: 3, max: 3 })!,
    label:    requireString(obj, "label",    { min: 1, max: 200 })!,
    network:  requireEnum(obj, "network",    NETWORKS)!,
    redirect_url:    requireString(obj, "redirect_url",    { max: 2048, optional: true }),
    idempotency_key: requireString(obj, "idempotency_key", { min: 16, max: 64, optional: true }),
  };
}

export function parseVerifyPayment(raw: unknown): VerifyPaymentInput {
  const obj = expectObject(raw);
  assertKeys(obj, ["token", "tx_id"]);
  return {
    token: requireString(obj, "token", { min: 1, max: 200 })!,
    tx_id: requireString(obj, "tx_id", { min: 1, max: 200, optional: true }),
  };
}

export function parsePrepareExtensionPayment(
  raw: unknown
): PrepareExtensionPaymentInput {
  const obj = expectObject(raw);
  assertKeys(obj, ["amount", "currency", "label", "network"]);
  const net = requireEnum(obj, "network", [
    "algorand_mainnet", "voi_mainnet", "algorand_mainnet_algo", "voi_mainnet_voi",
    "algorand_testnet", "voi_testnet", "algorand_testnet_algo", "voi_testnet_voi",
  ] as const)!;
  return {
    amount:   requireNumber(obj, "amount",  { gt: 0, le: 10_000_000 })!,
    currency: requireString(obj, "currency", { min: 3, max: 3 })!,
    label:    requireString(obj, "label",    { min: 1, max: 200 })!,
    network:  net,
  };
}

export function parseVerifyWebhook(raw: unknown): VerifyWebhookInput {
  const obj = expectObject(raw);
  assertKeys(obj, ["raw_body", "signature"]);
  return {
    raw_body:  requireString(obj, "raw_body",  { max: MAX_WEBHOOK_BODY })!,
    signature: requireString(obj, "signature", { min: 1, max: 512 })!,
  };
}

export function parseListNetworks(raw: unknown): Record<string, never> {
  const obj = expectObject(raw);
  assertKeys(obj, []);
  return {};
}

export function parseGenerateMppChallenge(
  raw: unknown
): GenerateMppChallengeInput {
  const obj = expectObject(raw);
  assertKeys(obj, ["resource_id", "amount_microunits", "networks", "expires_in_seconds"]);
  return {
    resource_id:       requireString(obj, "resource_id", { min: 1, max: 200 })!,
    amount_microunits: requireNumber(obj, "amount_microunits", { gt: 0, le: 1e15, integer: true })!,
    networks:          requireStringArray(obj, "networks", NETWORKS, { min: 1, max: 4, optional: true }),
    expires_in_seconds: requireNumber(obj, "expires_in_seconds", { gt: 0, le: 86_400, integer: true, optional: true }),
  };
}

export function parseVerifyMppReceipt(raw: unknown): VerifyMppReceiptInput {
  const obj = expectObject(raw);
  assertKeys(obj, ["resource_id", "tx_id", "network"]);
  return {
    resource_id: requireString(obj, "resource_id", { min: 1, max: 200 })!,
    tx_id:       requireString(obj, "tx_id",       { min: 1, max: 200 })!,
    network:     requireEnum(obj, "network",       NETWORKS)!,
  };
}

export function parseVerifyX402Proof(raw: unknown): VerifyX402ProofInput {
  const obj = expectObject(raw);
  assertKeys(obj, ["proof", "network"]);
  return {
    proof:   requireString(obj, "proof",   { min: 1, max: MAX_WEBHOOK_BODY })!,
    network: requireEnum(obj,   "network", NETWORKS)!,
  };
}

export function parseGenerateX402Challenge(raw: unknown): GenerateX402ChallengeInput {
  const obj = expectObject(raw);
  assertKeys(obj, ["resource", "amount_microunits", "network", "expires_in_seconds", "description"]);
  return {
    resource:           requireString(obj, "resource",          { min: 1, max: 2048 })!,
    amount_microunits:  requireNumber(obj, "amount_microunits", { gt: 0, le: 1e15, integer: true })!,
    network:            requireEnum(obj,   "network",           NETWORKS, { optional: true }),
    expires_in_seconds: requireNumber(obj, "expires_in_seconds", { gt: 0, le: 86_400, integer: true, optional: true }),
    description:        requireString(obj, "description",       { max: 200, optional: true }),
  };
}

export function parseGenerateAp2Mandate(raw: unknown): GenerateAp2MandateInput {
  const obj = expectObject(raw);
  assertKeys(obj, ["resource_id", "amount_microunits", "network", "expires_in_seconds", "description"]);
  return {
    resource_id:        requireString(obj, "resource_id",       { min: 1, max: 200 })!,
    amount_microunits:  requireNumber(obj, "amount_microunits", { gt: 0, le: 1e15, integer: true })!,
    network:            requireEnum(obj,   "network",           NETWORKS, { optional: true }),
    expires_in_seconds: requireNumber(obj, "expires_in_seconds", { gt: 0, le: 86_400, integer: true, optional: true }),
    description:        requireString(obj, "description",       { max: 200, optional: true }),
  };
}

export function parseVerifyAp2Payment(raw: unknown): VerifyAp2PaymentInput {
  const obj = expectObject(raw);
  assertKeys(obj, ["mandate_id", "tx_id", "network"]);
  return {
    mandate_id: requireString(obj, "mandate_id", { min: 1, max: 64 })!,
    tx_id:      requireString(obj, "tx_id",      { min: 1, max: 200 })!,
    network:    requireEnum(obj,   "network",    NETWORKS)!,
  };
}

function expectObject(raw: unknown): Record<string, unknown> {
  if (raw === null || typeof raw !== "object" || Array.isArray(raw)) {
    throw new ValidationError("arguments must be an object");
  }
  return raw as Record<string, unknown>;
}

// ── 12. fetch_agent_card ──────────────────────────────────────────────────────

export interface FetchAgentCardInput {
  agent_url: string;
}

export function parseFetchAgentCard(raw: unknown): FetchAgentCardInput {
  const obj = expectObject(raw);
  assertKeys(obj, ["agent_url"]);
  const url = requireString(obj, "agent_url", { min: 10, max: 2048 })!;
  if (!url.startsWith("https://")) {
    throw new ValidationError('"agent_url" must start with https://');
  }
  return { agent_url: url };
}

// ── 13. send_a2a_message ──────────────────────────────────────────────────────

export interface SendA2aMessageInput {
  agent_url: string;
  text: string;
  payment_proof?: string;
  message_id?: string;
}

export function parseSendA2aMessage(raw: unknown): SendA2aMessageInput {
  const obj = expectObject(raw);
  assertKeys(obj, ["agent_url", "text", "payment_proof", "message_id"]);
  const url = requireString(obj, "agent_url", { min: 10, max: 2048 })!;
  if (!url.startsWith("https://")) {
    throw new ValidationError('"agent_url" must start with https://');
  }
  return {
    agent_url:     url,
    text:          requireString(obj, "text",          { min: 1, max: 4096 })!,
    payment_proof: requireString(obj, "payment_proof", { min: 1, max: 4096, optional: true }),
    message_id:    requireString(obj, "message_id",    { min: 1, max: 64,   optional: true }),
  };
}

// ── Tier 2 — Standing-Authority Recurring Payments ──────────────────────────

const RECURRING_NETWORKS = [
  "algorand_mainnet", "algorand_testnet",
  "voi_mainnet", "voi_testnet",
  "base_mainnet", "base_sepolia",
  "tempo_mainnet", "tempo_testnet",
  "solana_mainnet", "solana_devnet",
  "hedera_mainnet", "hedera_testnet",
  "stellar_mainnet", "stellar_testnet",
] as const;

export type RecurringNetwork = typeof RECURRING_NETWORKS[number];

export interface CreateRecurringAuthorityInput {
  subscription_id: string;
  chain: RecurringNetwork;
  customer_wallet_address: string;
  cap_amount_minor: number;
  cap_period_seconds: number;
  per_cycle_amount_minor: number;
  asset?: string;
  metadata?: Record<string, unknown>;
}

export interface GetAuthorityInput {
  authority_id: string;
}

export interface ListAuthoritiesInput {
  subscription_id?: string;
  status?: string;
  limit?: number;
  offset?: number;
}

export interface ConfirmAuthorityInput {
  authority_id: string;
  on_chain_address: string;
  first_cycle_due_at?: string;
}

export interface RevokeAuthorityInput {
  authority_id: string;
}

export interface PauseAuthorityInput {
  authority_id: string;
}

export interface ResumeAuthorityInput {
  authority_id: string;
  next_cycle_due_at?: string;
}

export interface ManualPullInput {
  authority_id: string;
  amount_minor: number;
  idempotency_key?: string;
}

export function parseCreateRecurringAuthority(raw: unknown): CreateRecurringAuthorityInput {
  const obj = expectObject(raw);
  assertKeys(obj, [
    "subscription_id",
    "chain",
    "customer_wallet_address",
    "cap_amount_minor",
    "cap_period_seconds",
    "per_cycle_amount_minor",
    "asset",
    "metadata",
  ]);
  const out: CreateRecurringAuthorityInput = {
    subscription_id:        requireString(obj, "subscription_id",        { min: 1, max: 36 })!,
    chain:                  requireEnum(obj, "chain",                    RECURRING_NETWORKS) as RecurringNetwork,
    customer_wallet_address: requireString(obj, "customer_wallet_address", { min: 1, max: 200 })!,
    cap_amount_minor:       requireInt(obj, "cap_amount_minor",          { gt: 0 })!,
    cap_period_seconds:     requireInt(obj, "cap_period_seconds",        { ge: 86400 })!,
    per_cycle_amount_minor: requireInt(obj, "per_cycle_amount_minor",    { gt: 0 })!,
  };
  if (out.per_cycle_amount_minor > out.cap_amount_minor) {
    throw new ValidationError(
      '"per_cycle_amount_minor" cannot exceed "cap_amount_minor"',
    );
  }
  const asset = requireString(obj, "asset", { min: 1, max: 16, optional: true });
  if (asset) out.asset = asset.toUpperCase();
  if (obj.metadata !== undefined) {
    if (obj.metadata === null || typeof obj.metadata !== "object" || Array.isArray(obj.metadata)) {
      throw new ValidationError('"metadata" must be an object');
    }
    out.metadata = obj.metadata as Record<string, unknown>;
  }
  return out;
}

export function parseGetAuthority(raw: unknown): GetAuthorityInput {
  const obj = expectObject(raw);
  assertKeys(obj, ["authority_id"]);
  return { authority_id: requireString(obj, "authority_id", { min: 1, max: 36 })! };
}

export function parseListAuthorities(raw: unknown): ListAuthoritiesInput {
  const obj = expectObject(raw);
  assertKeys(obj, ["subscription_id", "status", "limit", "offset"]);
  const out: ListAuthoritiesInput = {};
  const sid = requireString(obj, "subscription_id", { min: 1, max: 36, optional: true });
  if (sid) out.subscription_id = sid;
  const status = requireString(obj, "status", { min: 1, max: 32, optional: true });
  if (status !== undefined) {
    if (!/^[A-Za-z0-9_]+$/.test(status)) {
      throw new ValidationError('"status" must be alphanumeric / underscore');
    }
    out.status = status;
  }
  const limit = requireInt(obj, "limit", { ge: 1, le: 200, optional: true });
  if (limit !== undefined) out.limit = limit;
  const offset = requireInt(obj, "offset", { ge: 0, optional: true });
  if (offset !== undefined) out.offset = offset;
  return out;
}

export function parseConfirmAuthority(raw: unknown): ConfirmAuthorityInput {
  const obj = expectObject(raw);
  assertKeys(obj, ["authority_id", "on_chain_address", "first_cycle_due_at"]);
  const out: ConfirmAuthorityInput = {
    authority_id:    requireString(obj, "authority_id",     { min: 1, max: 36 })!,
    on_chain_address: requireString(obj, "on_chain_address", { min: 1, max: 200 })!,
  };
  const due = requireString(obj, "first_cycle_due_at", { min: 1, max: 64, optional: true });
  if (due) out.first_cycle_due_at = due;
  return out;
}

export function parseRevokeAuthority(raw: unknown): RevokeAuthorityInput {
  const obj = expectObject(raw);
  assertKeys(obj, ["authority_id"]);
  return { authority_id: requireString(obj, "authority_id", { min: 1, max: 36 })! };
}

export function parsePauseAuthority(raw: unknown): PauseAuthorityInput {
  const obj = expectObject(raw);
  assertKeys(obj, ["authority_id"]);
  return { authority_id: requireString(obj, "authority_id", { min: 1, max: 36 })! };
}

export function parseResumeAuthority(raw: unknown): ResumeAuthorityInput {
  const obj = expectObject(raw);
  assertKeys(obj, ["authority_id", "next_cycle_due_at"]);
  const out: ResumeAuthorityInput = {
    authority_id: requireString(obj, "authority_id", { min: 1, max: 36 })!,
  };
  const due = requireString(obj, "next_cycle_due_at", { min: 1, max: 64, optional: true });
  if (due) out.next_cycle_due_at = due;
  return out;
}

export function parseManualPull(raw: unknown): ManualPullInput {
  const obj = expectObject(raw);
  assertKeys(obj, ["authority_id", "amount_minor", "idempotency_key"]);
  const out: ManualPullInput = {
    authority_id: requireString(obj, "authority_id", { min: 1, max: 36 })!,
    amount_minor: requireInt(obj, "amount_minor",     { gt: 0 })!,
  };
  const idem = requireString(obj, "idempotency_key", { min: 1, max: 128, optional: true });
  if (idem) out.idempotency_key = idem;
  return out;
}

export const PARSERS = {
  create_payment_link:       parseCreatePaymentLink,
  verify_payment:            parseVerifyPayment,
  prepare_extension_payment: parsePrepareExtensionPayment,
  verify_webhook:            parseVerifyWebhook,
  list_networks:             parseListNetworks,
  generate_mpp_challenge:    parseGenerateMppChallenge,
  verify_mpp_receipt:        parseVerifyMppReceipt,
  verify_x402_proof:         parseVerifyX402Proof,
  generate_x402_challenge:   parseGenerateX402Challenge,
  generate_ap2_mandate:      parseGenerateAp2Mandate,
  verify_ap2_payment:        parseVerifyAp2Payment,
  fetch_agent_card:          parseFetchAgentCard,
  send_a2a_message:          parseSendA2aMessage,
  // Tier 2 — Standing-Authority Recurring Payments
  create_recurring_authority: parseCreateRecurringAuthority,
  get_authority:              parseGetAuthority,
  list_authorities:           parseListAuthorities,
  confirm_authority:          parseConfirmAuthority,
  revoke_authority:           parseRevokeAuthority,
  pause_authority:            parsePauseAuthority,
  resume_authority:           parseResumeAuthority,
  manual_pull:                parseManualPull,
} as const;
