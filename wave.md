# Wave Accounting Integration — AlgoVoi Tenant Services

Accept **USDC on Algorand** and **aUSDC on VOI** as payment against Wave invoices via AlgoVoi.

---

## Important: Wave API and webhook support

This adapter targets the **WaveApps GraphQL API** (`gql.waveapps.com`) — the invoicing and accounting API for Wave businesses.

> **Note:** Wave has two distinct APIs. This adapter uses the WaveApps GraphQL API (invoice-based, for accounting businesses). A separate Wave Business / Checkout API (`docs.wave.com`) handles payment terminals and checkout sessions — that API is not covered here.

Wave signs webhook payloads using HMAC-SHA256 — the signature is delivered in the `Wave-Signature` header with format `t=<timestamp>,v1=<signature>`.

---

## How it works

```
Invoice created or sent in Wave
            ↓
Wave webhook fires → AlgoVoi verifies Wave-Signature HMAC
            ↓
AlgoVoi generates a hosted payment link (USDC or aUSDC)
            ↓
Payment link added to invoice memo
            ↓
Customer pays on-chain
            ↓
AlgoVoi verifies transaction on-chain
            ↓
Wave invoice payment recorded — TX ID stored in memo
```

---

## Prerequisites

- An active AlgoVoi tenant account
- A Wave account (free tier supported)
- A Wave OAuth 2.0 app registered at [developer.waveapps.com](https://developer.waveapps.com)
- OAuth 2.0 access token with `account:* business:* invoices:*` scopes

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

## Step 2 — Create a Wave OAuth app

1. Go to [developer.waveapps.com](https://developer.waveapps.com) and sign in
2. Click **Create Application**
3. Fill in the app name and **Redirect URI**
4. Copy your **Client ID** and **Client Secret**
5. Authorise your Wave business via OAuth:

```
GET https://api.waveapps.com/oauth2/authorize
  ?client_id=<client_id>
  &response_type=code
  &redirect_uri=<redirect_uri>
  &scope=account%3A%2A+business%3A%2A+invoices%3A%2A
```

6. Exchange the code for tokens:

```http
POST https://api.waveapps.com/oauth2/token/
Content-Type: application/x-www-form-urlencoded

grant_type=authorization_code
&client_id=<client_id>
&client_secret=<client_secret>
&redirect_uri=<redirect_uri>
&code=<authorization_code>
```

7. Note your **Business ID** — query it after auth:

```graphql
query {
  businesses {
    edges {
      node {
        id
        name
      }
    }
  }
}
```

---

## Step 3 — Connect the integration

```http
POST /internal/integrations/{tenant_id}/wave
Authorization: Bearer <admin-key>
Content-Type: application/json

{
  "credentials": {
    "client_id": "<wave-client-id>",
    "client_secret": "<wave-client-secret>",
    "access_token": "<oauth2-access-token>",
    "refresh_token": "<oauth2-refresh-token>",
    "business_id": "<wave-business-id>"
  },
  "shop_identifier": "<business_id>",
  "base_currency": "USD",
  "preferred_network": "algorand_mainnet"
}
```

The response includes a `webhook_secret` and a `webhook_url`.

---

## Step 4 — Register the webhook

Register a webhook via the Wave REST API:

```http
POST https://api.waveapps.com/webhooks/v1/create
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "url": "<webhook_url from Step 3>",
  "events": ["invoice.created", "invoice.sent"],
  "secret": "<webhook_secret from Step 3>"
}
```

Wave signs every webhook delivery with a `Wave-Signature` header:

```
Wave-Signature: t=<timestamp>,v1=<hex(HMAC-SHA256(secret, timestamp + "." + raw_body))>
```

AlgoVoi verifies this signature automatically on receipt.

---

## Payment flow for your customers

Once connected:

1. A new Wave invoice triggers AlgoVoi to generate a hosted payment link (valid 24 hours)
2. The link is appended to the invoice memo via the Wave GraphQL API
3. Customer pays in USDC or aUSDC on-chain
4. AlgoVoi verifies the transaction and records the payment via:

#### Finding your receivables accountId

Before AlgoVoi can record payments, it needs the Wave `accountId` for your
Accounts Receivable (or equivalent income) account. Query it once after auth:

```graphql
query {
  business(id: "<BUSINESS_ID>") {
    accounts(subtypes: [ACCOUNTS_RECEIVABLE]) {
      edges {
        node {
          id
          name
        }
      }
    }
  }
}
```

Copy the `id` value (format: `QWNjb3VudDo...`) and pass it as
`accountId` in the Step 3 credentials payload:

```http
POST /internal/integrations/{tenant_id}/wave
{
  "credentials": {
    ...
    "receivables_account_id": "<accountId from above>"
  }
}
```

```graphql
mutation {
  moneyTransactionCreate(input: {
    businessId: "<business_id>",
    externalId: "<tx_id>",
    date: "<payment_date>",
    description: "AlgoVoi on-chain payment",
    anchor: {
      amount: <invoice_amount>,
      direction: DEPOSIT,
      accountId: "<receivables_account_id>"
    }
  }) {
    didSucceed
  }
}
```

---

## Troubleshooting

| Symptom | Likely cause |
|---------|-------------|
| HTTP 401 on webhook | `Wave-Signature` verification failed — check `webhook_secret` |
| HTTP 422 "No network config" | Network config missing for `preferred_network` |
| Token refresh failing | Wave refresh tokens are long-lived but can expire — re-authorise |
| Payment not posting | `accountId` for the receivables account must be pre-configured |
| GraphQL errors | Wave uses cursor-based pagination — check `businessId` is correct |

---

## Supported networks

| Network | Asset | Notes |
|---------|-------|-------|
| `algorand_mainnet` | USDC (ASA 31566704) | Requires ASA opt-in on payout wallet |
| `voi_mainnet` | WAD (ARC200 app ID 47138068) | | |
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

Verification: token comparison (no HMAC). The `webhook_secret` is sent verbatim in `X-Wave-Webhook-Token`. Amount field: `data.invoice.amountDue.value` (string, major units).
