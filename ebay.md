# eBay Integration — AlgoVoi Tenant Services

Accept **USDC on Algorand** and **aUSDC on VOI** for eBay orders via AlgoVoi.

---

## Important: eBay Managed Payments

eBay processes the vast majority of payments through **eBay Managed Payments**, which handles card, PayPal, and bank transfers internally. AlgoVoi's eBay integration targets two specific use cases:

1. **External checkout** — sellers using eBay's external checkout extension to offer additional payment methods
2. **Seller-initiated crypto invoicing** — seller receives an order notification, AlgoVoi creates a payment link, seller shares it with the buyer out-of-band

> This is not a replacement for eBay Managed Payments. It is a supplementary flow for sellers who want to offer on-chain stablecoin settlement.

---

## How it works

```
eBay order placed (checkout.order.created event)
            ↓
AlgoVoi receives Platform Notification → verifies X-EBAY-SIGNATURE
            ↓
AlgoVoi creates a hosted checkout link (USDC or aUSDC)
            ↓
Seller shares checkout link with buyer (email / eBay message)
            ↓
Buyer pays on-chain
            ↓
AlgoVoi verifies transaction on-chain
            ↓
eBay order marked as shipped with AlgoVoi TX reference
```

---

## Prerequisites

- An active AlgoVoi tenant account
- An eBay Developer account with a production application
- OAuth user token with `sell.fulfillment` scope
- eBay Platform Notifications subscription

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

## Step 2 — Get an eBay OAuth token

1. Register an application at the [eBay Developer Portal](https://developer.ebay.com)
2. Complete the OAuth flow to obtain a **User Access Token**
3. Ensure the token includes the `sell.fulfillment` scope
4. Copy the access token

---

## Step 3 — Connect the integration

```http
POST /internal/integrations/{tenant_id}/ebay
Authorization: Bearer <admin-key>
Content-Type: application/json

{
  "credentials": {
    "access_token": "<ebay-oauth-user-token>"
  },
  "shop_identifier": "<your-ebay-seller-id>",
  "base_currency": "GBP",
  "preferred_network": "algorand_mainnet"
}
```

The response includes a `webhook_secret` and a `webhook_url`.

---

## Step 4 — Subscribe to eBay Platform Notifications

Register a notification subscription via the eBay Commerce Notification API:

```http
POST https://api.ebay.com/commerce/notification/v1/subscription
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "topicId": "checkout.order.created",
  "deliveryConfig": {
    "endpoint": "<webhook_url from Step 3>",
    "verificationToken": "<webhook_secret from Step 3>"
  }
}
```

eBay will first send a **challenge-response** GET request to verify your endpoint before activating the subscription. AlgoVoi handles this automatically.

---

## Payment flow for your customers

Once connected:

1. AlgoVoi receives the `checkout.order.created` notification
2. A hosted checkout link is created (valid 30 minutes)
3. The checkout URL is returned in the webhook response — share this with your buyer via eBay messages or email
4. Buyer pays in USDC or aUSDC on-chain
5. AlgoVoi verifies the transaction and marks the eBay order as shipped with the TX ID as tracking reference

> eBay does not expose buyer email addresses in webhook payloads. The buyer's eBay username is recorded instead.

---

## Troubleshooting

| Symptom | Likely cause |
|---------|-------------|
| HTTP 401 on webhook | `X-EBAY-SIGNATURE` mismatch — reconnect to rotate secret |
| HTTP 422 "No network config" | Network config missing for `preferred_network` |
| Challenge-response failing | AlgoVoi endpoint must respond to eBay's GET verification request |
| Order not updating | OAuth token expired or missing `sell.fulfillment` scope |

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

Confirmed end-to-end on **2026-03-31** against `api1.ilovechicken.co.uk`:

| Test | Network | Result |
|------|---------|--------|
| Order notification webhook -> checkout link | `algorand_mainnet` (USDC (ASA 31566704)) | Pass |
| Webhook → checkout link | `voi_mainnet` (WAD (ARC200 app ID 47138068)) | Pass |
| Webhook → checkout link | `hedera_mainnet` (USDC (token 0.0.456858)) | Pass |
| Webhook → checkout link | `stellar_mainnet` (USDC (Circle)) | Pass |

Signature: `HMAC-SHA256` hex digest in `X-Ebay-Signature`. Amount from `notification.data.pricingSummary.total.value`.
