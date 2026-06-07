/**
 * Tier 2 recurring tests for native-typescript (zero test framework).
 *
 * Run with:
 *   npx tsx recurring_test.ts
 *   # or
 *   bun run recurring_test.ts
 *   # or compile + run:
 *   npx tsc && node recurring_test.js
 *
 * Mirrors the test surface in native-go's recurring_test.go,
 * native-php's recurring_test.php, and native-python's mocked
 * round-trip suite — same coverage, same shape.
 */

import {
  AlgoVoi,
  RECURRING_EVENT_TYPES,
  RECURRING_NETWORKS,
  isRecurringEvent,
  isRecurringNetwork,
  VERSION,
} from "./algovoi.ts";
import type { AuthorityCreateRequest } from "./algovoi.ts";

// ---------------------------------------------------------------------------
// Tiny test runner
// ---------------------------------------------------------------------------

const failures: string[] = [];

async function it(name: string, fn: () => void | Promise<void>): Promise<void> {
  try {
    await fn();
    console.log(`  PASS  ${name}`);
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e);
    failures.push(`${name}: ${msg}`);
    console.log(`  FAIL  ${name} — ${msg}`);
  }
}

function assertTrue(v: boolean, msg = "assertion failed"): void {
  if (!v) throw new Error(msg);
}

function assertEq<T>(want: T, got: T, msg = "eq"): void {
  if (Array.isArray(want) && Array.isArray(got)) {
    if (want.length !== got.length || want.some((w, i) => w !== got[i])) {
      throw new Error(`${msg}: want ${JSON.stringify(want)}, got ${JSON.stringify(got)}`);
    }
    return;
  }
  if (typeof want === "object" && want !== null) {
    if (JSON.stringify(want) !== JSON.stringify(got)) {
      throw new Error(`${msg}: want ${JSON.stringify(want)}, got ${JSON.stringify(got)}`);
    }
    return;
  }
  if (want !== got) {
    throw new Error(`${msg}: want ${String(want)}, got ${String(got)}`);
  }
}

// ---------------------------------------------------------------------------
// Mock fetch
// ---------------------------------------------------------------------------

interface CapturedRequest {
  method: string;
  url: string;
  body: unknown;
  headers: Record<string, string>;
}

function mockFetch(opts: {
  status: number;
  body: unknown;
  capture: { last?: CapturedRequest };
}): typeof fetch {
  return (async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = typeof input === "string" ? input : input.toString();
    const method = init?.method ?? "GET";
    let parsedBody: unknown = null;
    if (init?.body && typeof init.body === "string") {
      try {
        parsedBody = JSON.parse(init.body);
      } catch {
        parsedBody = init.body;
      }
    }
    const headers: Record<string, string> = {};
    if (init?.headers) {
      const h = init.headers as Record<string, string>;
      for (const k of Object.keys(h)) headers[k] = h[k];
    }
    opts.capture.last = { method, url, body: parsedBody, headers };
    const responseBody =
      typeof opts.body === "string" ? opts.body : JSON.stringify(opts.body);
    return new Response(responseBody, {
      status: opts.status,
      headers: { "Content-Type": "application/json" },
    });
  }) as typeof fetch;
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

