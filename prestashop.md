# PrestaShop Integration — AlgoVoi Tenant Services

Accept **USDC on Algorand** and **aUSDC on VOI** as payment in your PrestaShop store via AlgoVoi.

---

## How it works

```
Customer places a PrestaShop order
            ↓
Webhook module POSTs order to AlgoVoi → verifies Bearer token
            ↓
AlgoVoi creates a hosted checkout link (USDC or aUSDC)
            ↓
Customer pays on-chain
            ↓
AlgoVoi verifies the transaction on-chain
            ↓
PrestaShop order state updated to Payment Accepted + TX ID added
```

> PrestaShop has no native webhook system. A third-party module is required
> to dispatch order events to AlgoVoi.

---

## Prerequisites

- An active AlgoVoi tenant account
- A PrestaShop store (1.7+ or 8.x recommended)
- A PrestaShop WebService API key with Orders access
- A webhook module (see Step 3)

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

## Step 2 — Create a PrestaShop WebService API key

1. In PrestaShop Admin go to **Advanced Parameters → Webservice**
2. Enable the webservice if not already active
3. Click **Add new webservice key**
4. Set a description (e.g. "AlgoVoi") and generate a key
5. Under **Permissions**, enable `GET` and `PUT` for:
   - `orders`
   - `order_histories`
6. Save and copy the API key

---

## Step 3 — Connect the integration

```http
POST /internal/integrations/{tenant_id}/prestashop
Authorization: Bearer <admin-key>
Content-Type: application/json

{
  "credentials": {
    "base_url": "https://mystore.com",
    "api_key": "<prestashop-webservice-api-key>",
    "paid_state_id": 2
  },
  "shop_identifier": "mystore.com",
  "base_currency": "EUR",
  "preferred_network": "algorand_mainnet"
}
```

**`paid_state_id`** — the PrestaShop order state ID for "Payment Accepted". Default is `2`. Check your store's order states at **Orders → Statuses** if you've customised them.

The response includes a `webhook_secret` and a `webhook_url`.

---

## Step 4 — Install a webhook module

PrestaShop requires a module to send order webhooks. Options:

- **Knowband Webhook** — configurable event-based HTTP POSTs
- **Prestahero Webhook** — supports `actionValidateOrder`
- **Custom module** — implement an observer on `actionValidateOrder` hook

Configure the module:
- **Event**: `actionValidateOrder` (order placed and validated)
- **Endpoint URL**: the `webhook_url` from Step 3
- **Authentication**: set `Authorization` header to `Bearer <webhook_secret>`
- **Body format**: full order object (JSON)

---

## Payment flow for your customers

Once connected, every new PrestaShop order triggers AlgoVoi to:

1. Create a hosted checkout link valid for **30 minutes**
2. Display the amount in USDC (or aUSDC) with a QR code and wallet link
3. On successful on-chain confirmation:
   - PrestaShop order state updated to **Payment Accepted** (state ID 2)
   - Order history entry added with TX ID

---

## Troubleshooting

| Symptom | Likely cause |
|---------|-------------|
| HTTP 401 on webhook | Bearer token mismatch — reconnect to rotate the secret |
| HTTP 422 "No network config" | Network config missing for `preferred_network` |
| Order state not updating | API key lacks `PUT` permission for orders |
| Wrong paid state | Set `paid_state_id` to match your store's "Payment Accepted" state ID |

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
| Order webhook -> checkout link | `algorand_mainnet` (USDC ASA 31566704) | Pass |

Authentication uses a Bearer token (`Authorization: Bearer <webhook_secret>`) -- PrestaShop modules do not sign payloads. Amount field: `order.total_paid` (float, major units).
