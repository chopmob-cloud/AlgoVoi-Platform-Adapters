/**
 * AlgoVoi Vercel AI SDK Adapter — unit tests
 *
 * All network calls (blockchain indexers) and AI SDK calls are mocked.
 * No live API keys or network access required.
 *
 * Run:  npx vitest run
 */

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

// ── vi.hoisted ensures mock fns are available when vi.mock factory runs ───────

const { mockGenerateTextFn, mockStreamTextFn, mockToolFn } = vi.hoisted(() => ({
  mockGenerateTextFn: vi.fn(),
  mockStreamTextFn: vi.fn(),
  mockToolFn: vi.fn((opts: unknown) => opts),
}));

vi.mock("ai", () => ({
  generateText: mockGenerateTextFn,
  streamText: mockStreamTextFn,
  tool: mockToolFn,
}));

// ── Import adapter after mock registration ────────────────────────────────────

import { AlgoVoiVercelAI, VercelAIResult, VERSION } from "./vercel_ai_algovoi";

// ── Fetch mock ────────────────────────────────────────────────────────────────

const mockFetch = vi.fn();

// ── Helpers ───────────────────────────────────────────────────────────────────

function b64(obj: unknown): string {
  return Buffer.from(JSON.stringify(obj)).toString("base64");
}

function makeAlgorandTxResp(
  receiver: string,
  amount: number,
  assetId: number,
  confirmedRound = 12345678
) {
  return {
    ok: true,
    json: async () => ({
      transaction: {
        "confirmed-round": confirmedRound,
        sender: "SENDERADDRESS",
        "asset-transfer-transaction": {
          receiver,
          amount,
          "asset-id": assetId,
        },
      },
    }),
  };
}

function makeHederaTxResp(
  payoutAddress: string,
  amount: number,
  tokenId = "0.0.456858"
) {
  return {
    ok: true,
    json: async () => ({
      transactions: [
        {
          result: "SUCCESS",
          token_transfers: [
            { token_id: tokenId, account: "PAYER", amount: -amount },
            { token_id: tokenId, account: payoutAddress, amount },
          ],
        },
      ],
    }),
  };
}

function makeStellarTxResp(payoutAddress: string, amount: string) {
  return {
    ok: true,
    json: async () => ({
      _embedded: {
        records: [
          {
            type: "payment",
            to: payoutAddress,
            from: "STELLARPAYER",
            asset_code: "USDC",
            asset_issuer:
              "GA5ZSEJYB37JRC5AVCIA5MOP4RHTM335X2KGX3IHOJAPP5RE34K4KZVN",
            amount,
          },
        ],
      },
    }),
  };
}

function mppCredential(txId: string, network = "algorand-mainnet"): string {
  return b64({ payload: { txId }, network });
}

function x402Proof(txId: string): string {
  return b64({ payload: { signature: { txId } } });
}

function ap2Mandate(txId: string, network = "algorand-mainnet"): string {
  return b64({
    ap2_version: "0.1",
    type: "PaymentMandate",
    payment_response: {
      method_name:
        "https://api1.ilovechicken.co.uk/ap2/extensions/crypto-algo/v1",
      details: { network, tx_id: txId },
    },
    signature: "fakesig",
  });
}

const PAYOUT = "ZVLRVYQSLJNVFMOIOKT35XH5SNQG45IVFMLLRFLHDQJQA5TO5H3SO4TVDQ";
const TENANT = "smoke-tenant-uuid";
const KEY = "algv_smokekey";
const TX = "TESTXYZ123TXID";

function makeMppGate(overrides: Partial<ConstructorParameters<typeof AlgoVoiVercelAI>[0]> = {}) {
  return new AlgoVoiVercelAI({
    algovoiKey: KEY,
    tenantId: TENANT,
    payoutAddress: PAYOUT,
    protocol: "mpp",
    network: "algorand-mainnet",
    amountMicrounits: 10_000,
    ...overrides,
  });
}

function makeX402Gate(overrides: Partial<ConstructorParameters<typeof AlgoVoiVercelAI>[0]> = {}) {
  return new AlgoVoiVercelAI({
    algovoiKey: KEY,
    tenantId: TENANT,
    payoutAddress: PAYOUT,
    protocol: "x402",
    network: "algorand-mainnet",
    amountMicrounits: 10_000,
    ...overrides,
  });
}

