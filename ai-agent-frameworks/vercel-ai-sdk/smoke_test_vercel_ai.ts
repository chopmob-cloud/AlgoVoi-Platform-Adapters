/**
 * AlgoVoi Vercel AI SDK Adapter — two-phase smoke test
 * ======================================================
 *
 * Phase 1 — Challenge render (no live API needed)
 *   Verifies each protocol / network combination returns the correct 402
 *   challenge, and the payment tool returns challenge JSON with no proof.
 *
 * Phase 2 — Full on-chain round-trip
 *   Requires env vars: ALGOVOI_KEY, TENANT_ID, PAYOUT_ADDRESS, OPENAI_KEY
 *   Requires live AlgoVoi gateway + OpenAI API (@ai-sdk/openai installed)
 *
 * Usage:
 *   npx tsx smoke_test_vercel_ai.ts --phase 1
 *   ALGOVOI_KEY=algv_... TENANT_ID=... PAYOUT_ADDRESS=... OPENAI_KEY=sk-... \
 *     npx tsx smoke_test_vercel_ai.ts --phase 2
 */

import { AlgoVoiVercelAI } from "./vercel_ai_algovoi.js";

// ── Helpers ───────────────────────────────────────────────────────────────────

function ok(msg: string) {
  console.log(`  PASS  ${msg}`);
}
function fail(msg: string) {
  console.log(`  FAIL  ${msg}`);
}
function head(msg: string) {
  console.log(`\n${msg}`);
}

function b64(obj: unknown): string {
  return Buffer.from(JSON.stringify(obj)).toString("base64");
}

// ── Phase 1 cases ─────────────────────────────────────────────────────────────

const PHASE1_CASES: Array<{
  protocol: "mpp" | "x402" | "ap2";
  network: string;
  expectedHeader: string;
}> = [
  { protocol: "mpp", network: "algorand-mainnet", expectedHeader: "WWW-Authenticate" },
  { protocol: "mpp", network: "voi-mainnet",      expectedHeader: "WWW-Authenticate" },
  { protocol: "mpp", network: "hedera-mainnet",   expectedHeader: "WWW-Authenticate" },
  { protocol: "mpp", network: "stellar-mainnet",  expectedHeader: "WWW-Authenticate" },
  { protocol: "x402", network: "algorand-mainnet", expectedHeader: "X-PAYMENT-REQUIRED" },
  { protocol: "x402", network: "hedera-mainnet",   expectedHeader: "X-PAYMENT-REQUIRED" },
  { protocol: "ap2",  network: "algorand-mainnet", expectedHeader: "X-AP2-Cart-Mandate" },
  { protocol: "ap2",  network: "voi-mainnet",      expectedHeader: "X-AP2-Cart-Mandate" },
];

async function runPhase1(): Promise<number> {
  head("Phase 1 — challenge render (8 cases)");
  let failures = 0;

  for (const { protocol, network, expectedHeader } of PHASE1_CASES) {
    const label = `${protocol} / ${network}`;
    try {
      const gate = new AlgoVoiVercelAI({
        algovoiKey: "algv_smoke",
        tenantId: "smoke-tid",
        payoutAddress: "SMOKE_ADDR",
        protocol,
        network,
        amountMicrounits: 10_000,
      });

      const result = await gate.check({});
      if (!result.requiresPayment) throw new Error("Expected requiresPayment=true");

      const resp = result.as402Response();
      if (resp.status !== 402) throw new Error(`Expected 402, got ${resp.status}`);

      const header = result.challengeHeaders[expectedHeader];
      if (!header) throw new Error(`Missing ${expectedHeader} header`);

      // Validate structure (WWW-Authenticate is a plain string, not base64)
      if (protocol === "mpp") {
        if (!header.startsWith("Payment ")) throw new Error("Must start with 'Payment '");
        if (!header.includes("realm=")) throw new Error("Missing realm= in WWW-Authenticate");
        if (!header.includes("intent=")) throw new Error("Missing intent= in WWW-Authenticate");
      } else {
        const decoded = JSON.parse(Buffer.from(header, "base64").toString());
        if (protocol === "x402") {
          if (decoded.x402Version !== 1) throw new Error("Missing x402Version=1");
          if (!Array.isArray(decoded.accepts)) throw new Error("Missing accepts array");
        } else {
          if (decoded.type !== "CartMandate") throw new Error("Missing CartMandate type");
          if (decoded.ap2_version !== "0.1") throw new Error("Missing ap2_version=0.1");
        }
      }

      ok(label);
    } catch (e) {
      fail(`${label}: ${e}`);
      failures++;
    }
  }

  return failures;
}

