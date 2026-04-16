/**
 * AlgoVoi HTTP client — thin fetch-based wrapper used by the MCP tools.
 *
 * Mirrors the surface of the existing `native-python/algovoi.py`:
 *   - create_payment_link    POST /v1/payment-links
 *   - verify_hosted_return   GET  /checkout/{token}
 *   - extension_checkout     (= create_payment_link + scrape)
 *   - verify_extension       POST /checkout/{token}/verify
 *   - verify_mpp_receipt     GET  /mpp/{resource_id}
 *   - verify_x402_proof      POST /x402/verify
 *
 * Auth is injected automatically from env vars (see index.ts).
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

export class AlgoVoiClient {
  constructor(private readonly cfg: AlgoVoiClientConfig) {
    if (!cfg.apiBase.startsWith("https://")) {
      throw new Error("AlgoVoi apiBase must be an https:// URL");
    }
  }

  // ── HTTP helpers ──────────────────────────────────────────────────────

  private async post<T = any>(path: string, body: unknown): Promise<T> {
    const resp = await fetch(`${this.cfg.apiBase}${path}`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${this.cfg.apiKey}`,
        "X-Tenant-Id": this.cfg.tenantId,
      },
      body: JSON.stringify(body),
    });
    if (!resp.ok) {
      const text = await resp.text().catch(() => "");
      throw new Error(
        `AlgoVoi API ${path} returned ${resp.status}: ${text.slice(0, 200)}`
      );
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
      const text = await resp.text().catch(() => "");
      throw new Error(
        `AlgoVoi API ${path} returned ${resp.status}: ${text.slice(0, 200)}`
      );
    }
    return (await resp.json()) as T;
  }

  // ── Public surface ────────────────────────────────────────────────────

  /**
   * Create a hosted-checkout payment link.
   * @see native-python/algovoi.py::create_payment_link
   */
  async createPaymentLink(args: {
    amount: number;
    currency: string;
    label: string;
    network: string;
    redirectUrl?: string;
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
    const resp = await this.post<CheckoutLink & Record<string, unknown>>(
      "/v1/payment-links",
      payload
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

  /**
   * Verify a hosted-checkout return token.
   * @see native-python/algovoi.py::verify_hosted_return
   */
  async verifyHostedReturn(token: string): Promise<{
    paid: boolean;
    status: string;
    raw: Record<string, unknown>;
  }> {
    if (!token || token.length > 200) {
      return { paid: false, status: "invalid_token", raw: {} };
    }
    const safe = encodeURIComponent(token);
    const resp = await fetch(`${this.cfg.apiBase}/checkout/${safe}`);
    if (!resp.ok) {
      return { paid: false, status: `http_${resp.status}`, raw: {} };
    }
    const data = (await resp.json()) as Record<string, unknown>;
    const status = String(data.status ?? "unknown");
    return {
      paid: ["paid", "completed", "confirmed"].includes(status),
      status,
      raw: data,
    };
  }

  /**
   * Verify an on-chain transaction for a checkout token.
   * @see native-python/algovoi.py::verify_extension_payment
   */
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

  /**
   * Verify an MPP receipt for a resource.
   * @see mpp-adapter/mpp.py::MppGate._verify_payment
   */
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

  /**
   * Verify an x402 payment proof (base64-encoded).
   * @see ai-adapters/openai/openai_algovoi.py::_X402Gate
   */
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
