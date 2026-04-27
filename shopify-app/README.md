# AlgoVoi Shopify App

Accept stablecoin payments (**USDC / aUSDC / USDCe** on Algorand, VOI, Hedera, Stellar, Base, Solana, and Tempo) on a Shopify store, alongside the merchant's normal Shopify checkout.

The app deploys to **Cloudflare Pages** and wires into Shopify via:

- **OAuth** with expiring offline tokens (Shopify standard since April 2026), with auto-refresh on 401/403
- **A Checkout UI Extension** that injects a "Pay with Crypto" call-to-action on the thank-you and order status pages
- **An `orders/create` webhook** that verifies HMAC and creates the corresponding AlgoVoi checkout link
- **The three required GDPR webhooks** (customers-data-request, customers-redact, shop-redact)

> **License:** Reference implementation for connecting your own store to your own AlgoVoi tenant. You may NOT operate it as a competing hosted payment service. See [LICENSE](../LICENSE).

---

## Flow

```
                    ┌─────────────────────────────────────────────┐
                    │  Shopify Native Checkout (untouched)        │
                    │  Customer pays via card / Apple Pay / etc.  │
                    └──────────────┬──────────────────────────────┘
                                   │
                                   ▼
    Shopify thank-you page ─────►  ◆ AlgoVoi   [Pay with Crypto]
                                   │ (UI extension renders blue
                                   │  button block, all 7 chains
                                   │  available)
                                   ▼
    /pay (branded chain picker) ─► Customer selects network
                                   │
                                   ▼
    /api/pay-redirect           ─► AlgoVoi /v1/payment-links
                                   │
                                   ▼
    302 to AlgoVoi hosted        ─► Customer pays on-chain
    checkout (USDC / aUSDC /        (Algorand / VOI / Hedera /
    USDCe across all 7 chains)      Stellar / Base / Solana / Tempo)
                                   │
                                   ▼
    AlgoVoi → /api/order-paid    ─► HMAC verified → mark Shopify
    (signed by SHOPIFY_CLIENT_       order paid via GraphQL Admin
    SECRET)                          orderMarkAsPaid mutation
```

The Shopify checkout itself is never touched — AlgoVoi is a **post-checkout payment surface**, so the app slips in alongside any other payment processor without conflicting.

---

## Architecture

```
shopify-app/
├── functions/                            Cloudflare Pages Functions
│   ├── auth/
│   │   ├── install.js                    OAuth start
│   │   └── callback.js                   OAuth callback (offline expiring tokens)
│   ├── api/
│   │   ├── _shopify-client.js            Shared Admin API helper with
│   │   │                                 auto token-refresh on 401/403
│   │   ├── connect.js                    Save merchant AlgoVoi creds +
│   │   │                                 register orders/create webhook
│   │   ├── payment-link.js               Multi-chain payment link API
│   │   ├── pay-redirect.js               Per-chain payment-link 302 with
│   │   │                                 HMAC callback signature
│   │   ├── order-paid.js                 AlgoVoi → Shopify mark-as-paid
│   │   │                                 (HMAC-verified)
│   │   └── x402/session.js               Browser-extension auto-pay session
│   └── webhooks/
│       ├── shopify.js                    HMAC-validated inbound webhook handler
│       └── gdpr/
│           ├── customers-data-request.js Required GDPR endpoint
│           ├── customers-redact.js       Required GDPR endpoint
│           └── shop-redact.js            Required GDPR endpoint
├── extensions/
│   └── algovoi-pay-button/               Checkout UI Extension (Preact)
│       └── src/
│           ├── thank-you.jsx             purchase.thank-you.block.render
│           └── index.jsx                 customer-account.order-status.block.render
├── public/
│   ├── index.html                        Merchant setup page
│   ├── pay/index.html                    Customer chain selection page
│   │                                     (canonical AlgoVoi panel design)
│   └── privacy.html                      Privacy policy (Shopify-required)
├── shopify.app.toml                      Shopify partner config
├── wrangler.toml                         Cloudflare Pages config (placeholder
│                                          KV namespace ID — fill in your own)
├── package.json
├── order-confirmation-email.liquid       Optional email template
└── shopify-additional-scripts.html       Legacy thank-you injection (deprecated
                                           by Shopify in newer themes; kept for
                                           historical reference)
```

---

## Architectural notes (read first)

**The Cloudflare Worker is admin-key-free.** Earlier revisions of this app held an `ALGOVOI_ADMIN_KEY` secret in Cloudflare Pages and used it to register Shopify integrations on the AlgoVoi platform (`POST /api/integrations/{tenant}/shopify`). This put a privileged admin token on the public-internet attack surface, which is the wrong shape.

