/**
 * Unit tests for all 8 MCP tools.
 * Mocks global.fetch — no network calls made.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { AlgoVoiClient } from "../src/client.js";
import {
  createPaymentLink,
  verifyPayment,
  prepareExtensionPayment,
  verifyWebhook,
  listNetworks,
  generateMppChallenge,
  verifyMppReceipt,
  verifyX402Proof,
  TOOL_SCHEMAS,
} from "../src/tools.js";

function makeClient() {
  return new AlgoVoiClient({
    apiBase: "https://api1.example.test",
    apiKey: "algv_test",
    tenantId: "tenant-test",
    payoutAddress: "PAYOUT_ADDR_TEST",
  });
}

function mockFetch(impl: (input: string, init?: any) => unknown) {
  // @ts-expect-error — overriding global fetch for the test
  globalThis.fetch = vi.fn(async (input: any, init?: any) => {
    const body = impl(String(input), init);
    return {
      ok: (body as any)?._status ? (body as any)._status < 400 : true,
      status: (body as any)?._status ?? 200,
      text: async () => JSON.stringify(body),
      json: async () => body,
    } as any;
  });
}

afterEach(() => {
  vi.restoreAllMocks();
});

// ── Tool schemas (3 tests) ────────────────────────────────────────────────────

describe("TOOL_SCHEMAS", () => {
  it("has exactly 8 tools", () => {
    expect(TOOL_SCHEMAS).toHaveLength(8);
  });
  it("every tool has name, description, inputSchema", () => {
    for (const t of TOOL_SCHEMAS) {
      expect(t.name).toBeTypeOf("string");
      expect(t.description.length).toBeGreaterThan(20);
      expect(t.inputSchema).toMatchObject({ type: "object" });
    }
  });
  it("tool names are unique", () => {
    const names = TOOL_SCHEMAS.map((t) => t.name);
    expect(new Set(names).size).toBe(names.length);
  });
});

// ── create_payment_link (5 tests) ─────────────────────────────────────────────

describe("createPaymentLink", () => {
  it("happy path returns checkout_url, token, chain, amount_microunits", async () => {
    mockFetch(() => ({
      checkout_url: "https://api1.example.test/checkout/abc123",
      chain: "algorand-mainnet",
      amount_microunits: 5_000_000,
    }));
    const out = await createPaymentLink(makeClient(), {
      amount: 5,
      currency: "usd",
      label: "Order #1",
      network: "algorand_mainnet",
    });
    expect(out.token).toBe("abc123");
    expect(out.chain).toBe("algorand-mainnet");
    expect(out.amount_microunits).toBe(5_000_000);
    expect(out.amount_display).toBe("5.00 USD");
  });

  it("rejects invalid network", async () => {
    await expect(
      createPaymentLink(makeClient(), {
        amount: 5,
        currency: "USD",
        label: "x",
        network: "ethereum_mainnet",
      })
    ).rejects.toThrow(/network must be one of/);
  });

  it("rejects non-positive amount", async () => {
    mockFetch(() => ({ checkout_url: "x" }));
    await expect(
      createPaymentLink(makeClient(), {
        amount: 0,
        currency: "USD",
        label: "x",
        network: "algorand_mainnet",
      })
    ).rejects.toThrow(/positive/);
  });

  it("passes redirect_url when https", async () => {
    let capturedBody = "";
    mockFetch((_u, init) => {
      capturedBody = init?.body ?? "";
      return {
        checkout_url: "https://api1.example.test/checkout/xyz",
        amount_microunits: 100,
      };
    });
    await createPaymentLink(makeClient(), {
      amount: 1,
      currency: "USD",
      label: "x",
      network: "algorand_mainnet",
      redirect_url: "https://shop.example.com/thanks",
    });
    expect(capturedBody).toContain("https://shop.example.com/thanks");
  });

  it("rejects http redirect_url", async () => {
    mockFetch(() => ({ checkout_url: "x" }));
    await expect(
      createPaymentLink(makeClient(), {
        amount: 1,
        currency: "USD",
        label: "x",
        network: "algorand_mainnet",
        redirect_url: "http://shop.example.com/thanks",
      })
    ).rejects.toThrow();
  });
});

// ── verify_payment (4 tests) ──────────────────────────────────────────────────

describe("verifyPayment", () => {
  it("without tx_id, checks hosted return — paid", async () => {
    mockFetch(() => ({ status: "paid" }));
    const out = await verifyPayment(makeClient(), { token: "abc123" });
    expect(out.paid).toBe(true);
    expect(out.status).toBe("paid");
  });

  it("without tx_id — unpaid", async () => {
    mockFetch(() => ({ status: "pending" }));
    const out = await verifyPayment(makeClient(), { token: "abc123" });
    expect(out.paid).toBe(false);
  });

  it("with tx_id, calls extension verify endpoint", async () => {
    let hitUrl = "";
    mockFetch((u) => {
      hitUrl = u;
      return { success: true };
    });
    const out = await verifyPayment(makeClient(), {
      token: "abc123",
      tx_id: "TX-ABC",
    });
    expect(hitUrl).toMatch(/\/checkout\/abc123\/verify$/);
    expect(out.paid).toBe(true);
  });

  it("rejects oversized token", async () => {
    await expect(
      verifyPayment(makeClient(), { token: "x".repeat(500) })
    ).rejects.toThrow(/token must be/);
  });
});

// ── prepare_extension_payment (3 tests) ───────────────────────────────────────

describe("prepareExtensionPayment", () => {
  it("happy path returns token, asset_id, ticker", async () => {
    mockFetch(() => ({
      checkout_url: "https://api1.example.test/checkout/ext1",
      chain: "algorand-mainnet",
      amount_microunits: 100_000,
    }));
    const out = await prepareExtensionPayment(makeClient(), {
      amount: 0.1,
      currency: "USD",
      label: "x",
      network: "algorand_mainnet",
    });
    expect(out.token).toBe("ext1");
    expect(out.asset_id).toBe("31566704");
    expect(out.ticker).toBe("USDC");
  });

  it("rejects hedera (hosted only)", async () => {
    await expect(
      prepareExtensionPayment(makeClient(), {
        amount: 1,
        currency: "USD",
        label: "x",
        network: "hedera_mainnet",
      })
    ).rejects.toThrow(/extension payments require/);
  });

  it("voi chain returns aUSDC", async () => {
    mockFetch(() => ({
      checkout_url: "https://api1.example.test/checkout/voi1",
      chain: "voi-mainnet",
      amount_microunits: 1_000_000,
    }));
    const out = await prepareExtensionPayment(makeClient(), {
      amount: 1,
      currency: "USD",
      label: "x",
      network: "voi_mainnet",
    });
    expect(out.ticker).toBe("aUSDC");
  });
});

// ── verify_webhook (6 tests) ──────────────────────────────────────────────────

import { createHmac } from "node:crypto";

function sign(secret: string, body: string): string {
  return createHmac("sha256", secret).update(body, "utf8").digest("base64");
}

describe("verifyWebhook", () => {
  const SECRET = "whsec_test";

  it("valid signature returns parsed payload", () => {
    const body = JSON.stringify({ order_id: "1", status: "paid" });
    const sig = sign(SECRET, body);
    const out = verifyWebhook(SECRET, { raw_body: body, signature: sig });
    expect(out.valid).toBe(true);
    expect(out.payload).toEqual({ order_id: "1", status: "paid" });
  });

  it("wrong signature returns {valid: false}", () => {
    const out = verifyWebhook(SECRET, {
      raw_body: JSON.stringify({ x: 1 }),
      signature: "AAAA",
    });
    expect(out.valid).toBe(false);
    expect(out.error).toMatch(/mismatch/);
  });

  it("missing secret returns error", () => {
    const out = verifyWebhook(undefined, {
      raw_body: "{}",
      signature: "x",
    });
    expect(out.valid).toBe(false);
    expect(out.error).toMatch(/webhook_secret not configured/);
  });

  it("missing signature returns error", () => {
    const out = verifyWebhook(SECRET, {
      raw_body: "{}",
      signature: "" as any,
    });
    expect(out.valid).toBe(false);
  });

  it("oversized body rejected", () => {
    const big = "x".repeat(70_000);
    const sig = sign(SECRET, big);
    const out = verifyWebhook(SECRET, { raw_body: big, signature: sig });
    expect(out.valid).toBe(false);
    expect(out.error).toMatch(/64 KiB cap/);
  });

  it("non-JSON body after valid sig still returns invalid", () => {
    const body = "not-json";
    const sig = sign(SECRET, body);
    const out = verifyWebhook(SECRET, { raw_body: body, signature: sig });
    expect(out.valid).toBe(false);
    expect(out.error).toMatch(/valid JSON/);
  });
});

// ── list_networks (2 tests) ───────────────────────────────────────────────────

describe("listNetworks", () => {
  it("returns 4 networks", () => {
    const out = listNetworks();
    expect(out.networks).toHaveLength(4);
  });
  it("includes CAIP-2 and asset_id", () => {
    const out = listNetworks();
    const algo = out.networks.find((n) => n.key === "algorand_mainnet");
    expect(algo?.caip2).toBe("algorand:mainnet");
    expect(algo?.asset_id).toBe("31566704");
  });
});

// ── generate_mpp_challenge (5 tests) ──────────────────────────────────────────

describe("generateMppChallenge", () => {
  it("defaults to algorand_mainnet", () => {
    const out = generateMppChallenge(makeClient(), {
      resource_id: "kb",
      amount_microunits: 10_000,
    });
    expect(out.status_code).toBe(402);
    expect(out.accepts).toHaveLength(1);
    expect(out.accepts[0].network).toBe("algorand:mainnet");
  });

  it("WWW-Authenticate header is spec-shaped", () => {
    const out = generateMppChallenge(makeClient(), {
      resource_id: "kb",
      amount_microunits: 10_000,
    });
    const h = out.headers["WWW-Authenticate"];
    expect(h).toMatch(/^Payment /);
    expect(h).toMatch(/realm=/);
    expect(h).toMatch(/intent="charge"/);
    expect(h).toMatch(/id="/);
    expect(h).toMatch(/expires="/);
    expect(h).toMatch(/request="/);
  });

  it("multi-network challenge", () => {
    const out = generateMppChallenge(makeClient(), {
      resource_id: "kb",
      amount_microunits: 10_000,
      networks: ["algorand_mainnet", "hedera_mainnet"],
    });
    expect(out.accepts).toHaveLength(2);
  });

  it("unknown network rejected", () => {
    expect(() =>
      generateMppChallenge(makeClient(), {
        resource_id: "kb",
        amount_microunits: 10_000,
        networks: ["solana_mainnet"],
      })
    ).toThrow(/unsupported network/);
  });

  it("receiver is the tenant payout address", () => {
    const out = generateMppChallenge(makeClient(), {
      resource_id: "kb",
      amount_microunits: 10_000,
    });
    expect(out.accepts[0].receiver).toBe("PAYOUT_ADDR_TEST");
  });
});

// ── verify_mpp_receipt (3 tests) ──────────────────────────────────────────────

describe("verifyMppReceipt", () => {
  it("happy path returns {verified: true}", async () => {
    mockFetch(() => ({ verified: true, tx_id: "TX1" }));
    const out = await verifyMppReceipt(makeClient(), {
      resource_id: "kb",
      tx_id: "TX1",
      network: "algorand_mainnet",
    });
    expect(out.verified).toBe(true);
  });

  it("missing tx_id rejected", async () => {
    await expect(
      verifyMppReceipt(makeClient(), {
        resource_id: "kb",
        tx_id: "",
        network: "algorand_mainnet",
      })
    ).rejects.toThrow();
  });

  it("invalid network rejected", async () => {
    await expect(
      verifyMppReceipt(makeClient(), {
        resource_id: "kb",
        tx_id: "TX1",
        network: "eth_mainnet",
      })
    ).rejects.toThrow(/unsupported network/);
  });
});

// ── verify_x402_proof (3 tests) ───────────────────────────────────────────────

describe("verifyX402Proof", () => {
  it("verified:true passes through", async () => {
    mockFetch(() => ({ verified: true }));
    const out = await verifyX402Proof(makeClient(), {
      proof: "abc",
      network: "algorand_mainnet",
    });
    expect(out.verified).toBe(true);
  });

  it("empty proof rejected", async () => {
    await expect(
      verifyX402Proof(makeClient(), {
        proof: "",
        network: "algorand_mainnet",
      })
    ).rejects.toThrow(/proof is required/);
  });

  it("bad network rejected", async () => {
    await expect(
      verifyX402Proof(makeClient(), {
        proof: "abc",
        network: "bitcoin",
      })
    ).rejects.toThrow(/unsupported network/);
  });
});
