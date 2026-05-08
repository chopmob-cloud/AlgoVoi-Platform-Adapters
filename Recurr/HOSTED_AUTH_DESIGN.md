# Recurr Hosted Authorisation Page — Design (v1, enterprise-ready)

**Status:** Design complete, awaiting approval before implementation
**Domain:** `recurr.algovoi.co.uk`
**Scope:** Customer-facing wallet UI for Tier 2 standing-authority signing across all 7 chains
**Synthesis source:** v0 draft (commit 4462c6d) + Claude pass + Comet pass at `content/{claude,comet}_recurr_hosted_auth_review.md`
**Reviewer:** the operator before any code lands

---

## What changed v0 → v1

v0 (343 lines) covered the architectural shape: domain, token model, customer
flow, per-chain wallet plan, tech stack, sequencing. Sound for shipping a
demo. Light on enterprise-readiness.

v1 (this document) keeps v0's architecture intact and layers in 21 enterprise
dimensions reviewed by Claude + Comet in parallel. Both reviewers converged
on the same five highest-priority gaps:

1. **No sanctions screening at confirm time** — a sanctioned wallet currently
   completes the entire flow and lands an active authority. Direct breach of
   the compliance perimeter AlgoVoi sells.
2. **Audit chain has a gap at the customer-touch point** — the new gateway
   endpoints emit zero `compliance_events` rows; a regulator asking "show me
   every step of authority X" gets nothing.
