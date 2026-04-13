# Instagram & Facebook Shops Integration — AlgoVoi Tenant Services

Accept **USDC on Algorand** and **aUSDC on VOI** as payment via Instagram and Facebook Shops using AlgoVoi.

> **Social Commerce integration.** Meta's Commerce API supports external checkout — customers browse your Instagram or Facebook Shop and are redirected to an AlgoVoi hosted checkout page to complete payment on-chain.

---

## Important: Meta Tech Provider requirement

> **This integration requires a formal agreement with Meta.** To use external checkout with Facebook/Instagram Shops, you must:
> 1. Complete **Meta Business Verification**
> 2. Sign the **Meta Tech Provider Amendment**
> 3. Be approved as a **Commerce Partner** via [facebook.com/business/partner-directory](https://www.facebook.com/business/partner-directory)
>
> Without this agreement, external checkout is not available. Contact Meta Partner Support to begin the approval process.

---

## How it works

```
Customer browses Instagram/Facebook Shop
            ↓
Customer clicks "Checkout" → redirected to AlgoVoi hosted checkout
            ↓
AlgoVoi creates payment link (USDC or aUSDC)
            ↓
Customer pays on-chain
            ↓
AlgoVoi verifies transaction on-chain
            ↓
AlgoVoi notifies your backend — order fulfillment triggered
            ↓
Order status updated via Meta Commerce API
```

---

## Prerequisites

- An active AlgoVoi tenant account
- A Meta Business Account with business verification complete
- A Facebook/Instagram Shop with Commerce Account
- Meta Tech Provider Amendment signed
- Meta App with `catalog`, `commerce`, and `orders` permissions
- A permanent System User access token

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

## Step 2 — Create a Meta App with Commerce permissions

1. Go to [developers.facebook.com](https://developers.facebook.com) and create a Business app
2. Add the **Commerce** product to your app
3. Under **App Review**, request the following permissions:
   - `catalog_management`
   - `commerce_account_manage_orders`
   - `commerce_account_read_orders`
4. In Meta Business Manager, create a **System User** and generate a permanent access token with these permissions
5. Note your **Commerce Account ID** from [facebook.com/commerce_manager](https://www.facebook.com/commerce_manager)

---

## Step 3 — Connect the integration

```http
POST /internal/integrations/{tenant_id}/instagram-shops
Authorization: Bearer <admin-key>
Content-Type: application/json

{
  "credentials": {
    "access_token": "<meta-system-user-access-token>",
    "commerce_account_id": "<meta-commerce-account-id>",
    "app_secret": "<meta-app-secret>"
  },
  "shop_identifier": "<commerce_account_id>",
  "base_currency": "GBP",
  "preferred_network": "algorand_mainnet"
}
```

The response includes a `webhook_secret` and a `webhook_url`.

---

## Step 4 — Configure external checkout

Set your AlgoVoi checkout URL as the external checkout destination for your Commerce Account:

```http
POST https://graph.facebook.com/v18.0/{commerce_account_id}
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "external_checkout_url": "<webhook_url from Step 3>"
}
```

---

## Step 5 — Register the webhook

1. In your Meta App go to **Webhooks**
2. Subscribe to the `commerce` object — enable the `orders` field
3. Set the **Callback URL** to your endpoint
4. Set the **Verify Token** to your `webhook_secret`

> **Note:** The exact webhook object and field names for Meta Commerce orders may vary depending on your Commerce Account configuration. Confirm the subscribed fields in your Meta App Dashboard after setup.

### Webhook signature verification

Meta signs every webhook with an `X-Hub-Signature-256` header:

```
X-Hub-Signature-256: sha256=<hex(HMAC-SHA256(app_secret, raw_body))>
```

---

## Order webhook payload

When a customer reaches checkout, AlgoVoi receives an order event:

```json
{
  "object": "commerce",
  "entry": [{
    "changes": [{
      "field": "orders",
      "value": {
        "order_id": "<meta-order-id>",
        "buyer_details": {
          "name": "Customer Name"
        },
        "channel": "instagram",
        "items": [{
          "retailer_id": "SKU-001",
          "quantity": 1,
          "price_per_unit": { "amount": "29.99", "currency": "GBP" }
        }]
      }
    }]
  }]
}
```

---

## Order fulfillment

After AlgoVoi confirms on-chain payment, update the order status via the Commerce API:

```http
POST https://graph.facebook.com/v18.0/{order_id}/shipments
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "tracking_info": {
    "tracking_number": "<algovoi-tx-id>",
    "carrier": "AlgoVoi"
  }
}
```

---

## Troubleshooting

| Symptom | Likely cause |
|---------|-------------|
| External checkout not available | Meta Tech Provider agreement not signed |
| `X-Hub-Signature-256` mismatch | `app_secret` incorrect |
| Order webhooks not arriving | Check subscribed fields in Meta App Dashboard — confirm `orders` field enabled |
| Permission denied on Commerce API | App Review not complete for `commerce_account_manage_orders` |
| HTTP 422 "No network config" | Network config missing for `preferred_network` |

---

---

## Live test status

Confirmed end-to-end on **2026-04-01** against `api1.ilovechicken.co.uk`:

| Test | Network | Result |
|------|---------|--------|
| Webhook → checkout link | `algorand_mainnet` (USDC (ASA 31566704)) | Skip |
| Webhook → checkout link | `voi_mainnet` (WAD (ARC200 app ID 47138068)) | Pass |
| Webhook → checkout link | `hedera_mainnet` (USDC (token 0.0.456858)) | Pass |
| Webhook → checkout link | `stellar_mainnet` (USDC (Circle)) | Pass |

Webhook signature verified on `algorand_mainnet`; full order-amount fetch requires real platform API credentials.

## Supported networks

| Network | Asset | Notes |
|---------|-------|-------|
| `algorand_mainnet` | USDC (ASA 31566704) | Requires ASA opt-in on payout wallet |
| `voi_mainnet` | WAD (ARC200 app ID 47138068) |  |
| `algorand_testnet` | Test USDC | For development and testing |
| `voi_testnet` | Test aUSDC | For development and testing |