**Current model:**

- The Worker stores per-merchant data in Cloudflare KV: `tenant_id`, `api_key` (merchant-scoped), Shopify access/refresh tokens, and `webhook_secret` for inbound HMAC validation.
- `webhook_secret` and `integration_id` are provisioned **out of band by the AlgoVoi dashboard** when a merchant connects their store. The dashboard has internal access to AlgoVoi admin endpoints; the Worker does not.
- `connect.js` only verifies the merchant key works, registers the Shopify webhook, and persists tenant/key. It MERGES into the existing KV record so out-of-band fields (`webhook_secret`, `webhook_url`, `integration_id`) are preserved.

**Token lifecycle:**

- Shopify access tokens are **expiring offline** (Shopify standard since April 1, 2026) — TTL ~60 min, with a 90-day refresh token.
- All Shopify API calls go through `shopifyFetch()` in `_shopify-client.js`, which auto-refreshes on 401/403 and updates KV transparently.
- If the refresh token is also expired, the helper returns a friendly "Reconnect Store" page (`reauthResponse()`).

**AlgoVoi credentials lifecycle:**

- The merchant `algv_*` API key is stored in KV alongside the Shopify tokens.
- If AlgoVoi rotates/revokes that key, `pay-redirect.js` detects the 401 from `/v1/payment-links` and serves a friendly "AlgoVoi connection expired" page directing the merchant to the dashboard to issue a fresh key.

---

## Setup

### Prerequisites

