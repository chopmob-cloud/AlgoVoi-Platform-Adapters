# TikTok Shop Integration — AlgoVoi Tenant Services

Accept **USDC on Algorand** and **aUSDC on VOI** for TikTok Shop orders via AlgoVoi.

---

## Important: TikTok Shop payment model

TikTok Shop processes all consumer checkout payments internally. AlgoVoi's TikTok Shop integration targets:

- **B2B / supplier invoicing** — receive order notifications and issue a crypto payment request to a supplier or fulfilment partner
- **Seller-initiated settlement** — settle platform fees or inter-company invoices in USDC/aUSDC
- **Operator-initiated flows** — your own backend posts order data directly to AlgoVoi (bypass mode)

---

## How it works

```
TikTok Shop order placed → TikTok Shop Open Platform webhook fired
            ↓
AlgoVoi receives + verifies HMAC-SHA256 signature → parses order
            ↓
AlgoVoi creates a hosted checkout link (USDC or aUSDC)
            ↓
Counterparty pays on-chain
            ↓
AlgoVoi verifies transaction on-chain
            ↓
TikTok Shop order shipping info updated with AlgoVoi TX reference
```

---

## Prerequisites

- An active AlgoVoi tenant account
- A TikTok Shop seller account
- A TikTok Shop Open Platform app (registered at [partner.tiktokshop.com](https://partner.tiktokshop.com))
- OAuth access token with `order` scope

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

## Step 2 — Get TikTok Shop API credentials

1. Register an app at the [TikTok Shop Open Platform](https://partner.tiktokshop.com)
2. Complete the OAuth flow to obtain an **Access Token** for your shop
3. Ensure the token includes the `order:read` and `order:write` scopes
4. Note your **App Key** and **App Secret**

---

## Step 3 — Connect the integration

```http
POST /internal/integrations/{tenant_id}/tiktok_shop
Authorization: Bearer <admin-key>
Content-Type: application/json

{
  "credentials": {
    "app_key": "<tiktok-app-key>",
    "app_secret": "<tiktok-app-secret>",
    "access_token": "<oauth-access-token>"
  },
  "shop_identifier": "<your-tiktok-shop-id>",
  "base_currency": "GBP",
  "preferred_network": "algorand_mainnet"
}
```

The response includes a `webhook_secret` and a `webhook_url`.

---

## Step 4 — Subscribe to order webhooks

Register your AlgoVoi webhook endpoint via the TikTok Shop Open Platform:

```http
POST https://open-api.tiktokglobalshop.com/api/webhook/register
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "events": ["ORDER_STATUS_CHANGE"],
  "url": "<webhook_url from Step 3>",
  "secret": "<webhook_secret from Step 3>"
}
```

TikTok Shop signs webhook requests with HMAC-SHA256. The signature is delivered in the `Webhook-Signature` header:

```
Webhook-Signature: <hex(HMAC-SHA256(webhook_secret, raw_body))>
```

AlgoVoi verifies this signature automatically on receipt.

> **Note:** TikTok Shop's webhook signature header name is not clearly documented in their public partner docs. `Webhook-Signature` is the value used here, but you should confirm the exact header name from your TikTok Shop Partner dashboard or by inspecting a live webhook delivery. If it differs, update your AlgoVoi integration credentials accordingly.

### Option B — Direct operator POST (bypass mode)

POST order data directly from your backend with `Authorization: Bearer <webhook_secret>`.

---

## Payment flow

Once connected:

1. AlgoVoi receives the `ORDER_STATUS_CHANGE` webhook (status: `AWAITING_SHIPMENT`)
2. A hosted checkout link is created (valid 30 minutes)
3. Share the checkout URL with your supplier or fulfilment partner
4. Counterparty pays in USDC or aUSDC on-chain
5. AlgoVoi verifies the transaction and updates the TikTok Shop order with TX ID as the tracking number reference

---

## Troubleshooting

| Symptom | Likely cause |
|---------|-------------|
| HTTP 401 on webhook | `Webhook-Signature` mismatch — check secret, re-register subscription, or verify exact header name in Partner dashboard |
| HTTP 422 "No network config" | Network config missing for `preferred_network` |
| OAuth token expired | TikTok Shop tokens expire — use refresh token to obtain a new access token |
| Order not updating | Access token lacks `order:write` scope |

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
| `ORDER_STATUS_CHANGE` webhook -> checkout link | `algorand_mainnet` (USDC (ASA 31566704)) | Pass |
| Webhook → checkout link | `voi_mainnet` (WAD (ARC200 app ID 47138068)) | Pass |
| Webhook → checkout link | `hedera_mainnet` (USDC (token 0.0.456858)) | Pass |
| Webhook → checkout link | `stellar_mainnet` (USDC (Circle)) | Pass |

Signature: `HMAC-SHA256` hex digest in `Webhook-Signature`. AlgoVoi processes orders with status `AWAITING_SHIPMENT` or `AWAITING_COLLECTION` (payment already captured by TikTok). Amount field: `data.payment_info.total_amount` (float, major units).
