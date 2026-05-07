/**
 * AlgoVoi Native TypeScript Payment Adapter
 *
 * Single-file drop-in for any TypeScript / JavaScript runtime that has
 * `fetch` + WebCrypto. That covers:
 *   - Node 18+ (native fetch since Node 18; SubtleCrypto since Node 20)
 *   - Bun (any version)
 *   - Deno (any version)
 *   - Cloudflare Workers, Vercel Edge, Netlify Edge, Deno Deploy
 *   - Modern browsers
 *
 * Zero npm dependencies. Pure stdlib types only.
 *
 * Supports:
 *
 * Tier 1 — one-shot payments
 *   - createPaymentLink / hostedCheckout / verifyHostedReturn
 *   - extensionCheckout / verifyExtensionPayment
 *   - verifyWebhook (HMAC-SHA256 via WebCrypto)
 *   - SSRF-safe checkout URL handling
 *   - Cancel-bypass prevention on hosted return
 *
 * Tier 2 — standing-authority recurring (subscriptions, agent-bound auth)
 *   - createRecurringAuthority / getAuthority / listAuthorities
 *   - confirmAuthority / revokeAuthority / pauseAuthority / resumeAuthority
 *   - manualPull
 *   - Seven chains: Algorand, VOI, Base, Tempo, Solana, Hedera, Stellar
 *
 * Why this exists alongside `@algovoi/sdk` (the official npm package):
 *   - Edge / serverless: bundle size matters; this is one file.
 *   - Audit / DD: single self-contained module is faster to review.
 *   - npm-averse projects: drop the .ts file in your repo and import.
 *
 * For full chain-direct flows (signing transactions client-side, etc.)
 * use `@algovoi/sdk` from npm. This adapter is the merchant-side HTTP
 * wrapper — the wallet does chain-native signing.
 *
 * AlgoVoi docs: https://github.com/chopmob-cloud/AlgoVoi-Platform-Adapters
 * Licensed under the Business Source License 1.1 — see LICENSE for details.
 *
 * Version: 1.2.0
 */

// =====================================================================
// Constants
// =====================================================================

export const VERSION = "1.2.0" as const;

/** Hard cap on inbound webhook bodies (64 KB — AlgoVoi webhooks are <2 KB). */
export const MAX_WEBHOOK_BODY_BYTES = 64 * 1024;

/** Maximum length for checkout tokens — guard against pathological input. */
export const MAX_TOKEN_LEN = 200;

/** Maximum length for on-chain transaction IDs (Algorand 52, Stellar 64, etc.). */
export const MAX_TX_ID_LEN = 200;

/** Recurring API responses are typically <4 KB; defence-in-depth cap at 16 KB. */
export const MAX_RECURRING_BODY_BYTES = 16 * 1024;

/** Standard UUID string length. */
export const MAX_UUID_LEN = 36;

/** Tier 1 hosted-checkout chains. */
export const HOSTED_NETWORKS = [
  "algorand_mainnet",
  "voi_mainnet",
  "hedera_mainnet",
  "stellar_mainnet",
] as const;

/** Tier 1 extension-payment chains (in-page wallet flow). */
export const EXT_NETWORKS = ["algorand_mainnet", "voi_mainnet"] as const;

/**
 * Every Tier 2 chain id (7 mainnets + 7 testnets) — matches the
 * `RECURRING_NETWORKS` set in native-python / native-go / native-php /
 * native-rust.
 */
export const RECURRING_NETWORKS = [
  "algorand_mainnet", "algorand_testnet",
  "voi_mainnet",      "voi_testnet",
  "base_mainnet",     "base_sepolia",
  "tempo_mainnet",    "tempo_testnet",
  "solana_mainnet",   "solana_devnet",
  "hedera_mainnet",   "hedera_testnet",
  "stellar_mainnet",  "stellar_testnet",
] as const;

/** Tier 2 webhook event types (alongside Tier 1's `payment.*`). */
export const RECURRING_EVENT_TYPES = [
  "recurring.authority_created",
  "recurring.authority_activated",
  "recurring.authority_paused",
  "recurring.authority_resumed",
  "recurring.authority_revoked",
  "recurring.authority_expired",
  "subscription.charged",
  "subscription.payment_failed",
] as const;

