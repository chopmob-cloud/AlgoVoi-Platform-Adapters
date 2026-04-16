/**
 * AlgoVoi HTTP client — thin fetch-based wrapper used by the MCP tools.
 *
 * Auth is injected automatically from env vars (see index.ts).  External
 * error messages are generic — they never include the upstream URL, path,
 * or HTTP status code so that tool-call failures cannot be used to probe
 * the service's internal structure.
 */

export interface AlgoVoiClientConfig {
  apiBase: string;
  apiKey: string;
  tenantId: string;
  payoutAddress: string;
}

export interface CheckoutLink {
  checkout_url: string;
  token: string;
  chain: string;
  amount_microunits: number;
}

export interface ExtensionPaymentData {
  token: string;
  receiver: string;
  memo: string;
  amount_mu: number;
  amount_display: string;
  asset_id: string | number;
  algod_url?: string;
  ticker: string;
  chain: string;
  checkout_url: string;
}

/**
 * Lazily install a process-wide undici dispatcher that enforces TLS 1.3 as
 * the minimum negotiated protocol version (§4.6 of ALGOVOI_MCP.md).
 *
 * We do this on first client construction rather than at module load so
 * that unit tests mocking global.fetch are not affected.
 */
let _tlsHardened = false;
async function hardenTls(): Promise<void> {
  if (_tlsHardened) return;
  _tlsHardened = true;
  try {
    // @ts-ignore — undici is a runtime optional dep; types not required at build time
    const { Agent, setGlobalDispatcher } = await import("undici");
    setGlobalDispatcher(
      new Agent({
        connect: { minVersion: "TLSv1.3" },
      })
    );
  } catch {
    // undici not available (very old Node) — defaults already prefer 1.3.
  }
}

export class AlgoVoiClient {
  constructor(private readonly cfg: AlgoVoiClientConfig) {
    if (!cfg.apiBase.startsWith("https://")) {
      throw new Error("AlgoVoi apiBase must be an https:// URL");
    }
    // Fire-and-forget: harden TLS settings in the background on first use.
    void hardenTls();
  }

  // ── HTTP helpers ──────────────────────────────────────────────────────

