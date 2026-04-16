/**
 * AlgoVoi Vercel AI SDK Adapter
 * ================================
 *
 * Payment-gate any Vercel AI SDK model call or tool using x402, MPP, or AP2 —
 * paid in USDC on Algorand, VOI, Hedera, or Stellar.
 *
 * Works with any Vercel AI SDK provider (OpenAI, Anthropic, Google, Groq,
 * Ollama, Azure, …) via the `model` constructor parameter.
 * Designed for Next.js App Router, Express, and Vercel Edge Functions.
 *
 * Verification uses public blockchain indexers directly — no AlgoVoi server
 * dependency for the proof verification step.
 *
 * Version: 1.0.0
 *
 * @example
 * ```ts
 * import { openai } from "@ai-sdk/openai";
 * import { AlgoVoiVercelAI } from "./vercel_ai_algovoi";
 *
 * const gate = new AlgoVoiVercelAI({
 *   algovoiKey:       "algv_...",
 *   tenantId:         "your-tenant-uuid",
 *   payoutAddress:    "YOUR_ALGORAND_ADDRESS",
 *   protocol:         "mpp",
 *   network:          "algorand-mainnet",
 *   amountMicrounits: 10_000,
 *   model:            openai("gpt-4o"),
 * });
 *
 * // Next.js App Router
 * export async function POST(req: Request) {
 *   return gate.nextHandler(req);
 * }
 * ```
 */

import { createHmac } from "node:crypto";
import {
  generateText,
  streamText,
  tool,
  type CoreMessage,
  type LanguageModel,
} from "ai";
import { z } from "zod";

export const VERSION = "1.0.0";

const MAX_BODY_BYTES = 1_048_576; // 1 MiB

// ── Network config ─────────────────────────────────────────────────────────────

interface NetworkConfig {
  assetId: number | string;
  ticker: string;
  caip2: string;
  indexerBase: string;
}

const NETWORKS: Record<string, NetworkConfig> = {
  "algorand-mainnet": {
    assetId: 31566704,
    ticker: "USDC",
    caip2: "algorand:mainnet",
    indexerBase: "https://mainnet-idx.algonode.cloud/v2",
  },
  "voi-mainnet": {
    assetId: 302190,
    ticker: "aUSDC",
    caip2: "voi:mainnet",
    indexerBase: "https://mainnet-idx.voi.nodely.dev/v2",
  },
  "hedera-mainnet": {
    assetId: "0.0.456858",
    ticker: "USDC",
    caip2: "hedera:mainnet",
    indexerBase: "https://mainnet-public.mirrornode.hedera.com/api/v1",
  },
  "stellar-mainnet": {
    assetId:
      "USDC:GA5ZSEJYB37JRC5AVCIA5MOP4RHTM335X2KGX3IHOJAPP5RE34K4KZVN",
    ticker: "USDC",
    caip2: "stellar:pubnet",
    indexerBase: "https://horizon.stellar.org",
  },
};

const CAIP2_TO_NETWORK: Record<string, string> = {
  "algorand:mainnet": "algorand-mainnet",
  "voi:mainnet": "voi-mainnet",
  "hedera:mainnet": "hedera-mainnet",
  "stellar:pubnet": "stellar-mainnet",
};

// ── Helpers ────────────────────────────────────────────────────────────────────

function safeB64Decode(s: string): string {
  const fixed = s.replace(/-/g, "+").replace(/_/g, "/");
  const padded = fixed + "=".repeat((4 - (fixed.length % 4)) % 4);
  return Buffer.from(padded, "base64").toString("utf-8");
}

function b64Encode(s: string): string {
  return Buffer.from(s, "utf-8").toString("base64");
}

function normaliseHeaders(
  h: Headers | Record<string, string>
): Record<string, string> {
  const out: Record<string, string> = {};
  if (h instanceof Headers) {
    h.forEach((v, k) => {
      out[k.toLowerCase()] = v;
    });
  } else {
    for (const [k, v] of Object.entries(h)) out[k.toLowerCase()] = v;
  }
  return out;
}

function isoNow(offsetSeconds: number): string {
  return new Date(Date.now() + offsetSeconds * 1000)
    .toISOString()
    .replace(/\.\d+Z$/, "Z");
}