async function runPhase1Tool(): Promise<number> {
  head("Phase 1 — tool challenge (3 cases)");
  let failures = 0;

  for (const protocol of ["mpp", "x402", "ap2"] as const) {
    const label = `tool / ${protocol}`;
    try {
      const gate = new AlgoVoiVercelAI({
        algovoiKey: "algv_smoke",
        tenantId: "smoke-tid",
        payoutAddress: "SMOKE_ADDR",
        protocol,
        network: "algorand-mainnet",
        amountMicrounits: 10_000,
      });

      const toolObj = gate.asTool(() => "premium content") as {
        execute: (args: { query: string; paymentProof: string }) => Promise<string>;
      };

      const out = await toolObj.execute({ query: "test", paymentProof: "" });
      const data = JSON.parse(out);
      if (data.error !== "payment_required") {
        throw new Error(`Expected payment_required, got: ${data.error}`);
      }

      ok(label);
    } catch (e) {
      fail(`${label}: ${e}`);
      failures++;
    }
  }

  return failures;
}

async function runPhase1Headers(): Promise<number> {
  head("Phase 1 — MPP WWW-Authenticate content (1 case)");
  let failures = 0;
  try {
    const gate = new AlgoVoiVercelAI({
      algovoiKey: "algv_smoke",
      tenantId: "smoke-tid",
      payoutAddress: "SMOKE_ADDR",
      protocol: "mpp",
      network: "algorand-mainnet",
    });

    const r = await gate.check({});
    const wwwAuth = r.challengeHeaders["WWW-Authenticate"];

    if (!wwwAuth.startsWith("Payment ")) throw new Error("Must start with 'Payment '");
    if (!wwwAuth.includes('intent="charge"')) throw new Error("Missing intent=charge");
    if (!wwwAuth.includes("id=")) throw new Error("Missing id=");
    if (!wwwAuth.includes("request=")) throw new Error("Missing request=");
    if (!wwwAuth.includes("expires=")) throw new Error("Missing expires=");

    ok("WWW-Authenticate content valid");
  } catch (e) {
    fail(`MPP header content: ${e}`);
    failures++;
  }
  return failures;
}

// ── Phase 2 ───────────────────────────────────────────────────────────────────

const PHASE2_NETWORKS = [
  "algorand-mainnet",
  "voi-mainnet",
  "hedera-mainnet",
  "stellar-mainnet",
];