3. **No pre-sign human-readable summary card** — customers sign a 6-action
   Algorand group (or any chain's primitive) with no informed-consent
   disclosure. Top-3 abandonment driver and a UK Equality Act + informed-
   consent regulatory exposure.
4. **Confirm endpoint is not idempotent** — browser retry / network hiccup /
   back-button creates duplicate audit rows OR a 500 the user sees as
   "failed" after a successful sign. Breaks chain integrity.
5. **GDPR Art. 17 vs Object Lock 7y retention not resolved** — wallet
   addresses written to immutable Object Lock COMPLIANCE-mode rows can't be
   erased. Without the documented MLRs Reg 40(3) legal-obligation basis,
   any ICO inquiry after a customer erasure request is unanswerable.

All five are **Phase 1 must-have**. None block the architecture; all are
small additions to the gateway endpoints + page logic.

---

## Goal (unchanged from v0)

Close the missing UX layer between "Tier 2 surface exists" and "any merchant
can ship subscriptions in 5 minutes." When a merchant calls
`create_recurring_authority(...)` the gateway returns a chain-specific
`customer_signing_payload` that the merchant must hand to a wallet UI they
build themselves (or piece together from `Recurr/<chain>/README.md`). This
is a real adoption blocker.

The hosted authorisation page is the Tier 2 equivalent of Tier 1's
`/checkout/<token>` page: AlgoVoi-hosted, chain-aware, walks the customer
through wallet-native signing, hands the on-chain handle back to the
gateway, redirects to the merchant's `redirect_url`. Merchant integration
becomes:

```ts
const resp = await algovoi.recurring.createAuthority({...});
window.location.href = resp.authorisation_url;  // ← currently null; populated once page ships
```

---

## URL structure (refined v1)

All paths under `recurr.algovoi.co.uk` (subdomain reserved). The page is
chain-agnostic at the URL layer — chain is read from the resolved payload,
not the URL — matching Tier 1's `/checkout/<token>` pattern.

| Path | Purpose |
|---|---|
| `recurr.algovoi.co.uk/` | Empty / 302 → `docs.algovoi.co.uk/recurring`. Marketing landing deferred to post-£150k. |
| `recurr.algovoi.co.uk/<token>` | Main signing flow. Detects chain, invokes wallet, walks customer through signing. |
| `recurr.algovoi.co.uk/<token>/success` | Confirmation screen with on-chain handle, brief auto-redirect to merchant. |
| `recurr.algovoi.co.uk/<token>/error` | Failure screen with retry option + "I'm stuck" mailto. |
| `recurr.algovoi.co.uk/<token>/expired` | Token TTL hit before sign. Friendly message + merchant contact. |
| `recurr.algovoi.co.uk/health` | Plain-text `ok` for uptime monitoring + status banner JSON fetch. |
| `recurr.algovoi.co.uk/status.json` | Operator-updateable status banner. `{status: "ok"\|"degraded", message, chains_affected}`. |
| `recurr.algovoi.co.uk/terms` | Static ToS. |
| `recurr.algovoi.co.uk/privacy` | Static privacy policy (covers GDPR Art. 17 vs audit chain explicitly). |

**Forward-compatibility note (Comet recommendation):** the gateway's token
resolution endpoint must NOT validate the request `Origin` against a
whitelist — that breaks Phase-2 custom-domain support. Validate token
identity only.

---

## Token model (refined v1)

Mirrors Tier 1's `/checkout/<token>` pattern with hardening:

- **Format:** 32 bytes from `crypto.randomBytes()` → URL-safe base64 (43 chars no padding)
- **Storage:** new column `signing_token` on `recurring_authorities` in
  -Hand. Indexed UNIQUE for token → authority lookup.
- **Generated:** at `create_recurring_authority` time, server-side, before
  the response returns. Returned to merchant as
  `authorisation_url = "https://recurr.algovoi.co.uk/<token>"` in the
  create response.
- **Resolvable while pending:** the gateway lookup endpoint returns
  `200 + payload` only while authority status == `pending`. Once status
  flips to `active` / `revoked` / `expired`, the lookup returns
  `410 Gone`. Multiple reads while pending are allowed (page refreshes).
- **Constant-time enumeration resistance (Comet add-on):** the lookup
  responds in constant time regardless of token validity. `SELECT WHERE
  signing_token = $1` for non-existent tokens hits the same code path +
  sleep-pad as expired tokens. Prevents timing-oracle distinguishing
  "never created" from "already used" from "expired."
- **First-resolved tracking:** `signing_token_first_resolved_at` column
  records first-read time for security ops + signing-latency metrics.
- **Expiry:** 24h after creation, regardless of whether `cap_period_seconds`
  is longer. Configurable per-tenant later. Merchant dashboard surfaces
  pending-token age + a "regenerate link" action for stale tokens.
- **Token never logged in plaintext:** existing `-Hand` redaction rules
  cover `token` / `signing_token` keys. Audit chain rows reference
  `signing_token_hash = SHA-256(signing_token)` only.
- **No token in URL parameters / hash / referrer:** the token IS the
  path. `Referrer-Policy: strict-origin-when-cross-origin` prevents
  leakage to merchant's redirect destination.

**Why server-side lookup (not JWT):** keeps the URL short, avoids leaking
the customer_signing_payload in browser history, lets the gateway
invalidate at any time, hashes audit-chain references safely.

---

## Customer flow (sequence — v1 with compliance integration)

```
Customer browser     recurr.algovoi.co.uk SPA       Gateway (-Hand)            Customer wallet
       |                       |                          |                         |
       |  GET /<token>         |                          |                         |
       |---------------------->|                          |                         |
       |                       | GET /v1/recurring/auth/<token>                     |
       |                       |------------------------->|                         |
       |                       |                     [resolve token]                |
       |                       |                     [WRITE compliance_events:      |
       |                       |                      authority_token_resolved]     |
       |                       |   200 {chain, payload, merchant, expires_at}       |
       |                       |<-------------------------|                         |
       |  Render: Authority    |                          |                         |
       |  Summary Card         |                          |                         |
       |  + EU geo-block check (Cloudflare WAF, before SPA loads)                   |
       |<----------------------|                          |                         |
       |                       |                          |                         |
       | [click Connect Wallet]|                          |                         |
       |---------------------->|                          |                         |
       |                       |          invokeWallet(payload)                     |
       |                       |---------------------------------------------------->
       |                       |                          |                  [show confirm]
       |                       |                          |       [user signs]      |
       |                       |    signedTx + on_chain_address                     |
       |                       |<----------------------------------------------------|
       |                       |                          |                         |
       |                       | POST /v1/recurring/auth/<token>/confirm            |
       |                       | {on_chain_address, idempotency_key}                |
       |                       |------------------------->|                         |
       |                       |          [SCREEN customer wallet] ←─ COMPLIANCE GATE
       |                       |          [if hit: 403 + WRITE screening_hits row]  |
       |                       |          [if pass: confirm_authority + WRITE       |
       |                       |           compliance_events: authority_confirmed]  |
       |                       |     200 {authority: {status: 'active'}}            |
       |                       |<-------------------------|                         |
       |  Redirect /success    |                          |                         |
       |  → merchant.redirect_url after 3s                |                         |
       |<----------------------|                          |                         |
```

Five compliance/audit-chain integration points marked. All but one
(geo-block at edge) live in the gateway, not the SPA — keeps the SPA's
attack surface minimal.

---

## Per-chain wallet plan (refined v1)

| Chain | Wallets v1 | Construction lib | Connect strategy |
|---|---|---|---|
| **Algorand** | Pera, Defly, Lute, Daffi | `algosdk` v3 | `@perawallet/connect` (preferred), `@blockshake/defly-connect`, `lute-connect`, `@daffiwallet/connect`. Note: hardware wallets via Pera mobile only — extension flow doesn't expose Ledger. Documented limitation. |
| **VOI** | Lute, Kibisis | `algosdk` v3 (AVM-compat) | `lute-connect`. Kibisis is Chrome-only extension; documented. |
| **Base + Tempo (EVM)** | MetaMask, Rainbow, Coinbase Wallet, WalletConnect | `viem` | `@reown/appkit-wagmi` (formerly RainbowKit/Web3Modal). Covers all WC2-compatible EVM wallets including Ledger via MetaMask. |
| **Solana** | Phantom, Solflare, Backpack | `@solana/web3.js` + `@solana/spl-token` | `@solana/wallet-adapter-react` + `@solana/wallet-adapter-wallets`. Native Ledger via Solana adapter. |
| **Hedera** | HashPack, Blade, Kabila | (proto via `@hashgraph/hedera-wallet-connect`) | `@hashgraph/hedera-wallet-connect` (WC2-based). |
| **Stellar** | Freighter, LOBSTR, Albedo | `@stellar/stellar-sdk` v13 | `@creit.tech/stellar-wallets-kit`. Soroban auth_entry signing v1: Freighter only; LOBSTR/Albedo to follow as adapter support matures. |

**Algorand 6-action UX (per Comet — mandatory):** populate the `note`
field of the first transaction in the atomic group with a UTF-8
human-readable string:

```
"AlgoVoi standing auth: up to $10 USDC/month x 12 months from this wallet.
Revocable anytime."
```

Under 1024 bytes. Surfaces in every Algorand wallet's UI as the primary
human-readable disclosure channel — Pera/Defly/Daffi all show it
prominently. Lute decodes action types separately so it renders even
without the note. The note is the disclosure of last resort.

**Multi-sig wallets:** detect via on-chain code presence (EVM:
`eth_getCode` non-empty; Algorand: address is multisig if msig group is
non-trivial). Phase 1: show "Multi-sig wallet detected — please contact
your merchant; we'll add multi-sig flow support shortly." Real Safe
support Phase 2 (EVM only).

**MPC / embedded wallets (Magic, Privy, Web3Auth):** these expect to be
embedded in the merchant's site. Phase 1: show "Embedded wallets like
Magic / Privy aren't supported on this page. Use the merchant's in-site
checkout instead." Per-tenant CSP relaxation for iframe-embed is post-
£150k.

**Hardware wallets (Ledger, Trezor):**
- EVM: transparent through MetaMask + RainbowKit.
- Solana: native via wallet-adapter.
- Algorand: Pera mobile only (extension flow doesn't expose Ledger
  natively). Document.
- Hedera / Stellar: limited browser-context support. Document.

---

## Tech stack (refined v1)

**Choice:** Vite + React + TypeScript + Tailwind CSS, deployed as a
static SPA to Cloudflare Pages. i18n via `react-i18next` (English-only
populated v1, architecture supports more).

**Why:**
- Pre-built wallet adapters cover all 7 chains
- Vite static build small (target ≤ 500 KB gzipped)
- Edge-deployable to Cloudflare Pages free tier
- React's mental model maps to chain-detect → wallet-prompt → sign → confirm
- Tailwind's logical properties (`margin-inline-start` etc.) make RTL
  free; supports later Arabic / Hebrew localisation
- `react-i18next` from day one means every user-visible string is a
  translation key — adding `de.json` / `ja.json` later is a translation-
  team task with zero engineering cost

**Repo location decision:** **Option B — new public repo
`chopmob-cloud/recurr-hosted-page`**. Reasoning:
- Customer-facing production application; shouldn't share a repo with
  docs and adapters
- Separate deploy pipeline + CI; cleaner incident response
- Per-tenant config (custom domains in Phase 2-7) easier to manage
- Renovate / Dependabot scoping is per-repo; isolates dep churn

**Cloudflare Pages setup:**
- Repo connected to Cloudflare Pages project `recurr-algovoi`
- Custom domain `recurr.algovoi.co.uk` mapped
- Build command: `npm ci && npm run build` → `dist/`
- Auto-deploy on push to `master`
- Preview deploys on PRs
- Atomic deploys (no partial-update window)

---

## Gateway changes (-Hand, private)

Six small private-only changes. All clean-additive.

### 1. New columns on `recurring_authorities`

```sql
-- migration 106_recurring_signing_token.sql
ALTER TABLE recurring_authorities ADD COLUMN signing_token TEXT UNIQUE;
ALTER TABLE recurring_authorities ADD COLUMN signing_token_first_resolved_at TIMESTAMPTZ;
ALTER TABLE recurring_authorities ADD COLUMN signing_token_signed_at TIMESTAMPTZ;
ALTER TABLE recurring_authorities ADD COLUMN on_chain_tx_id TEXT;
CREATE INDEX idx_recurring_authorities_signing_token ON recurring_authorities (signing_token) WHERE signing_token IS NOT NULL;
```

The `on_chain_tx_id` column supports **signed-but-unconfirmed recovery**
(Comet add-on): if the customer signs and the browser dies before
`/confirm` lands, the gateway-side reaper polls each chain for
known-pending authorities and matches them against the chain's tx
history.

### 2. New gateway endpoints

```
GET  /v1/recurring/auth/<token>
POST /v1/recurring/auth/<token>/confirm
```

Both **constant-time**, both **rate-limited** at edge (Cloudflare WAF: 30
req/min/IP for GET, 3 req/min/token for POST). Both **CORS-locked** to
`https://recurr.algovoi.co.uk` v1 + Phase-2 custom-domain allowlist.

### 3. Idempotency on `POST .../confirm`

Service checks: if `recurring_authorities.status == 'active'` and
`on_chain_address` matches the submitted address, return `200` with the
existing row. If `status == 'active'` and `on_chain_address` does NOT
match, return `409 Conflict` (different wallet signed). One
`authority_confirmed` audit row regardless of how many times confirm is
called. Optional `Idempotency-Key` header for additional client-side
dedup.

### 4. Pre-confirm sanctions screening

Inside the confirm handler, before calling `confirm_authority`:

```python
result = screen_wallet(on_chain_address, record_in_chain=True)
if result["status"] == "blocked":
    # Tipping-off compliant: generic error
    log.warning("authority_creation_declined", extra={"reason": "sanctions", ...})  # MLRO sees, customer doesn't
    return JSONResponse({"error": "authority_creation_declined"}, status_code=403)
```

The screening_hits chain row is written before the 403 — audit trail
records the decline event with full reason, even though the customer
sees a generic error.

### 5. Audit-chain integration

Six new event types written to `compliance_events`:

| Event | When |
|---|---|
| `authority_token_resolved` | First successful GET of a pending token |
| `authority_signing_started` | Optional: page calls a notify-started endpoint when wallet prompt fires (telemetry-driven; nice-to-have for funnel tracking) |
| `authority_signed` | Page POSTs confirm with on_chain_address — pre-screening |
| `authority_confirmed` | Confirm passes all gates; status flips active |
| `authority_confirm_failed` | Confirm fails (screening / chain error / idempotency mismatch) |
| `authority_token_expired` | TTL hit before sign — written by token-cleanup cron |

Row contents (from Comet):

```json
{
  "event_type": "authority_token_resolved",
  "authority_id": "<uuid>",
  "signing_token_hash": "<sha256 of token>",
  "tenant_id": "<uuid>",
  "chain": "algorand_mainnet",
  "ip_hash": "<sha256(ip + daily_salt)>",
  "user_agent_class": "browser|mobile|bot",
  "timestamp": "...",
  "chain_position": "<auto>",
  "prev_hash": "<auto>",
  "content_hash": "<auto>",
  "bundle_signature": "<auto>"
}
```

**Critical:** raw token never written to chain — only its SHA-256 hash.
Raw IPs never written — daily-salted hash. Wallet addresses written
operationally to `recurring_authorities` but only their hash to chain
events (matches existing per-pull screening pattern).

### 6. Populate `authorisation_url` in create response

Currently returns `null`. After token generation, populate:

```python
return AuthorityCreateResponse(
    authority=row,
    customer_signing_payload=payload,
    authorisation_url=f"https://recurr.algovoi.co.uk/{row.signing_token}",
)
```

For Phase-2 custom domains, this becomes per-tenant lookup:

```python
domain = tenant.custom_recurr_domain or "recurr.algovoi.co.uk"
authorisation_url = f"https://{domain}/{row.signing_token}"
```

**Total -Hand work:** ~60-90 minutes including migrations + audit-chain
event-type registration + idempotency tests. Cleanly additive.

---

## Compliance integration (Phase 1, mandatory)

The hosted page is the first time real customer wallets touch Tier 2.
Compliance hooks must fire:

### 5.1 Pre-confirm screening — gateway

`POST .../confirm` calls `screen_wallet(on_chain_address, record_in_chain=True)`
**before** activating the authority. Sanctioned address → 403 generic +
chain row written + log entry for MLRO review. **Never disclose the
specific reason to the customer** (SAMLA s.20 tipping-off + UK MLRs).

### 5.2 Token-resolve screening — gateway, optional UX gate

If the page collects the wallet address pre-sign (some wallets expose
it on connect without signing), run `screen_wallet(addr, record_in_chain=False)`
as a UX-friendly early gate. Same generic error if blocked. Read-only
screen, doesn't pollute the chain. Phase 2 enhancement; not Phase 1.

### 5.3 PEP screening posture

Out of scope v1. AlgoVoi runs simplified CDD (UK MLRs Reg 37). Document
in code comment at confirm endpoint:

```python
# PEP screening not in scope — simplified CDD per Reg 37.
# Review if Tier 2 volume exceeds £15k/month per customer.
```

### 5.4 Travel Rule applicability

Standing-authority creation is **not** a Travel Rule event. The first
pull from the authority IS. The existing per-pull facilitator path
already carries Travel Rule originator/beneficiary info. Document in
the gateway code; no page-side action required.

### 5.5 EU geo-blocking — Cloudflare WAF rule

Until full MiCA CASP analysis lands (post-£150k or when EU launch is
imminent), block EU IPs from the page entirely. Cloudflare WAF rule:

```
(ip.geoip.continent eq "EU") and not (ip.geoip.country in {"GB"})
→ Custom response 451 Unavailable For Legal Reasons
```

Page never loads for blocked IPs. Buyer's legal team can lift the
geo-block post-MiCA analysis.

### 5.6 OFAC-sanctioned-jurisdiction blocking

Currently 11 countries on OFAC's sanctioned list (Cuba, Iran, North
Korea, Syria, Crimea, etc.). Cloudflare WAF rule blocks page load for
those IPs; gateway endpoints reject inbound requests as well (defence
in depth).