// ── Result ─────────────────────────────────────────────────────────────────────

/**
 * Result of a `check()` call.
 *
 * If `requiresPayment` is true, return `as402Response()` to the client.
 * If false, the payment proof is verified — proceed with the AI call.
 */
export class VercelAIResult {
  readonly requiresPayment: boolean;
  readonly error?: string;
  private readonly _headers402: Record<string, string>;
  private readonly _bodyJson: Record<string, unknown>;

  constructor(opts: {
    requiresPayment: boolean;
    error?: string;
    headers402?: Record<string, string>;
    bodyJson?: Record<string, unknown>;
  }) {
    this.requiresPayment = opts.requiresPayment;
    this.error = opts.error;
    this._headers402 = opts.headers402 ?? {};
    this._bodyJson =
      opts.bodyJson ??
      (opts.error ? { error: opts.error } : { error: "Payment Required" });
  }

  /** Web API `Response` with status 402. Use in Next.js App Router / Edge. */
  as402Response(): Response {
    return new Response(JSON.stringify(this._bodyJson), {
      status: 402,
      headers: { "Content-Type": "application/json", ...this._headers402 },
    });
  }

  /** Challenge headers (for custom response construction). */
  get challengeHeaders(): Record<string, string> {
    return { ...this._headers402 };
  }
}

// ── On-chain verification ──────────────────────────────────────────────────────

interface VerifiedPayment {
  txId: string;
  payer: string;
  network: string;
  amount: number;
}

async function verifyAvm(
  txId: string,
  network: string,
  payoutAddress: string,
  amountMicrounits: number,
  cfg: NetworkConfig
): Promise<VerifiedPayment | null> {
  try {
    const resp = await fetch(`${cfg.indexerBase}/transactions/${txId}`, {
      headers: { Accept: "application/json" },
    });
    if (!resp.ok) return null;
    const data = await resp.json();
    const tx = (data?.transaction ?? {}) as Record<string, unknown>;
    if (!tx["confirmed-round"]) return null;
    const atx = (tx["asset-transfer-transaction"] ?? {}) as Record<
      string,
      unknown
    >;
    if (atx["receiver"] !== payoutAddress) return null;
    if ((atx["amount"] as number) < amountMicrounits) return null;
    if (atx["asset-id"] !== cfg.assetId) return null;
    return {
      txId,
      payer: String(tx["sender"] ?? ""),
      network,
      amount: atx["amount"] as number,
    };
  } catch {
    return null;
  }
}

async function verifyHedera(
  txId: string,
  payoutAddress: string,
  amountMicrounits: number,
  cfg: NetworkConfig
): Promise<VerifiedPayment | null> {
  try {
    // Normalise: "0.0.account@seconds.nanos" → "0.0.account-seconds-nanos"
    const normalised = txId.includes("@")
      ? (() => {
          const [account, time] = txId.split("@");
          return `${account}-${time.replace(".", "-")}`;
        })()
      : txId;

    const resp = await fetch(
      `${cfg.indexerBase}/transactions/${normalised}`,
      { headers: { Accept: "application/json" } }
    );
    if (!resp.ok) return null;
    const data = await resp.json();
    const transactions = (data?.transactions ?? []) as Record<
      string,
      unknown
    >[];
    if (!transactions.length) return null;
    const tx = transactions[0];
    if (tx["result"] !== "SUCCESS") return null;
    let payer = "";
    for (const t of (tx["token_transfers"] ?? []) as Record<
      string,
      unknown
    >[]) {
      if (t["token_id"] !== cfg.assetId) continue;
      if ((t["amount"] as number) < 0) payer = String(t["account"] ?? "");
      if (
        t["account"] === payoutAddress &&
        (t["amount"] as number) >= amountMicrounits
      ) {
        return {
          txId,
          payer,
          network: "hedera-mainnet",
          amount: t["amount"] as number,
        };
      }
    }
    return null;
  } catch {
    return null;
  }
}

