# Recurr Hosted Authorisation Page — Design (v0)

**Status:** Draft for review · No implementation yet
**Domain:** `recurr.algovoi.co.uk`
**Scope:** Customer-facing wallet UI for Tier 2 standing-authority signing across all 7 chains
**Author target:** AlgoVoi platform (Chris)
**Reviewer:** before any code lands

---

## Goal

Close the missing UX layer between "Tier 2 surface exists" and "any merchant can ship Tier 2 in 5 minutes." Today, when a merchant calls
`create_recurring_authority(...)` the gateway returns a chain-specific
`customer_signing_payload` that the merchant must hand to a wallet UI
they build themselves (or piece together from `Recurr/<chain>/README.md`).
This is a real adoption blocker — most merchants want to ship subscriptions,
not build SDK wrappers around 7 different wallet ecosystems.

The hosted authorisation page is the Tier 2 equivalent of Tier 1's
`api.algovoi.co.uk/checkout/<token>` page: AlgoVoi-hosted, chain-aware,
walks the customer through wallet-native signing, hands the on-chain
handle back to the gateway, redirects the customer to the merchant's
`redirect_url`. Merchant integration becomes:

```ts
const resp = await algovoi.recurring.createAuthority({...});
window.location.href = resp.authorisation_url;  // ← currently null; fills in once page ships
```

---

## URL structure

All paths under `recurr.algovoi.co.uk` (subdomain reserved for this
purpose; nothing else lives there).

| Path | Purpose |
|---|---|
| `recurr.algovoi.co.uk/` | Marketing landing — what is Tier 2, who's it for. Static, optional, can ship later. |
| `recurr.algovoi.co.uk/<token>` | Main signing flow. Detects chain, invokes wallet, walks customer through signing. |
| `recurr.algovoi.co.uk/<token>/success` | Confirmation screen shown briefly before redirect. Carries on-chain handle for display. |
| `recurr.algovoi.co.uk/<token>/error` | Failure screen with retry option. Reasons: wallet rejected, network mismatch, insufficient balance, expired token. |
| `recurr.algovoi.co.uk/health` | Plain text `ok` for uptime monitoring. |

**Why one path scheme for all 7 chains, not `/algorand/<token>` etc:**
the token resolves to an authority that already has `chain` set in its
row. The page reads the chain from the resolved payload, not from the
URL. This keeps URLs short + single-issue + matches the Tier 1 pattern.

---

## Token model

Mirrors Tier 1's `/checkout/<token>` pattern exactly:

- **Format:** 32 bytes of `crypto.randomBytes()` → URL-safe base64 (43 chars no padding)
- **Storage:** new column `signing_token` on `recurring_authorities` table in -Hand. Indexed for token → authority lookup.
- **Generated:** at `create_recurring_authority` time, server-side, before the response returns. Token included in response under `authorisation_url` field as `https://recurr.algovoi.co.uk/<token>`.
- **One-time-resolvable while pending:** the gateway lookup endpoint returns `200 + payload` only while authority status == `pending`. Once status flips to `active` / `revoked` / `expired`, the lookup returns `410 Gone`.
- **Expiry:** authority's `cap_period_seconds` is the natural ceiling, but the token specifically is invalidated 24h after creation if not used (configurable). Prevents stale share-a-link scenarios.
- **One-shot read:** after first successful resolve, the gateway records `signing_token_first_resolved_at`. Multiple reads allowed (page refreshes are normal) but the field is exposed for security ops.
- **Token never logged in plaintext:** existing redaction rules in -Hand already cover `token` / `signing_token` keys.

**Why server-side lookup (not JWT):** keeps the URL short (~50 chars
inc. domain), avoids leaking the customer_signing_payload in the URL
or browser history, and lets the gateway invalidate at any time.

---

## Customer flow (sequence)