---

## Audit trail (Phase 1, mandatory)

Six event types defined above. All write rows to the existing
`compliance_events` chain in -Hand. Critical implementation
requirements:

- `chain_position` increments correctly relative to the existing chain
- `prev_hash` matches the previous row's `content_hash` exactly
- `bundle_signature` per existing HMAC-SHA256 scheme — uses the
  rotation-friendly `AUDIT_BUNDLE_SIGNING_KEY_ID`
- After adding the first event, run the public verifier
  (`github.com/chopmob-cloud/algovoi-audit-verifier`) against a test
  bundle — confirm PASS verdict
- The `/compliance/attestation` endpoint adds a `tier2_hosted_auth`
  stanza (5 lines) once the page ships:

```json
"tier2_hosted_auth": {
  "status": "active",
  "chains_supported": ["algorand_mainnet", "voi_mainnet", ...],
  "page_url": "https://recurr.algovoi.co.uk",
  "audit_trail": true,
  "pre_confirm_screening": true,
  "geo_blocked_regions": ["EU", "OFAC-sanctioned"]
}
```

Buyer-DD-relevant: machine-readable confirmation that the customer-
touching surface honours the same compliance + audit posture as the
rest of the gateway.

---

## Security posture (Phase 1, mandatory)

### 6.1 Content Security Policy

Cloudflare Pages `_headers` file:

```
Content-Security-Policy:
  default-src 'none';
  script-src 'self' 'unsafe-eval';
  style-src 'self' 'unsafe-inline';
  connect-src 'self'
    https://api.algovoi.co.uk
    wss://relay.walletconnect.com
    wss://relay.walletconnect.org
    https://rpc.walletconnect.com
    https://mainnet-api.algonode.cloud
    https://mainnet-idx.algonode.cloud
    https://mainnet-api.voi.nodely.io
    https://api.mainnet-beta.solana.com
    https://mainnet.hedera.com
    https://mainnet-public.mirrornode.hedera.com
    https://horizon.stellar.org
    https://soroban-rpc.stellar.org
    https://mainnet.base.org
    https://*.tempo.io;
  img-src 'self' data: https://merchant-logos.algovoi.co.uk;
  font-src 'self';
  frame-src https://verify.walletconnect.com https://verify.walletconnect.org;
  object-src 'none';
  base-uri 'self';
  form-action 'none';
  frame-ancestors 'none';
  upgrade-insecure-requests;
```

Notes:
- `'unsafe-eval'` required by viem / some wallet adapters. LOW finding,
  same posture as `/recurr/portal`.
- `'unsafe-inline'` for style-src acceptable v1 (no dynamic style
  injection). Nonce migration tracked post-£150k.
- All wallet-adapter RPC origins explicitly named — no wildcards.
- Per-chain RPC list maintained in `src/csp.ts` as the source of truth;
  build emits CSP from that file (no hand-edited duplication).

### 6.2 CSP-Report-Only window (Comet add-on)

For first 7 days of each new deployment, ship `Content-Security-
Policy-Report-Only` alongside the enforcing CSP. Reports go to
`/v1/csp-reports` on the gateway. After 7 days clean, drop report-only
mode for that release. Catches wallet-adapter version bumps that pull
in new origins.

### 6.3 Other security headers

```
Strict-Transport-Security: max-age=31536000; includeSubDomains; preload
X-Frame-Options: DENY
X-Content-Type-Options: nosniff
Referrer-Policy: strict-origin-when-cross-origin
Permissions-Policy: geolocation=(), camera=(), microphone=(), payment=(), interest-cohort=()
Cross-Origin-Opener-Policy: same-origin-allow-popups
Cross-Origin-Embedder-Policy: unsafe-none
```

`COEP: require-corp` would be ideal but breaks several wallet adapters;
`unsafe-none` v1, hardening to `require-corp` tracked post-launch.

`HSTS preload` requires submission to `hstspreload.org` after the
domain is live and serving the correct headers for ≥ 30 days.

### 6.4 Cloudflare WAF

- `GET /v1/recurring/auth/*` rate limit: 30 req/min/IP at edge (gateway's
  10 req/min is the backstop)
- `POST .../confirm` rate limit: 3 req/min/token + 10 req/min/IP
- Block requests where `Referer` header is set but doesn't include
  `recurr.algovoi.co.uk` (per-tenant domain in Phase 2)
- Cloudflare Bot Fight Mode enabled
- EU geofence + OFAC-jurisdiction geofence (above)

### 6.5 Dependency hygiene

- All npm dependencies pinned to exact versions (no `^`, no `~`)
- Renovate auto-merges patch security updates only; minor/major require
  PR review
- `npm audit --audit-level=high` is a CI gate
- Snyk free tier for SCA
- Manual review of every wallet-adapter version bump (these libs have
  caretaker churn; trust-but-verify)

### 6.6 Secret hygiene

- Zero environment variables read by the SPA at runtime
- Build-time env: `VITE_GATEWAY_URL` (public) and `VITE_WALLETCONNECT_PROJECT_ID`
  (public) only
- WalletConnect Project ID: dedicated for `recurr.algovoi.co.uk`, NOT
  shared with the existing `/recurr/portal` Project ID (separate
  application registrations)
- Source maps disabled in production
- `console.log` / `console.debug` lint-banned in production
- License: BSL 1.1 on the repo (matches other adapters); makes hostile
  vendoring a license violation

### 6.7 Defensive domain registrations

Cheap insurance against typo-phishing:

- `recur.algovoi.co.uk` (typo) → 302 to canonical
- `recurr-algovoi.com` → 302
- `recurr.algovoi.com` → 302
- `recurring.algovoi.co.uk` → 302
- All at Cloudflare; trivially managed

DMARC + SPF + DKIM on `algovoi.co.uk` already exists; verify `recurr`
subdomain inherits.

---

## Pre-sign human-readable rendering (Phase 1, mandatory)

The Authority Summary Card renders **before any wallet prompt** from
the resolved token payload. Standard layout per chain:

```
┌─────────────────────────────────────────────────────────────────────────┐
│  [merchant-logo]   ACME Subscriptions                                   │
│                                                                         │
│  You are authorising AlgoVoi to pull payments on behalf of:             │
│    Merchant: ACME                                                       │
│                                                                         │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │  Amount per cycle:    $10.00 USDC                                 │  │
│  │  Cycle:               Monthly                                     │  │
│  │  Total cap:           $120.00 USDC (12 months)                    │  │
│  │  Per-transaction cap: $10.00 USDC                                 │  │
│  │  Authority expires:   2027-05-08                                  │  │
│  └───────────────────────────────────────────────────────────────────┘  │
│                                                                         │
│  Your wallet:  [Connect to confirm]                                     │
│  Chain:        Algorand mainnet                                         │
│                                                                         │
│  How it works                                                           │
│  • You sign a one-time authorisation in your wallet                     │
│  • ACME pulls $10 each month automatically                              │
│  • You can cancel any time at billing.acme.com                          │
│                                                                         │
│  About to sign:  [chain-specific copy — see below]                      │
│                                                                         │
│  This standing authority is not covered by the Payment Services         │
│  Regulations' chargeback provisions. For disputes contact ACME directly.│
│                                                                         │
│  By connecting your wallet and signing, you agree to AlgoVoi's          │
│  Terms of Service and Privacy Policy.                                   │
│                                                                         │
│         [Cancel]                       [Connect Wallet → Sign]          │
└─────────────────────────────────────────────────────────────────────────┘
```

Per-chain "About to sign" copy:

| Chain | Copy |
|---|---|
| **Algorand / VOI** | "You will sign 6 transactions in one atomic group: deploy a vault contract on your account, fund it with the subscription amount, register ACME as the only authorised recipient. The vault enforces caps on chain — even if AlgoVoi's keys are compromised, only ACME can pull, only up to your authorised amounts. Revoke by closing the vault contract — your unspent funds return to your wallet." |
| **Base / Tempo** | "You will sign one ERC-20 approve transaction granting AlgoVoi's facilitator address spending rights up to $120.00 USDC from your wallet. Standard token approval — your wallet shows this as 'Approve USDC.' AlgoVoi cannot spend more than this total. Revoke by approving 0 USDC to the same spender from any EVM wallet." |
| **Solana** | "You will sign one SPL Approve transaction delegating $120.00 USDC authority to AlgoVoi's facilitator program. The chain enforces this cap — over-spending is impossible. Revoke by calling Approve with amount=0." |
| **Hedera** | "You will sign one HTS AccountAllowanceApproveTransaction granting AlgoVoi's account allowance to spend up to $120.00 USDC from your account. Hedera enforces the allowance natively at the consensus layer. Revoke by approving 0 allowance." |
| **Stellar** | "You will sign a Soroban authorisation entry. This pre-authorises AlgoVoi's contract to call transfer up to $120.00 USDC from your account, valid for 12 months (about 6.3 million ledgers). Revoke by signing a new auth_entry with a past `valid_until_ledger`." |