async function verifyStellar(
  txId: string,
  payoutAddress: string,
  amountMicrounits: number,
  cfg: NetworkConfig
): Promise<VerifiedPayment | null> {
  try {
    const resp = await fetch(
      `${cfg.indexerBase}/transactions/${txId}/operations`,
      { headers: { Accept: "application/json" } }
    );
    if (!resp.ok) return null;
    const data = await resp.json();
    const [expectedCode, expectedIssuer] = String(cfg.assetId).split(":");
    for (const op of ((data?._embedded?.records ?? []) as Record<
      string,
      unknown
    >[])) {
      if (op["type"] !== "payment") continue;
      if (op["to"] !== payoutAddress) continue;
      if (op["asset_code"] !== expectedCode) continue;
      if (op["asset_issuer"] !== expectedIssuer) continue;
      const amount = Math.round(parseFloat(String(op["amount"] ?? "0")) * 1_000_000);
      if (amount >= amountMicrounits) {
        return {
          txId,
          payer: String(op["from"] ?? ""),
          network: "stellar-mainnet",
          amount,
        };
      }
    }
    return null;
  } catch {
    return null;
  }
}

async function verifyPayment(
  txId: string,
  network: string,
  payoutAddress: string,
  amountMicrounits: number
): Promise<VerifiedPayment | null> {
  const cfg = NETWORKS[network];
  if (!cfg) return null;
  if (network === "hedera-mainnet") {
    return verifyHedera(txId, payoutAddress, amountMicrounits, cfg);
  }
  if (network === "stellar-mainnet") {
    return verifyStellar(txId, payoutAddress, amountMicrounits, cfg);
  }
  return verifyAvm(txId, network, payoutAddress, amountMicrounits, cfg);
}

// ── MPP Gate ───────────────────────────────────────────────────────────────────

class MppGate {
  private readonly usedTxIds = new Set<string>();
  private readonly issuedChallenges = new Map<string, number>(); // id → expiry ms

  constructor(
    private readonly algovoiKey: string,
    private readonly payoutAddress: string,
    private readonly network: string,
    private readonly amountMicrounits: number,
    private readonly resourceId: string,
    private readonly realm: string,
    private readonly challengeTtl: number
  ) {}

  private makeHmac(requestB64: string, expires: string): string {
    const msg = `${this.realm}|algorand|charge|${requestB64}|${expires}`;
    return createHmac("sha256", this.algovoiKey || "mpp")
      .update(msg)
      .digest("hex")
      .slice(0, 32);
  }

  private validateChallengeId(id: string): boolean {
    const expiry = this.issuedChallenges.get(id);
    return expiry !== undefined && Date.now() < expiry;
  }

  private buildChallenge(): {
    headers: Record<string, string>;
    bodyJson: Record<string, unknown>;
  } {
    const cfg = NETWORKS[this.network]!;
    const accepts = [
      {
        network: this.network,
        amount: String(this.amountMicrounits),
        asset: String(cfg.assetId),
        payTo: this.payoutAddress,
        resource: this.resourceId,
      },
    ];

    const expires = isoNow(this.challengeTtl);
    const requestObj = {
      amount: String(this.amountMicrounits),
      currency: "usdc",
      recipient: this.payoutAddress,
      methodDetails: { accepts, resource: this.resourceId },
    };
    const requestB64 = b64Encode(JSON.stringify(requestObj));
    const challengeId = this.makeHmac(requestB64, expires);

    // Store issued challenge; prune expired entries
    const now = Date.now();
    this.issuedChallenges.set(challengeId, now + this.challengeTtl * 1000);
    for (const [k, exp] of this.issuedChallenges) {
      if (exp <= now) this.issuedChallenges.delete(k);
    }

    const wwwAuth =
      `Payment realm="${this.realm}", id="${challengeId}", ` +
      `method="algorand", intent="charge", ` +
      `request="${requestB64}", expires="${expires}"`;

    const xPayReq = b64Encode(
      JSON.stringify({ accepts, resource: this.resourceId })
    );

    return {
      headers: {
        "WWW-Authenticate": wwwAuth,
        "X-Payment-Required": xPayReq,
      },
      bodyJson: {
        error: "Payment Required",
        detail: "This endpoint requires payment via MPP.",
      },
    };
  }

