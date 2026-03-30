# QuickBooks Online Integration — AlgoVoi Tenant Services

Accept **USDC on Algorand** and **aUSDC on VOI** as payment against QuickBooks Online invoices via AlgoVoi.

---

## How it works

```
Invoice created in QuickBooks Online
            ↓
Intuit webhook fires (intuit-signature HMAC verified)
            ↓
AlgoVoi generates a hosted payment link (USDC or aUSDC)
            ↓
Payment link sent to customer (email / invoice note)
            ↓
Customer pays on-chain
            ↓
AlgoVoi verifies transaction on-chain
            ↓
QuickBooks invoice marked as PAID — TX ID recorded in memo
```

---

## Prerequisites

- An active AlgoVoi tenant account
- A QuickBooks Online account (Simple Start or above)
- An Intuit Developer app with `com.intuit.quickbooks.accounting` scope
- OAuth 2.0 access token and refresh token for your QBO company

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
  "preferred_asset_id": "311051",
  "preferred_asset_decimals": 6
}
```

---

## Step 2 — Create an Intuit Developer app

1. Go to the [Intuit Developer Portal](https://developer.intuit.com) and sign in
2. Click **Dashboard → Create an app → QuickBooks Online and Payments**
3. Under **Keys & OAuth**, copy your **Client ID** and **Client Secret**
4. Complete the OAuth 2.0 flow to obtain an **access token** and **refresh token** for your QBO company
   - Required scope: `com.intuit.quickbooks.accounting`
5. Note your **Company ID (Realm ID)** — visible in the QBO URL: `app.qbo.intuit.com/app/homepage?...companyId=<realm_id>`

---

## Step 3 — Connect the integration

```http
POST /internal/integrations/{tenant_id}/quickbooks_online
Authorization: Bearer <admin-key>
Content-Type: application/json

{
  "credentials": {
    "client_id": "<intuit-client-id>",
    "client_secret": "<intuit-client-secret>",
    "access_token": "<oauth2-access-token>",
    "refresh_token": "<oauth2-refresh-token>",
    "realm_id": "<qbo-company-id>"
  },
  "shop_identifier": "<realm_id>",
  "base_currency": "USD",
  "preferred_network": "algorand_mainnet"
}
```

The response includes a `webhook_verifier_token` and a `webhook_url`.

> AlgoVoi automatically refreshes the QBO access token using the refresh token when it expires (tokens expire after 1 hour).

---

## Step 4 — Register the webhook in Intuit Developer Portal

1. In the [Intuit Developer Portal](https://developer.intuit.com), go to your app → **Webhooks**
2. Enter your `webhook_url` from Step 3 as the **Endpoint URL**
3. Under **Entities**, enable:
   - `Invoice` → `Create`
4. Copy the **Verifier Token** shown — this must match the `webhook_verifier_token` returned in Step 3
5. Click **Save**

Intuit signs every webhook delivery with an `intuit-signature` header:

```
intuit-signature: <base64(HMAC-SHA256(verifier_token, raw_body))>
```

AlgoVoi verifies this signature automatically on receipt.

---

## Payment flow for your customers

Once connected:

1. Every new QBO invoice triggers AlgoVoi to generate a hosted payment link (valid 24 hours)
2. The payment link is added as a note on the invoice via the QBO API
3. Customer pays in USDC or aUSDC on-chain
4. AlgoVoi verifies the transaction and:
   - Creates a **Payment** record in QBO linked to the invoice
   - Sets the invoice status to **Paid**
   - Records the Algorand/VOI TX ID in the payment memo

---

## Troubleshooting

| Symptom | Likely cause |
|---------|-------------|
| HTTP 401 on webhook | `intuit-signature` mismatch — check `webhook_verifier_token` matches the Intuit portal value |
| HTTP 422 "No network config" | Network config missing for `preferred_network` |
| Token refresh failing | `refresh_token` expired (valid 100 days) — re-authorise via OAuth |
| Invoice not updating | `realm_id` incorrect or access token lacks accounting scope |
| Payment not posting | QBO Payment requires a valid `CustomerRef` — ensure invoice has a linked customer |

---

## Supported networks

| Network | Asset | Notes |
|---------|-------|-------|
| `algorand_mainnet` | USDC (ASA 31566704) | Requires ASA opt-in on payout wallet |
| `voi_mainnet` | aUSDC (ARC200 app ID 311051) | |
| `algorand_testnet` | Test USDC | For integration testing only |
| `voi_testnet` | Test aUSDC | For integration testing only |