**Algorand wallet UX honesty (critical):** Pera, Defly, Daffi all show
"Sign 6 transactions" on the wallet side. The summary card prepares
the customer; the txn note field carries the disclosure into every
wallet UI as a fallback.

**Legal disclosure (UK):** "This standing authority is not covered by
the Payment Services Regulations' chargeback provisions" line is
mandatory — accurate (crypto-native standing authorities are outside
PSR chargeback regime) and sets correct customer expectations.

---

## Post-sign monitoring + per-chain finality

| Chain | Mark active at | Reorg risk | Tx-stuck handling |
|---|---|---|---|
| **Algorand** | 1 confirmation (~4.5s, true finality) | None | `lastValid` round expiry → re-prompt with fresh params (no user re-sign of metadata) |
| **VOI** | Same as Algorand | None | Same |
| **Base** | 2 confirmations (~24s, PoS finality at L2) | First 2 blocks | Sit-in-mempool → "Pending — your wallet may need to speed up gas." Block-explorer link. After 5 min unconfirmed → "start over" with fresh token |
| **Tempo** | Same as Base | First 2 blocks | Same |
| **Solana** | `commitment: "confirmed"` (~1s, supermajority) | Slim | `recentBlockhash` 90s expiry → re-prompt |
| **Hedera** | 1 confirmation (~5s, true finality) | None | Near-instant; stuck effectively impossible |
| **Stellar** | 1 ledger close (~5-6s, true finality) | None | Same |

**EVM reorg honesty (cross-cuts the SDK):** the existing native adapters
+ MCP tools advertise the lifecycle as `pending → active`. On Base/Tempo
this is wrong for the first ~2 blocks. v1 introduces an intermediate
status `confirming`:

```
pending → confirming (EVM only, 2-block window) → active
        → active (Algorand / VOI / Hedera / Stellar — true finality)
```

This change touches all 5 native adapters + 2 MCP runtimes. Ships
alongside Phase 2 (EVM hosted page) as a v1.3.0 bump across the
adapter family.

**Reorg-drop detection (Phase 2-3):** if the per-pull reaper finds an
`approve` / `allowance` / `delegate` no longer exists on chain
(reorg dropped it), flag for manual review rather than auto-deactivate
— a false positive from a transient reorg shouldn't cancel a
legitimate subscription.

**Signing latency tracking:** delta between
`signing_token_first_resolved_at` and `activated_at` is the funnel
metric. SLO P95 < 30s for AVM/Stellar/Hedera/Solana; P95 < 120s for
EVM (includes reorg confirmation depth).

---

## Resilience / DR (Phase 1)

### Idempotency on `/confirm`

Specified above (gateway change #3). One `authority_confirmed` audit
row per authority regardless of how many times confirm is called.

### Signed-but-unconfirmed recovery

Gateway-side reaper (cron, every 60s) polls each chain for
authorities still in `pending` status whose
`signing_token_first_resolved_at` is > 5 minutes ago. If a matching
tx is found on chain, auto-confirm. Surfaces in the merchant
dashboard as "X authorities recovered automatically last 24h."

Page-side: persists `on_chain_tx_id` in `sessionStorage` immediately
after wallet returns the signature, before posting confirm. On page
reload after browser crash, page detects the stored tx_id, polls the
chain directly, and posts `/confirm` with the recovered address.

### Mid-sign network failure UX

`/confirm` returns 504 / network timeout → page shows "Processing —
your wallet signed successfully; we're finalising your subscription.
This may take up to 60 seconds." Auto-retry every 10s for up to 5
minutes. After 5 minutes, fall back to "Email us at
support@algovoi.co.uk with token hash `<hash>`."

### Status banner

`recurr.algovoi.co.uk/status.json` updated by operator during
incidents:

```json
{
  "status": "degraded",
  "message": "Algorand confirmations are slower than usual — please allow 30 extra seconds.",
  "chains_affected": ["algorand_mainnet"],
  "updated_at": "2026-05-08T12:00:00Z"
}
```

Page fetches on load + every 60s. Renders thin amber bar at top when
status != "ok". Operator updates via gh-pages branch with auto-deploy.

### DR domain

Phase 7 / post-£150k: `recurr2.algovoi.co.uk` as a separate Cloudflare
Pages project for manual failover. Failover is operator-action, not
automatic — automatic failover for crypto-signing surfaces creates
split-brain risk.

### Brand-incident playbook

`content/runbooks/recurr_hosted_auth/brand_incident.md`:
- DNS rollback path documented (Cloudflare DNS history)
- Public statement template ready
- Rebuild-from-clean-source playbook (last-known-good commit pinned in
  CI as the rollback target)
- Customer comms via merchants' channels (AlgoVoi has no direct
  customer channel)

---

## Multi-tenant architecture

### Phase 1 (v1): shared domain, per-tenant branding

`recurr.algovoi.co.uk/<token>` for all tenants. Merchant logo + name +
brand colour from the resolved token payload's `merchant` object.
Defaults to AlgoVoi branding if tenant hasn't uploaded.

### Phase 2-7 (post-Algorand-demo): forward-compatible architecture

The token-resolve endpoint MUST NOT validate `Origin` against a
whitelist — that breaks per-tenant custom domains later. Validates
only token identity.

`merchant` payload includes `brand_primary_color`, `brand_secondary_color`,
`logo_url` — page applies as CSS custom properties.

### Post-£150k: custom domains

`billing.acme.com` → CNAME → Cloudflare Pages project. Cloudflare
handles per-tenant TLS via ACME automatically (Cloudflare for SaaS).
Per-tenant CORS allowlist on the gateway. Per-tenant CSP relaxation
optional. Operator action: add domain to Pages project (can be
automated via Cloudflare API from the merchant dashboard).

`create_recurring_authority` response chooses domain:

```python
domain = tenant.custom_recurr_domain or "recurr.algovoi.co.uk"
authorisation_url = f"https://{domain}/{row.signing_token}"
```

---

## Privacy / GDPR (Phase 1)

### Data collected

| Data | Where | Retention | Legal basis |
|---|---|---|---|
| Wallet address | `recurring_authorities` operational + `compliance_events` (hashed) chain | Operational: cap_period_seconds + 30d, then auto-delete. Chain: 7 years (Object Lock) | Legitimate interests + contractual necessity |
| IP address | Cloudflare logs (raw, 30d) + chain (daily-salted hash, 7y) | 30d raw / 7y hash | Legitimate interests (rate-limit + bot protection) |
| User-Agent class | Chain rows only ("browser" / "mobile" / "bot") | 7y | Legitimate interests |
| Country (geofence) | Not stored, only inspected at edge | N/A | Legitimate interests |

