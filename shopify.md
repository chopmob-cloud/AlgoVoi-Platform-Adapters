# Shopify Integration — AlgoVoi Tenant Services

Accept **USDC on Algorand** and **aUSDC on VOI** as payment in your Shopify store via AlgoVoi.

---

## How it works

```
Shopify order created
        ↓
AlgoVoi receives webhook → verifies signature → parses order
        ↓
AlgoVoi creates a hosted checkout link (USDC or aUSDC)
        ↓
Customer pays on-chain
        ↓
AlgoVoi verifies the transaction on-chain
        ↓
Shopify order marked as paid
```

No code changes needed in your Shopify store — AlgoVoi handles everything via webhooks.

---

## Prerequisites

- An active AlgoVoi tenant account
- A Shopify store with Admin API access
- A Shopify Custom App with the `write_orders` and `read_orders` scopes

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

## Step 2 — Create a Shopify Custom App

1. In Shopify Admin go to **Settings → Apps and sales channels → Develop apps**
2. Click **Create an app** and give it a name (e.g. "AlgoVoi Payments")
3. Under **Configuration → Admin API scopes**, enable:
   - `read_orders`
   - `write_orders`
4. Click **Install app** and copy the **Admin API access token**

---

## Step 3 — Connect the integration

```http
POST /internal/integrations/{tenant_id}/shopify
Authorization: Bearer <admin-key>
Content-Type: application/json

{
  "credentials": {
    "shop_domain": "your-store.myshopify.com",
    "access_token": "<shopify-admin-api-access-token>"
  },
  "shop_identifier": "your-store.myshopify.com",
  "base_currency": "USD",
  "preferred_network": "algorand_mainnet"
}
```

**`preferred_network`** — which chain to settle payments on:

| Value | Settles in |
|-------|-----------|
| `algorand_mainnet` | USDC on Algorand |
| `voi_mainnet` | aUSDC on VOI |

The response includes a `webhook_secret` and a `webhook_url`. Save both — the secret is shown once.

```json
{
  "webhook_url": "https://api.algovoi.com/webhooks/shopify/{tenant_id}",
  "webhook_secret": "...",
  "preferred_network": "algorand_mainnet"
}
```

---

## Step 4 — Register the webhook in Shopify

1. In Shopify Admin go to **Settings → Notifications → Webhooks**
2. Click **Create webhook**
3. Set:
   - **Event**: Order creation
   - **URL**: the `webhook_url` from Step 3
   - **Format**: JSON
4. Copy the **Signing secret** Shopify shows — this must match the `webhook_secret` from Step 3

> AlgoVoi verifies every inbound webhook using HMAC-SHA256 against the `X-Shopify-Hmac-Sha256` header. Mismatched secrets will be rejected with HTTP 401.

---

## Payment flow for your customers

Once connected, every new Shopify order triggers AlgoVoi to:

1. Create a hosted checkout link valid for **30 minutes**
2. Display the amount in USDC (or aUSDC) with a QR code and wallet link
3. On successful on-chain confirmation, mark the Shopify order as **paid**

The customer is redirected back to the Shopify order status page after payment.

---

## Tenant limits to check

Ensure your tenant's limits allow the integration to function:

```http
PUT /internal/tenants/{tenant_id}/limits
Authorization: Bearer <admin-key>
Content-Type: application/json

{
  "allowed_networks": ["algorand_mainnet"],
  "allowed_assets": ["31566704"],
  "kill_switch": false
}
```

---

## Troubleshooting

| Symptom | Likely cause |
|---------|-------------|
| HTTP 401 on webhook | `webhook_secret` mismatch — reconnect the integration to rotate the secret |
| HTTP 422 "No network config" | Network config missing or no payout address set for `preferred_network` |
| Order not marked paid | Shopify Admin API token lacks `write_orders` scope |
| Payment link expired | Customer took longer than 30 minutes — a new order webhook will create a fresh link |

---

## Supported networks

| Network | Asset | Notes |
|---------|-------|-------|
| `algorand_mainnet` | USDC (ASA 31566704) | Requires ASA opt-in on payout wallet |
| `voi_mainnet` | aUSDC (ARC200 app ID 311051) | |
| `algorand_testnet` | Test USDC | For integration testing only |
| `voi_testnet` | Test aUSDC | For integration testing only |

---

## Live test status

Confirmed end-to-end on **2026-03-31** against `api1.ilovechicken.co.uk`:

| Test | Network | Result |
|------|---------|--------|
| `orders/create` webhook → checkout link | `algorand_mainnet` (USDC ASA 31566704) | ✅ Pass |
| `orders/create` webhook → checkout link | `voi_mainnet` (aUSDC app ID 311051) | ✅ Pass |

Both tests received HTTP 200 with `{"received":true,"status":"awaiting_payment","checkout_url":"..."}`.

Signature verification uses `HMAC-SHA256` over the raw request body. The webhook header is `X-Shopify-Hmac-Sha256` (lowercase when received by AlgoVoi). The `webhook_secret` is auto-generated by AlgoVoi on integration creation — it is not the Shopify app secret.
