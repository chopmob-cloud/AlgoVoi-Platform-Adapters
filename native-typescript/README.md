# AlgoVoi Native TypeScript Adapter

Single-file, zero-dependency TypeScript adapter for the AlgoVoi
payment platform. Drop `algovoi.ts` into any modern TS / JS project
— Node, Bun, Deno, Cloudflare Workers, Vercel Edge, or browsers.

**Version:** 1.2.0 · **Tier 1** (one-shot checkout) · **Tier 2** (standing-authority recurring)

---

## When to use this vs `@algovoi/sdk` (npm)

| | `@algovoi/sdk` (npm) | `native-typescript` (this folder) |
|---|---|---|
| Distribution | `npm install @algovoi/sdk` | Copy `algovoi.ts` into your repo |
| Chain SDKs (algosdk / eth-account / solders / hiero / stellar-sdk) | Optional peer deps for chain-direct flows | None — adapter is HTTP-only |
| Bundle size | Tree-shaken; peer deps lazy-loaded | ~25 KB single file |
| Runtimes | Node, Bun, Deno, browsers | Node 18+, Bun, Deno, browsers, Edge runtimes |
| Audit-friendly | 7 chain provider modules + facade | One file, top-to-bottom readable |
| Use case | Standard server / CLI / app integration | Edge / serverless / npm-averse / DD review |

Both ship Tier 2 with the same gateway HTTP contract. Pick based on
distribution + audit needs. Most users want `@algovoi/sdk`.

---

## Install

No install. Single file:

```bash
curl -O https://raw.githubusercontent.com/chopmob-cloud/AlgoVoi-Platform-Adapters/master/native-typescript/algovoi.ts
```

Or copy `algovoi.ts` directly into your `src/`.

Requires a runtime with native `fetch` and WebCrypto:
- **Node 18+** (fetch since 18, SubtleCrypto since 16)
- **Bun** (any version)
- **Deno** (any version)
- **Cloudflare Workers, Vercel Edge, Netlify Edge, Deno Deploy**
- **Modern browsers**

---

## Quickstart

```ts
import { AlgoVoi, isRecurringEvent } from "./algovoi.ts";

const av = new AlgoVoi({
  api_base: "https://api1.ilovechicken.co.uk",
  api_key: "algv_...",
  tenant_id: "your-tenant-uuid",
  webhook_secret: "whsec_...",
});

// Tier 1 — one-shot
const link = await av.hostedCheckout(
  10, "USD", "Order #1", "algorand_mainnet",
  "https://shop.example/return",
);

// Tier 2 — standing-authority recurring
const resp = await av.createRecurringAuthority({
  subscription_id: subID,
  chain: "algorand_mainnet",
  customer_wallet_address: "ABCD...XYZ",
  cap_amount_minor: 120_000_000,        // $120 USDC = 12 × $10
  cap_period_seconds: 365 * 86400,
  per_cycle_amount_minor: 10_000_000,
});
// resp.customer_signing_payload is the chain-specific template
// the customer's wallet will sign — see Recurr/<chain>/README.md.
```

Full lifecycle samples in [`example.ts`](example.ts) and
[`../Recurr/merchant-examples/typescript.ts`](../Recurr/merchant-examples/typescript.ts).

---

## Tier 2 surface

8 lifecycle methods + helpers, mirroring the other native-* adapters
(Python / Go / PHP / Rust):

| Method | HTTP |
|---|---|
| `createRecurringAuthority(req)` | POST `/v1/recurring/authorities` |
| `getAuthority(id)` | GET `/v1/recurring/authorities/{id}` |
| `listAuthorities(opts)` | GET `/v1/recurring/authorities?...` |
| `confirmAuthority(id, req)` | POST `/v1/recurring/authorities/{id}/confirm` |
| `revokeAuthority(id)` | POST `/v1/recurring/authorities/{id}/revoke` |
| `pauseAuthority(id)` | POST `/v1/recurring/authorities/{id}/pause` |
| `resumeAuthority(id, ...)` | POST `/v1/recurring/authorities/{id}/resume` |
| `manualPull(req)` | POST `/v1/recurring/pulls` |

Plus:
- `isRecurringEvent(payload)` — fork webhook handlers
- `isRecurringNetwork(chain)` — type-guard for Tier 2 chain ids
- `RECURRING_NETWORKS` — 14 chain ids (7 mainnets + 7 testnets)
- `RECURRING_EVENT_TYPES` — 8 webhook events

All methods return `Promise<T | null>`. `null` means HTTP failure,
plaintext refusal, or invalid input — caller checks with `if (result === null)`.

---

## Tests

```bash
# Type check (strict)
npx tsc --noEmit -p tsconfig.json

# Run tests (Node 24+ with native TS strip)
node --experimental-strip-types --no-warnings recurring_test.ts

# Or with Bun
bun run recurring_test.ts

# Or with Deno
deno run --allow-net recurring_test.ts
```

24/24 tests pass:
- 5 helper / constant tests
- 9 input-validation tests (guarantee no fetch fires on bad input)
- 6 mocked HTTP round-trip tests (URL + method + body + headers + null on non-2xx)
- 4 webhook tests (real WebCrypto HMAC-SHA256 round-trip)

---

## File layout

```
native-typescript/
├── algovoi.ts          single-file adapter (Tier 1 + Tier 2)
├── recurring_test.ts   tests (zero-framework runner)
├── example.ts          usage samples
├── tsconfig.json       strict / ES2022 / Bundler resolution
└── README.md           you are here
```

No `package.json`, no `node_modules`, no build step required.

---

## Per-chain wallet integration

This adapter is the **merchant side**. The customer's wallet does the
chain-native signing. For per-chain wallet integration code (the
template returned by `createRecurringAuthority` and how the wallet
constructs the on-chain transaction), see:

- [`../Recurr/algorand/`](../Recurr/algorand/) — SpendingCapVault, 6-action atomic group
- [`../Recurr/voi/`](../Recurr/voi/) — same contract, AVM-compatible
- [`../Recurr/evm/`](../Recurr/evm/) — Base + Tempo, ERC-20 approve
- [`../Recurr/solana/`](../Recurr/solana/) — SPL Token Approve
- [`../Recurr/hedera/`](../Recurr/hedera/) — HTS allowance
- [`../Recurr/stellar/`](../Recurr/stellar/) — Soroban auth_entry

---

## Licence

Business Source License 1.1. See `../LICENSE`.
