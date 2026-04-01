# BigCommerce Integration — AlgoVoi Tenant Services

Accept **USDC on Algorand** and **aUSDC on VOI** as payment in your BigCommerce store via AlgoVoi.

---

## How it works

```
Customer places a BigCommerce order
            ↓
BigCommerce sends webhook (order ID only)
            ↓
AlgoVoi verifies X-Bc-Signature → fetches full order via BigCommerce API
            ↓
AlgoVoi creates a hosted checkout link (USDC or aUSDC)
            ↓
Customer pays on-chain
            ↓
AlgoVoi verifies the transaction on-chain
            ↓
BigCommerce order set to Completed + merchant message added with TX ID
```

> BigCommerce webhooks carry only the order ID. AlgoVoi automatically fetches
> the full order details using your API credentials.

---

## Prerequisites

- An active AlgoVoi tenant account
- A BigCommerce store
- A BigCommerce API account with `Orders` read/write scope

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
  "preferred_asset_id": "302190",
  "preferred_asset_decimals": 6
}
```

---

## Step 2 — Create a BigCommerce API account

1. In BigCommerce Admin go to **Settings → API → API Accounts**
2. Click **Create API Account → Create V2/V3 API Token**
3. Set a name (e.g. "AlgoVoi") and enable these OAuth scopes:
   - **Orders**: `modify`
   - **Order Transactions**: `read-only`
4. Click **Save** and copy the **Access Token** and **Store Hash** (from the API Path URL)

---

## Step 3 — Connect the integration

```http
POST /internal/integrations/{tenant_id}/bigcommerce
Authorization: Bearer <admin-key>
Content-Type: application/json

{
  "credentials": {
    "store_hash": "abc123",
    "access_token": "<bigcommerce-access-token>"
  },
  "shop_identifier": "mystore.mybigcommerce.com",
  "base_currency": "USD",
  "preferred_network": "algorand_mainnet"
}
```

The response includes a `webhook_secret` and a `webhook_url`.

---

## Step 4 — Register the webhook in BigCommerce

BigCommerce webhooks are registered via the API (not the admin UI):

```http
POST https://api.bigcommerce.com/stores/{store_hash}/v3/hooks
X-Auth-Token: <access_token>
Content-Type: application/json

{
  "scope": "store/order/created",
  "destination": "<webhook_url from Step 3>",
  "is_active": true,
  "headers": {
    "X-Bc-Signature-Key": "<webhook_secret from Step 3>"
  }
}
```

> BigCommerce does not natively sign webhook payloads. The `headers` field lets you inject a custom header that BigCommerce echoes verbatim on every delivery. AlgoVoi reads `X-Bc-Signature-Key` from the incoming request and compares it to the stored `webhook_secret` to authenticate the delivery.

---

## Payment flow for your customers

Once connected, every new BigCommerce order triggers AlgoVoi to:

1. Fetch the full order from BigCommerce API
2. Create a hosted checkout link valid for **30 minutes**
3. Display the amount in USDC (or aUSDC) with a QR code and wallet link
4. On successful on-chain confirmation:
   - BigCommerce order status set to **Completed**
   - Merchant message added with TX ID

---

## Troubleshooting

| Symptom | Likely cause |
|---------|-------------|
| HTTP 401 on webhook | `X-Bc-Signature-Key` mismatch — check `webhook_secret` matches the value set at webhook registration |
| HTTP 422 "No network config" | Network config missing for `preferred_network` |
| Order fetch failed | `access_token` lacks Orders read scope |
| Order not completing | `access_token` lacks Orders modify scope |

---

## Supported networks

| Network | Asset | Notes |
|---------|-------|-------|
| Webhook → checkout link | Webhook → checkout link | `algorand_mainnet` (USDC (ASA 31566704)) | Skip | Requires ASA opt-in on payout wallet |
| Webhook → checkout link | `voi_mainnet` (WAD (ARC200 app ID 47138068)) | Skip | |
| `algorand_testnet` | Test USDC | For integration testing only |
| `voi_testnet` | Test aUSDC | For integration testing only |

---

## Live test status

Partially confirmed on **2026-03-31** against `api1.ilovechicken.co.uk`:

| Test | Network | Result |
|------|---------|--------|
| Webhook signature verification | n/a | Pass |
| Full order flow | Webhook → checkout link | Webhook → checkout link | `algorand_mainnet` (USDC (ASA 31566704)) | Skip |

BigCommerce webhooks carry the order ID only -- AlgoVoi makes a follow-up `GET /v2/orders/{id}` call to fetch the amount. Full end-to-end flow requires a valid `store_hash` and `access_token`. Signature: `HMAC-SHA256` base64 in `X-Bc-Signature`.