```
Customer's browser              recurr.algovoi.co.uk page              Gateway (-Hand)              Customer's wallet
       |                                  |                                  |                              |
       | GET /<token>                     |                                  |                              |
       |--------------------------------->|                                  |                              |
       |                                  | GET /v1/recurring/auth/<token>   |                              |
       |                                  |--------------------------------->|                              |
       |                                  |                              [resolves token]                   |
       |                                  |              200 {chain, customer_signing_payload, merchant: {...}}  |
       |                                  |<---------------------------------|                              |
       |  HTML+JS shell + chain-specific  |                                  |                              |
       |  module loaded                   |                                  |                              |
       |<---------------------------------|                                  |                              |
       |                                  |                                  |                              |
       |  [user clicks "Connect wallet"]  |                                  |                              |
       |--------------------------------->|                                  |                              |
       |                                  |  invokeWallet(payload)           |                              |
       |                                  |---------------------------------------------------------------->|
       |                                  |                                  |                  [wallet shows confirm dialog]
       |                                  |                                  |                              |
       |                                  |                                  |        [user signs]          |
       |                                  |    signedTx + on_chain_address   |                              |
       |                                  |<----------------------------------------------------------------|
       |                                  |                                  |                              |
       |                                  | POST /v1/recurring/auth/<token>/confirm                         |
       |                                  | {on_chain_address}               |                              |
       |                                  |--------------------------------->|                              |
       |                                  |                              [marks authority active]           |
       |                                  |              200 {authority: {status:'active'}}                 |
       |                                  |<---------------------------------|                              |
       |  redirect to /success?tx=...     |                                  |                              |
       |<---------------------------------|                                  |                              |
       |  [shows "Subscription active"]   |                                  |                              |
       |  [auto-redirect to merchant      |                                  |                              |
       |   redirect_url after 3s]         |                                  |                              |
       |                                  |                                  |                              |
```

---

## Per-chain wallet plan

Each chain gets a **module file** that knows two things: how to detect /
prompt the right wallet, and how to construct the chain-native
transaction(s) from the `customer_signing_payload`.

| Chain | Wallets supported v1 | Construction lib | Connect lib(s) |
|---|---|---|---|
| Algorand | Pera, Defly, Lute, Daffi | `algosdk` v3 | `@perawallet/connect`, `@blockshake/defly-connect`, `lute-connect`, `@daffiwallet/connect` |
| VOI | Lute, Kibisis | `algosdk` v3 (AVM-compat) | `lute-connect`, `kibisis-cli` (TBD — limited adapter selection) |
| Base + Tempo (EVM) | MetaMask, Rainbow, Coinbase Wallet, WalletConnect | `viem` | `@rainbow-me/rainbowkit` (covers all ~20 EVM wallets) |
| Solana | Phantom, Solflare, Backpack | `@solana/web3.js` + `@solana/spl-token` | `@solana/wallet-adapter-react` + `@solana/wallet-adapter-wallets` |
| Hedera | HashPack, Blade, Kabila | (none on JS — use HashConnect protocol) | `@hashgraph/hedera-wallet-connect` |
| Stellar | Freighter, LOBSTR, Albedo | `@stellar/stellar-sdk` | `@creit.tech/stellar-wallets-kit` |

**Algorand caveat:** the 6-action atomic group is the most complex
flow of any chain. Pera's `signTransactions` API supports atomic groups
natively but the UX shows "sign 6 transactions" which is intimidating.
We'll add a copy block above the wallet prompt explaining what the 6
actions do (deploy vault → fund ALGO → opt-in USDC → register agent →
register recipient → fund USDC). This is unique to Algorand+VOI.

**Hedera caveat:** HashConnect v3 uses WalletConnect under the hood
but the adapter is less mature than Solana's. Expect 30-60 min
debugging time vs other chains.

**Stellar caveat:** Soroban auth_entry signing in browser wallets is
new (mostly 2025+ adapter support). Freighter has it; LOBSTR and Albedo
are still catching up. v1 may ship Freighter-only on Stellar with a
"more wallets coming" note. Not a blocker.

---

## Tech stack

**Recommendation:** **Vite + React + TypeScript**, deployed as a static
SPA to Cloudflare Pages.

**Why:**
- Ecosystem of pre-built wallet adapters covers all 7 chains
- React's mental model maps naturally to the chain-detect → wallet-prompt → sign → confirm flow
- Vite static build is small (target ≤ 500 KB gzipped) and edge-deployable
- No backend required — page talks directly to the gateway over HTTPS
- Cloudflare Pages auto-deploys from a public repo on push

**Repo location options (pick one before implementation):**

| Option | Lives in | Pros | Cons |
|---|---|---|---|
| **A. New folder in Platform-Adapters** | `AlgoVoi-Platform-Adapters/recurr-hosted-page/` | Single public repo for all integrator surface; easy to discover; ships with the same Cloudflare deploy as `chrome/site` | Mixes a customer-facing app into a docs-and-adapters repo |
| **B. New repo `chopmob-cloud/recurr-hosted-page`** | New public repo | Clean separation; clear deployment target; easier CI | Adds another repo to maintain |
| **C. Add to existing `chopmob-cloud/AlgoVoi` (chrome/site)** | Sibling subdir of the marketing site | Reuses existing Cloudflare project + DNS infra; one less GitHub Action | The marketing site's stack may not match (need to check) |

