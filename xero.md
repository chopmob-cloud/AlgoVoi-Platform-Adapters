# Xero Integration — AlgoVoi Tenant Services

Accept **USDC on Algorand** and **aUSDC on VOI** as payment against Xero invoices via AlgoVoi.

---

## How it works

```
Invoice created in Xero (AUTHORISED status)
            ↓
Xero webhook fires (x-xero-signature HMAC verified)
            ↓
AlgoVoi generates a hosted payment link (USDC or aUSDC)
            ↓
Payment link added to invoice as a URL attachment
            ↓
Customer pays on-chain
            ↓
AlgoVoi verifies transaction on-chain
            ↓
Xero invoice marked as PAID — TX ID recorded in reference
```

---

## Prerequisites

- An active AlgoVoi tenant account
- A Xero account (Starter, Standard, or Premium)
- A Xero OAuth 2.0 app registered at [developer.xero.com](https://developer.xero.com)
- OAuth 2.0 access token and refresh token with `accounting.transactions` and `accounting.contacts.read` scopes

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

## Step 2 — Create a Xero OAuth 2.0 app

1. Go to [developer.xero.com](https://developer.xero.com) → **My Apps → New app**
2. Select **Web app** and fill in details
3. Copy your **Client ID** and **Client Secret**
4. Complete the OAuth 2.0 PKCE flow to authorise your Xero organisation
   - Required scopes: `accounting.transactions accounting.contacts.read offline_access`
5. Note your **Tenant ID** — returned in the `/connections` endpoint after OAuth

```http
GET https://api.xero.com/connections
Authorization: Bearer <access_token>
```

---

## Step 3 — Connect the integration

```http
POST /internal/integrations/{tenant_id}/xero
Authorization: Bearer <admin-key>
Content-Type: application/json

{
  "credentials": {
    "client_id": "<xero-client-id>",
    "client_secret": "<xero-client-secret>",
    "access_token": "<oauth2-access-token>",
    "refresh_token": "<oauth2-refresh-token>",
    "xero_tenant_id": "<xero-organisation-tenant-id>"
  },
  "shop_identifier": "<xero_tenant_id>",
  "base_currency": "GBP",
  "preferred_network": "algorand_mainnet"
}
```

The response includes a `webhook_key` and a `webhook_url`.

> Xero access tokens expire after 30 minutes. AlgoVoi uses the refresh token to obtain new tokens automatically.

---

## Step 4 — Register the webhook in Xero Developer Portal

1. In [developer.xero.com](https://developer.xero.com), go to your app → **Webhooks**
2. Enter your `webhook_url` as the **Delivery URL**
3. Under **Subscribe to events**, enable:
   - `Invoices` — `Created` and `Updated`
4. Copy the **Webhook key** — set this as the `webhook_key` from Step 3
5. Click **Save**

Xero signs every webhook delivery with an `x-xero-signature` header:

```
x-xero-signature: <base64(HMAC-SHA256(webhook_key, raw_body))>
```

AlgoVoi verifies this signature automatically. Xero also requires your endpoint to respond with HTTP 200 to an **intent to receive** validation request on registration.

---

## Payment flow for your customers

Once connected:

1. A new `AUTHORISED` Xero invoice triggers AlgoVoi to generate a hosted payment link (valid 24 hours)
2. The link is attached to the invoice as a URL via the Xero API
3. Customer pays in USDC or aUSDC on-chain
4. AlgoVoi verifies the transaction and:
   - Posts a **Payment** against the invoice via `PUT /api.xro/2.0/Payments`
   - Sets the invoice to **PAID** status
   - Records the TX ID in the payment `Reference` field

---

## Troubleshooting

| Symptom | Likely cause |
|---------|-------------|
| HTTP 401 on webhook | `x-xero-signature` mismatch — check `webhook_key` matches the Xero Developer Portal value |
| Intent to receive failing | Endpoint must respond HTTP 200 within 5 seconds — check network connectivity |
| HTTP 422 "No network config" | Network config missing for `preferred_network` |
| Token refresh failing | Refresh token expired (valid 60 days when unused) — re-authorise via OAuth |
| Payment not posting | Invoice must be in `AUTHORISED` status; `DRAFT` invoices cannot be paid |
| Wrong tenant | Verify `xero_tenant_id` matches the organisation you authorised |

---

## Supported networks

| Network | Asset | Notes |
|---------|-------|-------|
| Webhook → checkout link | Webhook → checkout link | Webhook → checkout link | `algorand_mainnet` (USDC (ASA 31566704)) | Skip | Requires ASA opt-in on payout wallet |
| Webhook → checkout link | Webhook → checkout link | Webhook → checkout link | `voi_mainnet` (WAD (ARC200 app ID 47138068)) | Skip | |
| `algorand_testnet` | Test USDC | For integration testing only |
| `voi_testnet` | Test aUSDC | For integration testing only |

---

## Live test status

Partially confirmed on **2026-03-31** against `api1.ilovechicken.co.uk`:

| Test | Network | Result |
|------|---------|--------|
| Webhook signature verification | n/a | Pass |
| Full order flow | Webhook → checkout link | Webhook → checkout link | Webhook → checkout link | `algorand_mainnet` (USDC (ASA 31566704)) | Skip |

Xero webhooks carry event metadata only (no invoice amount). AlgoVoi makes a follow-up API call to fetch the invoice. Full flow requires valid OAuth credentials. Signature: `HMAC-SHA256` base64 in `X-Xero-Signature`.