export type RecurringNetwork = typeof RECURRING_NETWORKS[number];
export type RecurringEventType = typeof RECURRING_EVENT_TYPES[number];
export type HostedNetwork = typeof HOSTED_NETWORKS[number];
export type ExtNetwork = typeof EXT_NETWORKS[number];

// =====================================================================
// Tier 2 types
// =====================================================================

export interface AuthorityCreateRequest {
  subscription_id: string;
  chain: RecurringNetwork | string;
  customer_wallet_address: string;
  /** Atomic units. Stellar uses 7 decimals; every other chain uses 6. */
  cap_amount_minor: number;
  /** Must be >= 86400 (1 day). */
  cap_period_seconds: number;
  /** Per-pull cap. Must be <= cap_amount_minor. */
  per_cycle_amount_minor: number;
  /** Defaults to "USDC". */
  asset?: string;
  /** Forwarded on every webhook event. */
  metadata?: Record<string, unknown>;
}

export interface Authority {
  id: string;
  tenant_id: string;
  subscription_id: string;
  chain: string;
  customer_wallet_address: string;
  cap_amount_minor: number;
  cap_period_seconds: number;
  per_cycle_amount_minor: number;
  asset: string;
  status: "pending" | "active" | "paused" | "revoking" | "revoked" | "expired" | string;
  on_chain_address?: string | null;
  cap_remaining_minor: number;
  cycles_pulled: number;
  cycles_failed: number;
  created_at: string;
  activated_at?: string | null;
  revoked_at?: string | null;
  last_error?: string | null;
  metadata?: Record<string, unknown>;
}

export interface AuthorityCreateResponse {
  authority: Authority;
  /**
   * Chain-specific signing template. Pass through to your frontend
   * wallet UI without inspection — see `Recurr/<chain>/README.md`.
   */
  customer_signing_payload: Record<string, unknown>;
  authorisation_url: string | null;
}

export interface ListAuthoritiesOptions {
  subscription_id?: string;
  /** pending / active / paused / revoking / revoked / expired */
  status?: string;
  /** Default 50; max 200. */
  limit?: number;
  offset?: number;
}

export interface ConfirmAuthorityRequest {
  on_chain_address: string;
  /** ISO8601; gateway computes one if empty. */
  first_cycle_due_at?: string;
}

export interface PullRequest {
  authority_id: string;
  /** Atomic units. Must be <= per_cycle_amount_minor. */
  amount_minor: number;
  idempotency_key?: string;
}

// =====================================================================
// Helpers — pure functions
// =====================================================================

/** Refuse to make any outbound call over plaintext HTTP. */
function isHttps(url: string): boolean {
  return url.startsWith("https://");
}

/** Test whether a chain id is a Tier 2 (recurring) network. */
export function isRecurringNetwork(network: string): network is RecurringNetwork {
  return (RECURRING_NETWORKS as readonly string[]).includes(network);
}

/** Test whether a parsed webhook payload is a Tier 2 event. */
export function isRecurringEvent(payload: unknown): boolean {
  if (!payload || typeof payload !== "object") return false;
  const obj = payload as Record<string, unknown>;
  const type = (obj.event_type ?? obj.type) as unknown;
  return typeof type === "string" && (RECURRING_EVENT_TYPES as readonly string[]).includes(type);
}

/** Extract the short token from a checkout URL like `/checkout/abc123`. */
export function extractToken(checkoutURL: string): string {
  const m = checkoutURL.match(/\/checkout\/([A-Za-z0-9_-]+)$/);
  return m ? m[1] : "";
}

// =====================================================================
// Configuration
// =====================================================================

export interface AlgoVoiConfig {
  api_base?: string;
  api_key: string;
  tenant_id: string;
  webhook_secret: string;
  /**
   * Optional per-instance fetch override — useful for tests, custom
   * agents, or runtimes where you want to inject a wrapped fetch.
   * Defaults to `globalThis.fetch`.
   */
  fetch?: typeof fetch;
  /** Override per-chain algod endpoints (Tier 1 extension flow only). */
  algod_overrides?: Record<string, AlgodConfig>;
}

export interface AlgodConfig {
  url: string;
  asset_id: number;
  ticker: string;
  dec: number;
}