function makeAp2Gate(overrides: Partial<ConstructorParameters<typeof AlgoVoiVercelAI>[0]> = {}) {
  return new AlgoVoiVercelAI({
    algovoiKey: KEY,
    tenantId: TENANT,
    payoutAddress: PAYOUT,
    protocol: "ap2",
    network: "algorand-mainnet",
    amountMicrounits: 10_000,
    ...overrides,
  });
}

// ── Setup / teardown ──────────────────────────────────────────────────────────

beforeEach(() => {
  vi.stubGlobal("fetch", mockFetch);
  mockFetch.mockReset();
  mockGenerateTextFn.mockReset();
  mockStreamTextFn.mockReset();
  mockToolFn.mockClear();
});

afterEach(() => {
  vi.unstubAllGlobals();
});

// ─────────────────────────────────────────────────────────────────────────────
// VercelAIResult
// ─────────────────────────────────────────────────────────────────────────────

describe("VercelAIResult", () => {
  it("requiresPayment=false is falsy", () => {
    const r = new VercelAIResult({ requiresPayment: false });
    expect(r.requiresPayment).toBe(false);
  });

  it("requiresPayment=true is truthy", () => {
    const r = new VercelAIResult({ requiresPayment: true });
    expect(r.requiresPayment).toBe(true);
  });

  it("as402Response() returns status 402", () => {
    const r = new VercelAIResult({ requiresPayment: true });
    expect(r.as402Response().status).toBe(402);
  });

  it("as402Response() sets Content-Type header", () => {
    const r = new VercelAIResult({ requiresPayment: true });
    expect(r.as402Response().headers.get("Content-Type")).toBe("application/json");
  });

  it("as402Response() includes custom 402 headers", () => {
    const r = new VercelAIResult({
      requiresPayment: true,
      headers402: { "WWW-Authenticate": "Payment realm=test" },
    });
    expect(r.as402Response().headers.get("WWW-Authenticate")).toBe("Payment realm=test");
  });

  it("challengeHeaders exposes protocol headers", () => {
    const r = new VercelAIResult({
      requiresPayment: true,
      headers402: { "X-PAYMENT-REQUIRED": "abc123" },
    });
    expect(r.challengeHeaders["X-PAYMENT-REQUIRED"]).toBe("abc123");
  });

  it("error is exposed on result", () => {
    const r = new VercelAIResult({ requiresPayment: true, error: "Bad proof" });
    expect(r.error).toBe("Bad proof");
  });
});

// ─────────────────────────────────────────────────────────────────────────────
// VERSION
// ─────────────────────────────────────────────────────────────────────────────

describe("VERSION", () => {
  it("is a semver string", () => {
    expect(VERSION).toMatch(/^\d+\.\d+\.\d+$/);
  });
});

// ─────────────────────────────────────────────────────────────────────────────
// MPP — check() no credential
// ─────────────────────────────────────────────────────────────────────────────

describe("MPP check() — no credential", () => {
  it("returns requiresPayment=true with no Authorization header", async () => {
    const gate = makeMppGate();
    const r = await gate.check({});
    expect(r.requiresPayment).toBe(true);
  });

  it("sets WWW-Authenticate header", async () => {
    const gate = makeMppGate();
    const r = await gate.check({});
    expect(r.challengeHeaders["WWW-Authenticate"]).toMatch(/^Payment /);
  });

  it("WWW-Authenticate contains realm", async () => {
    const gate = makeMppGate();
    const r = await gate.check({});
    expect(r.challengeHeaders["WWW-Authenticate"]).toContain("realm=");
  });

  it("WWW-Authenticate contains id (HMAC)", async () => {
    const gate = makeMppGate();
    const r = await gate.check({});
    expect(r.challengeHeaders["WWW-Authenticate"]).toContain("id=");
  });

  it("WWW-Authenticate contains intent=charge", async () => {
    const gate = makeMppGate();
    const r = await gate.check({});
    expect(r.challengeHeaders["WWW-Authenticate"]).toContain('intent="charge"');
  });

  it("WWW-Authenticate contains request= (base64)", async () => {
    const gate = makeMppGate();
    const r = await gate.check({});
    expect(r.challengeHeaders["WWW-Authenticate"]).toContain("request=");
  });

  it("WWW-Authenticate contains expires=", async () => {
    const gate = makeMppGate();
    const r = await gate.check({});
    expect(r.challengeHeaders["WWW-Authenticate"]).toContain("expires=");
  });

  it("sets X-Payment-Required header", async () => {
    const gate = makeMppGate();
    const r = await gate.check({});
    expect(r.challengeHeaders["X-Payment-Required"]).toBeTruthy();
  });

  it("as402Response() status 402", async () => {
    const gate = makeMppGate();
    const r = await gate.check({});
    expect(r.as402Response().status).toBe(402);
  });

  it("accepts Headers object", async () => {
    const gate = makeMppGate();
    const r = await gate.check(new Headers());
    expect(r.requiresPayment).toBe(true);
  });

  it("accepts case-insensitive header keys", async () => {
    const gate = makeMppGate();
    const r = await gate.check({ AUTHORIZATION: "" });
    expect(r.requiresPayment).toBe(true);
  });
});

