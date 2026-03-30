# OpenCart Integration — AlgoVoi Tenant Services

Accept **USDC on Algorand** and **aUSDC on VOI** as payment in your OpenCart store via AlgoVoi.

---

## How it works

```
Customer places an OpenCart order
            ↓
OpenCart fires a webhook via the AlgoVoi extension
            ↓
AlgoVoi verifies HMAC-SHA256 signature → parses order
            ↓
AlgoVoi creates a hosted checkout link (USDC or aUSDC)
            ↓
Customer pays on-chain
            ↓
AlgoVoi verifies the transaction on-chain
            ↓
OpenCart order status updated to "Processing" with TX ID in history
```

---

## Prerequisites

- An active AlgoVoi tenant account
- OpenCart 3.x or 4.x
- OpenCart REST API enabled (Admin → Extensions → APIs)
- Your OpenCart admin URL and an API key with order management permissions

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

## Step 2 — Enable the OpenCart REST API

1. In your OpenCart Admin go to **System → Users → API**
2. Click **Add New**
3. Give the key a name (e.g. "AlgoVoi") and set Status to **Enabled**
4. Copy the generated **API Key**
5. Add your server IP to the **IP Addresses** allowlist

---

## Step 3 — Connect the integration

```http
POST /internal/integrations/{tenant_id}/opencart
Authorization: Bearer <admin-key>
Content-Type: application/json

{
  "credentials": {
    "api_key": "<opencart-api-key>",
    "store_url": "https://yourstore.com"
  },
  "shop_identifier": "yourstore.com",
  "base_currency": "GBP",
  "preferred_network": "algorand_mainnet"
}
```

The response includes a `webhook_secret` and a `webhook_url`.

---

## Step 4 — Configure order notifications

OpenCart does not have native outbound webhooks. Use one of the following approaches:

### Option A — AlgoVoi OpenCart Extension (recommended)

Install the AlgoVoi payment extension from the OpenCart Marketplace. It automatically POSTs new orders to your `webhook_url` with an `X-AlgoVoi-Signature` header:

```
X-AlgoVoi-Signature: <hex(HMAC-SHA256(webhook_secret, raw_body))>
```

1. Download and install the **AlgoVoi Payments** extension from the OpenCart Marketplace
2. Go to **Extensions → Payments → AlgoVoi**
3. Enter your `webhook_url` and `webhook_secret`
4. Enable the extension

### Option B — Direct operator POST (bypass mode)

POST order data directly from your custom code or a third-party automation tool with `Authorization: Bearer <webhook_secret>`.

---

## Payment flow for your customers

Once connected:

1. AlgoVoi receives the new order notification
2. A hosted checkout link is created (valid 30 minutes)
3. Customer is redirected to the checkout page to pay in USDC or aUSDC
4. On successful on-chain confirmation:
   - OpenCart order status updated to **Processing**
   - TX ID added to order history comments

---

## Troubleshooting

| Symptom | Likely cause |
|---------|-------------|
| HTTP 401 on webhook | Signature mismatch — check `webhook_secret` in the extension settings |
| HTTP 422 "No network config" | Network config missing for `preferred_network` |
| Order not updating | API key lacks write permissions or IP not allowlisted |
| Extension not triggering | Check OpenCart extension is enabled and pointing to the correct `webhook_url` |

---

## Supported networks

| Network | Asset | Notes |
|---------|-------|-------|
| `algorand_mainnet` | USDC (ASA 31566704) | Requires ASA opt-in on payout wallet |
| `voi_mainnet` | aUSDC (ARC200 app ID 311051) | |
| `algorand_testnet` | Test USDC | For integration testing only |
| `voi_testnet` | Test aUSDC | For integration testing only |
