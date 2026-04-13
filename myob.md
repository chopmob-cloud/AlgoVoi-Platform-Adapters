# MYOB Integration — AlgoVoi Tenant Services

Accept **USDC on Algorand** and **aUSDC on VOI** as payment against MYOB invoices via AlgoVoi.

---

## How it works

```
Invoice created in MYOB AccountRight or Essentials
            ↓
AlgoVoi polls MYOB API for new invoices (no native webhooks)
            ↓
AlgoVoi generates a hosted payment link (USDC or aUSDC)
            ↓
Payment link added to invoice notes
            ↓
Customer pays on-chain
            ↓
AlgoVoi verifies transaction on-chain
            ↓
MYOB invoice payment recorded — TX ID stored in memo
```

---

## Prerequisites

- An active AlgoVoi tenant account
- A MYOB Business account (Lite or above) or MYOB AccountRight
- A MYOB Developer app registered at [developer.myob.com](https://developer.myob.com)
- OAuth 2.0 access token with access to your MYOB company file

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

## Step 2 — Register a MYOB Developer app

1. Go to [developer.myob.com](https://developer.myob.com) and sign in
2. Register a new app — copy your **API Key** (Client ID) and **API Secret** (Client Secret)
3. Complete the OAuth 2.0 flow to obtain an access token:

```
GET https://secure.myob.com/oauth2/account/authorize
  ?client_id=<api_key>
  &redirect_uri=<redirect_uri>
  &response_type=code
  &scope=CompanyFile
```

4. Exchange the code for tokens:

```http
POST https://secure.myob.com/oauth2/v1/token
Content-Type: application/x-www-form-urlencoded

grant_type=authorization_code
&client_id=<api_key>
&client_secret=<api_secret>
&redirect_uri=<redirect_uri>
&code=<authorization_code>
```

5. Retrieve your **company file URI** — list available company files:

```http
GET https://api.myob.com/accountright
Authorization: Bearer <access_token>
x-myobapi-key: <api_key>
```

---

## Step 3 — Connect the integration

```http
POST /internal/integrations/{tenant_id}/myob
Authorization: Bearer <admin-key>
Content-Type: application/json

{
  "credentials": {
    "api_key": "<myob-api-key>",
    "api_secret": "<myob-api-secret>",
    "access_token": "<oauth2-access-token>",
    "refresh_token": "<oauth2-refresh-token>",
    "company_file_uri": "https://api.myob.com/accountright/<company-file-id>"
  },
  "shop_identifier": "<company-file-id>",
  "base_currency": "AUD",
  "preferred_network": "algorand_mainnet"
}
```

> MYOB access tokens expire after 20 minutes. AlgoVoi refreshes them automatically using the refresh token.

---

## Step 4 — Invoice polling

> **MYOB does not support outbound webhooks.** AlgoVoi detects new invoices by polling the MYOB API at regular intervals using the `$filter` and `If-Modified-Since` headers.

AlgoVoi polls for new invoices via:

```http
GET https://api.myob.com/accountright/<company-file-id>/sale/invoice/service
Authorization: Bearer <access_token>
x-myobapi-key: <api_key>
If-Modified-Since: <last_poll_timestamp>
```

No webhook URL or secret is required. AlgoVoi handles the polling schedule automatically after the integration is connected.

> Poll separate endpoints for service invoices (`sale/invoice/service`) and product invoices (`sale/invoice/item`) to capture all invoice types.

---

## Payment flow for your customers

Once connected:

1. A new MYOB invoice triggers AlgoVoi to generate a hosted payment link (valid 24 hours)
2. The link is appended to the invoice notes field via the MYOB API
3. Customer pays in USDC or aUSDC on-chain
4. AlgoVoi verifies the transaction and:
   - Posts a payment via `POST /accountright/<company-file-id>/sale/receivemoney`
   - Links the payment to the invoice
   - Records the TX ID in the payment `Memo` field

---

## Troubleshooting

| Symptom | Likely cause |
|---------|-------------|
| Invoices not detected | Check polling is active and `company_file_uri` is correct |
| HTTP 422 "No network config" | Network config missing for `preferred_network` |
| Token refresh failing | MYOB refresh tokens expire after 365 days — re-authorise if expired |
| Company file 404 | `company_file_uri` incorrect — re-list files via `/accountright` |
| Payment not linking | Invoice UID required — ensure AlgoVoi fetches invoice by ID before payment |
| x-myobapi-key missing | All MYOB API requests require the `x-myobapi-key` header in addition to Bearer token |

---

## Supported networks

| Network | Asset | Notes |
|---------|-------|-------|
| `algorand_mainnet` | USDC (ASA 31566704) | Requires ASA opt-in on payout wallet |
| `voi_mainnet` | WAD (ARC200 app ID 47138068) |  |
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

Signature: `HMAC-SHA256` base64 in `X-Myob-Signature`. Default currency: AUD. Amount field: `Invoice.TotalIncTax` (float, major units).