  async check(headers: Record<string, string>): Promise<VercelAIResult> {
    const auth = headers["authorization"] ?? "";
    const xPayment = headers["x-payment"] ?? "";

    let credential: string | null = null;
    if (auth.toLowerCase().startsWith("payment ")) {
      credential = auth.slice(8).trim();
    } else if (xPayment) {
      credential = xPayment.trim();
    }

    if (!credential) {
      const ch = this.buildChallenge();
      return new VercelAIResult({
        requiresPayment: true,
        headers402: ch.headers,
        bodyJson: ch.bodyJson,
      });
    }

    let decoded: Record<string, unknown>;
    try {
      decoded = JSON.parse(safeB64Decode(credential));
    } catch {
      const ch = this.buildChallenge();
      return new VercelAIResult({
        requiresPayment: true,
        error: "Invalid credential encoding",
        headers402: ch.headers,
        bodyJson: ch.bodyJson,
      });
    }

    // Challenge echo validation (IETF spec Table 3)
    const challengeObj = (
      decoded["challenge"] ?? {}
    ) as Record<string, unknown>;
    if (
      challengeObj &&
      typeof challengeObj["id"] === "string" &&
      challengeObj["id"]
    ) {
      if (!this.validateChallengeId(challengeObj["id"])) {
        const ch = this.buildChallenge();
        return new VercelAIResult({
          requiresPayment: true,
          error: "Invalid or expired challenge",
          headers402: ch.headers,
          bodyJson: ch.bodyJson,
        });
      }
    }

    const payload = (decoded["payload"] ?? {}) as Record<string, unknown>;
    const txId = String(
      payload["txId"] ??
        payload["tx_id"] ??
        decoded["tx_id"] ??
        ""
    );
    const rawNetwork = String(
      challengeObj["method"] ?? decoded["network"] ?? "algorand-mainnet"
    );
    const network = CAIP2_TO_NETWORK[rawNetwork] ?? rawNetwork;

    if (!txId || txId.length > 200) {
      const ch = this.buildChallenge();
      return new VercelAIResult({
        requiresPayment: true,
        error: "Missing or invalid txId",
        headers402: ch.headers,
        bodyJson: ch.bodyJson,
      });
    }

    if (this.usedTxIds.has(txId)) {
      const ch = this.buildChallenge();
      return new VercelAIResult({
        requiresPayment: true,
        error: "Payment proof already used",
        headers402: ch.headers,
        bodyJson: ch.bodyJson,
      });
    }

    const verified = await verifyPayment(
      txId,
      network,
      this.payoutAddress,
      this.amountMicrounits
    );
    if (!verified) {
      const ch = this.buildChallenge();
      return new VercelAIResult({
        requiresPayment: true,
        error: "Payment verification failed",
        headers402: ch.headers,
        bodyJson: ch.bodyJson,
      });
    }

    this.usedTxIds.add(txId);
    return new VercelAIResult({ requiresPayment: false });
  }
}

// ── x402 Gate ─────────────────────────────────────────────────────────────────

class X402Gate {
  constructor(
    private readonly payoutAddress: string,
    private readonly network: string,
    private readonly amountMicrounits: number,
    private readonly resourceId: string
  ) {}

  private buildChallenge(): {
    headers: Record<string, string>;
    bodyJson: Record<string, unknown>;
  } {
    const cfg = NETWORKS[this.network]!;
    const payload = {
      x402Version: 1,
      accepts: [
        {
          network: cfg.caip2,
          asset: String(cfg.assetId),
          amount: String(this.amountMicrounits),
          payTo: this.payoutAddress,
          maxTimeoutSeconds: 300,
          extra: {},
        },
      ],
    };
    return {
      headers: { "X-PAYMENT-REQUIRED": b64Encode(JSON.stringify(payload)) },
      bodyJson: {
        error: "Payment Required",
        detail: "This endpoint requires x402 payment.",
      },
    };
  }

