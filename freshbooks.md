# FreshBooks Integration — AlgoVoi Tenant Services

Accept **USDC on Algorand** and **aUSDC on VOI** as payment against FreshBooks invoices via AlgoVoi.

---

## How it works

```
Invoice created or sent in FreshBooks
            ↓
FreshBooks webhook fires (X-FreshBooks-Hmac-SHA256 verified)
            ↓
AlgoVoi generates a hosted payment link (USDC or aUSDC)
            ↓
Payment link added to invoice notes
            ↓
Customer pays on-chain
            ↓
AlgoVoi verifies transaction on-chain
            ↓
FreshBooks invoice marked as PAID — TX ID recorded in notes
```

---

## Prerequisites

- An active AlgoVoi tenant account
- A FreshBooks account (Plus, Premium, or Select plan — required for API access)
- A FreshBooks OAuth 2.0 app registered at [my.freshbooks.com/service/auth/oauth/applications](https://my.freshbooks.com/service/auth/oauth/applications)
- OAuth 2.0 access token with invoices read/write access

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

## Step 2 — Create a FreshBooks OAuth app

1. Go to [my.freshbooks.com/service/auth/oauth/applications](https://my.freshbooks.com/service/auth/oauth/applications)
2. Click **Create App**
3. Fill in the app name and redirect URI
4. Copy your **Client ID** and **Client Secret**
5. Complete the OAuth 2.0 flow to authorise your FreshBooks account:

```
GET https://auth.freshbooks.com/service/auth/oauth/authorize
  ?client_id=<client_id>
  &response_type=code
  &redirect_uri=<redirect_uri>
```

6. Exchange the code for an access token:

```http
POST https://api.freshbooks.com/auth/oauth/token
Content-Type: application/json

{
  "grant_type": "authorization_code",
  "client_id": "<client_id>",
  "client_secret": "<client_secret>",
  "code": "<authorization_code>",
  "redirect_uri": "<redirect_uri>"
}
```

7. Note your **Account ID** from the `/auth/api/v1/users/me` endpoint

---

## Step 3 — Connect the integration

```http
POST /internal/integrations/{tenant_id}/freshbooks
Authorization: Bearer <admin-key>
Content-Type: application/json

{
  "credentials": {
    "client_id": "<freshbooks-client-id>",
    "client_secret": "<freshbooks-client-secret>",
    "access_token": "<oauth2-access-token>",
    "refresh_token": "<oauth2-refresh-token>",
    "account_id": "<freshbooks-account-id>"
  },
  "shop_identifier": "<account_id>",
  "base_currency": "USD",
  "preferred_network": "algorand_mainnet"
}
```

The response includes a `webhook_secret` and a `webhook_url`.

> FreshBooks access tokens expire after 24 hours. AlgoVoi uses the refresh token to obtain new tokens automatically.

---

## Step 4 — Register the webhook

Register a webhook subscription via the FreshBooks API:

```http
POST https://api.freshbooks.com/events/account/{account_id}/events/callbacks
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "callback": {
    "event": "invoice.create",
    "uri": "<webhook_url from Step 3>"
  }
}
```

FreshBooks signs webhook deliveries with an `X-FreshBooks-Hmac-SHA256` header:

```
X-FreshBooks-Hmac-SHA256: <hex(HMAC-SHA256(webhook_secret, raw_body))>
```

AlgoVoi verifies this signature automatically.

> **Important:** FreshBooks webhook payloads are `application/x-www-form-urlencoded` and contain only metadata (`name`, `object_id`, `account_id`, `business_id`). The invoice amount is **not** included in the webhook body. AlgoVoi fetches the full invoice via `GET /accounting/account/{account_id}/invoices/invoices/{invoice_id}` using the stored OAuth access token.

> Register a second subscription for `invoice.sent` to trigger payment links when invoices are emailed to clients.

---

## Payment flow for your customers

Once connected:

1. A new FreshBooks invoice triggers AlgoVoi to generate a hosted payment link (valid 24 hours)
2. The link is appended to the invoice notes via the FreshBooks API
3. Customer pays in USDC or aUSDC on-chain
4. AlgoVoi verifies the transaction and:
   - Creates a **Payment** record on the invoice via `POST /accounting/account/{account_id}/invoices/payments`
   - Sets the invoice status to **paid**
   - Records the TX ID in the payment notes

---

## Troubleshooting

| Symptom | Likely cause |
|---------|-------------|
| HTTP 401 on webhook | `X-FreshBooks-Hmac-SHA256` mismatch — check `webhook_secret` |
| HTTP 422 "No network config" | Network config missing for `preferred_network` |
| Token refresh failing | Refresh token may have expired — re-authorise via OAuth |
| Invoice not updating | `account_id` incorrect or access token scope insufficient |
| Payment duplicate | FreshBooks does not deduplicate payments — AlgoVoi checks TX ID before posting |

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

Confirmed end-to-end on **2026-04-14** against `api1.ilovechicken.co.uk`:

| Test | Network | Result |
|------|---------|--------|
| Webhook → checkout link | `algorand_mainnet` (USDC (ASA 31566704)) | Pass |
| Webhook → checkout link | `voi_mainnet` (WAD (ARC200 app ID 47138068)) | Pass |
| Webhook → checkout link | `hedera_mainnet` (USDC (token 0.0.456858)) | Pass |
| Webhook → checkout link | `stellar_mainnet` (USDC (Circle)) | Pass |

Signature: `HMAC-SHA256` hex digest in `X-FreshBooks-Hmac-SHA256`. Webhook body: `application/x-www-form-urlencoded` metadata only — invoice amount fetched via follow-up API call.