async function runPhase2(): Promise<number> {
  const algovoiKey    = process.env.ALGOVOI_KEY    ?? "";
  const tenantId      = process.env.TENANT_ID      ?? "";
  const payoutAddress = process.env.PAYOUT_ADDRESS ?? "";
  const openaiKey     = process.env.OPENAI_KEY     ?? "";

  const missing = Object.entries({ ALGOVOI_KEY: algovoiKey, TENANT_ID: tenantId, PAYOUT_ADDRESS: payoutAddress, OPENAI_KEY: openaiKey })
    .filter(([, v]) => !v)
    .map(([k]) => k);

  if (missing.length) {
    console.log(`\nPhase 2 skipped — missing env vars: ${missing.join(", ")}`);
    return 0;
  }

  let failures = 0;
  head("Phase 2 — live on-chain verification (4 chains × MPP)");

  for (const network of PHASE2_NETWORKS) {
    const label = `mpp / ${network}`;
    try {
      const gate = new AlgoVoiVercelAI({
        algovoiKey,
        tenantId,
        payoutAddress,
        protocol: "mpp",
        network,
        amountMicrounits: 10_000,
      });

      const r1 = await gate.check({});
      if (!r1.requiresPayment) throw new Error("Expected 402 before payment");

      // Issue a test proof via AlgoVoi test endpoint
      const proofResp = await fetch(
        "https://gateway.algovoi.com/v1/test/issue-proof",
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-AlgoVoi-Key": algovoiKey,
          },
          body: JSON.stringify({
            tenant_id: tenantId,
            network,
            amount_microunits: 10_000,
            resource_id: "ai-function",
          }),
        }
      );
      const { proof } = (await proofResp.json()) as { proof: string };

      const r2 = await gate.check({
        Authorization: `Payment ${proof}`,
      });
      if (r2.requiresPayment) throw new Error("Expected verified after proof");

      ok(label);
    } catch (e) {
      fail(`${label}: ${e}`);
      failures++;
    }
  }

  // generateText() round-trip
  head("Phase 2 — generateText() via Vercel AI SDK");
  try {
    const { openai } = await import("@ai-sdk/openai");
    process.env.OPENAI_API_KEY = openaiKey;

    const gate = new AlgoVoiVercelAI({
      algovoiKey,
      tenantId,
      payoutAddress,
      protocol: "mpp",
      network: "algorand-mainnet",
      model: openai("gpt-4o-mini"),
    });

    const reply = await gate.generateText([
      { role: "user", content: "Reply with exactly: AlgoVoi Vercel AI OK" },
    ]);
    if (!reply || typeof reply !== "string") throw new Error("Expected non-empty string");
    ok(`generateText reply: ${reply.slice(0, 80)}`);
  } catch (e) {
    fail(`generateText(): ${e}`);
    failures++;
  }

  // Tool verified path
  head("Phase 2 — tool verified proof");
  try {
    const gate = new AlgoVoiVercelAI({
      algovoiKey,
      tenantId,
      payoutAddress,
      protocol: "mpp",
      network: "algorand-mainnet",
      amountMicrounits: 10_000,
    });

    const proofResp = await fetch(
      "https://gateway.algovoi.com/v1/test/issue-proof",
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-AlgoVoi-Key": algovoiKey,
        },
        body: JSON.stringify({
          tenant_id: tenantId,
          network: "algorand-mainnet",
          amount_microunits: 10_000,
          resource_id: "ai-function",
        }),
      }
    );
    const { proof } = (await proofResp.json()) as { proof: string };

    const toolObj = gate.asTool((q) => `Answer to: ${q}`) as {
      execute: (args: { query: string; paymentProof: string }) => Promise<string>;
    };
    const out = await toolObj.execute({
      query: "What is AlgoVoi?",
      paymentProof: proof,
    });
    if (!out.includes("Answer to")) throw new Error(`Unexpected output: ${out}`);
    ok(`tool output: ${out.slice(0, 80)}`);
  } catch (e) {
    fail(`tool verified: ${e}`);
    failures++;
  }

  return failures;
}

// ── Entry point ───────────────────────────────────────────────────────────────

async function main() {
  const phase = process.argv.includes("--phase") ?
    parseInt(process.argv[process.argv.indexOf("--phase") + 1], 10) : 1;

  let total = 0;
  total += await runPhase1();
  total += await runPhase1Tool();
  total += await runPhase1Headers();

  if (phase === 2) {
    total += await runPhase2();
  }

  if (total === 0) {
    console.log("\nAll smoke tests passed.\n");
    process.exit(0);
  } else {
    console.log(`\n${total} smoke test(s) failed.\n`);
    process.exit(1);
  }
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