// ─────────────────────────────────────────────────────────────────────────────
// MPP — check() with credential
// ─────────────────────────────────────────────────────────────────────────────

describe("MPP check() — credential parsing", () => {
  it("invalid base64 credential returns 402", async () => {
    const gate = makeMppGate();
    const r = await gate.check({ Authorization: "Payment !!invalid!!" });
    expect(r.requiresPayment).toBe(true);
    expect(r.error).toContain("Invalid credential");
  });

  it("missing txId returns 402", async () => {
    const gate = makeMppGate();
    const credential = b64({ payload: {} });
    const r = await gate.check({ Authorization: `Payment ${credential}` });
    expect(r.requiresPayment).toBe(true);
    expect(r.error).toContain("txId");
  });

  it("txId longer than 200 chars returns 402", async () => {
    const gate = makeMppGate();
    const credential = b64({ payload: { txId: "X".repeat(201) } });
    const r = await gate.check({ Authorization: `Payment ${credential}` });
    expect(r.requiresPayment).toBe(true);
  });

  it("verification failure returns 402", async () => {
    mockFetch.mockResolvedValueOnce({ ok: false });
    const gate = makeMppGate();
    const r = await gate.check({
      Authorization: `Payment ${mppCredential(TX)}`,
    });
    expect(r.requiresPayment).toBe(true);
    expect(r.error).toContain("verification failed");
  });

  it("verified payment returns requiresPayment=false", async () => {
    mockFetch.mockResolvedValueOnce(
      makeAlgorandTxResp(PAYOUT, 10_000, 31566704)
    );
    const gate = makeMppGate();
    const r = await gate.check({
      Authorization: `Payment ${mppCredential(TX)}`,
    });
    expect(r.requiresPayment).toBe(false);
  });

  it("replay attack — same txId rejected second time", async () => {
    mockFetch
      .mockResolvedValueOnce(makeAlgorandTxResp(PAYOUT, 10_000, 31566704))
      .mockResolvedValueOnce(makeAlgorandTxResp(PAYOUT, 10_000, 31566704));
    const gate = makeMppGate();
    const cred = mppCredential(TX);
    await gate.check({ Authorization: `Payment ${cred}` });
    const r2 = await gate.check({ Authorization: `Payment ${cred}` });
    expect(r2.requiresPayment).toBe(true);
    expect(r2.error).toContain("already used");
  });

  it("accepts x-payment header as alternative to Authorization", async () => {
    mockFetch.mockResolvedValueOnce(
      makeAlgorandTxResp(PAYOUT, 10_000, 31566704)
    );
    const gate = makeMppGate();
    const r = await gate.check({ "x-payment": mppCredential(TX) });
    expect(r.requiresPayment).toBe(false);
  });

  it("amount below threshold returns 402", async () => {
    mockFetch.mockResolvedValueOnce(
      makeAlgorandTxResp(PAYOUT, 1, 31566704) // 1 microunit — too small
    );
    const gate = makeMppGate();
    const r = await gate.check({
      Authorization: `Payment ${mppCredential(TX)}`,
    });
    expect(r.requiresPayment).toBe(true);
  });

  it("wrong payout address returns 402", async () => {
    mockFetch.mockResolvedValueOnce(
      makeAlgorandTxResp("WRONGADDRESS", 10_000, 31566704)
    );
    const gate = makeMppGate();
    const r = await gate.check({
      Authorization: `Payment ${mppCredential(TX)}`,
    });
    expect(r.requiresPayment).toBe(true);
  });

  it("wrong asset-id returns 402", async () => {
    mockFetch.mockResolvedValueOnce(
      makeAlgorandTxResp(PAYOUT, 10_000, 999999) // wrong ASA
    );
    const gate = makeMppGate();
    const r = await gate.check({
      Authorization: `Payment ${mppCredential(TX)}`,
    });
    expect(r.requiresPayment).toBe(true);
  });
});

