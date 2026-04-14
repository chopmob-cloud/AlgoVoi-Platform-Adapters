# Cdiscount Integration — AlgoVoi Tenant Services

Accept **USDC on Algorand** and **aUSDC on VOI** for Cdiscount orders via AlgoVoi.

> **Regional marketplace.** Cdiscount is France's second-largest e-commerce marketplace. AlgoVoi integrates via the **Octopia REST API** — the modern replacement for Cdiscount's legacy SOAP interface.

---

## How it works

AlgoVoi polls the Octopia Orders API to detect new orders — Cdiscount/Octopia does not currently support push webhooks for order events.

```
AlgoVoi polls GET /orders periodically
        ↓
New order detected with status WaitingAcceptance
        ↓
AlgoVoi accepts order → creates hosted checkout link (USDC or aUSDC)
        ↓
Checkout URL returned — share with buyer via email
        ↓
Buyer pays on-chain
        ↓
AlgoVoi verifies transaction on-chain
        ↓
AlgoVoi ships order via Octopia API
```

---

## Prerequisites

- An active AlgoVoi tenant account
- A Cdiscount / Octopia seller account
- API credentials from **Seller Area > Settings > Connection Settings**

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

## Step 2 — Get Octopia API credentials

1. Sign in to the [Cdiscount Seller Area](https://seller.cdiscount.com)
2. Go to **Settings > Connection Settings**
3. Copy your **Client ID** and **Client Secret** from the API credentials section
4. Note your **Seller ID**

---

## Step 3 — Connect the integration

```http
POST /internal/integrations/{tenant_id}/cdiscount
Authorization: Bearer <admin-key>
Content-Type: application/json

{
  "credentials": {
    "client_id": "<octopia-client-id>",
    "client_secret": "<octopia-client-secret>",
    "seller_id": "<cdiscount-seller-id>"
  },
  "shop_identifier": "<cdiscount-seller-id>",
  "base_currency": "EUR",
  "preferred_network": "algorand_mainnet"
}
```

**`preferred_network`** — which chain to settle payments on:

| Value | Settles in |
|-------|-----------|
| `algorand_mainnet` | USDC (ASA 31566704) |
| `voi_mainnet` | WAD (ARC200 app ID 47138068) |

AlgoVoi authenticates via Octopia OAuth2:

```http
POST https://auth.octopia.com/auth/realms/maas/protocol/openid-connect/token
Content-Type: application/x-www-form-urlencoded

grant_type=client_credentials
&client_id=<client_id>
&client_secret=<client_secret>
```

All subsequent Octopia API calls include:

```
Authorization: Bearer <access_token>
SellerId: <seller_id>
```

---

## Step 4 — Order polling

AlgoVoi polls for new orders requiring acceptance:

```http
GET https://api.octopia-io.net/orders?status=WaitingAcceptance
Authorization: Bearer <access_token>
SellerId: <seller_id>
```

When a new order is found, AlgoVoi first accepts it:

```http
POST https://api.octopia-io.net/orders/{order_id}/accept
Authorization: Bearer <access_token>
SellerId: <seller_id>
```

Then creates and returns a hosted checkout link for the buyer.

> AlgoVoi polls at a configurable interval (default: every 5 minutes). Orders typically require acceptance within 2 business days on Cdiscount.

---

## Payment flow for your customers

Once AlgoVoi detects and accepts a new order:

1. A hosted checkout link is created (valid 30 minutes)
2. Share the checkout URL with your buyer via email
3. Buyer pays in USDC or aUSDC on-chain
4. AlgoVoi verifies the transaction on-chain
5. AlgoVoi ships the order:

```http
POST https://api.octopia-io.net/orders/{order_id}/ship
Authorization: Bearer <access_token>
SellerId: <seller_id>
Content-Type: application/json

{
  "trackingNumber": "<algovoi-tx-id>",
  "carrierName": "AlgoVoi",
  "trackingUrl": "https://algovoi.com/tx/<algovoi-tx-id>"
}
```

---

## Troubleshooting

| Symptom | Likely cause |
|---------|-------------|
| HTTP 401 on API calls | Access token expired — AlgoVoi will refresh automatically |
| HTTP 403 on order operations | `SellerId` header missing or incorrect |
| Orders stuck in WaitingAcceptance | Auto-accept failing — check API credentials |
| HTTP 422 "No network config" | Network config missing for `preferred_network` |
| Payment link expired | Buyer took longer than 30 minutes — share a new link via the AlgoVoi dashboard |
| SOAP deprecation errors | Ensure you are using the Octopia REST API, not the legacy SOAP endpoint |

---

---

## Live test status

Confirmed end-to-end on **2026-04-14** against `api1.ilovechicken.co.uk`:

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