- A [Shopify Partners](https://partners.shopify.com) account (free)
- A [Cloudflare](https://cloudflare.com) account (free tier sufficient)
- An [AlgoVoi tenant account](https://dash.algovoi.co.uk/) with a merchant API key

### 1. Create the Shopify Custom App

1. Go to **partners.shopify.com → Apps → Create app**
2. Set **Application URL** to your Cloudflare Pages URL (e.g. `https://worker.algovoi.co.uk`)
3. Set **Allowed redirection URL** to `https://<your-domain>/auth/callback`
4. Enable scopes: `read_orders`, `write_orders`
5. Note your **Client ID** (public, goes in `shopify.app.toml`) and **Client Secret** (sensitive, goes in Cloudflare secrets)

### 2. Create the Cloudflare KV namespace

```bash
cd shopify-app
npx wrangler kv namespace create MERCHANTS
```

Copy the returned `id` into `wrangler.toml`, replacing `YOUR_KV_NAMESPACE_ID`.

### 3. Set Cloudflare Pages secrets

```bash
npx wrangler pages secret put SHOPIFY_CLIENT_SECRET \
    --project-name=your-pages-project
```

(Paste the Shopify Client Secret when prompted. It is referenced by the Worker via `context.env.SHOPIFY_CLIENT_SECRET` and is used to verify HMAC callback signatures from AlgoVoi.)

### 4. Update `shopify.app.toml`

Replace `client_id` with your Shopify app's Client ID. Update `application_url` and the GDPR webhook URLs to your Cloudflare Pages domain.

### 5. Update `APP_BASE` constants

Search and replace `worker.algovoi.co.uk` with your actual domain in:

- `extensions/algovoi-pay-button/src/index.jsx`
- `extensions/algovoi-pay-button/src/thank-you.jsx`
- `functions/api/connect.js`
- `functions/api/pay-redirect.js`
- `functions/api/order-paid.js`
- `functions/api/x402/session.js`
- `functions/api/_shopify-client.js`
- `public/pay/index.html`
- `shopify-additional-scripts.html`

### 6. Deploy to Cloudflare Pages

```bash
npx wrangler pages deploy public --project-name=your-pages-project
```

### 7. Deploy the Shopify extension

```bash
npm install
npx shopify app deploy --allow-updates
```

This pushes the UI extension to Shopify's CDN and bumps the app version (e.g. `algovoi-NN`). The extension auto-installs into the merchant's checkout customizer when they install the app.

### 8. Merchant install flow

Direct merchants to:

```
https://<your-domain>/auth/install?shop=<their-store>.myshopify.com
```

This kicks off the OAuth flow. After install, the merchant lands on `/?shop=...&installed=1`, where they enter their AlgoVoi `tenant_id` + `api_key`.

### 9. Provision `webhook_secret` (admin-side)

The merchant's AlgoVoi dashboard registers the Shopify integration server-side, generates a `webhook_secret`, and writes it into the merchant's Cloudflare KV record (via a privileged channel). This step is intentionally NOT exposed via the public Worker.

### 10. Customer experience

- Customer completes Shopify checkout normally
- On the thank-you page, the UI extension renders a solid blue "Pay with Crypto" button
- Click → `/pay` (branded chain picker — same canonical AlgoVoi panel design used by all other adapter checkouts)
- Customer picks chain → 302 to AlgoVoi hosted checkout → pays on-chain
- AlgoVoi callback fires `/api/order-paid` (HMAC-verified) → Shopify order marked paid via `orderMarkAsPaid` GraphQL mutation

---

## Supported chains (all 7)

| Chain    | Asset | Token   | Default colour | URL chain code |
|----------|-------|---------|----------------|----------------|
| Algorand | USDC  | ASA #31566704 | `#3b82f6` | `ALGO`  → `algorand_mainnet` |
| VOI      | aUSDC | ASA #302190   | `#8b5cf6` | `VOI`   → `voi_mainnet` |
| Hedera   | USDC  | HTS token     | `#10b981` | `HBAR`  → `hedera_mainnet` |
| Stellar  | USDC  | Stellar asset | `#06b6d4` | `XLM`   → `stellar_mainnet` |
| Base     | USDC  | ERC-20        | `#2563eb` | `BASE`  → `base_mainnet` |
| Solana   | USDC  | SPL token     | `#9333ea` | `SOL`   → `solana_mainnet` |
| Tempo    | USDCe | Bridged ERC-20| `#f59e0b` | `TEMPO` → `tempo_mainnet` |

---

## Security

- **Inbound webhook HMAC** — every `orders/create` webhook from Shopify is verified via `X-Shopify-Hmac-Sha256` against `SHOPIFY_CLIENT_SECRET`
- **AlgoVoi callback HMAC** — `/api/order-paid` verifies a signature computed against `SHOPIFY_CLIENT_SECRET` (so a 3rd party can't fake "the order was paid"; only AlgoVoi knows the secret)
- **GDPR webhook handlers** — three required endpoints respond 200 within Shopify's 5-second SLA
- **Token storage** — Shopify access/refresh tokens, AlgoVoi `algv_*` keys, and webhook secrets all live in Cloudflare KV server-side, never exposed to client browsers
- **Auto token refresh** — expired Shopify access tokens are silently refreshed via the stored refresh token on next API call
- **Admin-key removed** — the Worker no longer holds any AlgoVoi admin credentials; integration registration is dashboard-mediated
- **Cancel-bypass prevention** — Shopify order is only marked paid AFTER an HMAC-verified callback from AlgoVoi (not on the AlgoVoi checkout redirect alone)

---

## Submitting to the Shopify App Store

This app is structured to satisfy Shopify's listing requirements:

| Requirement | Status |
|---|---|
| OAuth with expiring offline tokens (April 2026 standard) | ✅ `auth/callback.js` uses `expiring: 1` |
| Auto-refresh on 401/403 | ✅ `_shopify-client.js` |
| Three GDPR webhooks (data-request, customers-redact, shop-redact) | ✅ `functions/webhooks/gdpr/` |
| HMAC-verified inbound webhooks | ✅ `webhooks/shopify.js` |
| Privacy policy URL | ✅ `public/privacy.html` |
| Specific OAuth scopes (least privilege) | ✅ Only `read_orders, write_orders` |
| App icon + screenshots | Provided separately during submission |
| Demo video | Recommended for the listing |

See the upstream repo's [marketplace_submissions.md](../) memory for the full submission checklist.

---

## Extension SDK notes

The Shopify Checkout UI Extensions SDK changed significantly in 2026:

- Uses **Preact** (not React) with `jsxImportSource: "preact"`
- Components use the `s-` prefix: `<s-banner>`, `<s-button variant="primary">`, `<s-text>`, `<s-link>`, `<s-stack>`, `<s-divider>`
- Global `shopify` object (not passed as argument)
- `export default async () => { render(<Component />, document.body) }`
- Order ID accessed via `shopify.orderConfirmation?.value?.order?.id` (thank-you target) or `shopify.order?.id` (order-status target)
- Shop domain via `shopify.shop?.myshopifyDomain`
- Must extract numeric ID with `.match(/\d+$/)?.[0]` (GraphQL IDs include type prefix)
- `<s-button>` colour follows the **merchant's theme primary**, not configurable from inside the sandbox; raw `<a>` with inline styles is stripped by the extension worker

---

## Related

- [`../woocommerce/`](../woocommerce/) — WooCommerce gateway plugin (same canonical panel design)
- [`../prestashop/`](../prestashop/) — PrestaShop gateway module
- [`../opencart/`](../opencart/) — OpenCart hosted + extension gateway
- [`../shopware/`](../shopware/) — Shopware 6 plugin
- [`../magento2/`](../magento2/) — Magento 2 module
