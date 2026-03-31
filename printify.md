# Printify Integration — AlgoVoi Tenant Services

Pay your Printify production costs in **USDC on Algorand** or **aUSDC on VOI** via AlgoVoi.

---

## How it works

```
Merchant's customer places an order on their storefront
        ↓
Printify receives the fulfillment request → routes to a print provider
        ↓
AlgoVoi receives Printify webhook (order:created) → verifies signature → parses order
        ↓
AlgoVoi creates a hosted checkout link (USDC or aUSDC) for the production invoice
        ↓
Merchant pays on-chain
        ↓
AlgoVoi verifies the transaction on-chain
        ↓
Printify order confirmed and dispatched to the selected print provider
```

No code changes needed in your storefront — AlgoVoi handles everything via Printify webhooks.

> Printify connects to 900+ global print providers. Paying production costs in USDC eliminates card
> fees and FX conversion for every international order routed through the network.

---

## Prerequisites

- An active AlgoVoi tenant account
- A Printify account with at least one active shop
- A Printify API token (generated in Printify → My account → Connections → API token)
- Your Printify **shop ID** (visible in the URL when viewing your shop: `/shops/{shop_id}/`)

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

## Step 2 — Generate a Printify API token

1. Log in to the **Printify app**
2. Go to **My account → Connections**
3. Under **API**, click **Generate token**
4. Give it a name (e.g. "AlgoVoi") and copy the token — it is shown once

---

## Step 3 — Connect the integration

```http
POST /internal/integrations/{tenant_id}/printify
Authorization: Bearer <admin-key>
Content-Type: application/json

{
  "credentials": {
    "api_token": "<printify-api-token>",
    "shop_id": "<your-printify-shop-id>"
  },
  "shop_identifier": "<your-printify-shop-name>",
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
  "webhook_url": "https://api.algovoi.com/webhooks/printify/{tenant_id}",
  "webhook_secret": "...",
  "preferred_network": "algorand_mainnet"
}
```

---

## Step 4 — Register the webhook in Printify

Register the webhook using the Printify API with your stored API token:

```http
POST https://api.printify.com/v1/shops/{shop_id}/webhooks
Authorization: Bearer <printify-api-token>
Content-Type: application/json

{
  "topic": "order:created",
  "url": "https://api.algovoi.com/webhooks/printify/{tenant_id}",
  "secret": "<webhook_secret from Step 3>"
}
```

> AlgoVoi verifies every inbound webhook using HMAC-SHA256 against the `x-pfy-signature` header.
> Mismatched secrets will be rejected with HTTP 401.

---

## Payment flow for merchants

Once connected, every new Printify order triggers AlgoVoi to:

1. Parse the incoming `order:created` event and retrieve the production cost from the Printify API (`GET /orders/{id}`)
2. Create a hosted checkout link valid for **30 minutes**
3. Display the invoice amount in USDC (or aUSDC) with a QR code and wallet link
4. On successful on-chain confirmation:
   - AlgoVoi calls `POST /orders/{id}/shipments` to release the order to the assigned print provider
   - TX ID is recorded against the order in AlgoVoi

If the checkout link expires before payment, AlgoVoi will issue a fresh link on the next qualifying webhook event.

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
| Order not dispatched to print provider | On-chain payment not yet confirmed, or shipment call failed — check that the API token is valid and the shop ID matches |
| Payment link expired | Merchant took longer than 30 minutes — cancel and recreate the Printify order to trigger a fresh `order:created` webhook |
| HTTP 401 from Printify API | API token revoked or expired — generate a new token in Printify → My account → Connections |
| Wrong shop receiving webhooks | `shop_id` in credentials does not match the shop where orders are being created — update the integration credentials |

---

## Supported networks

| Network | Asset | Notes |
|---------|-------|-------|
| `algorand_mainnet` | USDC (ASA 31566704) | Requires ASA opt-in on payout wallet |
| `voi_mainnet` | aUSDC (ARC200 app ID 311051) | |
| `algorand_testnet` | Test USDC | For integration testing only |
| `voi_testnet` | Test aUSDC | For integration testing only |