// ─────────────────────────────────────────────────────────────────────────────
// MPP — network routing
// ─────────────────────────────────────────────────────────────────────────────

describe("MPP — network routing", () => {
  it("routes VOI to VOI indexer", async () => {
    mockFetch.mockResolvedValueOnce(makeAlgorandTxResp(PAYOUT, 10_000, 302190));
    const gate = makeMppGate({ network: "voi-mainnet" });
    const r = await gate.check({
      Authorization: `Payment ${mppCredential(TX, "voi-mainnet")}`,
    });
    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining("voi.nodely.dev"),
      expect.anything()
    );
    expect(r.requiresPayment).toBe(false);
  });

  it("routes Hedera to mirror node", async () => {
    mockFetch.mockResolvedValueOnce(makeHederaTxResp(PAYOUT, 10_000));
    const gate = makeMppGate({ network: "hedera-mainnet" });
    const r = await gate.check({
      Authorization: `Payment ${mppCredential(TX, "hedera-mainnet")}`,
    });
    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining("mirrornode.hedera.com"),
      expect.anything()
    );
    expect(r.requiresPayment).toBe(false);
  });

  it("routes Stellar to Horizon", async () => {
    mockFetch.mockResolvedValueOnce(makeStellarTxResp(PAYOUT, "0.0100000"));
    const gate = makeMppGate({ network: "stellar-mainnet" });
    const r = await gate.check({
      Authorization: `Payment ${mppCredential(TX, "stellar-mainnet")}`,
    });
    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining("horizon.stellar.org"),
      expect.anything()
    );
    expect(r.requiresPayment).toBe(false);
  });

  it("Hedera normalises @ in tx ID", async () => {
    mockFetch.mockResolvedValueOnce(makeHederaTxResp(PAYOUT, 10_000));
    const gate = makeMppGate({ network: "hedera-mainnet" });
    await gate.check({
      Authorization: `Payment ${mppCredential("0.0.1234@1234567890.000", "hedera-mainnet")}`,
    });
    // Should NOT contain @ in the URL
    expect(mockFetch).toHaveBeenCalledWith(
      expect.not.stringContaining("@"),
      expect.anything()
    );
  });

  it("Stellar decimal amount converted to microunits", async () => {
    mockFetch.mockResolvedValueOnce(makeStellarTxResp(PAYOUT, "0.0100000"));
    const gate = makeMppGate({ network: "stellar-mainnet" });
    const r = await gate.check({
      Authorization: `Payment ${mppCredential(TX, "stellar-mainnet")}`,
    });
    expect(r.requiresPayment).toBe(false);
  });
});

// ─────────────────────────────────────────────────────────────────────────────
// x402 Gate
// ─────────────────────────────────────────────────────────────────────────────

describe("x402 check() — no proof", () => {
  it("returns requiresPayment=true with no X-Payment header", async () => {
    const gate = makeX402Gate();
    const r = await gate.check({});
    expect(r.requiresPayment).toBe(true);
  });

  it("sets X-PAYMENT-REQUIRED header", async () => {
    const gate = makeX402Gate();
    const r = await gate.check({});
    expect(r.challengeHeaders["X-PAYMENT-REQUIRED"]).toBeTruthy();
  });

  it("X-PAYMENT-REQUIRED decodes to valid JSON with x402Version=1", async () => {
    const gate = makeX402Gate();
    const r = await gate.check({});
    const decoded = JSON.parse(
      Buffer.from(r.challengeHeaders["X-PAYMENT-REQUIRED"], "base64").toString()
    );
    expect(decoded.x402Version).toBe(1);
  });

  it("challenge accepts array contains CAIP-2 network", async () => {
    const gate = makeX402Gate();
    const r = await gate.check({});
    const decoded = JSON.parse(
      Buffer.from(r.challengeHeaders["X-PAYMENT-REQUIRED"], "base64").toString()
    );
    expect(decoded.accepts[0].network).toBe("algorand:mainnet");
  });

  it("challenge contains amount", async () => {
    const gate = makeX402Gate();
    const r = await gate.check({});
    const decoded = JSON.parse(
      Buffer.from(r.challengeHeaders["X-PAYMENT-REQUIRED"], "base64").toString()
    );
    expect(decoded.accepts[0].amount).toBe("10000");
  });
});