  async check(headers: Record<string, string>): Promise<VercelAIResult> {
    const proof = headers["x-payment"] ?? "";
    if (!proof) {
      const ch = this.buildChallenge();
      return new VercelAIResult({
        requiresPayment: true,
        headers402: ch.headers,
        bodyJson: ch.bodyJson,
      });
    }

    let decoded: Record<string, unknown>;
    try {
      decoded = JSON.parse(safeB64Decode(proof));
    } catch {
      const ch = this.buildChallenge();
      return new VercelAIResult({
        requiresPayment: true,
        error: "Invalid proof encoding",
        headers402: ch.headers,
        bodyJson: ch.bodyJson,
      });
    }

    // Extract txId from various proof shapes
    const payloadField = (decoded["payload"] ?? decoded) as Record<
      string,
      unknown
    >;
    const sigField = (payloadField["signature"] ?? {}) as Record<
      string,
      unknown
    >;
    const txId = String(
      sigField["txId"] ??
        sigField["tx_id"] ??
        payloadField["txId"] ??
        payloadField["tx_id"] ??
        decoded["txId"] ??
        decoded["tx_id"] ??
        ""
    );

    if (!txId || txId.length > 200) {
      const ch = this.buildChallenge();
      return new VercelAIResult({
        requiresPayment: true,
        error: "Missing txId in x402 proof",
        headers402: ch.headers,
        bodyJson: ch.bodyJson,
      });
    }

    const verified = await verifyPayment(
      txId,
      this.network,
      this.payoutAddress,
      this.amountMicrounits
    );
    if (!verified) {
      const ch = this.buildChallenge();
      return new VercelAIResult({
        requiresPayment: true,
        error: "Payment verification failed",
        headers402: ch.headers,
        bodyJson: ch.bodyJson,
      });
    }

    return new VercelAIResult({ requiresPayment: false });
  }
}

// ── AP2 Gate ───────────────────────────────────────────────────────────────────

const AP2_VERSION = "0.1";
const EXTENSION_URI =
  "https://api1.ilovechicken.co.uk/ap2/extensions/crypto-algo/v1";

class Ap2Gate {
  constructor(
    private readonly tenantId: string,
    private readonly payoutAddress: string,
    private readonly network: string,
    private readonly amountMicrounits: number,
    private readonly resourceId: string,
    private readonly expiresSec: number
  ) {}

  private buildChallenge(): {
    headers: Record<string, string>;
    bodyJson: Record<string, unknown>;
  } {
    const cfg = NETWORKS[this.network]!;
    const mandate = {
      ap2_version: AP2_VERSION,
      type: "CartMandate",
      merchant_id: this.tenantId,
      request_id: `ap2_${Date.now()}_${Math.floor(Math.random() * 100000)}`,
      contents: {
        payment_request: {
          payment_methods: [
            {
              supported_methods: EXTENSION_URI,
              data: {
                network: this.network,
                amount_microunits: this.amountMicrounits,
                currency: cfg.ticker,
                asset_id: String(cfg.assetId),
                receiver: this.payoutAddress,
                resource: this.resourceId,
                min_confirmations: 1,
                memo_required: false,
              },
            },
          ],
        },
      },
      expires_at: Math.floor(Date.now() / 1000) + this.expiresSec,
    };
    return {
      headers: { "X-AP2-Cart-Mandate": b64Encode(JSON.stringify(mandate)) },
      bodyJson: {
        error: "Payment Required",
        ap2_version: AP2_VERSION,
        cart_mandate: mandate,
      },
    };
  }

  private parseMandateFromHeaders(
    headers: Record<string, string>
  ): Record<string, unknown> | null {
    const raw =
      headers["x-ap2-mandate"] ?? headers["x-ap2-payment-mandate"] ?? "";
    if (!raw) return null;
    try {
      return JSON.parse(safeB64Decode(raw));
    } catch {
      try {
        return JSON.parse(raw);
      } catch {
        return null;
      }
    }
  }

