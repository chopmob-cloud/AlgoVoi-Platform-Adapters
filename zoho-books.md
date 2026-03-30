# Zoho Books Integration — AlgoVoi Tenant Services

Accept **USDC on Algorand** and **aUSDC on VOI** as payment against Zoho Books invoices via AlgoVoi.

---

## How it works

```
Invoice created in Zoho Books
            ↓
Zoho Books webhook fires (X-Zoho-Webhook-Token verified)
            ↓
AlgoVoi generates a hosted payment link (USDC or aUSDC)
            ↓
Payment link added as a custom field or note on the invoice
            ↓
Customer pays on-chain
            ↓
AlgoVoi verifies transaction on-chain
            ↓
Zoho Books invoice marked as paid — TX ID recorded in reference
```

---

## Prerequisites

- An active AlgoVoi tenant account
- A Zoho Books organisation (any plan)
- A Zoho OAuth 2.0 app registered at [api-console.zoho.com](https://api-console.zoho.com)
- OAuth 2.0 access token with `ZohoBooks.invoices.CREATE ZohoBooks.invoices.UPDATE` scopes

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

## Step 2 — Create a Zoho OAuth app

1. Go to [api-console.zoho.com](https://api-console.zoho.com) and sign in
2. Click **Add Client → Server-based Application**
3. Enter a name and **Authorized Redirect URI**
4. Copy your **Client ID** and **Client Secret**
5. Authorise your Zoho Books organisation:

```
GET https://accounts.zoho.com/oauth/v2/auth
  ?client_id=<client_id>
  &response_type=code
  &redirect_uri=<redirect_uri>
  &scope=ZohoBooks.invoices.CREATE,ZohoBooks.invoices.UPDATE,ZohoBooks.contacts.READ
  &access_type=offline
```

6. Exchange the code for tokens:

```http
POST https://accounts.zoho.com/oauth/v2/token
Content-Type: application/x-www-form-urlencoded

grant_type=authorization_code
&client_id=<client_id>
&client_secret=<client_secret>
&redirect_uri=<redirect_uri>
&code=<authorization_code>
```

7. Note your **Organisation ID** — visible in the Zoho Books URL: `books.zoho.com/app#/books/organisation/<org_id>`

> Zoho domains vary by region: `zoho.com` (US), `zoho.eu` (EU), `zoho.in` (India), `zoho.com.au` (AU). Use the matching domain for all API calls.

---

## Step 3 — Connect the integration

```http
POST /internal/integrations/{tenant_id}/zoho_books
Authorization: Bearer <admin-key>
Content-Type: application/json

{
  "credentials": {
    "client_id": "<zoho-client-id>",
    "client_secret": "<zoho-client-secret>",
    "access_token": "<oauth2-access-token>",
    "refresh_token": "<oauth2-refresh-token>",
    "organization_id": "<zoho-books-org-id>",
    "region": "com"
  },
  "shop_identifier": "<organization_id>",
  "base_currency": "USD",
  "preferred_network": "algorand_mainnet"
}
```

`region` must be one of: `com`, `eu`, `in`, `com.au`.

The response includes a `webhook_token` and a `webhook_url`.

> Zoho access tokens expire after 1 hour. AlgoVoi refreshes them automatically.

---

## Step 4 — Register the webhook

Register a webhook in Zoho Books via **Settings → Automation → Webhooks**:

1. Go to **Settings → Automation → Webhooks → New Webhook**
2. Set the **URL** to your `webhook_url` from Step 3
3. Under **Trigger**, select **Invoices → Created**
4. Under **Custom Headers**, add:
   - Header name: `X-Zoho-Webhook-Token`
   - Header value: `<webhook_token from Step 3>`
5. Save

> Zoho Books does not sign webhook payloads with HMAC. AlgoVoi authenticates incoming webhooks by matching the `X-Zoho-Webhook-Token` header value against the stored token.

---

## Payment flow for your customers

Once connected:

1. A new Zoho Books invoice triggers AlgoVoi to generate a hosted payment link (valid 24 hours)
2. The link is added to the invoice via a custom field or note
3. Customer pays in USDC or aUSDC on-chain
4. AlgoVoi verifies the transaction and:
   - Creates an invoice payment via `POST /v3/invoices/{invoice_id}/payments`
   - Records the TX ID in the payment `reference_number` field
   - Invoice status moves to **paid**

---

## Troubleshooting

| Symptom | Likely cause |
|---------|-------------|
| HTTP 401 on webhook | `X-Zoho-Webhook-Token` missing or incorrect — check webhook custom header setup |
| HTTP 422 "No network config" | Network config missing for `preferred_network` |
| Token refresh failing | Check `region` setting — wrong region returns 401 on token refresh |
| Payment not posting | Invoice must be in `sent` or `overdue` status to accept payments |
| API 404 errors | Verify `organization_id` and that the correct regional domain is set |

---

## Supported networks

| Network | Asset | Notes |
|---------|-------|-------|
| `algorand_mainnet` | USDC (ASA 31566704) | Requires ASA opt-in on payout wallet |
| `voi_mainnet` | aUSDC (ARC200 app ID 311051) | |
| `algorand_testnet` | Test USDC | For integration testing only |
| `voi_testnet` | Test aUSDC | For integration testing only |
