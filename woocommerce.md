# WooCommerce Integration — AlgoVoi Tenant Services

Accept **USDC on Algorand** and **aUSDC on VOI** as payment in your WooCommerce store via AlgoVoi.

---

## How it works

```
Customer places a WooCommerce order
            ↓
AlgoVoi receives webhook → verifies signature → parses order
            ↓
AlgoVoi creates a hosted checkout link (USDC or aUSDC)
            ↓
Customer pays on-chain
            ↓
AlgoVoi verifies the transaction on-chain
            ↓
WooCommerce order updated to 'processing' + TX ID added as order note
```

---

## Prerequisites

- An active AlgoVoi tenant account
- A WordPress site running WooCommerce
- WooCommerce REST API credentials (consumer key + secret) with `read/write` access to orders

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

## Step 2 — Generate WooCommerce REST API credentials

1. In your WordPress Admin go to **WooCommerce → Settings → Advanced → REST API**
2. Click **Add key**
3. Set **Description** (e.g. "AlgoVoi"), **User**, and **Permissions** to `Read/Write`
4. Click **Generate API key**
5. Copy the **Consumer key** (`ck_...`) and **Consumer secret** (`cs_...`) — these are shown once

> Your WooCommerce site must be served over **HTTPS**. Basic auth credentials are sent in plaintext over HTTP.

---

## Step 3 — Connect the integration

```http
POST /internal/integrations/{tenant_id}/woocommerce
Authorization: Bearer <admin-key>
Content-Type: application/json

{
  "credentials": {
    "site_url": "https://mystore.com",
    "consumer_key": "ck_xxxxxxxxxxxxxxxxxxxx",
    "consumer_secret": "cs_xxxxxxxxxxxxxxxxxxxx"
  },
  "shop_identifier": "mystore.com",
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
  "webhook_url": "https://api.algovoi.com/webhooks/woocommerce/{tenant_id}",
  "webhook_secret": "...",
  "preferred_network": "algorand_mainnet"
}
```

---

## Step 4 — Register the webhook in WooCommerce

1. In your WordPress Admin go to **WooCommerce → Settings → Advanced → Webhooks**
2. Click **Add webhook**
3. Set:
   - **Name**: AlgoVoi
   - **Status**: Active
   - **Topic**: Order created
   - **Delivery URL**: the `webhook_url` from Step 3
   - **Secret**: the `webhook_secret` from Step 3
   - **API version**: WP REST API Integration v3
4. Click **Save webhook**

> AlgoVoi verifies every inbound webhook using HMAC-SHA256 against the `X-WC-Webhook-Signature` header. Mismatched secrets will be rejected with HTTP 401.

---

## Payment flow for your customers

Once connected, every new WooCommerce order triggers AlgoVoi to:

1. Create a hosted checkout link valid for **30 minutes**
2. Display the amount in USDC (or aUSDC) with a QR code and wallet link
3. On successful on-chain confirmation:
   - WooCommerce order status updated to **processing**
   - TX ID recorded as an internal order note

The customer is redirected back to the WooCommerce order received page after payment.

---

## Tenant limits to check

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
| Order status not updating | Consumer key/secret lacks `write` permission, or site not on HTTPS |
| Payment link expired | Customer took longer than 30 minutes — a new order webhook will create a fresh link |
| `Skipping order.updated` in logs | Normal — AlgoVoi only processes `pending` or `on-hold` orders from update events |

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
| `order.created` webhook → checkout link | `algorand_mainnet` (USDC ASA 31566704) | ✅ Pass |

Signature verification uses `HMAC-SHA256` over the raw request body, base64-encoded, in the `X-Wc-Webhook-Signature` header.
