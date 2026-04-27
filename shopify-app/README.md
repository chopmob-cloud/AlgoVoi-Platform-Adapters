# AlgoVoi Shopify Payment App

Accept crypto payments (USDC on Algorand, VOI, Hedera, and Stellar) on your Shopify store. Deploys to **Cloudflare Pages** with **Shopify Checkout UI Extensions**.

> **License:** This code is provided as a reference implementation for integrating your own store with your own AlgoVoi tenant account. You may NOT operate it as a competing hosted payment service. See [LICENSE](../LICENSE) for full terms.

---

## How it works

```
Customer places order on Shopify
        ↓
Webhook fires → AlgoVoi creates payment link → order note updated
        ↓
Thank-you page shows "Pay with Crypto →" (checkout extension)
        ↓
Customer selects chain (Algorand / VOI / Stellar / Hedera)
        ↓
Redirected to AlgoVoi hosted checkout → pays on-chain
        ↓
Order marked as paid in Shopify via API
```

---

## Prerequisites

- [Shopify Partners](https://partners.shopify.com) account with a Custom App
- [Cloudflare](https://cloudflare.com) account (free tier works)
- [AlgoVoi tenant account](https://api1.ilovechicken.co.uk/signup) with API key

---

## Setup

### 1. Create a Shopify Custom App

1. Go to [partners.shopify.com](https://partners.shopify.com) → **Apps** → **Create app**
2. Set **Application URL** to `https://your-app.pages.dev`
3. Set **Redirect URL** to `https://your-app.pages.dev/auth/callback`
4. Enable scopes: `read_orders`, `write_orders`
5. Note your **Client ID** and **Client secret**

### 2. Configure files

Update these values in the source:

| File | Value to replace | With |
|------|-----------------|------|
| `shopify.app.toml` | `YOUR_SHOPIFY_CLIENT_ID` | Your Shopify app Client ID |
| `functions/auth/install.js` | `YOUR_SHOPIFY_CLIENT_ID` | Same Client ID |
| `functions/auth/callback.js` | `YOUR_SHOPIFY_CLIENT_ID` | Same Client ID |
| `wrangler.toml` | `YOUR_KV_NAMESPACE_ID` | Your Cloudflare KV namespace ID |

Update the `APP_BASE` URLs in these files if using a different domain:
- `functions/api/connect.js`
- `functions/api/pay-redirect.js`
- `functions/api/x402/session.js`
- `extensions/algovoi-pay-button/src/thank-you.jsx`
- `extensions/algovoi-pay-button/src/index.jsx`
- `public/pay/index.html`

### 3. Create Cloudflare KV namespace

```bash
npx wrangler kv namespace create MERCHANTS
```

Copy the `id` from the output into `wrangler.toml`.

### 4. Set Cloudflare secrets

```bash
npx wrangler pages secret put SHOPIFY_CLIENT_SECRET --project-name=your-project
```

Paste your Shopify Client Secret when prompted.

### 5. Deploy to Cloudflare Pages

```bash
npx wrangler pages deploy public --project-name=your-project
```

### 6. Deploy Shopify extension

```bash
npm install
npx shopify app deploy --allow-updates
```

### 7. Install the app on your store

Visit: `https://your-app.pages.dev/auth/install?shop=your-store.myshopify.com`

### 8. Connect AlgoVoi credentials

After installing, enter your AlgoVoi **Tenant ID** and **API Key** on the setup page.

### 9. Add the checkout extension

1. Shopify Admin → **Settings** → **Checkout** → **Customize**
2. Switch to **Thank you** page
3. **Add block** → **AlgoVoi Pay Button**
4. Save

### 10. Register the webhook

The app registers the `orders/create` webhook automatically on install. If needed manually:

```bash
curl -X POST "https://your-store.myshopify.com/admin/api/2024-01/webhooks.json" \
  -H "X-Shopify-Access-Token: YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"webhook":{"topic":"orders/create","address":"https://your-app.pages.dev/webhooks/shopify","format":"json"}}'
```

---

## Architecture

```
shopify-app/
├── functions/                    # Cloudflare Pages Functions (serverless)
│   ├── auth/
│   │   ├── install.js           # OAuth flow initiation
│   │   └── callback.js          # OAuth token exchange + KV storage
│   ├── api/
│   │   ├── connect.js           # Merchant credential setup
│   │   ├── payment-link.js      # Multi-chain payment link creation
│   │   ├── pay-redirect.js      # Single-chain redirect with HMAC callback
│   │   ├── order-paid.js        # HMAC-verified order completion
│   │   └── x402/session.js      # x402 protocol for browser extension auto-pay
│   └── webhooks/
│       └── shopify.js           # Order webhook → payment link + order note
├── extensions/
│   └── algovoi-pay-button/      # Shopify Checkout UI Extension (Preact)
│       ├── src/
│       │   ├── thank-you.jsx    # "Pay with Crypto" on thank-you page
│       │   └── index.jsx        # "Pay with Crypto" on order status page
│       ├── shopify.extension.toml
│       ├── shopify.d.ts
│       └── tsconfig.json
├── public/
│   ├── index.html               # Merchant setup page
│   └── pay/index.html           # Customer chain selection page
├── shopify.app.toml             # Shopify app configuration
├── wrangler.toml                # Cloudflare Pages configuration
├── package.json                 # Dependencies (Preact + Shopify UI Extensions)
├── order-confirmation-email.liquid  # Email template with pay link
└── shopify-additional-scripts.html  # Legacy checkout scripts (if available)
```

---

## Supported chains

| Chain | Button | Network param |
|-------|--------|---------------|
| Algorand | Pay with USDC (Algorand) | `ALGO` → `algorand_mainnet` |
| VOI | Pay with aUSDC (VOI) | `VOI` → `voi_mainnet` |
| Stellar | Pay with USDC (Stellar) | `XLM` → `stellar_mainnet` |
| Hedera | Pay with USDC (Hedera) | `HBAR` → `hedera_mainnet` |

---

## Security

- **HMAC webhook verification** — Shopify webhooks verified via `X-Shopify-Hmac-Sha256`
- **HMAC callback signatures** — order-paid callbacks signed with `SHOPIFY_CLIENT_SECRET`
- **Merchant credentials in KV** — access tokens stored server-side, never exposed to client
- **No hardcoded secrets** — all credentials via Cloudflare environment variables
- **Cancel-bypass prevention** — order only marked paid after verified callback

---

## Extension SDK notes

The Shopify Checkout UI Extensions SDK changed significantly in 2026:

- Uses **Preact** (not React) with `jsxImportSource: "preact"`
- Components use `s-` prefix: `<s-banner>`, `<s-text>`, `<s-link>`, `<s-stack>`
- Global `shopify` object (not passed as argument)
- `export default async () => { render(<Component />, document.body) }`
- Order ID accessed via `shopify.orderConfirmation?.value?.order?.id`
- Shop domain via `shopify.shop?.myshopifyDomain`
- Must extract numeric ID with `.match(/\d+$/)?.[0]` (GraphQL IDs include type prefix)