describe("x402 check() — with proof", () => {
  it("invalid base64 proof returns 402", async () => {
    const gate = makeX402Gate();
    const r = await gate.check({ "x-payment": "!!!invalid" });
    expect(r.requiresPayment).toBe(true);
    expect(r.error).toContain("Invalid proof");
  });

  it("missing txId in proof returns 402", async () => {
    const gate = makeX402Gate();
    const r = await gate.check({ "x-payment": b64({ payload: {} }) });
    expect(r.requiresPayment).toBe(true);
    expect(r.error).toContain("txId");
  });

  it("verified x402 proof returns requiresPayment=false", async () => {
    mockFetch.mockResolvedValueOnce(
      makeAlgorandTxResp(PAYOUT, 10_000, 31566704)
    );
    const gate = makeX402Gate();
    const r = await gate.check({ "x-payment": x402Proof(TX) });
    expect(r.requiresPayment).toBe(false);
  });

  it("x402 on Hedera routes to mirror node", async () => {
    mockFetch.mockResolvedValueOnce(makeHederaTxResp(PAYOUT, 10_000));
    const gate = makeX402Gate({ network: "hedera-mainnet" });
    await gate.check({ "x-payment": x402Proof(TX) });
    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining("mirrornode.hedera.com"),
      expect.anything()
    );
  });
});

// ─────────────────────────────────────────────────────────────────────────────
// AP2 Gate
// ─────────────────────────────────────────────────────────────────────────────

describe("AP2 check() — no mandate", () => {
  it("returns requiresPayment=true with no AP2 header", async () => {
    const gate = makeAp2Gate();
    const r = await gate.check({});
    expect(r.requiresPayment).toBe(true);
  });

  it("sets X-AP2-Cart-Mandate header", async () => {
    const gate = makeAp2Gate();
    const r = await gate.check({});
    expect(r.challengeHeaders["X-AP2-Cart-Mandate"]).toBeTruthy();
  });

  it("CartMandate decodes to valid AP2 structure", async () => {
    const gate = makeAp2Gate();
    const r = await gate.check({});
    const decoded = JSON.parse(
      Buffer.from(
        r.challengeHeaders["X-AP2-Cart-Mandate"],
        "base64"
      ).toString()
    );
    expect(decoded.type).toBe("CartMandate");
    expect(decoded.ap2_version).toBe("0.1");
  });

  it("CartMandate contains merchant_id", async () => {
    const gate = makeAp2Gate();
    const r = await gate.check({});
    const decoded = JSON.parse(
      Buffer.from(
        r.challengeHeaders["X-AP2-Cart-Mandate"],
        "base64"
      ).toString()
    );
    expect(decoded.merchant_id).toBe(TENANT);
  });

  it("CartMandate body field present in bodyJson", async () => {
    const gate = makeAp2Gate();
    const r = await gate.check({});
    // Body can be read via as402Response()
    const body = await r.as402Response().json();
    expect(body.cart_mandate).toBeTruthy();
  });
});

