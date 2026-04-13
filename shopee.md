# Shopee Integration — AlgoVoi Tenant Services

Accept **USDC on Algorand** and **aUSDC on VOI** for Shopee orders via AlgoVoi.

> **Regional marketplace.** Shopee operates across Southeast Asia (MY, TH, PH, SG, ID, VN, TW) and Brazil. All API requests require HMAC-SHA256 request signing using your Partner Key.

---

## How it works

```
Shopee order placed → order status changes to READY_TO_SHIP
        ↓
Shopee fires push notification to AlgoVoi webhook
        ↓
AlgoVoi verifies X-Shopee-Signature → fetches order via GET /order/get_order_detail
        ↓
AlgoVoi creates a hosted checkout link (USDC or aUSDC)
        ↓
Checkout URL returned — share with buyer via Shopee chat or email
        ↓
Buyer pays on-chain
        ↓
AlgoVoi verifies transaction on-chain
        ↓
AlgoVoi marks order shipped via POST /logistics/ship_order
```

---

## Prerequisites

- An active AlgoVoi tenant account
- A Shopee seller account
- A registered application on [Shopee Open Platform](https://open.shopee.com)
- Partner ID and Partner Key from the Open Platform console
- Shop ID from the seller account

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

> ASA `31566704` is Circle's native USDC on Algorand mainnet.
> Your payout wallet must have opted into this ASA before receiving payments.

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

## Step 2 — Register on Shopee Open Platform

1. Go to [open.shopee.com](https://open.shopee.com) and sign in with your Shopee account
2. Create a new application and submit for review
3. Once approved, note your **Live Partner ID** and **Live Partner Key** from the app console
4. Complete the OAuth flow to obtain a **Shop Access Token** and **Shop ID** for your seller account
5. Register the AlgoVoi webhook URL in your app's **Push Notification** settings

---

## Step 3 — Connect the integration

```http
POST /internal/integrations/{tenant_id}/shopee
Authorization: Bearer <admin-key>
Content-Type: application/json

{
  "credentials": {
    "partner_id": "<shopee-partner-id>",
    "partner_key": "<shopee-partner-key>",
    "shop_id": "<shopee-shop-id>",
    "access_token": "<shopee-shop-access-token>",
    "refresh_token": "<shopee-shop-refresh-token>"
  },
  "shop_identifier": "<shopee-shop-id>",
  "base_currency": "SGD",
  "preferred_network": "algorand_mainnet"
}
```

**`preferred_network`** — which chain to settle payments on:

| Value | Settles in |
|-------|-----------|
| `algorand_mainnet` | USDC (ASA 31566704) |
| `voi_mainnet` | WAD (ARC200 app ID 47138068) |

The response includes a `webhook_url` to register in the Shopee console.

---

## Step 4 — Register the push notification URL

In your Shopee Open Platform console, navigate to your app settings and set the **Push Notification URL** to the `webhook_url` returned in Step 3.

Shopee will send order status change events to this URL.

### Request signing

All AlgoVoi requests to the Shopee API are signed using HMAC-SHA256. The signature base string is:

```
{partner_id}{path}{timestamp}{access_token}{shop_id}
```

Signed with the `partner_key`. The result is passed as a query parameter `sign` on each request.

### Webhook signature verification

Shopee signs each push notification with an `X-Shopee-Signature` header:

```
HMAC-SHA256(partner_key, raw_body)
```

AlgoVoi verifies this signature automatically. Payloads that fail verification are rejected.

---

## Order push notification payload

When an order status changes, AlgoVoi receives:

```json
{
  "code": 3,
  "timestamp": 1640995200,
  "shop_id": 12345678,
  "data": {
    "ordersn": "220101ABCDEFGH",
    "status": "READY_TO_SHIP"
  }
}
```

> Shopee push notification codes: `3` = order status update. AlgoVoi fetches the full order detail after receiving this event.

---

## Order detail fetch

AlgoVoi fetches full order information for checkout link generation:

```http
GET https://partner.shopeemobile.com/api/v2/order/get_order_detail
  ?partner_id={partner_id}
  &shop_id={shop_id}
  &access_token={access_token}
  &timestamp={unix_timestamp}
  &sign={hmac_signature}
  &order_sn_list=220101ABCDEFGH
  &response_optional_fields=item_list,recipient_address
```

---

## Troubleshooting

| Symptom | Likely cause |
|---------|-------------|
| `X-Shopee-Signature` mismatch | `partner_key` incorrect in credentials |
| HTTP 401 on API calls | Access token expired — AlgoVoi will refresh automatically |
| Push notifications not arriving | Webhook URL not set in Shopee Open Platform console |
| HTTP 422 "No network config" | Network config missing for `preferred_network` |
| Order detail fetch failing | `order_sn_list` incorrectly formatted — must be a comma-separated string |
| App not approved | Shopee Open Platform app review pending — use sandbox credentials for testing |

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

Signature verified and checkout link generated. Asset: USDC (ASA 31566704).

## Supported networks

| Network | Asset | Notes |
|---------|-------|-------|
| `algorand_mainnet` | USDC (ASA 31566704) | Requires ASA opt-in on payout wallet |
| `voi_mainnet` | WAD (ARC200 app ID 47138068) |  |
| `algorand_testnet` | Test USDC | For integration testing only |
| `voi_testnet` | Test aUSDC | For integration testing only |

## Supported regions

| Region | Base URL |
|--------|---------|
| SE Asia (MY, TH, PH, SG, ID, VN, TW) | `https://partner.shopeemobile.com/api/v2/` |
| Brazil | `https://openplatform.shopee.com.br/api/v2/` |
