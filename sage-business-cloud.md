# Sage Business Cloud Integration — AlgoVoi Tenant Services

Accept **USDC on Algorand** and **aUSDC on VOI** as payment against Sage Business Cloud invoices via AlgoVoi.

---

## How it works

```
Sales invoice created in Sage Business Cloud
            ↓
Sage webhook fires (X-Sage-Signature HMAC verified)
            ↓
AlgoVoi generates a hosted payment link (USDC or aUSDC)
            ↓
Payment link added to invoice via Sage API
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

## Step 4 — Register the webhook

Register a webhook subscription via the Sage Accounting API:

```http
POST https://api.accounting.sage.com/v3.1/webhooks
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "webhook": {
    "endpoint": "<webhook_url from Step 3>",
    "event_types": ["sales_invoice"],
    "active": true,
    "signing_secret": "<webhook_secret from Step 3>"
  }
}
```

Sage signs every webhook delivery with an `X-Sage-Signature` header:

```
X-Sage-Signature: <hex(HMAC-SHA256(signing_secret, raw_body))>
```

AlgoVoi verifies this signature automatically on receipt.

---

## Payment flow for your customers

Once connected:

1. A new Sage sales invoice triggers AlgoVoi to generate a hosted payment link (valid 24 hours)
2. The link is added to the invoice via the Sage API
3. Customer pays in USDC or aUSDC on-chain
4. AlgoVoi verifies the transaction and:
   - Posts a payment against the invoice via `POST /v3.1/sales_invoice_payments`
   - Records the TX ID in the payment `reference` field
   - Invoice status moves to **PAID**

---

## Troubleshooting

| Symptom | Likely cause |
|---------|-------------|
| HTTP 401 on webhook | `X-Sage-Signature` mismatch — check `webhook_secret` / `signing_secret` match |
| HTTP 422 "No network config" | Network config missing for `preferred_network` |
| Token refresh failing | Refresh tokens expire after 31 days of inactivity — re-authorise |
| Payment not posting | Invoice must be in `UNPAID` status; voided invoices cannot receive payments |
| Wrong business | Sage tokens are scoped to a single business — verify the correct account was authorised |

---

## Supported networks

| Network | Asset | Notes |
|---------|-------|-------|
| Webhook → checkout link | Webhook → checkout link | Webhook → checkout link | Webhook → checkout link | `algorand_mainnet` (USDC (ASA 31566704)) | Pass | Requires ASA opt-in on payout wallet |
| Webhook → checkout link | `voi_mainnet` (WAD (ARC200 app ID 47138068)) | Pass | |
| `algorand_testnet` | Test USDC | For integration testing only |
| `voi_testnet` | Test aUSDC | For integration testing only |

---

## Live test status

Confirmed end-to-end on **2026-03-31** against `api1.ilovechicken.co.uk`:

| Test | Network | Result |
|------|---------|--------|
| `sales_invoice.created` webhook -> checkout link | Webhook → checkout link | Webhook → checkout link | Webhook → checkout link | Webhook → checkout link | `algorand_mainnet` (USDC (ASA 31566704)) | Pass |

Signature: `HMAC-SHA256` hex digest in `X-Sage-Signature`. Amount field: `data.total_amount` (float, major units). Currency from `data.currency.id`.