describe("AP2 check() — with mandate", () => {
  it("valid mandate from X-AP2-Mandate header returns requiresPayment=false", async () => {
    mockFetch.mockResolvedValueOnce(
      makeAlgorandTxResp(PAYOUT, 10_000, 31566704)
    );
    const gate = makeAp2Gate();
    const r = await gate.check({ "x-ap2-mandate": ap2Mandate(TX) });
    expect(r.requiresPayment).toBe(false);
  });

  it("valid mandate from x-ap2-payment-mandate header", async () => {
    mockFetch.mockResolvedValueOnce(
      makeAlgorandTxResp(PAYOUT, 10_000, 31566704)
    );
    const gate = makeAp2Gate();
    const r = await gate.check({
      "x-ap2-payment-mandate": ap2Mandate(TX),
    });
    expect(r.requiresPayment).toBe(false);
  });

  it("valid mandate from request body", async () => {
    mockFetch.mockResolvedValueOnce(
      makeAlgorandTxResp(PAYOUT, 10_000, 31566704)
    );
    const gate = makeAp2Gate();
    const body = {
      ap2_mandate: {
        ap2_version: "0.1",
        type: "PaymentMandate",
        payment_response: {
          details: { network: "algorand-mainnet", tx_id: TX },
        },
      },
    };
    const r = await gate.check({}, body);
    expect(r.requiresPayment).toBe(false);
  });

  it("missing tx_id in mandate returns 402", async () => {
    const gate = makeAp2Gate();
    const bad = b64({
      ap2_version: "0.1",
      type: "PaymentMandate",
      payment_response: { details: { network: "algorand-mainnet" } },
    });
    const r = await gate.check({ "x-ap2-mandate": bad });
    expect(r.requiresPayment).toBe(true);
    expect(r.error).toContain("tx_id");
  });
});

// ─────────────────────────────────────────────────────────────────────────────
// AlgoVoiVercelAI constructor
// ─────────────────────────────────────────────────────────────────────────────

describe("AlgoVoiVercelAI constructor", () => {
  it("defaults protocol to mpp", async () => {
    const gate = new AlgoVoiVercelAI({
      algovoiKey: KEY,
      tenantId: TENANT,
      payoutAddress: PAYOUT,
    });
    const r = await gate.check({});
    // MPP uses WWW-Authenticate
    expect(r.challengeHeaders["WWW-Authenticate"]).toBeTruthy();
  });

  it("x402 protocol uses X-PAYMENT-REQUIRED", async () => {
    const gate = makeX402Gate();
    const r = await gate.check({});
    expect(r.challengeHeaders["X-PAYMENT-REQUIRED"]).toBeTruthy();
  });

  it("ap2 protocol uses X-AP2-Cart-Mandate", async () => {
    const gate = makeAp2Gate();
    const r = await gate.check({});
    expect(r.challengeHeaders["X-AP2-Cart-Mandate"]).toBeTruthy();
  });

  it("model accessor returns configured model", () => {
    const fakeModel = {} as unknown as import("ai").LanguageModel;
    const gate = new AlgoVoiVercelAI({
      algovoiKey: KEY,
      tenantId: TENANT,
      payoutAddress: PAYOUT,
      model: fakeModel,
    });
    expect(gate.model).toBe(fakeModel);
  });

  it("model accessor returns undefined when not set", () => {
    const gate = makeMppGate();
    expect(gate.model).toBeUndefined();
  });

  it("custom realm in MPP challenge", async () => {
    const gate = makeMppGate({ realm: "Premium AI Access" });
    const r = await gate.check({});
    expect(r.challengeHeaders["WWW-Authenticate"]).toContain("Premium AI Access");
  });

  it("custom amountMicrounits in x402 challenge", async () => {
    const gate = makeX402Gate({ amountMicrounits: 50_000 });
    const r = await gate.check({});
    const decoded = JSON.parse(
      Buffer.from(r.challengeHeaders["X-PAYMENT-REQUIRED"], "base64").toString()
    );
    expect(decoded.accepts[0].amount).toBe("50000");
  });
});

// ─────────────────────────────────────────────────────────────────────────────
// generateText()
// ─────────────────────────────────────────────────────────────────────────────

describe("generateText()", () => {
  const fakeModel = {} as unknown as import("ai").LanguageModel;

  it("throws when no model configured", async () => {
    const gate = makeMppGate();
    await expect(gate.generateText([])).rejects.toThrow("no model configured");
  });

  it("calls ai.generateText with model and messages", async () => {
    mockGenerateTextFn.mockResolvedValueOnce({ text: "Hello!" });
    const gate = makeMppGate({ model: fakeModel });
    const messages = [{ role: "user" as const, content: "Hi" }];
    await gate.generateText(messages);
    expect(mockGenerateTextFn).toHaveBeenCalledWith({
      model: fakeModel,
      messages,
    });
  });

  it("returns the text string from result", async () => {
    mockGenerateTextFn.mockResolvedValueOnce({ text: "DSPy is great" });
    const gate = makeMppGate({ model: fakeModel });
    const result = await gate.generateText([
      { role: "user", content: "What is DSPy?" },
    ]);
    expect(result).toBe("DSPy is great");
  });
});

