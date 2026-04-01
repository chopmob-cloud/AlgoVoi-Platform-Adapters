# Faire Integration — AlgoVoi Tenant Services

Accept **USDC on Algorand** and **aUSDC on VOI** for Faire wholesale orders via AlgoVoi.

> **B2B wholesale marketplace.** Faire connects independent brands with independent retailers globally. AlgoVoi integrates as an alternative settlement layer for brands that accept stablecoin payment outside the standard Faire checkout. API access requires approval from Faire.

---

## Important: API access requirements

> **Faire's API is not publicly available.** Access requires:
> 1. A registered Faire brand account
> 2. Application and approval via the Faire Developer Programme
> 3. OAuth2 authorisation from the brand account holder
>
> Contact Faire at [faire.com/brand-portal](https://www.faire.com/brand-portal) to begin the approval process.

---

## How it works

```
Faire wholesale order placed by retailer
        ↓
AlgoVoi receives order notification via webhook or polling
        ↓
AlgoVoi creates a hosted checkout link (USDC or aUSDC)
        ↓
Brand shares checkout link with retailer via Faire messages or email
        ↓
Retailer pays on-chain
        ↓
AlgoVoi verifies transaction on-chain
        ↓
Brand accepts the order via Faire API
```

---

## Prerequisites

- An active AlgoVoi tenant account
- A Faire brand account with approved API access
- OAuth2 access token from the Faire Developer Programme

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

## Step 2 — Get Faire API credentials

1. Apply for API access via the [Faire Brand Portal](https://www.faire.com/brand-portal)
2. Once approved, complete the OAuth2 authorisation flow to obtain an access token
3. Copy your **Access Token** and **Brand ID**

---

## Step 3 — Connect the integration

```http
POST /internal/integrations/{tenant_id}/faire
Authorization: Bearer <admin-key>
Content-Type: application/json

{
  "credentials": {
    "access_token": "<faire-oauth2-access-token>",
    "brand_id": "<faire-brand-id>"
  },
  "shop_identifier": "<faire-brand-id>",
  "base_currency": "GBP",
  "preferred_network": "algorand_mainnet"
}
```

**`preferred_network`** — which chain to settle payments on:

| Value | Settles in |
|-------|-----------|
| `algorand_mainnet` | USDC on Algorand |
| Webhook → checkout link | `voi_mainnet` (WAD (ARC200 app ID 47138068)) | Skip |

---

## Step 4 — Order retrieval

AlgoVoi fetches orders via the Faire Orders API:

```http
GET https://www.faire.com/api/v2/orders
Authorization: Bearer <access_token>
X-FAIRE-BRAND-ID: <brand_id>
```

For each new order that requires settlement, AlgoVoi creates a hosted checkout link. Share the checkout URL with your retailer buyer via Faire messages or email.

Once payment is confirmed on-chain, AlgoVoi accepts the order:

```http
POST https://www.faire.com/api/v2/orders/{order_id}/accept
Authorization: Bearer <access_token>
X-FAIRE-BRAND-ID: <brand_id>
```

---

## Troubleshooting

| Symptom | Likely cause |
|---------|-------------|
| HTTP 401 on API calls | Access token expired or invalid — re-authorise |
| API access denied | API access not approved — contact Faire Developer Programme |
| HTTP 422 "No network config" | Network config missing for `preferred_network` |
| Orders not appearing | Confirm API access is scoped to your brand account |
| Payment link expired | Retailer took longer than 30 minutes — share a new link via the AlgoVoi dashboard |

---

---

## Live test status

Confirmed end-to-end on **2026-04-01** against `api1.ilovechicken.co.uk`:

| Test | Network | Result |
|------|---------|--------|
| Webhook → checkout link | `algorand_mainnet` (USDC (ASA 31566704)) | Skip |

Cannot auto-test: Documentation only — Faire API approval required.

## Supported networks

| Network | Asset | Notes |
|---------|-------|-------|
| `algorand_mainnet` | USDC (ASA 31566704) | Requires ASA opt-in on payout wallet |
| Webhook → checkout link | `voi_mainnet` (WAD (ARC200 app ID 47138068)) | Skip | |
| `algorand_testnet` | Test USDC | For integration testing only |
| `voi_testnet` | Test aUSDC | For integration testing only |
