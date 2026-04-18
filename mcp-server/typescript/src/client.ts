/**
 * AlgoVoi HTTP client — thin fetch-based wrapper used by the MCP tools.
 *
 * Auth is injected automatically from env vars (see index.ts).  External
 * error messages are generic — they never include the upstream URL, path,
 * or HTTP status code so that tool-call failures cannot be used to probe
 * the service's internal structure.
 *
 * On-chain verification (verify_mpp_receipt / verify_x402_proof /
 * verify_ap2_payment) hits the public blockchain indexers directly — no
 * AlgoVoi API call required — mirroring the MPP adapter approach.
 */

// Public indexer base URLs (no auth needed).
// Native token networks share the same indexer as their parent chain.
// Testnet networks share the same indexer key pattern with _testnet suffix.
const INDEXERS: Record<string, string> = {
  // Mainnet
  algorand_mainnet: "https://mainnet-idx.algonode.cloud/v2",
  voi_mainnet:      "https://mainnet-idx.voi.nodely.dev/v2",
  hedera_mainnet:   "https://mainnet-public.mirrornode.hedera.com/api/v1",
  stellar_mainnet:  "https://horizon.stellar.org",
  // Testnet
  algorand_testnet: "https://testnet-idx.algonode.cloud/v2",
  voi_testnet:      "https://testnet-idx.voi.nodely.dev/v2",
  hedera_testnet:   "https://testnet.mirrornode.hedera.com/api/v1",
  stellar_testnet:  "https://horizon-testnet.stellar.org",
};

/** Strip native-coin suffix to get the parent chain indexer key. */
function indexerKey(norm: string): string {
  return norm.replace(/_(?:algo|voi|hbar|xlm)$/, "") || norm;
}

/** True when the network key refers to a native coin (not a stablecoin ASA/HTS token). */
function isNativeNetwork(norm: string): boolean {
  return /_(algo|voi|hbar|xlm)$/.test(norm);
}

// USDC asset IDs per network (parent-chain keys only — omitting a key skips asset-id check).
const USDC_ASSET: Record<string, string | number> = {
  // Mainnet
  algorand_mainnet: 31566704,
  voi_mainnet:      302190,
  hedera_mainnet:   "0.0.456858",
  stellar_mainnet:  "USDC:GA5ZSEJYB37JRC5AVCIA5MOP4RHTM335X2KGX3IHOJAPP5RE34K4KZVN",
  // Testnet
  algorand_testnet: 10458941,
  // voi_testnet: asset ID varies — check skipped until standardised
  hedera_testnet:   "0.0.4279119",
  stellar_testnet:  "USDC:GBBD47IF6LWK7P7MDEVSCWR7DPUWV3NY3DTQEVFL4NAT4AQH3ZLLFLA5",
};

export interface AlgoVoiClientConfig {
  apiBase: string;
  apiKey: string;
  tenantId: string;
  /** Per-chain payout addresses. Keys are network keys (e.g. "algorand_mainnet"). */
  payoutAddresses: Record<string, string>;
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
    const resp = await fetch(`${this.cfg.apiBase}/checkout/${safe}/status`);
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

  /** Verify an MPP receipt for a resource via direct on-chain indexer. */
  async verifyMppReceipt(
    _resourceId: string,
    txId: string,
    network: string
  ): Promise<Record<string, unknown>> {
    return this.verifyOnChain(txId, network);
  }

  /** Verify an x402 payment proof (base64-encoded) via direct on-chain indexer. */
  async verifyX402Proof(
    proof: string,
    network: string
  ): Promise<Record<string, unknown>> {
    // Decode proof and extract tx_id.
    let txId: string | undefined;
    try {
      const decoded = Buffer.from(proof, "base64").toString("utf8");
      const data = JSON.parse(decoded) as Record<string, unknown>;
      txId = (data.tx_id ?? data.txId ?? data.transaction_id) as string | undefined;
    } catch {
      return { verified: false, error: "invalid proof encoding" };
    }
    if (!txId) return { verified: false, error: "proof missing tx_id" };
    return this.verifyOnChain(txId, network);
  }

  /** Verify an AP2 payment mandate receipt via direct on-chain indexer. */
  async verifyAp2Payment(
    _mandateId: string,
    txId: string,
    network: string
  ): Promise<Record<string, unknown>> {
    return this.verifyOnChain(txId, network);
  }

  /**
   * Verify a transaction against the appropriate blockchain indexer.
   * Returns { verified: true, tx_id, network, payer, amount } on success.
   * Returns { verified: false, error } on failure.
   */
  private async verifyOnChain(
    txId: string,
    network: string
  ): Promise<Record<string, unknown>> {
    const norm = network.replace(/-/g, "_");
    const iKey = indexerKey(norm);
    const indexer = INDEXERS[iKey];
    if (!indexer) {
      return { verified: false, error: `unsupported network: ${network}` };
    }
    try {
      if (norm.startsWith("algorand") || norm.startsWith("voi")) {
        return await this.verifyAvm(txId, norm, indexer);
      }
      if (norm.startsWith("hedera")) {
        return await this.verifyHedera(txId, norm, indexer);
      }
      if (norm.startsWith("stellar")) {
        return await this.verifyStellar(txId, norm, indexer);
      }
    } catch {
      return { verified: false, error: "indexer lookup failed" };
    }
    return { verified: false, error: "unsupported network" };
  }

