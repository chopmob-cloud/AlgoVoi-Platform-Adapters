/**
 * AlgoVoi Tier 2 — TypeScript merchant-side example.
 *
 * Runnable reference showing the full Tier 2 lifecycle from the
 * merchant's perspective. The wallet-side flow (where the customer
 * actually signs the on-chain authorisation) is documented per chain
 * in ../algorand/, ../voi/, ../evm/, ../solana/, ../hedera/, ../stellar/.
 *
 * Uses the native-typescript adapter at ../../native-typescript/algovoi.ts
 * (v1.2.0+) — the chain-agnostic merchant HTTP wrapper. Zero npm
 * dependencies; works in any modern TS / JS runtime with native fetch +
 * WebCrypto.
 *
 * Run:
 *   node --experimental-strip-types --no-warnings typescript.ts
 *   # or
 *   bun run typescript.ts
 *   # or
 *   deno run --allow-net typescript.ts
 *
 * Replace api_key / tenant_id / webhook_secret + an existing
 * subscription_id below to actually exercise the lifecycle.
 */

import {
  AlgoVoi,
  RECURRING_EVENT_TYPES,
  RECURRING_NETWORKS,
  isRecurringEvent,
  isRecurringNetwork,
} from "../../native-typescript/algovoi.ts";
import type {
  AuthorityCreateRequest,
  AuthorityCreateResponse,
} from "../../native-typescript/algovoi.ts";

// ---------------------------------------------------------------------------
// Configure
// ---------------------------------------------------------------------------

const av = new AlgoVoi({
  api_base: "https://api1.ilovechicken.co.uk",
  api_key: "algv_REPLACE_ME",
  tenant_id: "REPLACE_ME_UUID",
  webhook_secret: "whsec_REPLACE_ME",
});

// ---------------------------------------------------------------------------
// Step 1 — Create a Tier 2 standing authority for an existing subscription
// ---------------------------------------------------------------------------

/**
 * $10/month subscription, 12-month standing authority, on the customer's
 * chosen chain.
 */
async function exampleCreateAuthority(
  subscriptionID: string,
  customerWallet: string,
  chain: string,
): Promise<AuthorityCreateResponse> {
  if (!isRecurringNetwork(chain)) {
    throw new Error(`Unsupported chain: ${chain}`);
  }

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
  if (!resp) throw new Error("Authority creation failed (check logs / API key)");

  console.log(`[create] authority_id = ${resp.authority.id}`);
  console.log(`[create] status       = ${resp.authority.status}`);
  const tplVer = (resp.customer_signing_payload as Record<string, unknown>).version;
  console.log(`[create] template ver = ${tplVer}`);

  // Hand resp.customer_signing_payload to your frontend wallet UI.
  // The per-chain folders have wallet-side reference code.
  return resp;
}

// ---------------------------------------------------------------------------
// Step 2 — After the customer's wallet signs and on-chain auth lands
// ---------------------------------------------------------------------------

/**
 * `onChainHandle` format depends on the chain:
 *   Algorand / VOI : "app:<application_id>"
 *   EVM            : "0x<tx_hash>"
 *   Solana         : "<base58 tx signature>"
 *   Hedera         : "<account_id>@<seconds>.<nanos>"
 *   Stellar        : "<64-char hex tx hash>"
 */
async function exampleConfirmAuthority(authorityID: string, onChainHandle: string) {
  const confirmed = await av.confirmAuthority(authorityID, {
    on_chain_address: onChainHandle,
  });
  if (!confirmed) throw new Error("Confirmation failed");
  console.log(`[confirm] status = ${confirmed.status}  (should be 'active')`);
  return confirmed;
}

// ---------------------------------------------------------------------------
// Step 3 — Read state any time
// ---------------------------------------------------------------------------

async function exampleInspect(authorityID: string) {
  const a = await av.getAuthority(authorityID);
  if (!a) {
    console.log("[inspect] not found");
    return;
  }
  const total = a.cycles_pulled + a.cycles_failed;
  console.log(
    `[inspect] status=${a.status} cycles=${a.cycles_pulled}/${total} remaining=${a.cap_remaining_minor}`,
  );
  if (a.last_error) console.log(`[inspect] last_error = ${a.last_error}`);
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

// ---------------------------------------------------------------------------
// Step 4 — Lifecycle controls
// ---------------------------------------------------------------------------

async function examplePause(authorityID: string) {
  await av.pauseAuthority(authorityID);
}

async function exampleResume(authorityID: string) {
  await av.resumeAuthority(authorityID);
}

async function exampleRevoke(authorityID: string) {
  const r = await av.revokeAuthority(authorityID);
  if (!r) {
    console.log("[revoke] failed");
    return;
  }
  console.log(`[revoke] status = ${r.status}`); // 'revoking' → 'revoked'
}

async function exampleManualPull(authorityID: string, amountMinor: number) {
  const r = await av.manualPull({
    authority_id: authorityID,
    amount_minor: amountMinor,
    idempotency_key: `manual_${authorityID}_${amountMinor}`,
  });
  if (!r) {
    console.log("[pull] failed (check per-cycle cap)");
    return;
  }
  console.log(`[pull] accepted; status = ${r.status}`);
}

// ---------------------------------------------------------------------------
// Step 5 — Webhook handler (Hono / Express / Cloudflare Worker / etc.)
// ---------------------------------------------------------------------------

async function exampleWebhookHandler(
  rawBody: string,
  signature: string,
): Promise<Response> {
  const payload = await av.verifyWebhook(rawBody, signature);
  if (!payload) return new Response("Unauthorized", { status: 401 });

  if (isRecurringEvent(payload)) {
    const eventType = (payload.event_type ?? "") as string;
    const authorityID = payload.authority_id as string | undefined;

    switch (eventType) {
      case "subscription.charged": {
        const txID = payload.tx_id as string | undefined;
        console.log(`[webhook] charged: authority=${authorityID} tx=${txID}`);
        // extend customer access
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
        break;
      case "recurring.authority_expired":
        console.log(`[webhook] expired: authority=${authorityID}`);
        break;
      default:
        console.log(`[webhook] ${eventType}: authority=${authorityID}`);
    }
  } else {
    const orderID = payload.order_id;
    console.log(`[webhook] one-shot event for order=${orderID}`);
  }

  return new Response(JSON.stringify({ ok: true }), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}

// ---------------------------------------------------------------------------
// Smoke check (no network calls — just verifies the adapter is wired)
// ---------------------------------------------------------------------------

console.log("Tier 2 chains supported by this adapter:");
for (const c of [...RECURRING_NETWORKS].sort()) console.log(`  - ${c}`);

console.log("\nTier 2 webhook event types:");
for (const e of [...RECURRING_EVENT_TYPES].sort()) console.log(`  - ${e}`);

console.log(
  "\nReady to integrate. Replace the api_key / tenant_id / " +
    "webhook_secret at the top of this file with real values, " +
    "then call exampleCreateAuthority(subscriptionID, customerWallet, chain).",
);

// Touch unused fns so strict-CI lints don't flag them.
void exampleCreateAuthority;
void exampleConfirmAuthority;
void exampleInspect;
void exampleListActive;
void examplePause;
void exampleResume;
void exampleRevoke;
void exampleManualPull;
void exampleWebhookHandler;
