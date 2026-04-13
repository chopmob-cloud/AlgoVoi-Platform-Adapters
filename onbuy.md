# OnBuy Integration — AlgoVoi Tenant Services

Accept **USDC on Algorand** and **aUSDC on VOI** for OnBuy orders via AlgoVoi.

> **Regional marketplace.** OnBuy is a UK-based online marketplace. AlgoVoi polls the OnBuy Orders API to detect new orders — OnBuy does not currently support push webhooks for order events.

---

## How it works

```
AlgoVoi polls GET /orders periodically
        ↓
New order detected with status OPEN
        ↓
AlgoVoi creates a hosted checkout link (USDC or aUSDC)
        ↓
Checkout URL returned — share with buyer via email or OnBuy messaging
        ↓
Buyer pays on-chain
        ↓
AlgoVoi verifies transaction on-chain
        ↓
AlgoVoi updates order/shipment status via OnBuy API
```

---

## Prerequisites

- An active AlgoVoi tenant account
- An OnBuy seller account
- API credentials from the OnBuy Seller Centre (**Listing > Imports & Integrations**)

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

## Step 2 — Get OnBuy API credentials

1. Sign in to the [OnBuy Seller Centre](https://seller.onbuy.com)
2. Go to **Listing > Imports & Integrations**
3. Generate your **Consumer Key** and **Secret Key**
4. Note your **Site ID** (UK site ID is `2000`)

---

## Step 3 — Connect the integration

```http
POST /internal/integrations/{tenant_id}/onbuy
Authorization: Bearer <admin-key>
Content-Type: application/json

{
  "credentials": {
    "consumer_key": "<onbuy-consumer-key>",
    "secret_key": "<onbuy-secret-key>",
    "site_id": "2000"
  },
  "shop_identifier": "<your-onbuy-seller-id>",
  "base_currency": "GBP",
  "preferred_network": "algorand_mainnet"
}
```

**`preferred_network`** — which chain to settle payments on:

| Value | Settles in |
|-------|-----------|
| `algorand_mainnet` | USDC (ASA 31566704) |
| `voi_mainnet` | WAD (ARC200 app ID 47138068) |

AlgoVoi authenticates using OAuth2 client credentials:

```http
POST https://api.onbuy.com/v2/oauth/token
Content-Type: application/x-www-form-urlencoded

grant_type=client_credentials
&client_id=<consumer_key>
&client_secret=<secret_key>
```

---

## Step 4 — Order polling

AlgoVoi polls for new orders periodically:

```http
GET https://api.onbuy.com/v2/orders?site_id=2000&status=awaiting_dispatch
Authorization: Bearer <access_token>
```

For each new order, AlgoVoi generates a hosted checkout link. The checkout URL is returned in the AlgoVoi API response — share it with your buyer via email.

> OnBuy does not currently provide push webhooks. AlgoVoi polls at a configurable interval (default: every 5 minutes) to detect new orders.

---

## Payment flow for your customers

Once AlgoVoi detects a new order:

1. A hosted checkout link is created (valid 30 minutes)
2. Share the checkout URL with your buyer via email or OnBuy messages
3. Buyer pays in USDC or aUSDC on-chain
4. AlgoVoi verifies the transaction on-chain
5. AlgoVoi dispatches the order via the OnBuy API:

```http
PUT https://api.onbuy.com/v2/orders/{order_id}/dispatch
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "site_id": "2000",
  "tracking_number": "<algovoi-tx-id>",
  "tracking_url": "https://algovoi.com/tx/<algovoi-tx-id>",
  "courier_name": "AlgoVoi"
}
```

---

## Troubleshooting

| Symptom | Likely cause |
|---------|-------------|
| HTTP 401 on API calls | Access token expired — AlgoVoi will refresh automatically |
| HTTP 403 on order fetch | Consumer Key or Secret Key incorrect — re-generate in Seller Centre |
| HTTP 422 "No network config" | Network config missing for `preferred_network` |
| Orders not detected | Polling interval or `status` filter issue — check AlgoVoi polling logs |
| Payment link expired | Buyer took longer than 30 minutes — share a new link via the AlgoVoi dashboard |
| Wrong Site ID | UK is `2000` — verify in OnBuy Seller Centre |

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