// ─────────────────────────────────────────────────────────────────────────────
// streamText()
// ─────────────────────────────────────────────────────────────────────────────

describe("streamText()", () => {
  const fakeModel = {} as unknown as import("ai").LanguageModel;
  const fakeStream = { toDataStreamResponse: vi.fn() };

  it("throws when no model configured", () => {
    const gate = makeMppGate();
    expect(() => gate.streamText([])).toThrow("no model configured");
  });

  it("calls ai.streamText with model and messages", () => {
    mockStreamTextFn.mockReturnValueOnce(fakeStream);
    const gate = makeMppGate({ model: fakeModel });
    const messages = [{ role: "user" as const, content: "Stream this" }];
    gate.streamText(messages);
    expect(mockStreamTextFn).toHaveBeenCalledWith({ model: fakeModel, messages });
  });

  it("returns the stream result from ai.streamText", () => {
    mockStreamTextFn.mockReturnValueOnce(fakeStream);
    const gate = makeMppGate({ model: fakeModel });
    const result = gate.streamText([]);
    expect(result).toBe(fakeStream);
  });
});

// ─────────────────────────────────────────────────────────────────────────────
// asTool()
// ─────────────────────────────────────────────────────────────────────────────

describe("asTool()", () => {
  it("calls ai.tool() to construct the tool", () => {
    const gate = makeMppGate();
    gate.asTool(() => "result");
    expect(mockToolFn).toHaveBeenCalledOnce();
  });

  it("tool has a description", () => {
    const gate = makeMppGate();
    const t = gate.asTool(() => "result") as { description: string };
    expect(typeof t.description).toBe("string");
    expect(t.description.length).toBeGreaterThan(0);
  });

  it("custom tool description is used", () => {
    const gate = makeMppGate();
    const t = gate.asTool(() => "result", {
      toolDescription: "My custom tool",
    }) as { description: string };
    expect(t.description).toBe("My custom tool");
  });

  it("tool has a Zod parameters schema", () => {
    const gate = makeMppGate();
    const t = gate.asTool(() => "result") as {
      parameters: { shape: { query: unknown; paymentProof: unknown } };
    };
    expect(t.parameters).toBeTruthy();
    expect(t.parameters.shape.query).toBeTruthy();
    expect(t.parameters.shape.paymentProof).toBeTruthy();
  });

  it("execute returns payment challenge when no proof", async () => {
    const gate = makeMppGate();
    const t = gate.asTool(() => "premium content") as {
      execute: (args: { query: string; paymentProof: string }) => Promise<string>;
    };
    const out = await t.execute({ query: "test", paymentProof: "" });
    const data = JSON.parse(out);
    expect(data.error).toBe("payment_required");
  });

  it("execute calls resourceFn when payment verified", async () => {
    mockFetch.mockResolvedValueOnce(
      makeAlgorandTxResp(PAYOUT, 10_000, 31566704)
    );
    const gate = makeMppGate();
    const t = gate.asTool(() => "premium answer") as {
      execute: (args: { query: string; paymentProof: string }) => Promise<string>;
    };
    const out = await t.execute({
      query: "What is AlgoVoi?",
      paymentProof: mppCredential(TX + "TOOL"),
    });
    expect(out).toBe("premium answer");
  });

  it("execute handles async resourceFn", async () => {
    mockFetch.mockResolvedValueOnce(
      makeAlgorandTxResp(PAYOUT, 10_000, 31566704)
    );
    const gate = makeMppGate();
    const t = gate.asTool(async (q) => `async result: ${q}`) as {
      execute: (args: { query: string; paymentProof: string }) => Promise<string>;
    };
    const out = await t.execute({
      query: "hello",
      paymentProof: mppCredential(TX + "ASYNC"),
    });
    expect(out).toBe("async result: hello");
  });

  it("execute returns resource_error JSON on resourceFn throw", async () => {
    mockFetch.mockResolvedValueOnce(
      makeAlgorandTxResp(PAYOUT, 10_000, 31566704)
    );
    const gate = makeMppGate();
    const t = gate.asTool(() => {
      throw new Error("DB connection failed");
    }) as {
      execute: (args: { query: string; paymentProof: string }) => Promise<string>;
    };
    const out = await t.execute({
      query: "q",
      paymentProof: mppCredential(TX + "ERR"),
    });
    const data = JSON.parse(out);
    expect(data.error).toBe("resource_error");
    expect(data.detail).toContain("DB connection");
  });
});