  private async post<T = any>(
    path: string,
    body: unknown,
    extraHeaders?: Record<string, string>
  ): Promise<T> {
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
      Authorization: `Bearer ${this.cfg.apiKey}`,
      "X-Tenant-Id": this.cfg.tenantId,
    };
    if (extraHeaders) Object.assign(headers, extraHeaders);
    const resp = await fetch(`${this.cfg.apiBase}${path}`, {
      method: "POST",
      headers,
      body: JSON.stringify(body),
    });
    if (!resp.ok) {
      // Do not echo the path, upstream status, or body back to the caller —
      // keeps tool-call failures from probing internal service structure.
      throw new Error("AlgoVoi request failed");
    }
    return (await resp.json()) as T;
  }

  private async get<T = any>(path: string): Promise<T> {
    const resp = await fetch(`${this.cfg.apiBase}${path}`, {
      method: "GET",
      headers: {
        Authorization: `Bearer ${this.cfg.apiKey}`,
        "X-Tenant-Id": this.cfg.tenantId,
      },
    });
    if (!resp.ok) {
      // Do not echo the path, upstream status, or body back to the caller —
      // keeps tool-call failures from probing internal service structure.
      throw new Error("AlgoVoi request failed");
    }
    return (await resp.json()) as T;
  }

  // ── Public surface ────────────────────────────────────────────────────

  /** Create a hosted-checkout payment link. */
  async createPaymentLink(args: {
    amount: number;
    currency: string;
    label: string;
    network: string;
    redirectUrl?: string;
    idempotencyKey?: string;
  }): Promise<CheckoutLink> {
    if (!Number.isFinite(args.amount) || args.amount <= 0) {
      throw new Error("amount must be a positive finite number");
    }
    const payload: Record<string, unknown> = {
      amount: Math.round(args.amount * 100) / 100,
      currency: args.currency.toUpperCase(),
      label: args.label,
      preferred_network: args.network,
    };
    if (args.redirectUrl) {
      const u = new URL(args.redirectUrl);
      if (u.protocol !== "https:") {
        throw new Error("redirect_url must be https://");
      }
      payload.redirect_url = args.redirectUrl;
      payload.expires_in_seconds = 3600;
    }
    // §6.4 — forward idempotency key to gateway as an HTTP header so
    // duplicate requests within the gateway's window return the same link.
    const extra = args.idempotencyKey
      ? { "Idempotency-Key": args.idempotencyKey }
      : undefined;
    const resp = await this.post<CheckoutLink & Record<string, unknown>>(
      "/v1/payment-links",
      payload,
      extra
    );
    if (!resp.checkout_url) {
      throw new Error("API did not return checkout_url");
    }
    return {
      checkout_url: resp.checkout_url,
      token: this.extractToken(resp.checkout_url),
      chain: (resp.chain as string) ?? "algorand-mainnet",
      amount_microunits: Number(resp.amount_microunits ?? 0),
    };
  }

  /** Verify a hosted-checkout return token. */
  async verifyHostedReturn(token: string): Promise<{
    paid: boolean;
    status: string;
  }> {
    if (!token || token.length > 200) {
      return { paid: false, status: "invalid_token" };
    }
    const safe = encodeURIComponent(token);
    const resp = await fetch(`${this.cfg.apiBase}/checkout/${safe}`);
    if (!resp.ok) {
      return { paid: false, status: `http_${resp.status}` };
    }
    let data: Record<string, unknown>;
    try {
      data = (await resp.json()) as Record<string, unknown>;
    } catch {
      return { paid: false, status: "invalid_response" };
    }
    const status = String(data.status ?? "unknown");
    return {
      paid: ["paid", "completed", "confirmed"].includes(status),
      status,
    };
  }

  /** Verify an on-chain transaction for a checkout token. */
  async verifyExtensionPayment(
    token: string,
    txId: string
  ): Promise<Record<string, unknown>> {
    if (!token || !txId || token.length > 200 || txId.length > 200) {
      return { error: "Invalid parameters", _http_code: 400 };
    }
    const safe = encodeURIComponent(token);
    const resp = await fetch(
      `${this.cfg.apiBase}/checkout/${safe}/verify`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ tx_id: txId }),
      }
    );
    const data = (await resp.json().catch(() => ({}))) as Record<
      string,
      unknown
    >;
    data._http_code = resp.status;
    return data;
  }

  /** Verify an MPP receipt for a resource. */
  async verifyMppReceipt(
    resourceId: string,
    txId: string,
    network: string
  ): Promise<Record<string, unknown>> {
    return this.post("/mpp/" + encodeURIComponent(resourceId), {
      tx_id: txId,
      network,
      tenant_id: this.cfg.tenantId,
    });
  }

  /** Verify an x402 payment proof (base64-encoded). */
  async verifyX402Proof(
    proof: string,
    network: string
  ): Promise<Record<string, unknown>> {
    return this.post("/x402/verify", {
      proof,
      network,
      tenant_id: this.cfg.tenantId,
    });
  }

  /** Verify an AP2 payment mandate receipt. */
  async verifyAp2Payment(
    mandateId: string,
    txId: string,
    network: string
  ): Promise<Record<string, unknown>> {
    return this.post("/ap2/verify", {
      mandate_id: mandateId,
      tx_id:      txId,
      network,
      tenant_id:  this.cfg.tenantId,
    });
  }

  // ── helpers ───────────────────────────────────────────────────────────

  extractToken(checkoutUrl: string): string {
    const m = checkoutUrl.match(/\/checkout\/([A-Za-z0-9_-]+)$/);
    return m ? m[1] : "";
  }

  get payoutAddress(): string {
    return this.cfg.payoutAddress;
  }

  get tenantId(): string {
    return this.cfg.tenantId;
  }

  get apiBase(): string {
    return this.cfg.apiBase;
  }
}