**My recommendation: B — new repo.** The page is a customer-facing
production application, not docs or adapter glue. Separation makes
incident response (if something breaks at sign time) cleaner. It's the
same bundle of work — just lives in its own repo with its own deploy
pipeline.

If you'd prefer to stay tighter (one less moving part), option A is
fine. The implementation diff is identical except for `git remote add`.

**Cloudflare Pages setup:**
- Repo connected to Cloudflare Pages project `recurr-algovoi`
- Custom domain `recurr.algovoi.co.uk` mapped to the Pages deployment
- Build command: `npm run build` → `dist/`
- Auto-deploy on push to `master`
- Preview deploys on PRs

---

## Gateway changes needed (-Hand, private)

Three small private-only changes:

1. **New column `signing_token` on `recurring_authorities`**
   - Migration `106_recurring_signing_token.sql`
   - 43-char URL-safe base64, indexed UNIQUE
   - Backfilled NULL for existing rows (none in production yet)

2. **New column `signing_token_first_resolved_at`** (optional, security ops nicety)
   - Tracks when a token was first looked up — useful for incident response

3. **Two new public endpoints** (no auth — token IS the auth)
   - `GET /v1/recurring/auth/<token>` — resolves token, returns
     `{chain, customer_signing_payload, merchant: {name, logo_url}, expires_at}`
     while status == pending; returns 410 once consumed
   - `POST /v1/recurring/auth/<token>/confirm` — accepts `{on_chain_address}`,
     calls existing `confirm_authority` service internally, returns the
     activated authority row

Both endpoints are **rate-limited** (10 req/min/IP) and CORS-locked
to `recurr.algovoi.co.uk` only.

4. **Modify `create_recurring_authority` response** to populate
   `authorisation_url` field with `https://recurr.algovoi.co.uk/<token>`
   (currently returns `null`).

Total -Hand work: ~30-45 min including tests + migration. Cleanly
additive to existing surface.

---

## Sequencing

**Phase 1 — Algorand-first end-to-end (~2-3 hours)**
- Repo scaffold, build, Cloudflare Pages connected, custom domain working
- Token resolution + confirm flow against gateway (mocked first, then real)
- Pera Wallet integration
- Algorand SpendingCapVault construction (port from `Recurr/algorand/README.md` reference code into runnable form)
- Demo: real testnet sign-and-confirm cycle, screenshot for buyer DD

**Phase 2 — EVM (Base + Tempo, both via same module) (~1 hour)**
- RainbowKit drop-in
- ERC-20 approve construction (trivial — single tx)
- Base sepolia testnet flow tested

**Phase 3 — Solana (~1 hour)**
- Wallet-adapter-react drop-in
- SPL Approve construction
- Phantom devnet flow tested

**Phase 4 — Hedera (~1.5 hours)**
- HashConnect 3 integration
- HTS allowance approve
- HashPack testnet flow tested

**Phase 5 — Stellar (~1.5 hours)**
- Stellar Wallets Kit integration
- Soroban auth_entry signing
- Freighter testnet flow tested

**Phase 6 — VOI (~30 min)**
- Lute + Kibisis adapters
- Same SpendingCapVault code path as Algorand (AVM-compatible)

**Phase 7 — Polish + deploy (~1 hour)**
- Loading states, error UX, retry flows, copy review
- Mobile responsiveness check
- Production deploy

**Total:** ~9-10 hours real-world for all 7 chains. **Phase 1 alone
(~2-3 hours)** ships the buyer-DD demo: "screenshot the page, customer
signs, subscription active." That's the valuation moment; the other
phases can land per session over a week.

---

## Failure modes (UX)

The page must handle these cleanly — each gets a distinct screen with
clear next-step copy:

| Failure | UX |
|---|---|
| Wallet not installed | Detect via window probe; show "Install <wallet>" with deeplink to wallet site |
| Wrong network selected (EVM) | Detect chainId mismatch, show "Switch to Base mainnet" with auto-switch button |
| User cancels in wallet | Return to signing screen with "Try again" button |
| Insufficient gas / native balance | Show specific message: "Top up <token> to proceed (need ~X)" |
| Insufficient asset balance | Show specific message: "You need at least <amount> USDC in your wallet" |
| Tx broadcast fails | Show error reason from chain (truncated to 160 chars), "Try again" button |
| Tx broadcast succeeds but never lands | Poll for 60s; if still unconfirmed, show "Pending — leave this page open" with manual refresh |
| Token expired (24h) | Show "Link expired — ask the merchant for a new one" with merchant contact |
| Token already used | Show "Authority already created — back to merchant" |