const DEFAULT_ALGOD: Record<string, AlgodConfig> = {
  "algorand-mainnet": {
    url: "https://mainnet-api.algonode.cloud",
    asset_id: 31566704,
    ticker: "USDC",
    dec: 6,
  },
  "voi-mainnet": {
    url: "https://mainnet-api.voi.nodely.io",
    asset_id: 302190,
    ticker: "aUSDC",
    dec: 6,
  },
};

// =====================================================================
// Client
// =====================================================================

export class AlgoVoi {
  readonly api_base: string;
  readonly api_key: string;
  readonly tenant_id: string;
  readonly webhook_secret: string;
  readonly algod: Record<string, AlgodConfig>;
  private readonly _fetch: typeof fetch;

  constructor(config: AlgoVoiConfig) {
    this.api_base = (config.api_base ?? "https://api1.ilovechicken.co.uk").replace(/\/+$/, "");
    this.api_key = config.api_key;
    this.tenant_id = config.tenant_id;
    this.webhook_secret = config.webhook_secret;

    // Deep-copy default algod config; apply caller overrides on top so
    // the package globals can't be mutated by a caller.
    this.algod = JSON.parse(JSON.stringify(DEFAULT_ALGOD));
    if (config.algod_overrides) {
      for (const [chain, override] of Object.entries(config.algod_overrides)) {
        if (chain in this.algod) {
          this.algod[chain] = { ...this.algod[chain], ...override };
        }
      }
    }

    if (config.fetch) {
      this._fetch = config.fetch;
    } else if (typeof globalThis.fetch === "function") {
      this._fetch = globalThis.fetch.bind(globalThis);
    } else {
      throw new Error(
        "algovoi: fetch is not available in this runtime. " +
          "Use Node 18+, Bun, Deno, or pass a fetch implementation via config.fetch.",
      );
    }
  }

  // -------------------------------------------------------------------
  // Tier 1 — Payment Link / Hosted Checkout
  // -------------------------------------------------------------------

  async createPaymentLink(
    amount: number,
    currency: string,
    label: string,
    network: string,
    redirectURL = "",
  ): Promise<{
    checkout_url: string;
    id: string;
    chain: string;
    amount_microunits: number;
    asset_id: number;
  } | null> {
    if (!Number.isFinite(amount) || amount <= 0) return null;

    const payload: Record<string, unknown> = {
      amount: Math.round(amount * 100) / 100,
      currency: currency.toUpperCase(),
      label,
      preferred_network: network,
    };
    if (redirectURL) {
      try {
        const u = new URL(redirectURL);
        if (u.protocol !== "https:" || !u.hostname) return null;
      } catch {
        return null;
      }
      payload.redirect_url = redirectURL;
      payload.expires_in_seconds = 3600;
    }

    return this._post("/v1/payment-links", payload);
  }

  async hostedCheckout(
    amount: number,
    currency: string,
    label: string,
    network: string,
    redirectURL: string,
  ): Promise<{
    checkout_url: string;
    token: string;
    chain: string;
    amount_microunits: number;
  } | null> {
    const net = (HOSTED_NETWORKS as readonly string[]).includes(network)
      ? network
      : "algorand_mainnet";
    const link = await this.createPaymentLink(amount, currency, label, net, redirectURL);
    if (!link || !link.checkout_url) return null;
    return {
      checkout_url: link.checkout_url,
      token: extractToken(link.checkout_url),
      chain: link.chain ?? "algorand-mainnet",
      amount_microunits: Number(link.amount_microunits ?? 0),
    };
  }

  /**
   * CRITICAL: call this when the customer returns from the hosted
   * checkout page. Without it, a customer can cancel and still appear
   * to have paid (cancel-bypass vulnerability).
   */
  async verifyHostedReturn(token: string): Promise<boolean> {
    if (!token || token.length > MAX_TOKEN_LEN) return false;
    if (!isHttps(this.api_base)) return false;

    const url = `${this.api_base}/checkout/${encodeURIComponent(token)}`;
    try {
      const resp = await this._fetch(url, { method: "GET" });
      if (resp.status !== 200) return false;
      const body = await resp.text();
      // The hosted-checkout page embeds a JSON-ish status field.
      const m = body.match(/"status"\s*:\s*"(paid|completed|confirmed)"/);
      return !!m;
    } catch {
      return false;
    }
  }

  // -------------------------------------------------------------------
  // Tier 1 — Extension payment (in-page wallet)
  // -------------------------------------------------------------------

