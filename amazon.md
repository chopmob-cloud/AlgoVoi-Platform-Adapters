# Amazon Marketplace Integration — AlgoVoi Tenant Services

Accept **USDC on Algorand** and **aUSDC on VOI** for Amazon Marketplace orders via AlgoVoi.

---

## Important: Amazon Pay handles buyer payments

Amazon does not allow third-party payment methods for marketplace buyers — **Amazon Pay** processes all buyer transactions internally. AlgoVoi's Amazon integration serves a different use case:

- **B2B / wholesale invoicing** — receive SP-API order notifications and issue a crypto payment request to a trade buyer or supplier
- **Seller fee settlement** — settle Amazon platform fees or inter-company invoices in USDC/aUSDC
- **Operator-initiated flows** — your own backend sends order data directly to AlgoVoi (bypass mode)

---

## How it works

```
Amazon SP-API ORDER_CHANGE notification (via SNS)
            ↓
AlgoVoi receives + verifies signature → parses order
            ↓
AlgoVoi creates a hosted checkout link (USDC or aUSDC)
            ↓
Buyer/supplier pays on-chain
            ↓
AlgoVoi verifies transaction on-chain
            ↓
SP-API shipment confirmation created with AlgoVoi TX reference
```

---

## Prerequisites

- An active AlgoVoi tenant account
- An Amazon Selling Partner API (SP-API) application
- SP-API Login with Amazon (LWA) access token with `orders` scope
- An Amazon SNS topic subscription pointing to AlgoVoi (or direct operator POST)

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

## Step 2 — Get SP-API credentials

1. Register an SP-API application at [Seller Central → Apps & Services → Develop Apps](https://sellercentral.amazon.co.uk/apps/develop)
2. Complete the LWA OAuth flow to obtain an **access token**
3. Ensure the token includes the `sellingpartnerapi::orders` scope
4. Note your **Marketplace ID** (e.g. `A1F83G8C2ARO7P` for Amazon.co.uk)

---

## Step 3 — Connect the integration

```http
POST /internal/integrations/{tenant_id}/amazon_mws
Authorization: Bearer <admin-key>
Content-Type: application/json

{
  "credentials": {
    "access_token": "<sp-api-lwa-access-token>",
    "marketplace_id": "A1F83G8C2ARO7P"
  },
  "shop_identifier": "<your-seller-id>",
  "base_currency": "GBP",
  "preferred_network": "algorand_mainnet"
}
```

The response includes a `webhook_secret` and a `webhook_url`.

---

## Step 4 — Subscribe to SP-API order notifications

### Option A — Via Amazon SNS (recommended)

Register an `ORDER_CHANGE` notification subscription via SP-API:

```http
POST https://sellingpartnerapi-eu.amazon.com/notifications/v1/subscriptions/ORDER_CHANGE
Authorization: Bearer <access_token>
x-amz-access-token: <access_token>
Content-Type: application/json

{
  "payloadVersion": "1.0",
  "destinationId": "<your-SNS-destination-id>"
}
```

Configure your SNS topic to forward to `webhook_url` with an `x-algovoi-signature` header containing `HMAC-SHA256(webhook_secret, raw_body)`.

### Option B — Direct operator POST (bypass mode)

POST order data directly from your backend with `Authorization: Bearer <webhook_secret>`.

---

## Supported marketplace IDs

| Marketplace | ID |
|-------------|-----|
| Amazon.co.uk | `A1F83G8C2ARO7P` |
| Amazon.de | `A1PA6795UKMFR9` |
| Amazon.fr | `A13V1IB3VIYZZH` |
| Amazon.com | `ATVPDKIKX0DER` |
| Amazon.ca | `A2EUQ1WTGCTBG2` |

---

## Troubleshooting

| Symptom | Likely cause |
|---------|-------------|
| HTTP 401 on webhook | Signature mismatch — check SNS forwarding setup or Bearer token |
| HTTP 422 "No network config" | Network config missing for `preferred_network` |
| Shipment confirmation failed | LWA token expired or missing orders scope |

---

---

## Live test status

Confirmed end-to-end on **2026-04-01** against `api1.ilovechicken.co.uk`:

| Test | Network | Result |
|------|---------|--------|
| Webhook → checkout link | `algorand_mainnet` (USDC (ASA 31566704)) | Pass |
| Webhook → checkout link | `voi_mainnet` (WAD (ARC200 app ID 47138068)) | Pass |
| Webhook → checkout link | `hedera_mainnet` (USDC (token 0.0.456858)) | Pass |
| Webhook → checkout link | `stellar_mainnet` (USDC (Circle)) | Pass |

Response 503: {'detail': 'Stablecoin FX conversion failed for GBP → ASA 31566704: Stablecoin conversion produced non-positive result: 0 GBP → 0 µ(ASA 31566704)'}

## Supported networks

| Network | Asset | Notes |
|---------|-------|-------|
| `algorand_mainnet` | USDC (ASA 31566704) | Requires ASA opt-in on payout wallet |
| `voi_mainnet` | WAD (ARC200 app ID 47138068) |  |
| `algorand_testnet` | Test USDC | For integration testing only |
| `voi_testnet` | Test aUSDC | For integration testing only |