  private async verifyAvm(
    txId: string,
    network: string,
    indexer: string
  ): Promise<Record<string, unknown>> {
    const resp = await fetch(`${indexer}/transactions/${encodeURIComponent(txId)}`, {
      headers: { Accept: "application/json" },
    });
    if (!resp.ok) return { verified: false, error: "tx not found" };
    const data = (await resp.json()) as Record<string, unknown>;
    const tx = (data.transaction ?? {}) as Record<string, unknown>;
    if (!tx["confirmed-round"]) return { verified: false, error: "tx not confirmed" };

    const payout = this.payoutAddressFor(network);

    if (isNativeNetwork(network)) {
      // Native ALGO / VOI — uses payment-transaction sub-object (no asset-id).
      const ptx = (tx["payment-transaction"] ?? {}) as Record<string, unknown>;
      if (ptx.receiver !== payout) {
        return { verified: false, error: "wrong recipient" };
      }
      return { verified: true, tx_id: txId, network, payer: tx.sender, amount: ptx.amount };
    }

    // USDC ASA path.
    const atx = (tx["asset-transfer-transaction"] ?? {}) as Record<string, unknown>;
    if (atx.receiver !== payout) {
      return { verified: false, error: "wrong recipient" };
    }
    const expectedAsset = USDC_ASSET[indexerKey(network)];
    if (expectedAsset !== undefined && atx["asset-id"] !== expectedAsset) {
      return { verified: false, error: "wrong asset" };
    }
    return { verified: true, tx_id: txId, network, payer: tx.sender, amount: atx.amount };
  }

  private async verifyHedera(
    txId: string,
    network: string,
    indexer: string
  ): Promise<Record<string, unknown>> {
    // Normalise wallet format 0.0.account@secs.nanos → 0.0.account-secs-nanos
    let normalised: string;
    if (txId.includes("@")) {
      const [acct, ts] = txId.split("@");
      normalised = `${acct}-${ts.replace(".", "-")}`;
    } else {
      normalised = txId;
    }
    const resp = await fetch(`${indexer}/transactions/${encodeURIComponent(normalised)}`, {
      headers: { Accept: "application/json" },
    });
    if (!resp.ok) return { verified: false, error: "tx not found" };
    const data = (await resp.json()) as Record<string, unknown>;
    const transactions = (data.transactions ?? []) as Record<string, unknown>[];
    if (!transactions.length) return { verified: false, error: "tx not found" };
    const tx = transactions[0];
    if (tx.result !== "SUCCESS") return { verified: false, error: "tx failed" };

    const payout = this.payoutAddressFor(network);

    if (isNativeNetwork(network)) {
      // Native HBAR — check `transfers` array (not token_transfers).
      const transfers = (tx.transfers ?? []) as Record<string, unknown>[];
      for (const t of transfers) {
        if (t.account === payout && Number(t.amount) > 0) {
          return { verified: true, tx_id: txId, network, amount: t.amount };
        }
      }
      return { verified: false, error: "payment to payout address not found" };
    }

    // USDC HTS path — check token_transfers.
    const expectedToken = USDC_ASSET[indexerKey(network)] as string;
    const transfers = (tx.token_transfers ?? []) as Record<string, unknown>[];
    for (const t of transfers) {
      if (t.token_id !== expectedToken) continue;
      if (t.account === payout && Number(t.amount) > 0) {
        return { verified: true, tx_id: txId, network: "hedera_mainnet", amount: t.amount };
      }
    }
    return { verified: false, error: "payment to payout address not found" };
  }

  private async verifyStellar(
    txId: string,
    network: string,
    indexer: string
  ): Promise<Record<string, unknown>> {
    const resp = await fetch(`${indexer}/transactions/${encodeURIComponent(txId)}/operations`, {
      headers: { Accept: "application/json" },
    });
    if (!resp.ok) return { verified: false, error: "tx not found" };
    const data = (await resp.json()) as Record<string, unknown>;
    const records = ((data._embedded as Record<string, unknown> | undefined)?.records ?? []) as Record<string, unknown>[];
    const payout = this.payoutAddressFor(network);
    const native = isNativeNetwork(network);

    if (!native) {
      const asset = USDC_ASSET[indexerKey(network)] as string;
      const [expectedCode, expectedIssuer] = asset.split(":");
      for (const op of records) {
        if (op.type !== "payment") continue;
        if (op.to !== payout) continue;
        if (op.asset_code !== expectedCode || op.asset_issuer !== expectedIssuer) continue;
        const amt = Math.round(Number(op.amount) * 1_000_000);
        return { verified: true, tx_id: txId, network: "stellar_mainnet", amount: amt, payer: op.from };
      }
    } else {
      // Native XLM — asset_type is "native", no asset_code / asset_issuer.
      for (const op of records) {
        if (op.type !== "payment") continue;
        if (op.to !== payout) continue;
        if (op.asset_type !== "native") continue;
        const amt = Math.round(Number(op.amount) * 10_000_000);
        return { verified: true, tx_id: txId, network, amount: amt, payer: op.from };
      }
    }
    return { verified: false, error: "payment to payout address not found" };
  }

  // ── helpers ───────────────────────────────────────────────────────────

  extractToken(checkoutUrl: string): string {
    const m = checkoutUrl.match(/\/checkout\/([A-Za-z0-9_-]+)$/);
    return m ? m[1] : "";
  }

  /** Return the payout address for a given network key, falling back to the
   *  first configured address if no per-chain entry exists. */
  payoutAddressFor(network: string): string {
    const norm = network.replace(/-/g, "_");
    if (this.cfg.payoutAddresses[norm]) return this.cfg.payoutAddresses[norm];
    // Strip native-coin suffix and try the parent chain key.
    const base = indexerKey(norm);
    if (base !== norm && this.cfg.payoutAddresses[base]) return this.cfg.payoutAddresses[base];
    return Object.values(this.cfg.payoutAddresses)[0] ?? "";
  }

  get tenantId(): string {
    return this.cfg.tenantId;
  }

  get apiBase(): string {
    return this.cfg.apiBase;
  }
}
