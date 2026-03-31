# Bol.com Integration — AlgoVoi Tenant Services

Accept **USDC on Algorand** and **aUSDC on VOI** for Bol.com orders via AlgoVoi.

---

## Important: Bol.com payment model

Bol.com processes all consumer checkout payments internally. AlgoVoi's Bol.com integration targets:

- **B2B / supplier invoicing** — receive order notifications and issue a crypto payment request to a supplier or fulfilment partner
- **Seller-initiated settlement** — settle platform fees or inter-company invoices in USDC/aUSDC
- **Operator-initiated flows** — your own backend posts order data directly to AlgoVoi (bypass mode)

---

## How it works

```
AlgoVoi polls GET /orders?status=OPEN on the Bol.com Retailer API
        ↓
New OPEN order detected → AlgoVoi parses order details
        ↓
AlgoVoi creates a hosted checkout link (USDC or aUSDC)
        ↓
Counterparty pays on-chain
        ↓
AlgoVoi verifies transaction on-chain
        ↓
Bol.com order updated via PUT /orders/{orderId}/shipment with AlgoVoi TX reference
```

> Bol.com does not offer native outbound webhooks. AlgoVoi polls for new OPEN orders at a configurable interval (default: every 60 seconds).

---

## Prerequisites

- An active AlgoVoi tenant account
- A Bol.com seller account on [seller.bol.com](https://seller.bol.com)
- API credentials (Client ID and Client Secret) from the Bol.com seller dashboard

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

## Step 2 — Get Bol.com API credentials

1. Log in to your Bol.com seller dashboard at [seller.bol.com](https://seller.bol.com)
2. Navigate to **Instellingen → API toegang** (Settings → API access)
3. Click **Nieuwe API-sleutel aanmaken** (Create new API key)
4. Copy the **Client ID** and **Client Secret** — the secret is shown once

> AlgoVoi authenticates with Bol.com using OAuth2 client credentials, exchanging your Client ID and Client Secret for a short-lived bearer token via `POST https://login.bol.com/token`. Token refresh is handled automatically.

---

## Step 3 — Connect the integration

```http
POST /internal/integrations/{tenant_id}/bolcom
Authorization: Bearer <admin-key>
Content-Type: application/json

{
  "credentials": {
    "client_id": "<bol-client-id>",
    "client_secret": "<bol-client-secret>"
  },
  "shop_identifier": "<your-bol-seller-id>",
  "base_currency": "EUR",
  "preferred_network": "algorand_mainnet"
}
```

**`preferred_network`** — which chain to settle payments on:

| Value | Settles in |
|-------|-----------|
| `algorand_mainnet` | USDC on Algorand |
| `voi_mainnet` | aUSDC on VOI |

The response confirms the integration is active. Because Bol.com uses polling rather than webhooks, there is no `webhook_url` or `webhook_secret` returned.

```json
{
  "status": "active",
  "platform": "bolcom",
  "preferred_network": "algorand_mainnet",
  "poll_interval_seconds": 60
}
```

---

## Step 4 — Polling and notifications

Bol.com does not support outbound webhooks. AlgoVoi polls `GET https://api.bol.com/retailer/orders?status=OPEN` on your behalf at the configured interval.

**No additional setup is required** — polling begins automatically once the integration is connected.

To adjust the poll interval, update the integration:

```http
POST /internal/integrations/{tenant_id}/bolcom
Authorization: Bearer <admin-key>
Content-Type: application/json

{
  "credentials": {
    "client_id": "<bol-client-id>",
    "client_secret": "<bol-client-secret>"
  },
  "shop_identifier": "<your-bol-seller-id>",
  "base_currency": "EUR",
  "preferred_network": "algorand_mainnet",
  "poll_interval_seconds": 120
}
```

> Minimum poll interval is 30 seconds. Setting a value below 30 will be clamped to 30 to respect Bol.com rate limits.

---

## Payment flow

Once connected:

1. AlgoVoi detects a new OPEN order on the next poll cycle
2. A hosted checkout link is created (valid 30 minutes)
3. Share the checkout URL with your supplier or fulfilment partner
4. Counterparty pays in USDC or aUSDC on-chain
5. AlgoVoi verifies the transaction and calls `PUT https://api.bol.com/retailer/orders/{orderId}/shipment` with the AlgoVoi TX ID as the shipment/tracking reference

---

## Troubleshooting

| Symptom | Likely cause |
|---------|-------------|
| HTTP 422 "No network config" | Network config missing for `preferred_network` |
| HTTP 401 from Bol.com API | Client ID or Client Secret is incorrect — reconnect the integration |
| Orders not being detected | Bol.com OAuth token refresh failure — check credentials and reconnect |
| Shipment update failing | Order may have already transitioned out of OPEN state on Bol.com |
| Payment link expired | Counterparty took longer than 30 minutes — re-trigger manually via operator POST |

---

## Supported networks

| Network | Asset | Notes |
|---------|-------|-------|
| `algorand_mainnet` | USDC (ASA 31566704) | Requires ASA opt-in on payout wallet |
| `voi_mainnet` | aUSDC (ARC200 app ID 311051) | |
| `algorand_testnet` | Test USDC | For integration testing only |
| `voi_testnet` | Test aUSDC | For integration testing only |
