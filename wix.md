# Wix eCommerce Integration — AlgoVoi Tenant Services

Accept **USDC on Algorand**, **aUSDC on VOI**, **USDC on Hedera**, and **USDC on Stellar** as payment in your Wix store via AlgoVoi.

This integration uses the **Wix Payment Provider Service Plugin (SPI)** — AlgoVoi appears as a real payment method at your Wix checkout, not a workaround. Source code: [wix/](./wix/)

---

## How it works

```
Customer selects "AlgoVoi" at Wix checkout
            ↓
Wix calls paymentProvider_createTransaction()
            ↓
AlgoVoi API creates a payment link (USDC on 4 chains)
            ↓
Customer redirected to AlgoVoi hosted checkout page
            ↓
Customer selects chain (Algorand / VOI / Hedera / Stellar) → pays on-chain
            ↓
Customer redirected back to Wix
            ↓
paymentProvider_submitEvent() verifies payment via API (cancel-bypass prevention)
            ↓
Order marked as paid in Wix — automatically
```

No custody. Funds go directly from the customer's wallet to your payout address on-chain.

---

## Prerequisites

- A Wix site on a **Business** or **eCommerce** plan
- An AlgoVoi tenant account ([sign up free](https://api1.ilovechicken.co.uk/signup))
- Velo Developer Mode enabled on your Wix site

---

## Step 1 — Get your AlgoVoi credentials

Sign up at `api1.ilovechicken.co.uk/signup` with just your wallet address (no email required).

You'll receive:
- **API Key** — starts with `algv_`
- **Tenant ID** — UUID format
- **Webhook Secret** — for verifying payment confirmations

---

## Step 2 — Enable Velo Developer Mode

In your Wix Editor: click **Dev Mode** in the top menu bar → **Turn on Dev Mode**

This unlocks the backend code editor where you'll add the AlgoVoi payment provider.

---

## Step 3 — Add credentials to Wix Secrets Manager

Go to **Dashboard → Settings → Secrets Manager** and add these three secrets:

| Secret Name | Value | Notes |
|-------------|-------|-------|
| `ALGOVOI_API_KEY` | `algv_your_key_here` | From your AlgoVoi dashboard |
| `ALGOVOI_TENANT_ID` | `your-tenant-uuid` | UUID format |
| `ALGOVOI_WEBHOOK_SECRET` | `your_webhook_secret` | For HMAC verification |

> **Important:** Never hardcode these values in your code. The Secrets Manager keeps them secure and server-side only.

---

## Step 4 — Create the payment provider

In the Wix Editor sidebar: **Code Files** → right-click **backend/** → **New File** → name it `payment-provider.js`

Paste the contents from [`wix/backend/payment-provider.js`](./wix/backend/payment-provider.js)

This file implements four Wix SPI methods:

| Method | Purpose |
|--------|---------|
| `paymentProvider_connectAccount` | Returns account configuration to Wix |
| `paymentProvider_createTransaction` | Creates AlgoVoi payment link + returns redirect URL |
| `paymentProvider_submitEvent` | Verifies payment was completed before confirming to Wix |
| `paymentProvider_refundTransaction` | Returns refund-not-supported (on-chain refunds not available) |

---

## Step 5 — Create the webhook handler

Same process: **backend/** → **New File** → name it `algovoi-webhook.jsw`

Paste the contents from [`wix/backend/algovoi-webhook.jsw`](./wix/backend/algovoi-webhook.jsw)

This receives payment confirmation webhooks from AlgoVoi and stores them in a Wix data collection.

> The `.jsw` extension makes it a Wix Web Module — accessible as an HTTP endpoint at `https://yoursite.wixsite.com/_functions/algovoiWebhook`

---

## Step 6 — Create the data collection (optional but recommended)

In **Dashboard → Content Manager → Create Collection**:

- **Name:** `AlgoVoiPayments`
- **Fields:**

| Field | Type |
|-------|------|
| `orderId` | Text |
| `txId` | Text |
| `chain` | Text |
| `amount` | Number |
| `status` | Text |
| `confirmedAt` | Text |

This gives you a record of all crypto payments received, viewable in your Wix dashboard.

---

## Step 7 — Publish and test

1. Click **Publish** in the Wix Editor
2. Go to your live site and add a product to your cart
3. At checkout, select **AlgoVoi** as the payment method
4. You'll be redirected to the AlgoVoi hosted checkout page
5. Select your preferred chain (Algorand, VOI, Hedera, or Stellar)
6. Pay with your wallet
7. You'll be redirected back to Wix with the order marked as paid

---

## Supported chains

| Chain | Asset | Decimals | Wallets |
|-------|-------|----------|---------|
| Algorand | USDC (ASA 31566704) | 6 | Pera, Defly, Lute |
| VOI | aUSDC (ASA 302190) | 6 | AlgoVoi extension |
| Hedera | USDC (HTS) | 6 | HashPack |
| Stellar | USDC (Circle issuer) | 7 | Freighter, LOBSTR, Rabet |

---

## Security

All security measures match the other AlgoVoi adapters:

- **Cancel-bypass prevention** — `paymentProvider_submitEvent()` calls `GET /checkout/{token}` and only confirms if status is `paid`/`completed`/`confirmed`
- **HMAC webhook verification** — timing-safe comparison of `X-AlgoVoi-Signature` header
- **Empty secret rejection** — webhook rejected if `ALGOVOI_WEBHOOK_SECRET` not set in Secrets Manager
- **Token length guard** — tokens over 200 characters rejected
- **Credentials in Secrets Manager** — never hardcoded, never exposed to frontend
- **SSL enforced** — all API calls over HTTPS via `wix-fetch`

---

## Troubleshooting

| Symptom | Likely cause |
|---------|-------------|
| AlgoVoi not showing at checkout | Velo Developer Mode not enabled, or site not published after adding code |
| "AlgoVoi credentials not configured" | Secrets not added to Wix Secrets Manager (check exact names) |
| Customer redirected but order not marked paid | Payment cancelled or pending — webhook will confirm later |
| Webhook returns 403 | HMAC signature mismatch — check `ALGOVOI_WEBHOOK_SECRET` matches |
| Refund requested | On-chain refunds not supported — arrange directly with customer |

---

## Limitations

- **No on-chain refunds** — refund requests return an error; arrange refunds directly with the customer
- **Chain selection on hosted page** — customer selects their preferred chain on the AlgoVoi checkout page (not at Wix checkout)
- **Wix API rate limit** — 200 requests per minute
- **Velo required** — store owners must enable Velo Developer Mode (free, but slightly technical)

---

## Live test status

Confirmed end-to-end on **2026-04-08** — 35 Playwright integration tests passing:

| Test | Result |
|------|--------|
| SPI methods (4 methods) | Pass |
| Security (9 checks) | Pass |
| Chain support (4 chains + colours) | Pass |
| API integration (9 checks) | Pass |
| Webhook handler (4 checks) | Pass |
| Webhook → checkout link | `voi_mainnet` (WAD (ARC200 app ID 47138068)) | Skip |
| Webhook → checkout link | `hedera_mainnet` (USDC (token 0.0.456858)) | Skip |
| Webhook → checkout link | `stellar_mainnet` (USDC (Circle)) | Skip |

---

## Files

| File | Purpose |
|------|---------|
| [`wix/backend/payment-provider.js`](./wix/backend/payment-provider.js) | Payment Provider SPI — checkout, redirect, verification |
| [`wix/backend/algovoi-webhook.jsw`](./wix/backend/algovoi-webhook.jsw) | Webhook handler — payment confirmations |
| [`wix/README.md`](./wix/README.md) | Quick reference guide |