  async extensionCheckout(
    amount: number,
    currency: string,
    label: string,
    network: string,
  ): Promise<{
    token: string;
    receiver: string;
    memo: string;
    amount_mu: number;
    asset_id: number;
    algod_url: string;
    ticker: string;
    amount_display: string;
    chain: string;
    checkout_url: string;
  } | null> {
    if (!(EXT_NETWORKS as readonly string[]).includes(network)) return null;
    const link = await this.createPaymentLink(amount, currency, label, network);
    if (!link) return null;

    const chainKey = link.chain || (network === "voi_mainnet" ? "voi-mainnet" : "algorand-mainnet");
    const algod = this.algod[chainKey] ?? this.algod["algorand-mainnet"];
    if (!algod) return null;

    const scrape = await this._scrapeCheckout(link.checkout_url);
    if (!scrape) return null;

    return {
      token: extractToken(link.checkout_url),
      receiver: scrape.receiver,
      memo: scrape.memo,
      amount_mu: Number(link.amount_microunits ?? 0),
      asset_id: algod.asset_id,
      algod_url: algod.url,
      ticker: algod.ticker,
      amount_display: amount.toFixed(algod.dec === 6 ? 2 : algod.dec),
      chain: chainKey,
      checkout_url: link.checkout_url,
    };
  }