// ─────────────────────────────────────────────────────────────────────────────
// nextHandler()
// ─────────────────────────────────────────────────────────────────────────────

describe("nextHandler()", () => {
  const fakeModel = {} as unknown as import("ai").LanguageModel;

  function makeRequest(
    body: unknown,
    headers: Record<string, string> = {}
  ): Request {
    return new Request("https://example.com/api/chat", {
      method: "POST",
      body: JSON.stringify(body),
      headers: { "Content-Type": "application/json", ...headers },
    });
  }

  it("returns 402 when payment required", async () => {
    const gate = makeMppGate({ model: fakeModel });
    const req = makeRequest({ messages: [] });
    const resp = await gate.nextHandler(req);
    expect(resp.status).toBe(402);
  });

  it("returns 200 when payment verified", async () => {
    mockFetch.mockResolvedValueOnce(
      makeAlgorandTxResp(PAYOUT, 10_000, 31566704)
    );
    mockGenerateTextFn.mockResolvedValueOnce({ text: "Hello!" });
    const gate = makeMppGate({ model: fakeModel });
    const req = makeRequest(
      { messages: [{ role: "user", content: "Hi" }] },
      { Authorization: `Payment ${mppCredential(TX + "NEXT")}` }
    );
    const resp = await gate.nextHandler(req);
    expect(resp.status).toBe(200);
  });

  it("response body contains content field on success", async () => {
    mockFetch.mockResolvedValueOnce(
      makeAlgorandTxResp(PAYOUT, 10_000, 31566704)
    );
    mockGenerateTextFn.mockResolvedValueOnce({ text: "AI response here" });
    const gate = makeMppGate({ model: fakeModel });
    const req = makeRequest(
      { messages: [{ role: "user", content: "Hello" }] },
      { Authorization: `Payment ${mppCredential(TX + "BODY")}` }
    );
    const resp = await gate.nextHandler(req);
    const body = await resp.json();
    expect(body.content).toBe("AI response here");
  });

  it("handles empty/invalid JSON body gracefully", async () => {
    const gate = makeMppGate({ model: fakeModel });
    const req = new Request("https://example.com/api/chat", {
      method: "POST",
      body: "not json",
      headers: { "Content-Type": "text/plain" },
    });
    const resp = await gate.nextHandler(req);
    expect(resp.status).toBe(402); // payment required (empty headers)
  });

  it("passes messages from body to generateText", async () => {
    mockFetch.mockResolvedValueOnce(
      makeAlgorandTxResp(PAYOUT, 10_000, 31566704)
    );
    mockGenerateTextFn.mockResolvedValueOnce({ text: "ok" });
    const gate = makeMppGate({ model: fakeModel });
    const messages = [{ role: "user" as const, content: "Test message" }];
    const req = makeRequest(
      { messages },
      { Authorization: `Payment ${mppCredential(TX + "MSG")}` }
    );
    await gate.nextHandler(req);
    expect(mockGenerateTextFn).toHaveBeenCalledWith({
      model: fakeModel,
      messages,
    });
  });

  it("sets Content-Type application/json on 200", async () => {
    mockFetch.mockResolvedValueOnce(
      makeAlgorandTxResp(PAYOUT, 10_000, 31566704)
    );
    mockGenerateTextFn.mockResolvedValueOnce({ text: "ok" });
    const gate = makeMppGate({ model: fakeModel });
    const req = makeRequest(
      { messages: [] },
      { Authorization: `Payment ${mppCredential(TX + "CT")}` }
    );
    const resp = await gate.nextHandler(req);
    expect(resp.headers.get("Content-Type")).toBe("application/json");
  });
});
