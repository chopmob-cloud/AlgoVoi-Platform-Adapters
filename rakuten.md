# Rakuten Ichiba Integration — AlgoVoi Tenant Services

Accept **USDC on Algorand** and **aUSDC on VOI** for Rakuten Ichiba orders via AlgoVoi.

---

## Important: Rakuten does not support outbound webhooks

Rakuten Ichiba's RMS (Rakuten Merchant Server) API is polling-based — there is no native webhook mechanism for new order events. AlgoVoi polls the RMS order list endpoint at a configured interval, detects new orders, and proceeds from there.

---

## How it works

```
AlgoVoi polls GET /order/searchOrder/ with last-modified timestamp
        ↓
New order detected → AlgoVoi parses order from RMS API response
        ↓
AlgoVoi creates a hosted checkout link (USDC or aUSDC)
        ↓
AlgoVoi writes the checkout URL to the order notes via RMS API
        ↓
Buyer sees payment link in order confirmation / merchant contacts buyer
        ↓
Buyer pays on-chain
        ↓
AlgoVoi verifies transaction on-chain
        ↓
Order marked as paid with AlgoVoi TX reference in RMS
```

---

## Prerequisites

- An active AlgoVoi tenant account
- A Rakuten Ichiba merchant account with RMS API access enabled
- A **Service Secret** and **License Key** from the Rakuten RMS portal (店舗管理)

---

## Step 1 — Configure your network

You need at least one network config with a payout address and your chosen stablecoin.

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
  "preferred_asset_id": "311051",
  "preferred_asset_decimals": 6
}
```

> ARC200 app ID `311051` is aUSDC on VOI mainnet.

---

## Step 2 — Get Rakuten RMS API credentials

1. Log in to the Rakuten RMS portal (店舗管理) for your shop
2. Navigate to **API連携設定** (API integration settings)
3. Enable RMS API access if not already active
4. Copy your **Service Secret** and **License Key**

> These credentials are used to authenticate all RMS API calls. The base URL for RMS API v1 is
> `https://api.rms.rakuten.co.jp/es/1.0/`.

### Rakuten France and Rakuten Germany

Rakuten also operates [rakuten.fr](https://www.rakuten.fr) and [rakuten.de](https://www.rakuten.de) as separate marketplace platforms. Each has its own merchant portal and issues separate credentials. If you sell on rakuten.fr or rakuten.de, connect each as a distinct AlgoVoi integration using the credentials from the respective portal.

---

## Step 3 — Connect the integration

```http
POST /internal/integrations/{tenant_id}/rakuten
Authorization: Bearer <admin-key>
Content-Type: application/json

{
  "credentials": {
    "service_secret": "<rakuten-service-secret>",
    "license_key": "<rakuten-license-key>"
  },
  "shop_identifier": "<your-rakuten-shop-url-name>",
  "base_currency": "JPY",
  "preferred_network": "algorand_mainnet"
}
```

**`preferred_network`** — which chain to settle payments on:

| Value | Settles in |
|-------|-----------|
| `algorand_mainnet` | USDC on Algorand |
| `voi_mainnet` | aUSDC on VOI |

For Rakuten France or Germany, set `base_currency` to `EUR` and use the credentials from the respective portal.

The response confirms the integration is active and polling is enabled:

```json
{
  "integration": "rakuten",
  "shop_identifier": "<your-rakuten-shop-url-name>",
  "polling": true,
  "preferred_network": "algorand_mainnet"
}
```

> There is no `webhook_url` or `webhook_secret` for Rakuten — AlgoVoi initiates all order
> discovery by polling the RMS API. No configuration is required in the Rakuten portal.

---

## Step 4 — Verify polling and order note delivery

Because Rakuten is polling-based, confirm the integration is working by checking that AlgoVoi can reach the RMS order endpoint:

1. Place a test order on your Rakuten shop
2. Wait for AlgoVoi's next poll cycle (typically within 5 minutes)
3. Check the order in RMS — AlgoVoi writes the checkout URL into the order's **seller memo / notes field** via the RMS API
4. Confirm the note appears with a valid AlgoVoi checkout URL

You can also share the checkout URL with your buyer directly via Rakuten's in-platform messaging.

---

## Payment flow for your customers

Once connected, AlgoVoi polls for new orders and:

1. Detects any orders with `orderStatus` indicating a new, unpaid purchase since the last poll
2. Creates a hosted checkout link valid for **30 minutes**
3. Writes the checkout URL to the order notes field in RMS so it is visible in the merchant order detail view
4. On successful on-chain confirmation, updates the order status in RMS with the AlgoVoi TX reference

> If the checkout link expires before the buyer pays, AlgoVoi will generate a fresh link on the
> next poll cycle when it detects the order is still unpaid.

---

## Troubleshooting

| Symptom | Likely cause |
|---------|-------------|
| HTTP 401 from RMS API | Service Secret or License Key incorrect — recheck credentials in Step 2 |
| HTTP 422 "No network config" | Network config missing or no payout address set for `preferred_network` |
| No orders detected | RMS API access not enabled in the portal, or credentials belong to a different shop |
| Order notes not updating | RMS API write permission not granted — check API settings in 店舗管理 |
| Payment link expired | Poll interval exceeded buyer's payment window — AlgoVoi issues a fresh link on next cycle |
| Wrong currency | `base_currency` set incorrectly — use `JPY` for Ichiba, `EUR` for rakuten.fr / rakuten.de |

---

## Supported networks

| Network | Asset | Notes |
|---------|-------|-------|
| `algorand_mainnet` | USDC (ASA 31566704) | Requires ASA opt-in on payout wallet |
| `voi_mainnet` | aUSDC (ARC200 app ID 311051) | |
| `algorand_testnet` | Test USDC | For integration testing only |
| `voi_testnet` | Test aUSDC | For integration testing only |