**Not collected:** name, email, phone, payment card, persistent
cookies, device fingerprints, browser cookies (zero-cookie target).

### GDPR Art. 17 vs Object Lock

Real tension:
- Operational `recurring_authorities` row: **erasable** on Art. 17
  request. Soft-delete with tombstone marker
  `[ERASED per Art. 17 request <date>]`.
- Audit chain rows (Object Lock 7y): **NOT erasable**. Documented
  legal basis: GDPR Recital 65 + Art. 17(3)(b) — retention required
  for compliance with a legal obligation. Specifically:
  - **UK MLRs Reg 40(3)** — 5-year retention of CDD records
  - **FCA SYSC 22** — prudent extension to 7 years for sanctions
    screening evidence
  - **AlgoVoi's Object Lock COMPLIANCE-mode** retention (7y) matches
    these obligations

Privacy policy must explicitly cover this:

> We retain transaction audit records for 7 years as required by
> UK Anti-Money Laundering Regulations (MLRs Reg 40(3)) and FCA SYSC
> 22 sanctions-screening evidence requirements. These records contain
> only your wallet address (which is public on-chain) and are stored
> in tamper-evident write-once storage. They cannot be deleted on
> request. Your operational subscription record, however, is fully
> erasable under GDPR Article 17 — contact privacy@algovoi.co.uk.

This is a **mandatory** policy text. Cannot ship Phase 1 without it.
Lawyer should review wording but the legal basis is sound.

### Cookie posture

**Zero cookies, zero analytics v1.** No GA, no Mixpanel, no Sentry-
with-cookies. Sentry-on-error is fine if cookieless (Glitchtip self-
hosted EU is the recommended path). Server-side metrics only via
Cloudflare's aggregate analytics. Avoids cookie banners entirely; UK
ICO + EU EDPB confirm zero-tracking sites need no consent banner.

### Data residency

- Operational store: AlgoVoi gateway (UK VM1)
- Audit chain: Backblaze B2 EU-Central-003 (Object Lock 7y) — EU adequacy
- Cloudflare logs: configurable, default UK / EU regions

---

## Observability (Phase 1 minimal, Phase 2 full)

### Phase 1 minimal

- `/health` endpoint → `200 ok`
- Cloudflare aggregate analytics (built-in, free)
- Sentry / Glitchtip for JS exceptions (no PII; filter stack traces)
- Structured logs on gateway endpoints (existing pattern)

### Phase 2 full funnel

Page sends events to `POST /v1/telemetry/page-metrics` on the gateway
(no auth — public endpoint, no PII):

- `page_loaded` — token resolved successfully
- `wallet_connect_started`
- `wallet_connect_failed` (kind: extension_not_found / user_rejected / network_mismatch)
- `pre_sign_displayed`
- `sign_requested`
- `sign_succeeded`
- `sign_rejected`
- `confirm_succeeded`
- `confirm_failed`
- `redirect_executed`

Dimensions per event: chain, wallet_kind (pera/metamask/etc.),
authority_id_hash, ts. **No customer-identifying data.**

Funnel SLO: page_loaded → confirm_succeeded > 70% per chain within
6 months. Industry benchmark for crypto-checkout: 60-80%.

### Compliance attestation

`/compliance/attestation` adds `tier2_hosted_auth` stanza (above) once
page ships. Updates monthly with rolling 30-day uptime + sign-success-
rate metrics. Public, machine-readable, buyer-DD-relevant.

### SLO targets

| Metric | Target |
|---|---|
| Page availability | 99.9% (Cloudflare Pages SLA) |
| Token resolution P95 latency | < 500ms |
| Confirm endpoint P95 latency | < 2s (incl. screening) |
| Time-to-active P95 (AVM/Stellar/Hedera/Solana) | < 30s |
| Time-to-active P95 (EVM) | < 120s |
| Confirm error rate (excluding user-rejected) | < 1% |

---

## Incident response

### Runbooks (private, in -Hand `content/runbooks/recurr_hosted_auth/`)

