# Walmart Marketplace Integration — AlgoVoi Tenant Services

Accept **USDC on Algorand** and **aUSDC on VOI** for Walmart Marketplace orders via AlgoVoi.

---

## Important: Walmart Pay handles buyer payments

Walmart Marketplace processes all buyer checkout payments through **Walmart Pay** internally. AlgoVoi's Walmart integration serves supplementary use cases:

- **B2B / supplier invoicing** — receive order notifications and issue a crypto payment request to a supplier or trade buyer
- **Seller-initiated settlement** — settle platform fees or inter-company invoices in USDC/aUSDC
- **Operator-initiated flows** — your own backend posts order data directly to AlgoVoi (bypass mode)

---

## How it works

```
Walmart Marketplace order notification (webhook)
            ↓
AlgoVoi receives + verifies WM_SEC.SIGNATURE HMAC → parses order
            ↓
AlgoVoi creates a hosted checkout link (USDC or aUSDC)
            ↓
Buyer/supplier pays on-chain
            ↓
AlgoVoi verifies transaction on-chain
            ↓
Walmart order acknowledged with AlgoVoi TX reference
```

---

## Prerequisites

- An active AlgoVoi tenant account
- A Walmart Marketplace Seller account with API access enabled
- A **Client ID** and **Client Secret** from Walmart Developer Center
- Webhook subscription via Walmart Notification API

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

## Step 2 — Get Walmart API credentials

1. Log in to the [Walmart Developer Center](https://developer.walmart.com)
2. Navigate to your seller application and go to **My Account → Credentials**
3. Copy your **Client ID** and **Client Secret**
4. Ensure your application has the `orders` permission scope

---

## Step 3 — Connect the integration

```http
POST /internal/integrations/{tenant_id}/walmart
Authorization: Bearer <admin-key>
Content-Type: application/json

{
  "credentials": {
    "client_id": "<walmart-client-id>",
    "client_secret": "<walmart-client-secret>"
  },
  "shop_identifier": "<your-walmart-seller-id>",
  "base_currency": "USD",
  "preferred_network": "algorand_mainnet"
}
```

The response includes a `webhook_secret` and a `webhook_url`.

---

## Step 4 — Subscribe to Walmart order notifications

### Option A — Via Walmart Notification API (recommended)

Register a webhook subscription for order events:

```http
POST https://marketplace.walmartapis.com/v3/webhooks/subscriptions
WM-SEC.ACCESS-TOKEN: <access_token>
WM-QOS-CORRELATION-ID: <uuid>
WM-SVC.NAME: Walmart Marketplace
Content-Type: application/json

{
  "eventTypes": ["PO_CREATED"],
  "deliveryConfig": {
    "type": "webhook",
    "endpoint": "<webhook_url from Step 3>",
    "secret": "<webhook_secret from Step 3>"
  }
}
```

Walmart signs webhook payloads with HMAC-SHA256 using your `webhook_secret`. The signature is delivered in the `WM_SEC.SIGNATURE` header.

To obtain a Walmart access token for the subscription call:

```http
POST https://marketplace.walmartapis.com/v3/token
Authorization: Basic <base64(client_id:client_secret)>
Content-Type: application/x-www-form-urlencoded

grant_type=client_credentials
```

### Option B — Direct operator POST (bypass mode)

POST order data directly from your backend with `Authorization: Bearer <webhook_secret>`.

---

## Webhook payload structure

AlgoVoi processes `PO_CREATED` events. Relevant fields:

```json
{
  "eventType": "PO_CREATED",
  "order": {
    "purchaseOrderId": "1234567890",
    "customerOrderId": "ABC123",
    "orderDate": "2026-03-01T12:00:00Z",
    "orderLines": {
      "orderLine": [
        {
          "item": { "productName": "Example Product" },
          "charges": {
            "charge": [
              {
                "chargeType": "PRODUCT",
                "chargeAmount": { "currency": "USD", "amount": 29.99 }
              }
            ]
          }
        }
      ]
    }
  }
}
```

---

## Troubleshooting

| Symptom | Likely cause |
|---------|-------------|
| HTTP 401 on webhook | `WM_SEC.SIGNATURE` mismatch — check secret or re-register subscription |
| HTTP 422 "No network config" | Network config missing for `preferred_network` |
| Token exchange failing | Client ID/Secret incorrect or seller account not API-enabled |
| Order not acknowledging | Access token expired — credential refresh required |

---

## Supported networks

| Network | Asset | Notes |
|---------|-------|-------|
| `algorand_mainnet` | USDC (ASA 31566704) | Requires ASA opt-in on payout wallet |
| `voi_mainnet` | aUSDC (ARC200 app ID 311051) | |
| `algorand_testnet` | Test USDC | For integration testing only |
| `voi_testnet` | Test aUSDC | For integration testing only |
