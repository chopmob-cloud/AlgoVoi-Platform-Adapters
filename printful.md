# Printful Integration — AlgoVoi Tenant Services

Pay your Printful production costs in **USDC on Algorand** or **aUSDC on VOI** via AlgoVoi.

---

## How it works

```
Merchant's customer places an order on their storefront
        ↓
Printful receives the fulfillment request
        ↓
AlgoVoi receives Printful webhook → verifies signature → parses order
        ↓
AlgoVoi creates a hosted checkout link (USDC or aUSDC) for the production invoice
        ↓
Merchant pays on-chain
        ↓
AlgoVoi verifies the transaction on-chain
        ↓
Printful order confirmed and sent to production
```

No code changes needed in your storefront — AlgoVoi handles everything via Printful webhooks.

> Printful is a fulfillment layer, not a marketplace. This integration lets you pay Printful production
> costs in USDC rather than fiat, eliminating card fees and FX conversion on every order.

---

## Prerequisites

- An active AlgoVoi tenant account
- A Printful account with at least one active store
- A Printful API key (generated in Printful Dashboard → Settings → API)

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
  "preferred_asset_id": "302190",
  "preferred_asset_decimals": 6
}
```

> ARC200 app ID `302190` is aUSDC on VOI mainnet.

---

## Step 2 — Generate a Printful API key

1. Log in to the **Printful Dashboard**
2. Go to **Settings → API**
3. Click **Create token**
4. Give it a name (e.g. "AlgoVoi") and copy the generated token — it is shown once

---

## Step 3 — Connect the integration

```http
POST /internal/integrations/{tenant_id}/printful
Authorization: Bearer <admin-key>
Content-Type: application/json

{
  "credentials": {
    "api_key": "<printful-api-key>"
  },
  "shop_identifier": "<your-printful-store-name>",
  "base_currency": "USD",
  "preferred_network": "algorand_mainnet"
}
```

**`preferred_network`** — which chain to settle payments on:

| Value | Settles in |
|-------|-----------|
| Webhook → checkout link | `algorand_mainnet` (USDC (ASA 31566704)) | Pass |
| Webhook → checkout link | `voi_mainnet` (WAD (ARC200 app ID 47138068)) | Pass |

The response includes a `webhook_secret` and a `webhook_url`. Save both — the secret is shown once.

```json
{
  "webhook_url": "https://api.algovoi.com/webhooks/printful/{tenant_id}",
  "webhook_secret": "...",
  "preferred_network": "algorand_mainnet"
}
```

---

## Step 4 — Register the webhook in Printful

Register the webhook using the Printful API with your stored API key:

```http
POST https://api.printful.com/webhooks
Authorization: Bearer <printful-api-key>
Content-Type: application/json

{
  "url": "https://api.algovoi.com/webhooks/printful/{tenant_id}",
  "types": ["order_created"],
  "params": {
    "secret": "<webhook_secret from Step 3>"
  }
}
```

> AlgoVoi verifies every inbound webhook using HMAC-SHA256 against the `x-pfy-signature` header.
> Mismatched secrets will be rejected with HTTP 401.

---

## Payment flow for merchants

Once connected, every new Printful order triggers AlgoVoi to:

1. Parse the incoming order and retrieve the production cost from the Printful API (`GET /orders/{id}`)
2. Create a hosted checkout link valid for **30 minutes**
3. Display the invoice amount in USDC (or aUSDC) with a QR code and wallet link
4. On successful on-chain confirmation:
   - AlgoVoi calls `POST /orders/{id}/confirm` to submit the order to Printful production
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
| Order not sent to production | On-chain payment not yet confirmed, or `POST /orders/{id}/confirm` failed — check API key permissions |
| Payment link expired | Merchant took longer than 30 minutes — cancel and recreate the Printful draft order to trigger a fresh webhook |
| HTTP 401 from Printful API | API key revoked or expired — generate a new token in Printful Dashboard → Settings → API |

---

---

## Live test status

Confirmed end-to-end on **2026-04-01** against `api1.ilovechicken.co.uk`:

| Test | Network | Result |
|------|---------|--------|
| Webhook → checkout link | Webhook → checkout link | `algorand_mainnet` (USDC (ASA 31566704)) | Pass |

Response 401: {'detail': 'Webhook signature invalid'}

## Supported networks

| Network | Asset | Notes |
|---------|-------|-------|
| Webhook → checkout link | `algorand_mainnet` (USDC (ASA 31566704)) | Pass | Requires ASA opt-in on payout wallet |
| Webhook → checkout link | `voi_mainnet` (WAD (ARC200 app ID 47138068)) | Pass | |
| `algorand_testnet` | Test USDC | For integration testing only |
| `voi_testnet` | Test aUSDC | For integration testing only |