  async check(
    headers: Record<string, string>,
    body?: unknown
  ): Promise<VercelAIResult> {
    let mandate = this.parseMandateFromHeaders(headers);

    if (!mandate && body && typeof body === "object") {
      const b = body as Record<string, unknown>;
      if (b["ap2_mandate"] && typeof b["ap2_mandate"] === "object") {
        mandate = b["ap2_mandate"] as Record<string, unknown>;
      }
    }

    if (!mandate) {
      const ch = this.buildChallenge();
      return new VercelAIResult({
        requiresPayment: true,
        headers402: ch.headers,
        bodyJson: ch.bodyJson,
      });
    }

    const pr = (mandate["payment_response"] ?? {}) as Record<string, unknown>;
    const details = (pr["details"] ?? {}) as Record<string, unknown>;
    const txId = String(details["tx_id"] ?? details["txId"] ?? "");
    const network = String(details["network"] ?? this.network);

    if (!txId || txId.length > 200) {
      const ch = this.buildChallenge();
      return new VercelAIResult({
        requiresPayment: true,
        error: "Missing tx_id in PaymentMandate",
        headers402: ch.headers,
        bodyJson: ch.bodyJson,
      });
    }

    const verified = await verifyPayment(
      txId,
      network,
      this.payoutAddress,
      this.amountMicrounits
    );
    if (!verified) {
      const ch = this.buildChallenge();
      return new VercelAIResult({
        requiresPayment: true,
        error: "Payment verification failed",
        headers402: ch.headers,
        bodyJson: ch.bodyJson,
      });
    }

    return new VercelAIResult({ requiresPayment: false });
  }
}

// ── Public types ───────────────────────────────────────────────────────────────

export type ResourceFn = (query: string) => string | Promise<string>;

export interface AlgoVoiToolOptions {
  /** Tool name visible to the LLM. Default: `"algovoi_payment_gate"`. */
  toolName?: string;
  /** Tool description visible to the LLM. */
  toolDescription?: string;
}

export interface AlgoVoiVercelAIOptions {
  /** AlgoVoi API key (`algv_…`). */
  algovoiKey: string;
  /** AlgoVoi tenant UUID. */
  tenantId: string;
  /** On-chain payout address. */
  payoutAddress: string;
  /** Payment protocol. Default: `"mpp"`. */
  protocol?: "mpp" | "x402" | "ap2";
  /** Blockchain network. Default: `"algorand-mainnet"`. */
  network?: string;
  /** Required payment in micro-USDC. Default: `10000` (= $0.01). */
  amountMicrounits?: number;
  /**
   * Vercel AI SDK `LanguageModel`. Pass the result of a provider factory:
   * `openai("gpt-4o")`, `anthropic("claude-opus-4-5")`, etc.
   * Required for `generateText()`, `streamText()`, and `nextHandler()`.
   */
  model?: LanguageModel;
  /** AlgoVoi resource identifier. Default: `"ai-function"`. */
  resourceId?: string;
  /** MPP realm string. Default: `"API Access"`. */
  realm?: string;
  /** MPP challenge TTL in seconds. Default: `300`. */
  challengeTtl?: number;
  /** AP2 CartMandate TTL in seconds. Default: `600`. */
  ap2ExpiresSec?: number;
}

// ── Main adapter ───────────────────────────────────────────────────────────────

/**
 * Payment gate for the Vercel AI SDK.
 *
 * Gates any Vercel AI SDK model call behind on-chain payment verification
 * using x402, MPP, or AP2. Provider-agnostic — works with any model returned
 * by an `@ai-sdk/*` provider package.
 */
export class AlgoVoiVercelAI {
  private readonly gate: MppGate | X402Gate | Ap2Gate;
  private readonly _model?: LanguageModel;

  constructor(opts: AlgoVoiVercelAIOptions) {
    const {
      algovoiKey,
      tenantId,
      payoutAddress,
      protocol = "mpp",
      network = "algorand-mainnet",
      amountMicrounits = 10_000,
      resourceId = "ai-function",
      realm = "API Access",
      challengeTtl = 300,
      ap2ExpiresSec = 600,
    } = opts;

    this._model = opts.model;

    if (protocol === "x402") {
      this.gate = new X402Gate(
        payoutAddress,
        network,
        amountMicrounits,
        resourceId
      );
    } else if (protocol === "ap2") {
      this.gate = new Ap2Gate(
        tenantId,
        payoutAddress,
        network,
        amountMicrounits,
        resourceId,
        ap2ExpiresSec
      );
    } else {
      this.gate = new MppGate(
        algovoiKey,
        payoutAddress,
        network,
        amountMicrounits,
        resourceId,
        realm,
        challengeTtl
      );
    }
  }

