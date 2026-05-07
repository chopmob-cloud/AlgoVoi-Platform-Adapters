/**
 * AlgoVoi Native TypeScript — Usage Examples
 *
 * Shows how to integrate AlgoVoi payments into any TS / JS application.
 * Runs in any modern runtime (Node 18+, Bun, Deno, Cloudflare Workers,
 * Vercel Edge, browsers).
 *
 * Run:
 *   node --experimental-strip-types example.ts
 *   # or
 *   bun run example.ts
 *   # or
 *   deno run --allow-net example.ts
 */

import { AlgoVoi, RECURRING_EVENT_TYPES, RECURRING_NETWORKS, isRecurringEvent } from "./algovoi.ts";
import type { AuthorityCreateRequest } from "./algovoi.ts";

const av = new AlgoVoi({
  api_base: "https://api1.ilovechicken.co.uk",
  api_key: "algv_REPLACE_ME",
  tenant_id: "REPLACE_ME_UUID",
  webhook_secret: "whsec_REPLACE_ME",
});

// ---------------------------------------------------------------------------
// Tier 1 — one-shot hosted checkout (e.g. Express / Hono / Fastify handler)
// ---------------------------------------------------------------------------

async function exampleHostedCheckout(amount: number, network: string) {
  const result = await av.hostedCheckout(
    amount,
    "USD",
    `Order #${Date.now()}`,
    network,
    "https://yoursite.com/payment-return",
  );
  if (!result) throw new Error("Payment could not be initiated");
  // store result.token in session / DB for verification on return
  return result.checkout_url;
}

async function exampleVerifyReturn(token: string) {
  // CRITICAL: without this, a customer can cancel and still appear paid.
  return av.verifyHostedReturn(token);
}

// ---------------------------------------------------------------------------
// Tier 2 — standing-authority recurring (subscriptions)
// ---------------------------------------------------------------------------

/**
 * $10/month subscription, 12-month standing authority, on the customer's
 * chosen chain.
 */
async function exampleCreateAuthority(
  subscriptionID: string,
  customerWallet: string,
  chain: string,
) {
  // Cap amounts depend on chain decimals.
  // Most chains: 6 decimals. Stellar: 7 decimals.
  const isStellar = chain.startsWith("stellar_");
  const perCycle = isStellar ? 10 * 10_000_000 : 10 * 1_000_000;
  const totalCap = isStellar ? 120 * 10_000_000 : 120 * 1_000_000;

  const req: AuthorityCreateRequest = {
    subscription_id: subscriptionID,
    chain,
    customer_wallet_address: customerWallet,
    cap_amount_minor: totalCap,
    cap_period_seconds: 365 * 86400,
    per_cycle_amount_minor: perCycle,
    asset: "USDC",
    metadata: { plan: "monthly_pro", customer_email: "alice@example.com" },
  };

  const resp = await av.createRecurringAuthority(req);
  if (!resp) throw new Error("Authority creation failed");

  console.log(`[create] authority_id = ${resp.authority.id}`);
  console.log(`[create] status       = ${resp.authority.status}`);
  // Hand resp.customer_signing_payload to your frontend wallet UI.
  // The per-chain folders (Recurr/<chain>/README.md) document the format.
  return resp;
}

async function exampleConfirmAuthority(authorityID: string, onChainHandle: string) {
  // Most tenants don't need this — the AlgoVoi widget does it via
  // webhook. Surfaced for self-hosted wallet UIs.
  //
  // onChainHandle format depends on the chain:
  //   Algorand / VOI : "app:<application_id>"
  //   EVM            : "0x<tx_hash>"
  //   Solana         : "<base58 tx signature>"
  //   Hedera         : "<account_id>@<seconds>.<nanos>"
  //   Stellar        : "<64-char hex tx hash>"
  return av.confirmAuthority(authorityID, { on_chain_address: onChainHandle });
}

async function exampleInspect(authorityID: string) {
  const a = await av.getAuthority(authorityID);
  if (!a) {
    console.log("[inspect] not found");
    return;
  }
  console.log(
    `[inspect] status=${a.status} cycles=${a.cycles_pulled}/${a.cycles_pulled + a.cycles_failed} remaining=${a.cap_remaining_minor}`,
  );
}

async function exampleListActive() {
  const auths = await av.listAuthorities({ status: "active", limit: 50 });
  if (!auths) {
    console.log("[list] failed");
    return;
  }
  console.log(`[list] ${auths.length} active authorities`);
  for (const a of auths) {
    console.log(`    ${a.id}  chain=${a.chain}  cycles=${a.cycles_pulled}`);
  }
}

async function exampleRevoke(authorityID: string) {
  const r = await av.revokeAuthority(authorityID);
  if (!r) {
    console.log("[revoke] failed");
    return;
  }
  console.log(`[revoke] status = ${r.status}`); // 'revoking' → 'revoked'
}

// ---------------------------------------------------------------------------
// Webhook handler (Hono / Express / fetch-style)
// ---------------------------------------------------------------------------

async function exampleWebhookHandler(rawBody: string, signature: string): Promise<Response> {
  const payload = await av.verifyWebhook(rawBody, signature);
  if (!payload) return new Response("Unauthorized", { status: 401 });

  if (isRecurringEvent(payload)) {
    const eventType = (payload.event_type ?? "") as string;
    const authorityID = payload.authority_id as string | undefined;

    switch (eventType) {
      case "subscription.charged": {
        const txID = payload.tx_id as string | undefined;
        console.log(`[webhook] charged: authority=${authorityID} tx=${txID}`);
        // extend customer access here
        break;
      }
      case "subscription.payment_failed": {
        const reason = payload.failure_reason as string | undefined;
        console.log(`[webhook] failed: authority=${authorityID} reason=${reason}`);
        // dunning logic
        break;
      }
      case "recurring.authority_revoked":
        console.log(`[webhook] revoked: authority=${authorityID}`);
        // cancel the subscription
        break;
      case "recurring.authority_expired":
        console.log(`[webhook] expired: authority=${authorityID}`);
        // notify customer to renew
        break;
      default:
        console.log(`[webhook] ${eventType}: authority=${authorityID}`);
    }
  } else {
    // Tier 1 one-shot events
    const orderID = payload.order_id;
    console.log(`[webhook] one-shot event for order=${orderID}`);
  }
  return new Response(JSON.stringify({ ok: true }), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}

// ---------------------------------------------------------------------------
// Smoke check (no network calls — verifies the adapter is wired)
// ---------------------------------------------------------------------------

console.log("Tier 2 chains supported by this adapter:");
for (const c of [...RECURRING_NETWORKS].sort()) console.log(`  - ${c}`);

console.log("\nTier 2 webhook event types:");
for (const e of [...RECURRING_EVENT_TYPES].sort()) console.log(`  - ${e}`);

console.log(
  "\nReady to integrate. Replace the api_key / tenant_id / " +
    "webhook_secret at the top of this file with real values, then call " +
    "exampleCreateAuthority(...).",
);

// Touch the example fns so unused-import linting is happy in strict CI.
void exampleHostedCheckout;
void exampleVerifyReturn;
void exampleConfirmAuthority;
void exampleInspect;
void exampleListActive;
void exampleRevoke;
void exampleWebhookHandler;
