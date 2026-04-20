/**
 * Unit tests for the 8 MCP tools and the new hardening modules
 * (schemas/parsers, redact, audit, idempotency).
 * Mocks global.fetch — no network calls made.
 */

import { afterEach, describe, expect, it, vi } from "vitest";
import { AlgoVoiClient } from "../src/client.js";
import { logCall } from "../src/audit.js";
import { scrub } from "../src/redact.js";
import { IdempotencyCache } from "../src/idempotency.js";
import {
  ValidationError,
  parseCreatePaymentLink,
  parseFetchAgentCard,
  parseGenerateAp2Mandate,
  parseGenerateMppChallenge,
  parseGenerateX402Challenge,
  parsePrepareExtensionPayment,
  parseSendA2aMessage,
  parseVerifyAp2Payment,
  parseVerifyMppReceipt,
  parseVerifyPayment,
  parseVerifyWebhook,
  parseVerifyX402Proof,
  PARSERS,
} from "../src/schemas.js";
import {
  createPaymentLink,
  fetchAgentCard,
  sendA2aMessage,
  verifyPayment,
  prepareExtensionPayment,
  verifyWebhook,
  listNetworks,
  generateMppChallenge,
  verifyMppReceipt,
  verifyX402Proof,
  generateX402Challenge,
  generateAp2Mandate,
  verifyAp2Payment,
  TOOL_SCHEMAS,
  _resetIdempotencyCacheForTests,
} from "../src/tools.js";
import { createHmac } from "node:crypto";

