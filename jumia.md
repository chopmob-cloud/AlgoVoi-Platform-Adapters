# Jumia Integration — AlgoVoi Tenant Services

Accept **USDC on Algorand** and **aUSDC on VOI** for Jumia orders via AlgoVoi.

> **Regional marketplace.** Jumia is Africa's leading e-commerce platform, operating across Nigeria, Kenya, Egypt, Ghana, Senegal, Ivory Coast, Uganda, Tanzania, Morocco, and Tunisia. Each country has its own Jumia SellerCenter domain.

---

## How it works

```
Jumia order placed
        ↓
Jumia fires Order.Created webhook to AlgoVoi
        ↓
AlgoVoi receives notification → fetches full order via GetOrders API
        ↓
AlgoVoi creates a hosted checkout link (USDC or aUSDC)
        ↓
Checkout URL returned — share with buyer via Jumia messaging or email
        ↓
Buyer pays on-chain
        ↓
AlgoVoi verifies transaction on-chain
        ↓
AlgoVoi updates order status via UpdateOrderStatus API
```

---

## Prerequisites

- An active AlgoVoi tenant account
- A Jumia seller account on the relevant country SellerCenter
- API access enabled via your Jumia account manager
- OAuth2 client credentials from the Jumia SellerCenter API portal

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

---

## Step 2 — Get Jumia API credentials

1. Sign in to your country's Jumia SellerCenter (e.g. [sellercenter.jumia.com.ng](https://sellercenter.jumia.com.ng) for Nigeria)
2. Contact your Jumia account manager to request API access
3. Once enabled, obtain your **Client ID** and **Client Secret** from the SellerCenter API settings
4. Note your **country domain** (e.g. `jumia.com.ng`, `jumia.co.ke`, `jumia.com.eg`)

---

## Step 3 — Connect the integration

```http
POST /internal/integrations/{tenant_id}/jumia
Authorization: Bearer <admin-key>
Content-Type: application/json

{
  "credentials": {
    "client_id": "<jumia-client-id>",
    "client_secret": "<jumia-client-secret>",
    "country_domain": "jumia.com.ng"
  },
  "shop_identifier": "<your-jumia-seller-id>",
  "base_currency": "NGN",
  "preferred_network": "algorand_mainnet"
}
```

**`preferred_network`** — which chain to settle payments on:

| Value | Settles in |
|-------|-----------|
| `algorand_mainnet` | USDC on Algorand |
| Webhook → checkout link | `voi_mainnet` (WAD (ARC200 app ID 47138068)) | Skip |

AlgoVoi's base URL for all Jumia API calls is:

```
https://sellerapi.sellercenter.{country_domain}/
```

The response includes a `webhook_url` to register with the Jumia webhook system.

---

## Step 4 — Register the webhook

AlgoVoi registers a webhook for order events via the Jumia SellerCenter API:

```http
POST https://sellerapi.sellercenter.{country_domain}/webhook
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "Url": "<webhook_url from Step 3>",
  "Events": ["Order.Created", "Order.StatusChanged"]
}
```

Jumia will deliver webhook notifications with up to 30 days of retry with exponential backoff. The notification payload is a lightweight event — AlgoVoi fetches full order details after receipt.

---

## Order webhook payload

When an order is created, AlgoVoi receives:

```json
{
  "Event": "Order.Created",
  "OrderId": "123456789",
  "Timestamp": "2024-01-15T10:30:00Z"
}
```

AlgoVoi then fetches the full order:

```http
GET https://sellerapi.sellercenter.{country_domain}/orders?order_id=123456789
Authorization: Bearer <access_token>
```

---

## Payment flow for your customers

Once AlgoVoi receives and processes a new order:

1. A hosted checkout link is created (valid 30 minutes)
2. Share the checkout URL with your buyer via Jumia messages or email
3. Buyer pays in USDC or aUSDC on-chain
4. AlgoVoi verifies the transaction on-chain
5. AlgoVoi updates the order status:

```http
POST https://sellerapi.sellercenter.{country_domain}/orders/status
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "OrderId": "123456789",
  "Status": "ready_to_ship"
}
```

---

## Troubleshooting

| Symptom | Likely cause |
|---------|-------------|
| HTTP 401 on API calls | Access token expired — AlgoVoi will refresh automatically |
| API access denied | API not enabled on your seller account — contact your Jumia account manager |
| Webhooks not arriving | Webhook not registered or country domain incorrect |
| HTTP 422 "No network config" | Network config missing for `preferred_network` |
| Payment link expired | Buyer took longer than 30 minutes — share a new link via the AlgoVoi dashboard |
| Wrong base URL | Ensure `country_domain` matches your Jumia country (e.g. `jumia.co.ke` for Kenya) |

---

## Supported countries and domains

| Country | Domain |
|---------|--------|
| Nigeria | `jumia.com.ng` |
| Kenya | `jumia.co.ke` |
| Egypt | `jumia.com.eg` |
| Ghana | `jumia.com.gh` |
| Senegal | `jumia.sn` |
| Ivory Coast | `jumia.ci` |
| Uganda | `jumia.ug` |
| Tanzania | `jumia.co.tz` |
| Morocco | `jumia.ma` |
| Tunisia | `jumia.com.tn` |

---

---

## Live test status

Confirmed end-to-end on **2026-04-01** against `api1.ilovechicken.co.uk`:

| Test | Network | Result |
|------|---------|--------|
| Webhook → checkout link | `algorand_mainnet` (USDC (ASA 31566704)) | Skip |

Cannot auto-test: Documentation only — no webhook adapter implemented.

## Supported networks

| Network | Asset | Notes |
|---------|-------|-------|
| `algorand_mainnet` | USDC (ASA 31566704) | Requires ASA opt-in on payout wallet |
| Webhook → checkout link | `voi_mainnet` (WAD (ARC200 app ID 47138068)) | Skip | |
| `algorand_testnet` | Test USDC | For integration testing only |
| `voi_testnet` | Test aUSDC | For integration testing only |