---

## Out of scope for v1

Tracked but not built first:

- **Mobile deep-linking** — most chains' wallets are mobile-only for many users; v1 assumes desktop with an installed extension. Mobile flows for each chain need ~30-45 min each, deferrable.
- **3DS-style fallback** — non-crypto users can't use this surface. They go through Tier 1 hosted checkout instead.
- **Multi-language** — English-only v1.
- **A11y formal audit** — basic semantic HTML + keyboard nav v1, formal WCAG audit deferred.
- **Operator dashboard for hosted-page funnel** — conversion analytics, drop-off tracking. Belongs in the merchant dashboard, not this page.
- **Customer-side authority listing** — "see all my AlgoVoi subscriptions" page. Different surface, can ship at `recurr.algovoi.co.uk/me` later.
- **Wallet-init smart-defaults beyond the basics** — e.g. auto-funding the Algorand vault if user has no ALGO. Edge case, deferrable.

---

## Open design questions (need your call before code)

1. **Repo location:** A (folder in Platform-Adapters) vs B (new public repo) vs C (chrome/site sibling)? **My recommendation: B.**
2. **Should v1 ship marketing landing page at `recurr.algovoi.co.uk/`** or just the signing flow? **My recommendation: defer the marketing page; ship the signing flow first. Empty root or 302 → docs.algovoi.co.uk for v1.**
3. **Should the page broadcast the signed transaction itself, or hand the signed bytes to the gateway and let it broadcast?** **My recommendation: page broadcasts. Faster UX, fewer round-trips, gateway only needs the on-chain handle on confirm.** (Caveat: facilitator-pays flows for gas-less UX would invert this — out of scope v1.)
4. **Token expiry default — 24h enough?** Common pattern in checkout flows is 1-4 hours, but standing-authority pages may sit in a customer's inbox longer. **My recommendation: 24h, configurable per-tenant later.**
5. **Should we re-prompt customers who land on `/<token>` with status already=`active`?** I.e., "you've already activated this — go back to merchant?" **My recommendation: yes, friendly redirect. Prevents confusion.**
6. **Brand bar / logo:** every chain's wallet UX shows the requesting domain (`recurr.algovoi.co.uk`). Do we also embed merchant branding (logo + name) on the page? Tier 1 hosted checkout already does this — we mirror that. Need merchant dashboard to upload a logo if not already wired (probably is).

---

## Buyer-DD value (honest)

**Today:** Tier 2 surface exists across 5 native adapters + MCP. Demoable
to a technical buyer reading code. Not demoable to a non-technical
buyer.

**After Phase 1 (Algorand-only, ~2-3 hours):** demoable in 60 seconds
on a Zoom call. "Open this URL → connect Pera → sign → subscription
active." That single screenshot fills the biggest remaining gap in the
DD narrative for the £150k arc.

**After Phase 7 (all 7 chains, ~10 hours):** the integration story is
one line: "any merchant on any of our 7 chains can ship Tier 2 in 5
minutes by setting `redirect_url` and using `authorisation_url` from
the create call." Stripe-comparable simplicity at the merchant boundary.

---

## Approval needed before code lands

Before any implementation:

1. **Repo location** (A / B / C above) — affects where the first commit lands.
2. **Tech stack confirmation** — Vite + React + TS OK? Or do you want vanilla JS / SvelteKit / something else?
3. **Phase 1 scope confirmation** — Algorand-first, then expand chain-by-chain. OK?
4. **Open design questions 1-6** — your call on each.

Once those are answered, the first commit is the repo scaffold +
Cloudflare Pages deploy + token resolution to a placeholder UI. From
there each chain lands as its own commit.

---

## Reference

- **Per-chain wire formats:** `Recurr/<chain>/README.md` in this repository
- **Tier 1 hosted checkout (existing pattern):** `api.algovoi.co.uk/checkout/<token>`
- **Smoke + e2e protocol:** `content/smoke_e2e_protocol.md` in -Hand (private) — apply same protocol to each chain's wallet flow before phase considered complete
- **Existing -Hand recurring router:** `gateway/app/routers/recurring.py` — token endpoints will live alongside existing 8 endpoints