async function runAll(): Promise<void> {
  console.log("\n[constants + helpers]");

  await it("VERSION is 1.2.0", () => {
    assertEq("1.2.0", VERSION);
  });

  await it("RECURRING_NETWORKS covers 7 mainnets + 7 testnets (14 total)", () => {
    assertEq(14, RECURRING_NETWORKS.length);
    const expect = [
      "algorand_mainnet", "algorand_testnet",
      "voi_mainnet", "voi_testnet",
      "base_mainnet", "base_sepolia",
      "tempo_mainnet", "tempo_testnet",
      "solana_mainnet", "solana_devnet",
      "hedera_mainnet", "hedera_testnet",
      "stellar_mainnet", "stellar_testnet",
    ];
    for (const n of expect) {
      assertTrue(isRecurringNetwork(n), `${n} should be recurring`);
    }
  });

  await it("isRecurringNetwork rejects ethereum / unknown", () => {
    assertEq(false, isRecurringNetwork("ethereum_mainnet"));
    assertEq(false, isRecurringNetwork("polygon_mainnet"));
    assertEq(false, isRecurringNetwork(""));
  });

  await it("RECURRING_EVENT_TYPES has all 8", () => {
    assertEq(8, RECURRING_EVENT_TYPES.length);
    const wanted = [
      "recurring.authority_created",
      "recurring.authority_activated",
      "recurring.authority_paused",
      "recurring.authority_resumed",
      "recurring.authority_revoked",
      "recurring.authority_expired",
      "subscription.charged",
      "subscription.payment_failed",
    ];
    for (const e of wanted) {
      assertTrue((RECURRING_EVENT_TYPES as readonly string[]).includes(e), `missing ${e}`);
    }
  });

  await it("isRecurringEvent classifies correctly", () => {
    assertEq(true, isRecurringEvent({ event_type: "subscription.charged" }));
    assertEq(true, isRecurringEvent({ event_type: "recurring.authority_revoked" }));
    assertEq(true, isRecurringEvent({ type: "subscription.payment_failed" }));
    assertEq(false, isRecurringEvent({ event_type: "payment.succeeded" }));
    assertEq(false, isRecurringEvent({}));
    assertEq(false, isRecurringEvent(null));
    assertEq(false, isRecurringEvent({ event_type: 12345 }));
  });

  // -------------------------------------------------------------------------
  // Input validation — must short-circuit BEFORE the wire
  // -------------------------------------------------------------------------

  console.log("\n[input validation]");

  function makeClient(): { av: AlgoVoi; capture: { last?: CapturedRequest } } {
    const capture: { last?: CapturedRequest } = {};
    const av = new AlgoVoi({
      api_base: "https://api.example.com",
      api_key: "algv_k",
      tenant_id: "t-uuid",
      webhook_secret: "whsec_test",
      fetch: mockFetch({ status: 200, body: {}, capture }),
    });
    return { av, capture };
  }

  function baseReq(): AuthorityCreateRequest {
    return {
      subscription_id: "sub-uuid",
      chain: "algorand_mainnet",
      customer_wallet_address: "X",
      cap_amount_minor: 120_000_000,
      cap_period_seconds: 365 * 86400,
      per_cycle_amount_minor: 10_000_000,
    };
  }

  await it("createRecurringAuthority rejects unknown chain (no HTTP)", async () => {
    const { av, capture } = makeClient();
    const req = { ...baseReq(), chain: "ethereum_mainnet" };
    const r = await av.createRecurringAuthority(req);
    assertEq(null, r);
    assertEq(undefined, capture.last);
  });

  await it("createRecurringAuthority rejects empty subscription_id", async () => {
    const { av, capture } = makeClient();
    const r = await av.createRecurringAuthority({ ...baseReq(), subscription_id: "" });
    assertEq(null, r);
    assertEq(undefined, capture.last);
  });

  await it("createRecurringAuthority rejects period < 1 day", async () => {
    const { av, capture } = makeClient();
    const r = await av.createRecurringAuthority({ ...baseReq(), cap_period_seconds: 3600 });
    assertEq(null, r);
    assertEq(undefined, capture.last);
  });

  await it("createRecurringAuthority rejects per_cycle > cap", async () => {
    const { av, capture } = makeClient();
    const r = await av.createRecurringAuthority({
      ...baseReq(),
      cap_amount_minor: 10,
      per_cycle_amount_minor: 100,
    });
    assertEq(null, r);
    assertEq(undefined, capture.last);
  });

  await it("createRecurringAuthority rejects non-integer amounts", async () => {
    const { av, capture } = makeClient();
    const r = await av.createRecurringAuthority({ ...baseReq(), cap_amount_minor: 1.5 });
    assertEq(null, r);
    assertEq(undefined, capture.last);
  });

  await it("getAuthority rejects empty / oversize id", async () => {
    const { av } = makeClient();
    assertEq(null, await av.getAuthority(""));
    assertEq(null, await av.getAuthority("a".repeat(100)));
  });

  await it("listAuthorities rejects oversize limit + bad status", async () => {
    const { av } = makeClient();
    assertEq(null, await av.listAuthorities({ limit: 500 }));
    assertEq(null, await av.listAuthorities({ status: "bad-status!" }));
    assertEq(null, await av.listAuthorities({ offset: -1 }));
  });

  await it("manualPull rejects non-positive / non-integer amount", async () => {
    const { av } = makeClient();
    assertEq(null, await av.manualPull({ authority_id: "a", amount_minor: 0 }));
    assertEq(null, await av.manualPull({ authority_id: "a", amount_minor: -1 }));
    assertEq(null, await av.manualPull({ authority_id: "a", amount_minor: 1.5 }));
  });

  await it("plaintext HTTP refused (no fetch call)", async () => {
    const capture: { last?: CapturedRequest } = {};
    const av = new AlgoVoi({
      api_base: "http://example.com",
      api_key: "k",
      tenant_id: "t",
      webhook_secret: "s",
      fetch: mockFetch({ status: 200, body: {}, capture }),
    });
    assertEq(null, await av.getAuthority("a1"));
    assertEq(null, await av.createRecurringAuthority(baseReq()));
    assertEq(undefined, capture.last);
  });

  // -------------------------------------------------------------------------
  // Mocked HTTP round-trips
  // -------------------------------------------------------------------------

  console.log("\n[mocked HTTP round-trips]");

  await it("createRecurringAuthority POSTs correct URL + headers + body", async () => {
    const capture: { last?: CapturedRequest } = {};
    const responseBody = {
      authority: {
        id: "auth-uuid",
        tenant_id: "t-uuid",
        subscription_id: "sub-uuid",
        chain: "algorand_mainnet",
        customer_wallet_address: "X",
        cap_amount_minor: 120_000_000,
        cap_period_seconds: 31_536_000,
        per_cycle_amount_minor: 10_000_000,
        asset: "USDC",
        status: "pending",
        cap_remaining_minor: 120_000_000,
        cycles_pulled: 0,
        cycles_failed: 0,
        created_at: "2026-05-07T00:00:00Z",
      },
      customer_signing_payload: {
        version: "algorand_spending_cap_vault_v1",
        actions: [{ id: "deploy_vault" }],
      },
      authorisation_url: null,
    };
    const av = new AlgoVoi({
      api_base: "https://api.example.com",
      api_key: "algv_k",
      tenant_id: "t-uuid",
      webhook_secret: "ws",
      fetch: mockFetch({ status: 201, body: responseBody, capture }),
    });

    const resp = await av.createRecurringAuthority(baseReq());
    assertTrue(resp !== null);
    assertEq("auth-uuid", resp!.authority.id);
    assertEq("pending", resp!.authority.status);
    assertEq("algorand_spending_cap_vault_v1", (resp!.customer_signing_payload as Record<string, unknown>).version as string);

    const cap = capture.last!;
    assertEq("POST", cap.method);
    assertEq("https://api.example.com/v1/recurring/authorities", cap.url);
    const body = cap.body as Record<string, unknown>;
    assertEq("algorand_mainnet", body.chain as string);
    assertEq(120_000_000, body.cap_amount_minor as number);
    assertEq("USDC", body.asset as string, "asset default");
    assertEq("Bearer algv_k", cap.headers.Authorization);
    assertEq("t-uuid", cap.headers["X-Tenant-Id"]);
  });

  await it("listAuthorities GETs with query string", async () => {
    const capture: { last?: CapturedRequest } = {};
    const av = new AlgoVoi({
      api_base: "https://api.example.com",
      api_key: "k",
      tenant_id: "t",
      webhook_secret: "s",
      fetch: mockFetch({
        status: 200,
        body: [{ id: "a1", status: "active", chain: "base_mainnet", cycles_pulled: 3 }],
        capture,
      }),
    });

    const list = await av.listAuthorities({ status: "active", limit: 10 });
    assertTrue(list !== null);
    assertEq(1, list!.length);
    assertEq("a1", list![0].id);
    assertEq(3, list![0].cycles_pulled);

    const cap = capture.last!;
    assertEq("GET", cap.method);
    assertTrue(cap.url.includes("limit=10"), "limit in query");
    assertTrue(cap.url.includes("status=active"), "status in query");
    assertEq(null, cap.body);
  });

  await it("getAuthority GETs /v1/recurring/authorities/{id}", async () => {
    const capture: { last?: CapturedRequest } = {};
    const av = new AlgoVoi({
      api_base: "https://api.example.com",
      api_key: "k",
      tenant_id: "t",
      webhook_secret: "s",
      fetch: mockFetch({
        status: 200,
        body: { id: "a1", status: "active", cap_remaining_minor: 110_000_000 },
        capture,
      }),
    });
    const a = await av.getAuthority("a1");
    assertTrue(a !== null);
    assertEq("active", a!.status);
    assertEq(110_000_000, a!.cap_remaining_minor);
    const cap = capture.last!;
    assertEq("GET", cap.method);
    assertEq("https://api.example.com/v1/recurring/authorities/a1", cap.url);
  });

  await it("revokeAuthority POSTs to /revoke", async () => {
    const capture: { last?: CapturedRequest } = {};
    const av = new AlgoVoi({
      api_base: "https://api.example.com",
      api_key: "k",
      tenant_id: "t",
      webhook_secret: "s",
      fetch: mockFetch({
        status: 200,
        body: { id: "a1", status: "revoking" },
        capture,
      }),
    });
    const r = await av.revokeAuthority("a1");
    assertEq("revoking", r!.status);
    assertTrue(capture.last!.url.endsWith("/revoke"));
    assertEq("POST", capture.last!.method);
  });

  await it("confirmAuthority forwards optional first_cycle_due_at", async () => {
    const capture: { last?: CapturedRequest } = {};
    const av = new AlgoVoi({
      api_base: "https://api.example.com",
      api_key: "k",
      tenant_id: "t",
      webhook_secret: "s",
      fetch: mockFetch({
        status: 200,
        body: { id: "a1", status: "active" },
        capture,
      }),
    });
    await av.confirmAuthority("a1", {
      on_chain_address: "app:12345",
      first_cycle_due_at: "2026-06-07T00:00:00Z",
    });
    const body = capture.last!.body as Record<string, unknown>;
    assertEq("app:12345", body.on_chain_address);
    assertEq("2026-06-07T00:00:00Z", body.first_cycle_due_at);
  });

  await it("non-2xx returns null", async () => {
    const capture: { last?: CapturedRequest } = {};
    const av = new AlgoVoi({
      api_base: "https://api.example.com",
      api_key: "k",
      tenant_id: "t",
      webhook_secret: "s",
      fetch: mockFetch({
        status: 403,
        body: { error: "forbidden" },
        capture,
      }),
    });
    assertEq(null, await av.getAuthority("a1"));
  });

  // -------------------------------------------------------------------------
  // Webhook verification — real WebCrypto path
  // -------------------------------------------------------------------------

  console.log("\n[webhook verification]");

  await it("verifyWebhook accepts a correctly-signed body", async () => {
    const av = new AlgoVoi({
      api_base: "https://api.example.com",
      api_key: "k",
      tenant_id: "t",
      webhook_secret: "whsec_test",
    });
    const body = JSON.stringify({ event_type: "subscription.charged", authority_id: "a1" });
    const key = await crypto.subtle.importKey(
      "raw",
      new TextEncoder().encode("whsec_test") as unknown as BufferSource,
      { name: "HMAC", hash: "SHA-256" },
      false,
      ["sign"],
    );
    const sig = await crypto.subtle.sign(
      "HMAC",
      key,
      new TextEncoder().encode(body) as unknown as BufferSource,
    );
    // Universal base64 — works in Node 18+, Bun, Deno, browsers.
    const sigBytes = new Uint8Array(sig);
    let bin = "";
    for (let i = 0; i < sigBytes.length; i++) bin += String.fromCharCode(sigBytes[i]);
    const sigB64 = btoa(bin);

    const result = await av.verifyWebhook(body, sigB64);
    assertTrue(result !== null);
    assertEq("subscription.charged", (result as Record<string, unknown>).event_type as string);
    assertTrue(isRecurringEvent(result), "should classify as recurring");
  });

  await it("verifyWebhook rejects wrong signature", async () => {
    const av = new AlgoVoi({
      api_base: "https://api.example.com",
      api_key: "k",
      tenant_id: "t",
      webhook_secret: "whsec_test",
    });
    const body = JSON.stringify({ event_type: "payment.succeeded" });
    const result = await av.verifyWebhook(body, "wrong-sig");
    assertEq(null, result);
  });

  await it("verifyWebhook rejects oversized body", async () => {
    const av = new AlgoVoi({
      api_base: "https://api.example.com",
      api_key: "k",
      tenant_id: "t",
      webhook_secret: "whsec_test",
    });
    const oversize = "x".repeat(100_000);
    assertEq(null, await av.verifyWebhook(oversize, "any-sig"));
  });

  await it("verifyWebhook rejects empty signature", async () => {
    const av = new AlgoVoi({
      api_base: "https://api.example.com",
      api_key: "k",
      tenant_id: "t",
      webhook_secret: "whsec_test",
    });
    assertEq(null, await av.verifyWebhook("{}", ""));
  });

  // -------------------------------------------------------------------------
  // Summary — throw on failure so the runtime (Node / Bun / Deno) exits non-zero
  // -------------------------------------------------------------------------

  console.log("");
  if (failures.length > 0) {
    console.log(`${failures.length} FAILED`);
    for (const f of failures) console.log(`  - ${f}`);
    throw new Error(`${failures.length} test(s) failed`);
  }
  console.log("ALL TESTS PASS");
}

runAll().catch((e) => {
  console.error("\nTest run failed:", e instanceof Error ? e.message : String(e));
  // Re-throw so the JS runtime exits with a non-zero code naturally.
  // (Avoids relying on Node's `process.exit` — keeps the file portable
  //  to browsers / Bun / Deno without @types/node.)
  throw e;
});