  async verifyExtensionPayment(
    token: string,
    txID: string,
  ): Promise<Record<string, unknown> & { _http_code?: number }> {
    if (!token || !txID || token.length > MAX_TOKEN_LEN || txID.length > MAX_TX_ID_LEN) {
      return { error: "Invalid parameters", _http_code: 400 };
    }
    const url = `${this.api_base}/checkout/${encodeURIComponent(token)}/verify`;
    if (!isHttps(url)) return { _http_code: 400 };

    try {
      const resp = await this._fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ tx_id: txID }),
      });
      let body: Record<string, unknown> = {};
      try {
        body = (await resp.json()) as Record<string, unknown>;
      } catch {
        // empty / non-JSON body — fall through with just _http_code
      }
      body._http_code = resp.status;
      return body;
    } catch {
      return { error: "Request failed", _http_code: 502 };
    }
  }

  // -------------------------------------------------------------------
  // Tier 1 — Webhook verification (HMAC-SHA256 via WebCrypto)
  // -------------------------------------------------------------------

  /**
   * Verify and parse an incoming webhook. Returns the parsed payload on
   * success, or `null` if HMAC verification fails / body is too large /
   * body isn't valid JSON.
   *
   * SECURITY NOTE — replay protection: this method does NOT dedupe
   * replays. The HMAC carries no timestamp, so callers MUST track
   * processed webhook identifiers (e.g. order_id / authority_id +
   * event_type) and reject duplicates.
   */
  async verifyWebhook(
    rawBody: Uint8Array | string,
    signature: string,
  ): Promise<Record<string, unknown> | null> {
    if (!this.webhook_secret) return null;
    if (typeof signature !== "string" || signature === "") return null;

    const bodyBytes =
      typeof rawBody === "string" ? new TextEncoder().encode(rawBody) : rawBody;
    if (bodyBytes.byteLength > MAX_WEBHOOK_BODY_BYTES) return null;

    let expected: string;
    try {
      // TS 5.x: TextEncoder.encode() returns Uint8Array<ArrayBufferLike>,
      // but crypto.subtle expects BufferSource (ArrayBuffer-backed only).
      // Cast at the WebCrypto boundary — known idiom; safe because
      // TextEncoder always produces an ArrayBuffer-backed Uint8Array.
      const secretBytes = new TextEncoder().encode(this.webhook_secret) as unknown as BufferSource;
      const key = await crypto.subtle.importKey(
        "raw",
        secretBytes,
        { name: "HMAC", hash: "SHA-256" },
        false,
        ["sign"],
      );
      const sig = await crypto.subtle.sign("HMAC", key, bodyBytes as unknown as BufferSource);
      expected = bytesToBase64(new Uint8Array(sig));
    } catch {
      return null;
    }

    if (!constantTimeEqual(expected, signature)) return null;

    try {
      const text = new TextDecoder().decode(bodyBytes);
      const parsed = JSON.parse(text);
      return parsed && typeof parsed === "object" ? (parsed as Record<string, unknown>) : null;
    } catch {
      return null;
    }
  }

  // -------------------------------------------------------------------
  // Tier 2 — Standing-Authority Recurring Payments
  //
  // Lifecycle:
  //   1. Tenant creates a subscription (POST /v1/subscriptions — out
  //      of scope of this adapter).
  //   2. createRecurringAuthority — gateway returns customer_signing_payload.
  //   3. Frontend hands the template to the customer's wallet (Pera /
  //      Defly / MetaMask / Phantom / HashPack / Freighter / etc.).
  //   4. confirmAuthority marks status='active' (or AlgoVoi's hosted
  //      widget does it via webhook).
  //   5. AlgoVoi's cycle reaper auto-pulls per cap_period_seconds.
  //   6. revoke / pause / resume manage the lifecycle.
  // -------------------------------------------------------------------

  async createRecurringAuthority(
    req: AuthorityCreateRequest,
  ): Promise<AuthorityCreateResponse | null> {
    if (!isRecurringNetwork(req.chain as string)) return null;
    if (!req.subscription_id || req.subscription_id.length > MAX_UUID_LEN) return null;
    if (!req.customer_wallet_address) return null;
    for (const k of ["cap_amount_minor", "cap_period_seconds", "per_cycle_amount_minor"] as const) {
      const v = req[k];
      if (!Number.isFinite(v) || !Number.isInteger(v) || v <= 0) return null;
    }
    if (req.cap_period_seconds < 86400) return null;
    if (req.per_cycle_amount_minor > req.cap_amount_minor) return null;

    const body: Record<string, unknown> = {
      subscription_id: req.subscription_id,
      chain: req.chain,
      customer_wallet_address: req.customer_wallet_address,
      cap_amount_minor: req.cap_amount_minor,
      cap_period_seconds: req.cap_period_seconds,
      per_cycle_amount_minor: req.per_cycle_amount_minor,
      asset: (req.asset ?? "USDC").toUpperCase(),
    };
    if (req.metadata !== undefined) {
      if (typeof req.metadata !== "object" || Array.isArray(req.metadata)) return null;
      body.metadata = req.metadata;
    }

    return this._post<AuthorityCreateResponse>("/v1/recurring/authorities", body);
  }

  async getAuthority(authorityID: string): Promise<Authority | null> {
    if (!authorityID || authorityID.length > MAX_UUID_LEN) return null;
    return this._request<Authority>(
      "GET",
      `/v1/recurring/authorities/${encodeURIComponent(authorityID)}`,
    );
  }

  async listAuthorities(opts: ListAuthoritiesOptions = {}): Promise<Authority[] | null> {
    const limit = opts.limit ?? 50;
    const offset = opts.offset ?? 0;
    if (limit < 1 || limit > 200 || offset < 0) return null;
    if (opts.subscription_id && opts.subscription_id.length > MAX_UUID_LEN) return null;
    if (opts.status && (opts.status.length > 32 || !/^[A-Za-z0-9_]+$/.test(opts.status))) return null;

    const params = new URLSearchParams({ limit: String(limit), offset: String(offset) });
    if (opts.subscription_id) params.set("subscription_id", opts.subscription_id);
    if (opts.status) params.set("status", opts.status);

    const result = await this._request<unknown>(
      "GET",
      `/v1/recurring/authorities?${params.toString()}`,
    );
    return Array.isArray(result) ? (result as Authority[]) : null;
  }

  async confirmAuthority(
    authorityID: string,
    req: ConfirmAuthorityRequest,
  ): Promise<Authority | null> {
    if (!authorityID || authorityID.length > MAX_UUID_LEN) return null;
    if (!req.on_chain_address || req.on_chain_address.length > 200) return null;
    if (req.first_cycle_due_at && req.first_cycle_due_at.length > 64) return null;

    const body: Record<string, unknown> = { on_chain_address: req.on_chain_address };
    if (req.first_cycle_due_at) body.first_cycle_due_at = req.first_cycle_due_at;
    return this._post<Authority>(
      `/v1/recurring/authorities/${encodeURIComponent(authorityID)}/confirm`,
      body,
    );
  }

  async revokeAuthority(authorityID: string): Promise<Authority | null> {
    if (!authorityID || authorityID.length > MAX_UUID_LEN) return null;
    return this._post<Authority>(
      `/v1/recurring/authorities/${encodeURIComponent(authorityID)}/revoke`,
      {},
    );
  }

  async pauseAuthority(authorityID: string): Promise<Authority | null> {
    if (!authorityID || authorityID.length > MAX_UUID_LEN) return null;
    return this._post<Authority>(
      `/v1/recurring/authorities/${encodeURIComponent(authorityID)}/pause`,
      {},
    );
  }

  async resumeAuthority(
    authorityID: string,
    nextCycleDueAt = "",
  ): Promise<Authority | null> {
    if (!authorityID || authorityID.length > MAX_UUID_LEN) return null;
    if (nextCycleDueAt && nextCycleDueAt.length > 64) return null;
    const body: Record<string, unknown> = nextCycleDueAt
      ? { next_cycle_due_at: nextCycleDueAt }
      : {};
    return this._post<Authority>(
      `/v1/recurring/authorities/${encodeURIComponent(authorityID)}/resume`,
      body,
    );
  }

  async manualPull(req: PullRequest): Promise<Authority | null> {
    if (!req.authority_id || req.authority_id.length > MAX_UUID_LEN) return null;
    if (!Number.isFinite(req.amount_minor) || !Number.isInteger(req.amount_minor) || req.amount_minor <= 0) {
      return null;
    }
    if (req.idempotency_key && req.idempotency_key.length > 128) return null;

    const body: Record<string, unknown> = {
      authority_id: req.authority_id,
      amount_minor: req.amount_minor,
    };
    if (req.idempotency_key) body.idempotency_key = req.idempotency_key;
    return this._post<Authority>("/v1/recurring/pulls", body);
  }

  // -------------------------------------------------------------------
  // Internal helpers
  // -------------------------------------------------------------------

  private async _post<T = Record<string, unknown>>(
    path: string,
    data: Record<string, unknown>,
  ): Promise<T | null> {
    return this._request<T>("POST", path, data);
  }

  private async _request<T = unknown>(
    method: "GET" | "POST" | "DELETE",
    path: string,
    data?: Record<string, unknown>,
  ): Promise<T | null> {
    const url = `${this.api_base}${path}`;
    if (!isHttps(url)) return null;

    const init: RequestInit = {
      method,
      headers: {
        Authorization: `Bearer ${this.api_key}`,
        "X-Tenant-Id": this.tenant_id,
      },
    };
    if (data !== undefined) {
      (init.headers as Record<string, string>)["Content-Type"] = "application/json";
      init.body = JSON.stringify(data);
    }

    let resp: Response;
    try {
      resp = await this._fetch(url, init);
    } catch {
      return null;
    }
    if (resp.status < 200 || resp.status >= 300) return null;

    let text: string;
    try {
      text = await resp.text();
    } catch {
      return null;
    }
    if (text.length > MAX_RECURRING_BODY_BYTES) return null;

    try {
      return JSON.parse(text) as T;
    } catch {
      return null;
    }
  }

  private async _scrapeCheckout(checkoutURL: string): Promise<{ receiver: string; memo: string } | null> {
    const apiHost = new URL(this.api_base).host;
    let checkoutHost: string;
    try {
      checkoutHost = new URL(checkoutURL).host;
    } catch {
      return null;
    }
    if (apiHost !== checkoutHost) return null;

    try {
      const resp = await this._fetch(checkoutURL, { method: "GET" });
      if (resp.status !== 200) return null;
      const html = await resp.text();
      const addr = html.match(/<div[^>]+id=["']addr["'][^>]*>([A-Z2-7]{58})</);
      const memo = html.match(/<div[^>]+id=["']memo["'][^>]*>(algovoi:[^<]+)</);
      if (!addr || !memo) return null;
      return { receiver: addr[1], memo: memo[1].trim() };
    } catch {
      return null;
    }
  }
}

// =====================================================================
// Internal — base64 + constant-time compare
// =====================================================================

function bytesToBase64(bytes: Uint8Array): string {
  // btoa is universal in Node 18+, browsers, Bun, Deno.
  let bin = "";
  for (let i = 0; i < bytes.length; i++) {
    bin += String.fromCharCode(bytes[i]);
  }
  return btoa(bin);
}

function constantTimeEqual(a: string, b: string): boolean {
  if (a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) {
    diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  }
  return diff === 0;
}