  /**
   * Verify payment proof from request headers.
   *
   * @param headers - Web `Headers` object or plain `Record<string, string>`.
   * @param body    - Parsed request body (used by AP2 for mandate in body).
   * @returns `VercelAIResult` — check `.requiresPayment` before proceeding.
   */
  async check(
    headers: Headers | Record<string, string>,
    body?: unknown
  ): Promise<VercelAIResult> {
    const h = normaliseHeaders(headers);
    if (this.gate instanceof Ap2Gate) return this.gate.check(h, body);
    return this.gate.check(h);
  }

  /**
   * Run an OpenAI-format message list through the configured Vercel AI model.
   *
   * @throws if no `model` was supplied in the constructor.
   */
  async generateText(messages: CoreMessage[]): Promise<string> {
    if (!this._model) {
      throw new Error(
        "AlgoVoiVercelAI: no model configured — pass model: openai('gpt-4o') in constructor"
      );
    }
    const result = await generateText({ model: this._model, messages });
    return result.text;
  }

  /**
   * Stream an OpenAI-format message list through the configured model.
   *
   * Returns the raw `StreamTextResult` — pipe via `.toDataStreamResponse()` in
   * Next.js App Router for streaming to the client.
   *
   * @throws if no `model` was supplied in the constructor.
   */
  streamText(messages: CoreMessage[]) {
    if (!this._model) {
      throw new Error(
        "AlgoVoiVercelAI: no model configured — pass model: openai('gpt-4o') in constructor"
      );
    }
    return streamText({ model: this._model, messages });
  }

  /**
   * Return a Vercel AI SDK `tool()` compatible object for use with
   * `generateText({ tools: [tool] })` or any AI SDK agent.
   *
   * The tool accepts `query` and `paymentProof` parameters. The LLM receives
   * a payment challenge if no proof is provided; the resource result if verified.
   *
   * @param resourceFn    - Called with `query` when payment is verified.
   * @param opts          - Optional tool name and description overrides.
   */
  asTool(resourceFn: ResourceFn, opts: AlgoVoiToolOptions = {}) {
    const {
      toolName = "algovoi_payment_gate",
      toolDescription =
        "Payment-gated resource access. " +
        "Provide query (the question or task) and paymentProof " +
        "(base64-encoded payment proof — empty string to receive a payment challenge).",
    } = opts;

    const gate = this;
    return tool({
      description: toolDescription,
      parameters: z.object({
        query: z.string().describe("The question or task"),
        paymentProof: z
          .string()
          .describe(
            "Base64-encoded payment proof, or empty string to request a challenge"
          ),
      }),
      execute: async ({
        query,
        paymentProof,
      }: {
        query: string;
        paymentProof: string;
      }) => {
        const headers: Record<string, string> = {};
        if (paymentProof) {
          headers["Authorization"] = `Payment ${paymentProof}`;
        }
        const result = await gate.check(headers);
        if (result.requiresPayment) {
          return JSON.stringify({
            error: "payment_required",
            detail: result.error ?? "Payment proof required",
          });
        }
        try {
          return String(await resourceFn(query));
        } catch (err) {
          return JSON.stringify({
            error: "resource_error",
            detail: String(err),
          });
        }
      },
    });
  }

  /**
   * Convenience Next.js App Router handler.
   *
   * Reads the request body, verifies payment, then calls `generateText()`.
   * For streaming, use `check()` + `streamText()` manually.
   *
   * ```ts
   * // app/api/chat/route.ts
   * export const POST = (req: Request) => gate.nextHandler(req);
   * ```
   */
  async nextHandler(req: Request): Promise<Response> {
    const raw = await req.arrayBuffer();
    const capped =
      raw.byteLength > MAX_BODY_BYTES ? raw.slice(0, MAX_BODY_BYTES) : raw;

    let body: Record<string, unknown> = {};
    try {
      body = JSON.parse(new TextDecoder().decode(capped)) as Record<
        string,
        unknown
      >;
    } catch {
      /* ignore malformed JSON — treat as empty body */
    }

    const result = await this.check(req.headers, body);
    if (result.requiresPayment) return result.as402Response();

    const messages = (body["messages"] ?? []) as CoreMessage[];
    const content = await this.generateText(messages);
    return new Response(JSON.stringify({ content }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  }

  /** Expose model for advanced use cases (e.g. pass to other AI SDK functions). */
  get model(): LanguageModel | undefined {
    return this._model;
  }
}