- **`signing_stuck.md`** — customer signed but subscription not active.
  Step-by-step (existing in Comet's pass; adopted as canonical).
- **`page_unreachable.md`** — Cloudflare Pages outage. Failover steps.
- **`sanctions_false_positive.md`** — wallet flagged but customer is
  legitimate. SAMLA-tipping-off-aware response template + MLRO sign-off
  procedure.
- **`wallet_compatibility_issue.md`** — new wallet release breaks sign
  flow.
- **`mass_revoke.md`** — operational emergency: bulk-revoke for one
  tenant.
- **`brand_incident.md`** — page defacement / DNS hijack response.

### On-call (post-launch)

- Until v1 commercial launch: founder on-call (Chris)
- Post-launch: rotation between founder + first hire
- PagerDuty escalation: Chris primary
- Quiet hours: 22:00-08:00 UK; only critical alerts (page down, gateway
  5xx surge)

### Postmortem template

Standard blameless format (date, duration, impact, root cause, timeline,
resolution, follow-ons, audit-chain entries). Postmortems published
internally. Customer-facing summaries published if customer-impacting.

---

## Customer support integration

### Phase 1: mailto

Footer link "Having trouble?" opens
`mailto:<merchant_email>?subject=Signing+issue+with+authority+<token_hash>`.
Token hash (not raw) in subject lets merchant + AlgoVoi correlate
without exposing live token. Merchant owns the customer relationship
(B2B model); AlgoVoi support handles merchant-escalated issues only.

### Phase 3+: merchant dashboard support view

Read-only authority lifecycle view, scoped by tenant via existing RLS
policy. Manual confirm tool requires agent + MLRO sign-off. No direct
DB access from support agents.

---

## CI/CD + test pyramid

### Test pyramid

```
┌──────────────────────────┐
│ E2E (Playwright)         │  1 testnet test per chain
├──────────────────────────┤
│ Integration (vitest+MSW) │  mocked gateway, real chain libs
├──────────────────────────┤
│ Unit (vitest)            │  per-chain tx construction (high volume)
└──────────────────────────┘
```

### Unit (vitest)

Per-chain tx construction validates: correct fields in constructed tx,
correct signing-template fields, error paths (insufficient balance,
wrong network, oversize amounts). Target 80%+ coverage on chain
modules. Each chain gets its own test file mirroring the native-* SDK
pattern.

### Integration (vitest + MSW)

Mock the gateway endpoints via MSW. Test: token resolve → render
summary card → confirm success → redirect. Test: confirm 403 (sanctions)
→ generic "declined" error. Test: 410 (expired) → expired screen. Test:
500 → retry option.

### E2E (Playwright + wallet automation)

Real testnet, real wallet automation. Per chain:
- Algorand: Lute extension (most automation-friendly) on testnet
- Base: MetaMask Sepolia
- Solana: Phantom devnet
- Hedera: HashPack testnet
- Stellar: Freighter testnet
- VOI: Lute testnet (same code path as Algorand)

Apply the smoke+e2e protocol from -Hand to each chain. Before a chain
is declared "Phase N done," its e2e test must pass.

### CI gates (GitHub Actions)

```yaml
on: push
jobs:
  lint:    # tsc --noEmit + eslint + prettier check
  unit:    # vitest run
  audit:   # npm audit --audit-level=high
  build:   # vite build (verify bundle ≤ 500 KB gzip)
  e2e:     # playwright testnet (on merge to main only)
  deploy:  # Cloudflare Pages preview (PR) or production (main)
```

Manual approval gate for production deploy (paranoid but right for
wallet-signing surface). Preview deploys automatic on PR.

### Versioning + artefact integrity

Semantic versioning (`v0.1.0`, `v0.2.0`). Each release tag triggers
GitHub Release with `dist/` SHA-256 hash recorded in release notes
(Comet add-on: bundle-hash transparency for security-conscious
customers).

### Dependency management

- Renovate auto-merges patch security updates only; minor/major require
  PR review
- `package-lock.json` checked in
- `npm ci` in CI (not `npm install`)
- Dependabot for `actions/*` in workflows

---

## Wallet UX edge cases

| Category | Phase 1 posture |
|---|---|
| Hardware (Ledger/Trezor) | EVM transparent via MetaMask. Solana native via wallet-adapter. Algorand: Pera mobile only (extension flow doesn't expose Ledger natively). Hedera/Stellar: limited browser support — documented |
| Multi-sig (Safe / Squads) | Detect via on-chain code presence. Show "Multi-sig wallet detected — please contact your merchant; multi-sig flow coming Phase 2 (EVM)." |
| Smart-contract wallets (Coinbase Smart, Argent) | EVM: transparent through RainbowKit's coinbaseWallet connector + WC. Test on Base testnet. |
| MPC / embedded (Magic, Privy, Web3Auth) | Show "Embedded wallets aren't supported on this page. Use the merchant's in-site checkout instead." Per-tenant CSP relaxation for iframe-embed is post-£150k. |

---

## Browser compatibility matrix

| Browser | Min version | Notes |
|---|---|---|
| Chrome / Chromium | 90+ | Primary; all wallets work |
| Edge | 90+ | Same as Chrome |
| Firefox | 90+ | Most wallets work; HashPack issues |
| Safari | 15+ | EVM via WC2 only; Pera Web limited; Lute / Phantom / Freighter extensions don't ship for Safari. **Show "best on Chrome/Edge/Brave" copy on connect screen** |
| Brave | latest | Same as Chrome |
| Mobile Chrome (Android) | 90+ | WC v2 deep-link to wallet apps |
| Mobile Safari (iOS) | 15+ | WC v2 only; show "switch to desktop" advice |
| IE11 | NOT supported | Hard "browser not supported" page |

Per-chain × browser detail in Comet's matrix (above) — adopted as
canonical Phase-2-7 testing reference.

**Graceful degradation:** if a wallet extension is not installed, page
shows "No <wallet> extension found. [Install <wallet>] or [Connect
via QR with mobile wallet]." Install link goes to wallet's official
page (hardcoded per wallet — no dynamic URL construction).

---

## Internationalisation (architecture v1, locales later)

- `react-i18next` from day one
- Every user-visible string in `src/i18n/en.json`
- Locale detection: `Accept-Language` → fallback to `en`
- URL override `?lang=` (no language picker UI v1)
- Logical CSS properties (`margin-inline-start` etc.) for free RTL
- Wallet error mapping: catch error code → map to i18n key (not raw
  message)

Languages priority order (post-launch):
1. English (Phase 1)
2. Spanish (LATAM crypto)
3. German (DACH + EU compliance)
4. Japanese (large stablecoin market)
5. Portuguese (Brazil)
6. Arabic (RTL test + UAE/Saudi)

---

## Accessibility (WCAG 2.1 AA target)

Phase 1 must-haves:

1. **Focus management** — wallet prompt opens, focus stays in flow.
   After wallet closes (signed/cancelled), focus returns to "Connect
   Wallet" button.
2. **`aria-live="polite"` status region** — announces "Waiting for
   blockchain confirmation" → "Subscription activated" to screen
   readers.
3. **`role="alert"` on errors** — wallet rejection / network errors
   announced immediately.
4. **Colour contrast 4.5:1 body / 3:1 large** — verify with contrast
   analyser.
5. **Accessible button labels** — `aria-label="Connect with Pera Wallet"`
   not just "Connect."
6. **Keyboard-only navigation** — Tab/Enter/Space/Esc work throughout.
   Test with keyboard-only before launch.
7. **Skip link** — `<a href="#main" class="skip-link">Skip to main
   content</a>` first element.
8. **Page title updates per state** — "Authorising subscription — Sign
   in your wallet."
9. **No flashing > 3Hz** — covers seizure risk.
10. **Alt text or `role="presentation"`** on every image.

**Wallet extension a11y floor:** wallet extensions vary wildly (Pera +
MetaMask are best; some have inaccessible shadow-DOM modals). Privacy/
Access page recommends "If you use a screen reader, Pera (Algorand)
or MetaMask (EVM) have the strongest a11y support." Honest disclosure.

Formal WCAG audit by external firm: post-£150k or once volume warrants.

---

## Costs

| Volume | Page delivery | Gateway API | WalletConnect | Total |
|---|---|---|---|---|
| 100 sign events / month | $0 (CF free) | $0 | $0 (free tier) | **$0** |
| 10k / month | $0 (CF free) | ~$5 (VM overhead) | $0 | **~$5** |
| 100k / month | ~$5 | ~$50 | $0 (under 300k MAU) | **~$55** |
| 1M / month | ~$50 (CF Pro) | ~$200-500 (VM scale) | ~$50 (WC Pro) | **~$300-600** |

**Pricing model:** **free at all volumes.** The hosted page is part of
AlgoVoi's value proposition, not a revenue line. Cost absorbed into
existing subscription pricing (per-pull facilitator fees scale linearly
with volume; hosting cost is dwarfed).

---

## Versioning / migration

### Wire format dispatch

Every chain module's `handlePayload(payload)` switches on
`payload.format_version`. v1 handlers stay shipped permanently. When
v2 ships (post-£150k), add a v2 case; both work simultaneously during
the dual-path period.

### SPA versioning

Cloudflare Pages atomic deploys. No "old version still in use" scenario
— users are on the page < 5 minutes per session.

### URL versioning

Do NOT version URL (`recurr.algovoi.co.uk/v2/<token>`). Token resolves
to correct wire format regardless. If a future breaking change requires
new URL scheme, use 302 redirect from old → new with migration notice.

---

## Sequencing (Phase 1 = buyer-DD demo, ~3 hours real-world)

### Phase 1 — Algorand-first end-to-end (target: ~3 hours)

**Includes all Phase 1 must-haves from the gap analysis:**

1. Repo scaffold (Vite + React + TS + Tailwind + react-i18next + WC2)
2. Cloudflare Pages connected, custom domain working
3. CSP + security headers in `_headers` file
4. Token resolution + confirm against gateway (real, not mocked)
5. Authority Summary Card component (Algorand copy)
6. Pera Wallet integration with note-field disclosure
7. Algorand SpendingCapVault construction (port Recurr/algorand/README.md)
8. Sanctions screening at `/confirm` (gateway change)
9. Audit-chain events fired (gateway change)
10. Idempotency on `/confirm` (gateway change)
11. EU geo-block WAF rule
12. Constant-time token lookup (gateway change)
13. Privacy policy + ToS static pages with GDPR Art. 17 text
14. Health endpoint + status banner architecture
15. Mailto support footer
16. Basic a11y (focus mgmt, aria-live, contrast, keyboard nav)
17. Vitest unit tests for Algorand tx construction
18. GitHub Actions: lint + test + audit + build gates
19. Mailto runbook + signing-stuck runbook
20. Demo: real testnet sign-and-confirm cycle, screenshot for buyer DD

### Phase 2 — EVM (Base + Tempo) (~1.5 hours)

- RainbowKit / Reown AppKit drop-in
- ERC-20 approve construction
- Per-chain copy + summary card EVM variant
- `confirming` status introduced across native-* + MCP (touches all 5 + 2)
- Reorg handling (2-block depth before active)
- Multi-sig detection (Phase 2 stub message)
- Base sepolia testnet flow + e2e

### Phase 3 — Solana (~1 hour)

- wallet-adapter-react drop-in
- SPL Approve construction
- Phantom devnet flow + e2e

### Phase 4 — Hedera (~1.5 hours)

- HashConnect 3 / @hashgraph/hedera-wallet-connect
- HTS allowance approve
- HashPack testnet flow + e2e
- Protobuf runtime version pin

### Phase 5 — Stellar (~1.5 hours)

- Stellar Wallets Kit
- Soroban auth_entry signing (Freighter only v1)
- 7-decimal precision honoured
- Freighter testnet flow + e2e

### Phase 6 — VOI (~30 min)

- Lute + Kibisis adapters
- Same SpendingCapVault code path as Algorand

### Phase 7 — Polish + production

- Loading states, error UX, retry flows, copy review
- Mobile responsive check (still desktop-first; mobile deep-link post-£150k)
- HSTS preload submission
- CSP-Report-Only enforcement window
- Visual regression tests (Percy / Chromatic)
- WAF tuning based on Phase 1-6 telemetry
- Production deploy approval

**Total Phase 1-7:** ~10-12 hours real-world for all 7 chains. **Phase 1
alone (~3 hours)** ships the buyer-DD demo: "screenshot the page,
customer signs, subscription active." That's the £150k-arc valuation
moment.

---

## Out of scope v1 (deferred)

- Mobile-deep-linking deep dive (WC v2 covers basic case; per-chain
  deep-link UX optimisation post-£150k)
- 3DS-style fallback (out of scope — non-crypto users go through Tier 1)
- Multi-language (English only v1; architecture supports later)
- Operator-facing analytics on conversion funnels (separate dashboard)
- A11y formal external audit (basic a11y v1, formal post-£150k)
- Customer-side authority listing (`recurr.algovoi.co.uk/me`)
- Per-tenant custom domains (Phase-2-built architecture, ship-time
  post-£150k)
- Per-tenant CSP relaxation for iframe-embed (post-£150k)
- 100% wallet-extension a11y (out of our control)
- Embedded MPC wallets (Magic / Privy / Web3Auth) — show fallback
  message v1
- Multi-sig signing flow beyond detection-and-message (Phase 2 EVM Safe
  only; other chains post-£150k)
- Hardware wallets where chain-wallet doesn't expose them natively
  (documented limitation)

---

## Open design questions — operator decisions needed

Before any code lands, decisions on:

1. **Repo location:** A (folder in Platform-Adapters) / **B (new public
   repo `recurr-hosted-page`) ← recommended** / C (chrome/site sibling)?
2. **Tech stack:** Vite + React + TS + Tailwind + react-i18next +
   Reown AppKit confirmed?
3. **Phase 1 scope:** Algorand-first then chain-by-chain — confirmed?
4. **Token expiry:** 24h default — confirmed?
5. **Re-prompt active-status authority on `/<token>`:** friendly redirect
   to merchant — confirmed?
6. **Merchant branding:** logo + name + brand colour from tenant
   payload — confirmed (matches Tier 1)?
7. **Geo-block scope:** EU + OFAC-11 v1, with FCA-perimeter call before
   non-test merchant production launch — confirmed?
8. **Privacy policy text on Art. 17 vs Object Lock:** as drafted above —
   confirmed (suggests lawyer review pre-EU launch)?
9. **`confirming` status across native-* + MCP:** ship the lifecycle
   change as v1.3.0 bump alongside Phase 2? (Affects 5 native adapters
   + 2 MCP runtimes — additive enum value, doesn't break existing
   consumers)
10. **WalletConnect Project ID:** dedicated for `recurr.algovoi.co.uk`,
    NOT shared with the existing `/recurr/portal` — confirmed?

Once these are answered, **Phase 1 = ~3 hours of work** producing the
buyer-DD screenshot moment. Phases 2-7 land per session over the
following week.

---

## Reference

- **Synthesis source documents:**
  - `content/comet_recurr_hosted_auth_review.md` (~1,150 lines, Comet pass)
  - `content/claude_recurr_hosted_auth_review.md` (~750 lines, Claude pass)
- **Per-chain wire formats:** `Recurr/<chain>/README.md` in this repository
- **Tier 1 hosted checkout (existing pattern to mirror):**
  `api.algovoi.co.uk/checkout/<token>`
- **Smoke + e2e protocol:** `content/smoke_e2e_protocol.md` in -Hand
- **Existing -Hand recurring router:** `gateway/app/routers/recurring.py`
- **Existing audit chain shipping:** `audit_log` + `screening_hits` +
  `compliance_events` with Object Lock 7y B2 retention, HMAC
  bundle_signature, public verifier at
  `github.com/chopmob-cloud/algovoi-audit-verifier`
- **Compliance attestation surface:**
  `https://api.algovoi.co.uk/compliance/attestation`
- **CSP nonce migration reference (existing /recurr/portal work):**
  `content/csp_nonce_migration_recurr_portal.md` in -Hand

---

## Acknowledgements

This v1 design is the synthesis of independent reviews by Claude and
Comet, both working from v0 in parallel. The five highest-priority
gaps (sanctions screening at confirm, audit-chain integration, CSP +
security posture, pre-sign summary card, idempotency on confirm)
appeared in both reviews — high-confidence findings. Comet's pass
contributed: constant-time token lookup, CSP-Report-Only window, EU
geo-block as Phase 1, Algorand note-field as primary disclosure,
Reown vendor risk articulation, MLRs Reg 40(3) legal-basis text for
Art. 17 conflict, signed-but-unconfirmed reaper recovery flow,
webhook retry confirmation as a separate enterprise gap. Claude's pass
contributed: `confirming` status cross-cutting impact across SDK +
MCP, defensive domain registrations, hash-vs-raw audit-chain pattern,
per-chain finality table with explicit reorg-drop behaviour, full
test pyramid + visual regression, Algorand 6-action wallet UX honesty
audit. Both reviews independently flagged identical priority for Phase
1 must-haves.
