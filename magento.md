# Magento Integration — AlgoVoi Tenant Services

Accept **USDC on Algorand** and **aUSDC on VOI** as payment in your Magento store via AlgoVoi.

Both **Magento 1** and **Magento 2** are supported as separate integrations.

---

## How it works

```
Customer places a Magento order
            ↓
AlgoVoi receives webhook → verifies Bearer token → parses order
            ↓
AlgoVoi creates a hosted checkout link (USDC or aUSDC)
            ↓
Customer pays on-chain
            ↓
AlgoVoi verifies the transaction on-chain
            ↓
Magento order updated to 'processing' + TX ID recorded
```

---

## Prerequisites

- An active AlgoVoi tenant account
- A Magento 1.x or 2.x store
- Admin API access (see version-specific steps below)

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

## Magento 2

### Step 2 — Generate an integration access token

1. In your Magento 2 Admin go to **System → Extensions → Integrations**
2. Click **Add New Integration**
3. Give it a name (e.g. "AlgoVoi") and set your admin password
4. Under **API** tab, grant access to **Sales → Orders**
5. Click **Save** then **Activate** → **Allow**
6. Copy the **Access Token**

### Step 3 — Connect the integration

Use platform `magento`:

```http
POST /internal/integrations/{tenant_id}/magento
Authorization: Bearer <admin-key>
Content-Type: application/json

{
  "credentials": {
    "base_url": "https://mystore.com",
    "access_token": "<magento2-integration-access-token>"
  },
  "shop_identifier": "mystore.com",
  "base_currency": "USD",
  "preferred_network": "algorand_mainnet"
}
```

The response includes a `webhook_secret` and a `webhook_url`. Save both — the secret is shown once.

### Step 4 — Register the webhook in Magento 2

Magento 2 doesn't send webhooks natively for older versions. Use one of:

- **Adobe Commerce Webhooks** (built-in from 2.4.4+) — configure under **System → Webhooks**
- **Mageplaza Webhook extension** — available for all 2.x versions

Configure the webhook:
- **Hook name**: AlgoVoi Order
- **Event**: `sales_order_place_after`
- **Endpoint URL**: the `webhook_url` from Step 3
- **Authentication**: set `Authorization` header to `Bearer <webhook_secret>`
- **Body**: full order object (JSON)

---

## Magento 1

### Step 2 — Create an API user

1. In your Magento 1 Admin go to **System → Web Services → Users**
2. Click **Add New User**
3. Set a username and API key, assign the **Administrators** role (or a custom role with `sales_order` access)
4. Save and note the username and API key

### Step 3 — Connect the integration

Use platform `magento1`:

```http
POST /internal/integrations/{tenant_id}/magento1
Authorization: Bearer <admin-key>
Content-Type: application/json

{
  "credentials": {
    "base_url": "https://mystore.com",
    "api_user": "<magento1-api-username>",
    "api_key": "<magento1-api-key>"
  },
  "shop_identifier": "mystore.com",
  "base_currency": "GBP",
  "preferred_network": "algorand_mainnet"
}
```

The response includes a `webhook_secret` and a `webhook_url`.

### Step 4 — Install a webhook extension for Magento 1

Magento 1 has no native webhooks. Use one of:

- **Mageplaza Webhook for Magento 1** — sends `sales_order_place_after` events
- **Custom module** — dispatch an HTTP POST on `sales_order_place_after` observer

Configure the webhook:
- **Event**: `sales_order_place_after`
- **Endpoint URL**: the `webhook_url` from Step 3
- **Authentication**: set `Authorization` header to `Bearer <webhook_secret>`
- **Body**: full order object (JSON)

### Magento 1: Mark order as paid via XML-RPC

After AlgoVoi confirms the on-chain payment, it calls back to your Magento 1
store to update the order status using the Magento 1 XML-RPC API:

```
POST https://yourstore.com/api/xmlrpc/
```

```xml
<methodCall>
  <methodName>call</methodName>
  <params>
    <param><value><string><SESSION_ID></string></value></param>
    <param><value><string>sales_order.addComment</string></value></param>
    <param><value><array><data>
      <value><string><ORDER_INCREMENT_ID></string></value>
      <value><string>processing</string></value>
      <value><string>AlgoVoi TX: <TX_ID></string></value>
      <value><boolean>1</boolean></value>
    </data></array></value></param>
  </params>
</methodCall>
```

AlgoVoi uses the `api_user` and `api_key` from Step 3 to authenticate this
call. Ensure the XML-RPC endpoint is publicly accessible and not blocked by
your firewall or `.htaccess`.

---

## Payment flow for your customers

Once connected, every new Magento order triggers AlgoVoi to:

1. Create a hosted checkout link valid for **30 minutes**
2. Display the amount in USDC (or aUSDC) with a QR code and wallet link
3. On successful on-chain confirmation:
   - Magento order status updated to **processing**
   - TX ID recorded as an order comment (customer-visible)

---

## Troubleshooting

| Symptom | Likely cause |
|---------|-------------|
| HTTP 401 on webhook | `webhook_secret` / Bearer token mismatch — reconnect to rotate |
| HTTP 422 "No network config" | Network config missing or no payout address set for `preferred_network` |
| M2: order not updating | Integration token lacks Sales/Orders write access |
| M1: `notify_paid` failed | XML-RPC URL unreachable, or `api_user`/`api_key` incorrect |
| Payment link expired | Customer took longer than 30 minutes — a new order webhook creates a fresh link |

---

## Supported networks

| Network | Asset | Notes |
|---------|-------|-------|
| `algorand_mainnet` | USDC (ASA 31566704) | Requires ASA opt-in on payout wallet |
| `voi_mainnet` | WAD (ARC200 app ID 47138068) |  |
| `algorand_testnet` | Test USDC | For integration testing only |
| `voi_testnet` | Test aUSDC | For integration testing only |

---

## Live test status

Confirmed end-to-end on **2026-04-14** against `api1.ilovechicken.co.uk`:

| Test | Network | Result |
|------|---------|--------|
| Webhook → checkout link | `algorand_mainnet` (USDC (ASA 31566704)) | Pass |
| Webhook → checkout link | `voi_mainnet` (WAD (ARC200 app ID 47138068)) | Pass |
| Webhook → checkout link | `hedera_mainnet` (USDC (token 0.0.456858)) | Pass |
| Webhook → checkout link | `stellar_mainnet` (USDC (Circle)) | Pass |

Authentication uses a Bearer token (`Authorization: Bearer <webhook_secret>`) -- Magento does not sign payloads. The `webhook_secret` is auto-generated by AlgoVoi on integration creation.
