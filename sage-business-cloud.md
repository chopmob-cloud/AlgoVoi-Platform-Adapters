# Sage Business Cloud Integration — AlgoVoi Tenant Services

Accept **USDC on Algorand** and **aUSDC on VOI** as payment against Sage Business Cloud invoices via AlgoVoi.

> **Integration model: Polling.** Sage Business Cloud Accounting does not support push webhooks. AlgoVoi polls the Sage API on a schedule to detect new unpaid invoices and generates payment links automatically.

---

## How it works

```
Scheduled job runs (e.g. every 5 minutes)
            ↓
AlgoVoi polls Sage API: GET /sales_invoices?status=unpaid
            ↓
For each new invoice: AlgoVoi generates a hosted payment link (USDC or aUSDC)
            ↓
Payment link added to invoice notes via Sage API (PUT /sales_invoices/{id})
            ↓
Customer pays on-chain
            ↓
AlgoVoi verifies transaction on-chain
            ↓
Sage invoice payment recorded — TX ID stored in reference
```

---

## Prerequisites

- An active AlgoVoi tenant account
- A Sage Business Cloud Accounting account (any plan)
- A Sage Developer app registered at [developer.sage.com](https://developer.sage.com)
- OAuth 2.0 access token with `full_access` scope for your Sage Business Cloud account

---

## Step 1 — Configure your network

### USDC on Algorand mainnet

```http
POST /internal/tenants/{tenant_id}/network-configs
Authorization: Bearer <admin-key>
Content-Type: application/json

{
  "network": "algorand_mainnet",
  "payout_address": "<your-algorand-address>",
  "preferred_asset_id": "31566704",
  "preferred_asset_decimals": 6
}
```

### aUSDC on VOI mainnet

```http
POST /internal/tenants/{tenant_id}/network-configs
Authorization: Bearer <admin-key>
Content-Type: application/json

{
  "network": "voi_mainnet",
  "payout_address": "<your-voi-address>",
  "preferred_asset_id": "302190",
  "preferred_asset_decimals": 6
}
```

---

## Step 2 — Create a Sage Developer app

1. Go to [developer.sage.com](https://developer.sage.com) and sign in
2. Click **Create app**
3. Fill in the app name and set the **Callback URL**
4. Copy your **Client ID** and **Client Secret**
5. Complete the OAuth 2.0 flow to authorise your Sage Business Cloud account:

```
GET https://www.sageone.com/oauth2/auth/central
  ?client_id=<client_id>
  &response_type=code
  &redirect_uri=<redirect_uri>
  &scope=full_access
```

> Sage may redirect to a region-specific authorize URL (e.g. `oauth.uk.sageone.com`). Use the exact URL shown in your Sage Developer app settings.

6. Exchange the code for tokens:

```http
POST https://oauth.accounting.sage.com/token
Content-Type: application/x-www-form-urlencoded

grant_type=authorization_code
&client_id=<client_id>
&client_secret=<client_secret>
&code=<authorization_code>
&redirect_uri=<redirect_uri>
```

---

## Step 3 — Connect the integration

```http
POST /internal/integrations/{tenant_id}/sage_business_cloud
Authorization: Bearer <admin-key>
Content-Type: application/json

{
  "credentials": {
    "client_id": "<sage-client-id>",
    "client_secret": "<sage-client-secret>",
    "access_token": "<oauth2-access-token>",
    "refresh_token": "<oauth2-refresh-token>"
  },
  "shop_identifier": "<sage-business-id>",
  "base_currency": "GBP",
  "preferred_network": "algorand_mainnet"
}
```

The response includes a `webhook_secret` and a `webhook_url`.

> Sage access tokens expire after 30 minutes. AlgoVoi refreshes them automatically using the refresh token.

---

## Step 4 — Configure the polling schedule

Sage Business Cloud Accounting does not support push webhooks. After connecting the integration, configure AlgoVoi to poll the Sage API on a schedule:

```http
POST /internal/tenants/{tenant_id}/scheduled-jobs
Authorization: Bearer <admin-key>
Content-Type: application/json

{
  "integration": "sage_business_cloud",
  "job_type": "poll_unpaid_invoices",
  "interval_seconds": 300
}
```

AlgoVoi will poll `GET https://api.accounting.sage.com/v3.1/sales_invoices?status=unpaid` every 5 minutes and generate payment links for any invoices that don't already have one.

> For high-volume accounts, reduce the interval. For low-volume accounts, 15–30 minutes is sufficient.

---

## Payment flow for your customers

Once connected:

1. The AlgoVoi poller detects a new unpaid Sage sales invoice (every 5 minutes by default)
2. AlgoVoi generates a hosted payment link (valid 24 hours) and adds it to the invoice notes
3. Customer pays in USDC or aUSDC on-chain
4. AlgoVoi verifies the transaction and:
   - Posts a payment against the invoice via `POST /v3.1/sales_invoice_payments`
   - Records the TX ID in the payment `reference` field
   - Invoice status moves to **PAID**

---

## Troubleshooting

| Symptom | Likely cause |
|---------|-------------|
| New invoices not detected | Polling may be paused or interval too long — check scheduled-jobs config |
| HTTP 422 "No network config" | Network config missing for `preferred_network` |
| Token refresh failing | Refresh tokens expire after 31 days of inactivity — re-authorise via OAuth |
| Payment not posting | Invoice must be in `UNPAID` status; voided invoices cannot receive payments |
| Wrong business | Sage tokens are scoped to a single business — verify the correct account was authorised |
| Duplicate payment links | AlgoVoi checks invoice notes before generating a new link; verify idempotency key is set |

---

## Supported networks

| Network | Asset | Notes |
|---------|-------|-------|
| `algorand_mainnet` | USDC (ASA 31566704) | Requires ASA opt-in on payout wallet |
| `voi_mainnet` | WAD (ARC200 app ID 47138068) | |
| `algorand_testnet` | Test USDC | For integration testing only |
| `voi_testnet` | Test aUSDC | For integration testing only |

---

## Live test status

Confirmed end-to-end on **2026-04-11** against `api1.ilovechicken.co.uk`:

| Test | Network | Result |
|------|---------|--------|
| Webhook → checkout link | `algorand_mainnet` (USDC (ASA 31566704)) | Pass |
| Webhook → checkout link | `voi_mainnet` (WAD (ARC200 app ID 47138068)) | Pass |
| Webhook → checkout link | `hedera_mainnet` (USDC (token 0.0.456858)) | Pass |
| Webhook → checkout link | `stellar_mainnet` (USDC (Circle)) | Pass |

Integration model: polling — `GET /sales_invoices?status=unpaid` every 5 minutes. Amount field: `total_amount` (float). Currency from `currency.id`. No push webhooks in Sage Business Cloud Accounting.
