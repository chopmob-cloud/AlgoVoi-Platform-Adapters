# Shopware Integration — AlgoVoi Tenant Services

Accept **USDC on Algorand** and **aUSDC on VOI** as payment in your Shopware store via AlgoVoi.

---

## How it works

```
Customer places a Shopware order
            ↓
Shopware fires a webhook (checkout.order.placed event)
            ↓
AlgoVoi verifies sha256 HMAC signature → parses order
            ↓
AlgoVoi creates a hosted checkout link (USDC or aUSDC)
            ↓
Customer pays on-chain
            ↓
AlgoVoi verifies the transaction on-chain
            ↓
Shopware order transaction status updated to "Paid" with TX ID in notes
```

---

## Prerequisites

- An active AlgoVoi tenant account
- Shopware 6.x (self-hosted or Shopware cloud)
- A Shopware **Integration** (OAuth client) with `write_orders` permissions
- Admin API access enabled

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
  "preferred_asset_id": "311051",
  "preferred_asset_decimals": 6
}
```

---

## Step 2 — Create a Shopware Integration

1. In your Shopware Admin go to **Settings → System → Integrations**
2. Click **Add integration**
3. Give it a name (e.g. "AlgoVoi") and enable **Administrator** role or a custom role with order write access
4. Copy the **Access Key ID** and **Secret Access Key** — the secret is shown once

---

## Step 3 — Connect the integration

```http
POST /internal/integrations/{tenant_id}/shopware
Authorization: Bearer <admin-key>
Content-Type: application/json

{
  "credentials": {
    "access_key_id": "<shopware-integration-access-key-id>",
    "secret_access_key": "<shopware-integration-secret>",
    "store_url": "https://yourstore.com"
  },
  "shop_identifier": "yourstore.com",
  "base_currency": "EUR",
  "preferred_network": "algorand_mainnet"
}
```

The response includes a `webhook_secret` and a `webhook_url`.

---

## Step 4 — Register the webhook in Shopware

Register your AlgoVoi endpoint via the Shopware Admin API. First obtain a bearer token:

```http
POST https://yourstore.com/api/oauth/token
Content-Type: application/json

{
  "grant_type": "client_credentials",
  "client_id": "<access_key_id>",
  "client_secret": "<secret_access_key>"
}
```

Then register the webhook:

```http
POST https://yourstore.com/api/webhook
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "name": "algovoi-order-webhook",
  "url": "<webhook_url from Step 3>",
  "eventName": "checkout.order.placed",
  "active": true,
  "errorCount": 0
}
```

Shopware signs all webhook requests with a `shopware-shop-signature` header containing `hex(HMAC-SHA256(webhook_secret, raw_body))`. AlgoVoi verifies this automatically.

---

## Payment flow for your customers

Once connected, every new Shopware order triggers AlgoVoi to:

1. Create a hosted checkout link valid for **30 minutes**
2. Display the USDC (or aUSDC) amount with a QR code and wallet link
3. On successful on-chain confirmation:
   - Shopware order transaction status set to **Paid**
   - TX ID added as a custom field on the order

---

## Troubleshooting

| Symptom | Likely cause |
|---------|-------------|
| HTTP 401 on webhook | `shopware-shop-signature` mismatch — check `webhook_secret` |
| HTTP 422 "No network config" | Network config missing for `preferred_network` |
| OAuth token failing | Integration credentials incorrect or secret not copied at creation time |
| Order not updating | Integration role lacks `write_orders` permission |
| Webhook not active | Set `active: true` and check Shopware webhook event log |

---

## Supported networks

| Network | Asset | Notes |
|---------|-------|-------|
| `algorand_mainnet` | USDC (ASA 31566704) | Requires ASA opt-in on payout wallet |
| `voi_mainnet` | aUSDC (ARC200 app ID 311051) | |
| `algorand_testnet` | Test USDC | For integration testing only |
| `voi_testnet` | Test aUSDC | For integration testing only |
