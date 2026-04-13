# AlgoVoi Payment Provider for Wix

Accept USDC stablecoin payments on Algorand, VOI, Hedera, and Stellar directly at your Wix checkout.

This uses Wix's **Payment Provider Service Plugin (SPI)** — AlgoVoi appears as a real payment method at checkout, not a workaround.

---

## How it works

```
Customer selects "AlgoVoi" at Wix checkout
        ↓
Wix calls paymentProvider_createTransaction()
        ↓
AlgoVoi creates a payment link (customer selects chain on hosted page)
        ↓
Customer redirected to AlgoVoi hosted checkout → pays on-chain
        ↓
Customer redirected back to Wix
        ↓
paymentProvider_submitEvent() verifies payment via API (cancel-bypass prevention)
        ↓
Order marked as paid in Wix
```

---

## Setup

### 1. Enable Velo Developer Mode

In your Wix editor: **Dev Mode** → **Turn on Dev Mode**

### 2. Add credentials to Wix Secrets Manager

Go to **Dashboard → Settings → Secrets Manager** and add:

| Secret Name | Value |
|-------------|-------|
| `ALGOVOI_API_KEY` | Your AlgoVoi API key (starts with `algv_`) |
| `ALGOVOI_TENANT_ID` | Your AlgoVoi tenant UUID |
| `ALGOVOI_WEBHOOK_SECRET` | Your AlgoVoi webhook secret |

### 3. Create the payment provider

Copy `backend/payment-provider.js` to your Wix site's `backend/` folder.

### 4. Create the webhook handler

Copy `backend/algovoi-webhook.jsw` to your Wix site's `backend/` folder.

### 5. Create the data collection (optional)

In Wix Dashboard → **Content Manager** → **Create Collection**:
- Name: `AlgoVoiPayments`
- Fields: `orderId` (text), `txId` (text), `chain` (text), `amount` (number), `status` (text), `confirmedAt` (text)

### 6. Publish

Publish your site. AlgoVoi will appear as a payment option at checkout.

---

## Files

| File | Purpose |
|------|---------|
| `backend/payment-provider.js` | Wix Payment Provider SPI — handles checkout, redirect, and verification |
| `backend/algovoi-webhook.jsw` | Webhook receiver — accepts AlgoVoi payment confirmations |
| `README.md` | This file |

---

## Supported chains

| Chain | Asset | Network param |
|-------|-------|---------------|
| Algorand | USDC | `algorand_mainnet` |
| VOI | aUSDC | `voi_mainnet` |
| Hedera | USDC | `hedera_mainnet` |
| Stellar | USDC | `stellar_mainnet` |

---

## Security

- **Cancel-bypass prevention** — `paymentProvider_submitEvent()` verifies payment status via AlgoVoi API before confirming to Wix
- **HMAC webhook verification** — timing-safe comparison of `X-AlgoVoi-Signature` header
- **Empty secret rejection** — webhook rejected if secret not configured in Secrets Manager
- **tx_id length guard** — transactions over 200 chars rejected
- **Credentials in Secrets Manager** — never hardcoded, never exposed to frontend
- **SSL enforced** — all API calls over HTTPS

---

## Limitations

- **No on-chain refunds** — refund requests return an error; arrange refunds directly with the customer
- **Chain selection on hosted page** — customer selects their preferred chain on the AlgoVoi checkout page (not at Wix checkout)
- **Wix API rate limit** — 200 requests per minute