function makeClient() {
  return new AlgoVoiClient({
    apiBase: "https://api1.example.test",
    apiKey: "algv_test",
    tenantId: "tenant-test",
    payoutAddresses: {
      algorand_mainnet: "PAYOUT_ADDR_TEST",
      voi_mainnet:      "PAYOUT_ADDR_TEST",
      hedera_mainnet:   "PAYOUT_ADDR_TEST",
      stellar_mainnet:  "PAYOUT_ADDR_TEST",
    },
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
  _resetIdempotencyCacheForTests();
});

// ── TOOL_SCHEMAS (3 tests) ────────────────────────────────────────────────────

describe("TOOL_SCHEMAS", () => {
  it("has exactly 13 tools", () => {
    expect(TOOL_SCHEMAS).toHaveLength(13);
  });
  it("every tool has name, description, inputSchema, additionalProperties=false", () => {
    for (const t of TOOL_SCHEMAS) {
      expect(t.name).toBeTypeOf("string");
      expect(t.description.length).toBeGreaterThan(20);
      expect(t.inputSchema).toMatchObject({ type: "object" });
      expect((t.inputSchema as any).additionalProperties).toBe(false);
    }
  });
  it("tool names are unique and match PARSERS", () => {
    const names = TOOL_SCHEMAS.map((t) => t.name);
    expect(new Set(names).size).toBe(names.length);
    for (const n of names) {
      expect(PARSERS[n as keyof typeof PARSERS]).toBeTypeOf("function");
    }
  });
});

// ── Strict parsers (8 tests) ──────────────────────────────────────────────────

describe("parsers (extra=forbid)", () => {
  it("create rejects extra key", () => {
    expect(() =>
      parseCreatePaymentLink({
        amount: 1, currency: "USD", label: "x",
        network: "algorand_mainnet", bogus: "x",
      })
    ).toThrow(ValidationError);
  });

  it("create rejects string amount", () => {
    expect(() =>
      parseCreatePaymentLink({
        amount: "5.00", currency: "USD", label: "x",
        network: "algorand_mainnet",
      })
    ).toThrow(ValidationError);
  });

  it("create rejects zero amount", () => {
    expect(() =>
      parseCreatePaymentLink({
        amount: 0, currency: "USD", label: "x",
        network: "algorand_mainnet",
      })
    ).toThrow(ValidationError);
  });

  it("create rejects bad network", () => {
    expect(() =>
      parseCreatePaymentLink({
        amount: 1, currency: "USD", label: "x",
        network: "solana_mainnet",
      })
    ).toThrow(ValidationError);
  });

  it("create accepts valid idempotency_key", () => {
    const out = parseCreatePaymentLink({
      amount: 1, currency: "USD", label: "x",
      network: "algorand_mainnet",
      idempotency_key: "a".repeat(16),
    });
    expect(out.idempotency_key).toHaveLength(16);
  });

  it("create rejects short idempotency_key", () => {
    expect(() =>
      parseCreatePaymentLink({
        amount: 1, currency: "USD", label: "x",
        network: "algorand_mainnet",
        idempotency_key: "tooshort",
      })
    ).toThrow(ValidationError);
  });

  it("verify_payment rejects oversized token", () => {
    expect(() => parseVerifyPayment({ token: "x".repeat(500) })).toThrow(
      ValidationError
    );
  });

  it("generate_mpp rejects negative amount", () => {
    expect(() =>
      parseGenerateMppChallenge({
        resource_id: "kb",
        amount_microunits: -1,
      })
    ).toThrow(ValidationError);
  });
});

// ── redact (6 tests) ──────────────────────────────────────────────────────────

describe("scrub", () => {
  it("redacts mnemonic", () => {
    expect(scrub({ mnemonic: "abandon abandon..." })).toEqual({
      mnemonic: "[REDACTED]",
    });
  });

  it("redacts api_key", () => {
    expect(scrub({ api_key: "algv_123" })).toEqual({
      api_key: "[REDACTED]",
    });
  });

  it("is case-insensitive on keys", () => {
    expect(scrub({ Private_Key: "0x..." })).toEqual({
      Private_Key: "[REDACTED]",
    });
  });

  it("preserves checkout token", () => {
    const out = scrub({ token: "abc", checkout_url: "https://x/checkout/abc" });
    expect(out).toEqual({ token: "abc", checkout_url: "https://x/checkout/abc" });
  });

  it("truncates long strings", () => {
    const long = "x".repeat(1000);
    const out  = scrub({ memo: long }) as any;
    expect(out.memo.length).toBeLessThan(600);
    expect(out.memo).toContain("[truncated");
  });

  it("recurses into nested objects and arrays", () => {
    const src = { outer: { secret: "s", list: [{ password: "p" }] } };
    const out = scrub(src) as any;
    expect(out.outer.secret).toBe("[REDACTED]");
    expect(out.outer.list[0].password).toBe("[REDACTED]");
  });
});

// ── audit (3 tests) ───────────────────────────────────────────────────────────

describe("logCall", () => {
  it("writes a single JSON line to stderr", () => {
    const writes: string[] = [];
    const spy = vi.spyOn(process.stderr, "write").mockImplementation((chunk: any) => {
      writes.push(String(chunk));
      return true;
    });
    logCall({ tool_name: "x", args: { a: 1 }, status: "ok", duration_ms: 12.34 });
    spy.mockRestore();
    const entry = JSON.parse(writes[writes.length - 1]);
    expect(entry.tool_name).toBe("x");
    expect(entry.status).toBe("ok");
    expect(entry.duration_ms).toBe(12.34);
    expect(entry.trace_id).toMatch(/^[0-9a-f]{16}$/);
  });

  it("hashes args — secret never appears in log", () => {
    const writes: string[] = [];
    const spy = vi.spyOn(process.stderr, "write").mockImplementation((chunk: any) => {
      writes.push(String(chunk));
      return true;
    });
    logCall({
      tool_name: "x",
      args: { api_key: "algv_supersecret" },
      status: "ok",
      duration_ms: 0,
    });
    spy.mockRestore();
    expect(writes.join("")).not.toContain("algv_supersecret");
  });

  it("records error_code when present", () => {
    const writes: string[] = [];
    const spy = vi.spyOn(process.stderr, "write").mockImplementation((chunk: any) => {
      writes.push(String(chunk));
      return true;
    });
    logCall({
      tool_name: "x", args: {}, status: "rejected",
      duration_ms: 0, error_code: "ValidationError",
    });
    spy.mockRestore();
    const entry = JSON.parse(writes[writes.length - 1]);
    expect(entry.error_code).toBe("ValidationError");
  });
});

// ── idempotency (3 tests) ─────────────────────────────────────────────────────

describe("IdempotencyCache", () => {
  it("set/get round-trip", () => {
    const c = new IdempotencyCache<number>();
    c.set("k", 42);
    expect(c.get("k")).toBe(42);
  });

  it("miss returns undefined", () => {
    expect(new IdempotencyCache().get("missing")).toBeUndefined();
  });

  it("expires after ttl", async () => {
    const c = new IdempotencyCache(10); // 10 ms
    c.set("k", "v");
    await new Promise((r) => setTimeout(r, 30));
    expect(c.get("k")).toBeUndefined();
  });
});

// ── create_payment_link (6 tests) ─────────────────────────────────────────────

describe("createPaymentLink", () => {
  it("happy path returns token, chain, amount_microunits", async () => {
    mockFetch(() => ({
      checkout_url: "https://api1.example.test/checkout/abc123",
      chain: "algorand-mainnet",
      amount_microunits: 5_000_000,
    }));
    const args = parseCreatePaymentLink({
      amount: 5, currency: "usd", label: "Order #1",
      network: "algorand_mainnet",
    });
    const out = await createPaymentLink(makeClient(), args);
    expect(out.token).toBe("abc123");
    expect(out.chain).toBe("algorand-mainnet");
    expect(out.amount_microunits).toBe(5_000_000);
    expect(out.amount_display).toBe("5.00 USD");
  });

  it("rejects http redirect_url", async () => {
    mockFetch(() => ({ checkout_url: "x" }));
    await expect(
      createPaymentLink(
        makeClient(),
        parseCreatePaymentLink({
          amount: 1, currency: "USD", label: "x",
          network: "algorand_mainnet",
          redirect_url: "http://shop.example.com/thanks",
        })
      )
    ).rejects.toThrow();
  });

  it("forwards idempotency_key as Idempotency-Key header", async () => {
    let seenHeaders: Record<string, string> = {};
    mockFetch((_u, init) => {
      seenHeaders = init?.headers ?? {};
      return {
        checkout_url: "https://api1.example.test/checkout/a",
        chain: "algorand-mainnet",
        amount_microunits: 100,
      };
    });
    const key = "a".repeat(16);
    await createPaymentLink(
      makeClient(),
      parseCreatePaymentLink({
        amount: 1, currency: "USD", label: "x",
        network: "algorand_mainnet",
        idempotency_key: key,
      })
    );
    expect(seenHeaders["Idempotency-Key"]).toBe(key);
  });

  it("caches replay for same idempotency_key (fetch only hit once)", async () => {
    let hits = 0;
    mockFetch(() => {
      hits += 1;
      return {
        checkout_url: "https://api1.example.test/checkout/a",
        chain: "algorand-mainnet",
        amount_microunits: 100,
      };
    });
    const args = parseCreatePaymentLink({
      amount: 1, currency: "USD", label: "x",
      network: "algorand_mainnet",
      idempotency_key: "k".repeat(16),
    });
    const first  = await createPaymentLink(makeClient(), args);
    const second = await createPaymentLink(makeClient(), args);
    expect(first).toEqual(second);
    expect(hits).toBe(1);
  });

  it("without idempotency_key calls fetch every time", async () => {
    let hits = 0;
    mockFetch(() => {
      hits += 1;
      return {
        checkout_url: `https://api1.example.test/checkout/${hits}`,
        chain: "algorand-mainnet",
        amount_microunits: 100,
      };
    });
    const args = parseCreatePaymentLink({
      amount: 1, currency: "USD", label: "x",
      network: "algorand_mainnet",
    });
    await createPaymentLink(makeClient(), args);
    await createPaymentLink(makeClient(), args);
    expect(hits).toBe(2);
  });

  it("invalid network rejected by parser", () => {
    expect(() =>
      parseCreatePaymentLink({
        amount: 1, currency: "USD", label: "x",
        network: "eth_mainnet",
      })
    ).toThrow(ValidationError);
  });
});

// ── verify_payment (3 tests) ──────────────────────────────────────────────────

describe("verifyPayment", () => {
  it("without tx_id hits hosted-return", async () => {
    mockFetch(() => ({ status: "paid" }));
    const out = await verifyPayment(
      makeClient(),
      parseVerifyPayment({ token: "abc123" })
    );
    expect(out.paid).toBe(true);
  });

  it("with tx_id hits extension verify", async () => {
    let hitUrl = "";
    mockFetch((u) => {
      hitUrl = u;
      return { success: true };
    });
    await verifyPayment(
      makeClient(),
      parseVerifyPayment({ token: "abc123", tx_id: "TX-ABC" })
    );
    expect(hitUrl).toMatch(/\/checkout\/abc123\/verify$/);
  });

  it("rejects oversized token at parse time", () => {
    expect(() => parseVerifyPayment({ token: "x".repeat(500) })).toThrow(
      ValidationError
    );
  });
});

// ── prepare_extension_payment (3 tests) ───────────────────────────────────────

describe("prepareExtensionPayment", () => {
  it("algorand returns usdc", async () => {
    mockFetch(() => ({
      checkout_url: "https://api1.example.test/checkout/ext1",
      chain: "algorand-mainnet",
      amount_microunits: 100_000,
    }));
    const out = await prepareExtensionPayment(
      makeClient(),
      parsePrepareExtensionPayment({
        amount: 0.1, currency: "USD", label: "x",
        network: "algorand_mainnet",
      })
    );
    expect(out.token).toBe("ext1");
    expect(out.ticker).toBe("USDC");
  });

  it("voi returns aUSDC", async () => {
    mockFetch(() => ({
      checkout_url: "https://api1.example.test/checkout/voi1",
      chain: "voi-mainnet",
      amount_microunits: 1_000_000,
    }));
    const out = await prepareExtensionPayment(
      makeClient(),
      parsePrepareExtensionPayment({
        amount: 1, currency: "USD", label: "x", network: "voi_mainnet",
      })
    );
    expect(out.ticker).toBe("aUSDC");
  });

  it("hedera rejected by parser", () => {
    expect(() =>
      parsePrepareExtensionPayment({
        amount: 1, currency: "USD", label: "x", network: "hedera_mainnet",
      })
    ).toThrow(ValidationError);
  });
});

// ── verify_webhook (6 tests) ──────────────────────────────────────────────────

function sign(secret: string, body: string) {
  return createHmac("sha256", secret).update(body, "utf8").digest("base64");
}

describe("verifyWebhook", () => {
  const SECRET = "whsec_test";

  it("valid signature returns parsed payload", () => {
    const body = JSON.stringify({ order_id: "1", status: "paid" });
    const sig  = sign(SECRET, body);
    const out  = verifyWebhook(SECRET, parseVerifyWebhook({ raw_body: body, signature: sig }));
    expect(out.valid).toBe(true);
    expect(out.payload).toEqual({ order_id: "1", status: "paid" });
  });

  it("wrong signature returns valid=false", () => {
    const out = verifyWebhook(
      SECRET,
      parseVerifyWebhook({ raw_body: "{}", signature: "AAAA" })
    );
    expect(out.valid).toBe(false);
    expect(out.error).toMatch(/mismatch/);
  });

  it("missing secret returns error", () => {
    const out = verifyWebhook(undefined, parseVerifyWebhook({ raw_body: "{}", signature: "x" }));
    expect(out.valid).toBe(false);
    expect(out.error).toMatch(/not configured/);
  });

  it("empty signature rejected by parser", () => {
    expect(() => parseVerifyWebhook({ raw_body: "{}", signature: "" })).toThrow(
      ValidationError
    );
  });

  it("oversized body rejected by parser", () => {
    expect(() =>
      parseVerifyWebhook({
        raw_body: "x".repeat(70_000),
        signature: "x",
      })
    ).toThrow(ValidationError);
  });

  it("non-JSON body after valid sig returns valid=false", () => {
    const body = "not-json";
    const sig  = sign(SECRET, body);
    const out  = verifyWebhook(SECRET, parseVerifyWebhook({ raw_body: body, signature: sig }));
    expect(out.valid).toBe(false);
    expect(out.error).toMatch(/valid JSON/);
  });
});

// ── list_networks (2 tests) ───────────────────────────────────────────────────

describe("listNetworks", () => {
  it("returns 16 networks (8 mainnet + 8 testnet)", () => {
    expect(listNetworks().networks).toHaveLength(16);
  });
  it("includes CAIP-2 and asset_id", () => {
    const out = listNetworks();
    const algo = out.networks.find((n: any) => n.key === "algorand_mainnet");
    expect(algo?.caip2).toBe("algorand:mainnet");
    expect(algo?.asset_id).toBe("31566704");
  });
});

// ── generate_mpp_challenge (5 tests) ──────────────────────────────────────────

describe("generateMppChallenge", () => {
  it("defaults to algorand_mainnet", () => {
    const out = generateMppChallenge(
      makeClient(),
      parseGenerateMppChallenge({ resource_id: "kb", amount_microunits: 10_000 })
    );
    expect(out.status_code).toBe(402);
    expect(out.accepts).toHaveLength(1);
    expect(out.accepts[0].network).toBe("algorand:mainnet");
  });

  it("WWW-Authenticate is spec-shaped", () => {
    const out = generateMppChallenge(
      makeClient(),
      parseGenerateMppChallenge({ resource_id: "kb", amount_microunits: 10_000 })
    );
    const h = out.headers["WWW-Authenticate"];
    expect(h).toMatch(/^Payment /);
    expect(h).toMatch(/realm=/);
    expect(h).toMatch(/intent="charge"/);
    expect(h).toMatch(/id="/);
    expect(h).toMatch(/expires="/);
    expect(h).toMatch(/request="/);
  });

  it("multi-network challenge", () => {
    const out = generateMppChallenge(
      makeClient(),
      parseGenerateMppChallenge({
        resource_id: "kb",
        amount_microunits: 10_000,
        networks: ["algorand_mainnet", "hedera_mainnet"],
      })
    );
    expect(out.accepts).toHaveLength(2);
  });

  it("unknown network rejected by parser", () => {
    expect(() =>
      parseGenerateMppChallenge({
        resource_id: "kb",
        amount_microunits: 10_000,
        networks: ["solana_mainnet"],
      })
    ).toThrow(ValidationError);
  });

  it("receiver is tenant payout address", () => {
    const out = generateMppChallenge(
      makeClient(),
      parseGenerateMppChallenge({ resource_id: "kb", amount_microunits: 10_000 })
    );
    expect(out.accepts[0].receiver).toBe("PAYOUT_ADDR_TEST");
  });
});

// ── verify_mpp_receipt (3 tests) ──────────────────────────────────────────────

describe("verifyMppReceipt", () => {
  it("verified:true passes through", async () => {
    // Mock the Algorand indexer response with a valid confirmed USDC transfer to payout address.
    mockFetch(() => ({
      transaction: {
        "confirmed-round": 12345,
        sender: "PAYER_ADDR_TEST",
        "asset-transfer-transaction": {
          receiver: "PAYOUT_ADDR_TEST",
          amount: 10000,
          "asset-id": 31566704,
        },
      },
    }));
    const out = await verifyMppReceipt(
      makeClient(),
      parseVerifyMppReceipt({
        resource_id: "kb", tx_id: "TX1", network: "algorand_mainnet",
      })
    );
    expect(out.verified).toBe(true);
  });

  it("missing tx_id rejected by parser", () => {
    expect(() =>
      parseVerifyMppReceipt({
        resource_id: "kb", tx_id: "", network: "algorand_mainnet",
      })
    ).toThrow(ValidationError);
  });

  it("unknown network rejected by parser", () => {
    expect(() =>
      parseVerifyMppReceipt({
        resource_id: "kb", tx_id: "TX1", network: "eth_mainnet",
      })
    ).toThrow(ValidationError);
  });
});

// ── verify_x402_proof (3 tests) ───────────────────────────────────────────────

describe("verifyX402Proof", () => {
  it("verified:true passes through", async () => {
    // Mock the Algorand indexer response with a valid confirmed USDC transfer.
    mockFetch(() => ({
      transaction: {
        "confirmed-round": 12345,
        sender: "PAYER_ADDR_TEST",
        "asset-transfer-transaction": {
          receiver: "PAYOUT_ADDR_TEST",
          amount: 10000,
          "asset-id": 31566704,
        },
      },
    }));
    // Encode a proof that contains a tx_id field.
    const proof = Buffer.from(JSON.stringify({ tx_id: "TX1" })).toString("base64");
    const out = await verifyX402Proof(
      makeClient(),
      parseVerifyX402Proof({ proof, network: "algorand_mainnet" })
    );
    expect(out.verified).toBe(true);
  });

  it("empty proof rejected by parser", () => {
    expect(() => parseVerifyX402Proof({ proof: "", network: "algorand_mainnet" })).toThrow(
      ValidationError
    );
  });

  it("bad network rejected by parser", () => {
    expect(() => parseVerifyX402Proof({ proof: "abc", network: "bitcoin" })).toThrow(
      ValidationError
    );
  });
});

// ── generate_x402_challenge (4 tests) ─────────────────────────────────────────

describe("generateX402Challenge", () => {
  it("returns 402 with X-Payment-Required header", () => {
    const out = generateX402Challenge(
      makeClient(),
      parseGenerateX402Challenge({ resource: "https://api.example.com/kb", amount_microunits: 1_000_000 })
    );
    expect(out.status_code).toBe(402);
    expect(out.headers["X-Payment-Required"]).toBeTruthy();
  });

  it("header decodes to valid x402 v1 payload", () => {
    const out = generateX402Challenge(
      makeClient(),
      parseGenerateX402Challenge({ resource: "https://api.example.com/kb", amount_microunits: 500_000 })
    );
    const decoded = JSON.parse(Buffer.from(out.headers["X-Payment-Required"], "base64").toString("utf8"));
    expect(decoded.version).toBe("1");
    expect(decoded.payTo).toBe("PAYOUT_ADDR_TEST");
    expect(decoded.maxAmountRequired).toBe("500000");
  });

  it("defaults to algorand_mainnet", () => {
    const out = generateX402Challenge(
      makeClient(),
      parseGenerateX402Challenge({ resource: "https://x.com/r", amount_microunits: 100 })
    );
    expect(out.payload.networkId).toBe("algorand:mainnet");
  });

  it("zero amount rejected by parser", () => {
    expect(() =>
      parseGenerateX402Challenge({ resource: "https://x.com/r", amount_microunits: 0 })
    ).toThrow(ValidationError);
  });
});

// ── generate_ap2_mandate (4 tests) ────────────────────────────────────────────

describe("generateAp2Mandate", () => {
  it("returns mandate_id, mandate, mandate_b64", () => {
    const out = generateAp2Mandate(
      makeClient(),
      parseGenerateAp2Mandate({ resource_id: "task-42", amount_microunits: 1_000_000 })
    );
    expect(out.mandate_id).toHaveLength(16);
    expect(out.mandate_b64).toBeTruthy();
    expect(out.mandate.type).toBe("PaymentMandate");
  });

  it("mandate_b64 decodes to correct payee + amount", () => {
    const out = generateAp2Mandate(
      makeClient(),
      parseGenerateAp2Mandate({ resource_id: "task-42", amount_microunits: 2_000_000 })
    );
    const mandate = JSON.parse(Buffer.from(out.mandate_b64, "base64").toString("utf8"));
    expect(mandate.payee.address).toBe("PAYOUT_ADDR_TEST");
    expect(mandate.amount.value).toBe("2000000");
    expect(mandate.protocol).toBe("algovoi-ap2/0.1");
  });

  it("payout address set from client", () => {
    const out = generateAp2Mandate(
      makeClient(),
      parseGenerateAp2Mandate({ resource_id: "r", amount_microunits: 1_000_000 })
    );
    expect(out.mandate.payee.address).toBe("PAYOUT_ADDR_TEST");
  });

  it("negative amount rejected by parser", () => {
    expect(() =>
      parseGenerateAp2Mandate({ resource_id: "r", amount_microunits: -1 })
    ).toThrow(ValidationError);
  });
});

// ── verify_ap2_payment (3 tests) ──────────────────────────────────────────────

describe("verifyAp2Payment", () => {
  it("verified:true passes through", async () => {
    // Mock the Algorand indexer response with a valid confirmed USDC transfer to payout address.
    mockFetch(() => ({
      transaction: {
        "confirmed-round": 12345,
        sender: "PAYER_ADDR_TEST",
        "asset-transfer-transaction": {
          receiver: "PAYOUT_ADDR_TEST",
          amount: 10000,
          "asset-id": 31566704,
        },
      },
    }));
    const out = await verifyAp2Payment(
      makeClient(),
      parseVerifyAp2Payment({ mandate_id: "a".repeat(16), tx_id: "TX1", network: "algorand_mainnet" })
    );
    expect(out.verified).toBe(true);
  });

  it("empty mandate_id rejected by parser", () => {
    expect(() =>
      parseVerifyAp2Payment({ mandate_id: "", tx_id: "TX1", network: "algorand_mainnet" })
    ).toThrow(ValidationError);
  });

  it("bad network rejected by parser", () => {
    expect(() =>
      parseVerifyAp2Payment({ mandate_id: "a".repeat(16), tx_id: "TX1", network: "bitcoin" })
    ).toThrow(ValidationError);
  });
});

// ── fetch_agent_card (5 tests) ────────────────────────────────────────────────

/** Full-control mock that returns an explicit Response-like object. */
function mockFetchFull(respFactory: (url: string, init?: any) => any) {
  // @ts-expect-error — overriding global fetch for the test
  globalThis.fetch = vi.fn(async (url: any, init?: any) => respFactory(String(url), init));
}

describe("fetchAgentCard", () => {
  it("returns card on 200", async () => {
    mockFetchFull(() => ({
      ok:     true,
      status: 200,
      json:   async () => ({ name: "Test Agent", description: "A test agent" }),
    }));
    const out = await fetchAgentCard(parseFetchAgentCard({ agent_url: "https://agent.example.com" })) as any;
    expect(out.card.name).toBe("Test Agent");
    expect(out.error).toBeNull();
  });

  it("returns error on non-200", async () => {
    mockFetchFull(() => ({ ok: false, status: 404, json: async () => ({}) }));
    const out = await fetchAgentCard(parseFetchAgentCard({ agent_url: "https://agent.example.com" })) as any;
    expect(out.card).toBeNull();
    expect(out.error).toMatch(/404/);
  });

  it("appends /.well-known/agent.json to the agent_url", async () => {
    let capturedUrl = "";
    mockFetchFull((url) => {
      capturedUrl = url;
      return { ok: true, status: 200, json: async () => ({}) };
    });
    await fetchAgentCard(parseFetchAgentCard({ agent_url: "https://agent.example.com/" }));
    expect(capturedUrl).toBe("https://agent.example.com/.well-known/agent.json");
  });

  it("handles network error gracefully", async () => {
    // @ts-expect-error
    globalThis.fetch = vi.fn(async () => { throw new Error("ECONNREFUSED"); });
    const out = await fetchAgentCard(parseFetchAgentCard({ agent_url: "https://agent.example.com" })) as any;
    expect(out.card).toBeNull();
    expect(out.error).toMatch(/ECONNREFUSED/);
  });

  it("rejects http:// agent_url at parse time", () => {
    expect(() => parseFetchAgentCard({ agent_url: "http://insecure.example.com" }))
      .toThrow(ValidationError);
  });
});

// ── send_a2a_message (7 tests) ────────────────────────────────────────────────

function makeHeadersForEach(obj: Record<string, string>) {
  return { forEach: (cb: (v: string, k: string) => void) => Object.entries(obj).forEach(([k, v]) => cb(v, k)) };
}

describe("sendA2aMessage", () => {
  it("returns task on 200", async () => {
    mockFetchFull(() => ({
      ok:      true,
      status:  200,
      headers: makeHeadersForEach({}),
      json:    async () => ({ id: "task-1", status: "completed", artifacts: [] }),
    }));
    const out = await sendA2aMessage(parseSendA2aMessage({ agent_url: "https://agent.example.com", text: "Hello" })) as any;
    expect(out.payment_required).toBe(false);
    expect(out.task.id).toBe("task-1");
  });

  it("returns challenge_headers on 402", async () => {
    mockFetchFull(() => ({
      ok:      false,
      status:  402,
      headers: makeHeadersForEach({ "www-authenticate": 'Payment realm="AlgoVoi", id="abc123"' }),
      json:    async () => ({ request_id: "req-1" }),
    }));
    const out = await sendA2aMessage(parseSendA2aMessage({ agent_url: "https://agent.example.com", text: "Hello" })) as any;
    expect(out.payment_required).toBe(true);
    expect(out.challenge_headers["www-authenticate"]).toMatch(/AlgoVoi/);
    expect(out.request_id).toBe("req-1");
  });

  it("returns error on non-200/402", async () => {
    mockFetchFull(() => ({
      ok:      false,
      status:  500,
      headers: makeHeadersForEach({}),
      json:    async () => ({}),
    }));
    const out = await sendA2aMessage(parseSendA2aMessage({ agent_url: "https://agent.example.com", text: "Hi" })) as any;
    expect(out.payment_required).toBe(false);
    expect(out.error).toMatch(/500/);
  });

  it("includes Authorization header when payment_proof supplied", async () => {
    let capturedInit: any;
    mockFetchFull((_, init) => {
      capturedInit = init;
      return { ok: true, status: 200, headers: makeHeadersForEach({}), json: async () => ({}) };
    });
    await sendA2aMessage(
      parseSendA2aMessage({ agent_url: "https://agent.example.com", text: "Hi", payment_proof: "proof-abc" })
    );
    expect(capturedInit.headers["Authorization"]).toBe("Payment proof-abc");
  });

  it("POSTs to {agent_url}/message:send", async () => {
    let capturedUrl = "";
    mockFetchFull((url) => {
      capturedUrl = url;
      return { ok: true, status: 200, headers: makeHeadersForEach({}), json: async () => ({}) };
    });
    await sendA2aMessage(parseSendA2aMessage({ agent_url: "https://agent.example.com/", text: "Hi" }));
    expect(capturedUrl).toBe("https://agent.example.com/message:send");
  });

  it("handles network error gracefully", async () => {
    // @ts-expect-error
    globalThis.fetch = vi.fn(async () => { throw new Error("ETIMEDOUT"); });
    const out = await sendA2aMessage(parseSendA2aMessage({ agent_url: "https://agent.example.com", text: "Hi" })) as any;
    expect(out.payment_required).toBe(false);
    expect(out.error).toMatch(/ETIMEDOUT/);
  });

  it("rejects http:// agent_url at parse time", () => {
    expect(() => parseSendA2aMessage({ agent_url: "http://bad.example.com", text: "Hi" }))
      .toThrow(ValidationError);
  });
});
