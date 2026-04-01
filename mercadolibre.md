# Mercado Libre Integration — AlgoVoi Tenant Services

Accept **USDC on Algorand** and **aUSDC on VOI** for Mercado Libre orders via AlgoVoi.

> **Regional marketplace.** Mercado Libre is the leading e-commerce marketplace in Latin America, operating across Argentina, Brazil, Mexico, Colombia, Chile, and other LATAM countries.

---

## How it works

```
Mercado Libre order placed → payment confirmed
        ↓
Mercado Libre fires orders_v2 notification to AlgoVoi webhook
        ↓
AlgoVoi verifies x-signature → fetches order via GET /orders/{order_id}
        ↓
AlgoVoi creates a hosted checkout link (USDC or aUSDC)
        ↓
Checkout URL returned — share with buyer via Mercado Libre messaging
        ↓
Buyer pays on-chain
        ↓
AlgoVoi verifies transaction on-chain
        ↓
AlgoVoi updates order via Mercado Libre API
```

---

## Prerequisites

- An active AlgoVoi tenant account
- A Mercado Libre seller account
- An application registered at [developers.mercadolibre.com](https://developers.mercadolibre.com)
- OAuth2 access token with `read_orders` and `write_orders` scopes

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

## Step 2 — Register a Mercado Libre application

1. Go to [developers.mercadolibre.com](https://developers.mercadolibre.com) and sign in
2. Click **Create application**
3. Set the **Redirect URI** to your AlgoVoi callback URL (shown in your tenant dashboard)
4. Complete the OAuth2 Authorization Code flow to obtain an access token and refresh token:
   - Redirect the user to `https://auth.mercadolibre.com.ar/authorization?response_type=code&client_id={app_id}&redirect_uri={redirect_uri}`
     (replace `.com.ar` with the country-specific domain, e.g. `.com.mx` for Mexico, `.com.br` for Brazil)
   - Exchange the code at `https://api.mercadolibre.com/oauth/token` with `grant_type=authorization_code`
5. Copy the **App ID (client_id)**, **Client Secret**, **Access Token**, and **Refresh Token**

---

## Step 3 — Connect the integration

```http
POST /internal/integrations/{tenant_id}/mercadolibre
Authorization: Bearer <admin-key>
Content-Type: application/json

{
  "credentials": {
    "client_id": "<mercadolibre-app-id>",
    "client_secret": "<mercadolibre-client-secret>",
    "access_token": "<oauth2-access-token>",
    "refresh_token": "<oauth2-refresh-token>"
  },
  "shop_identifier": "<your-mercadolibre-seller-id>",
  "base_currency": "BRL",
  "preferred_network": "algorand_mainnet"
}
```

**`preferred_network`** — which chain to settle payments on:

| Value | Settles in |
|-------|-----------|
| `algorand_mainnet` | USDC on Algorand |
| Webhook → checkout link | `voi_mainnet` (WAD (ARC200 app ID 47138068)) | Pass |

The response includes a `webhook_secret` and a `webhook_url`.

---

## Step 4 — Register the webhook

Subscribe to order notifications for your application:

```http
POST https://api.mercadolibre.com/applications/{app_id}/webhooks
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "url": "<webhook_url from Step 3>",
  "topic": "orders_v2"
}
```

Also subscribe to `payments` if you need payment status events:

```http
{
  "url": "<webhook_url from Step 3>",
  "topic": "payments"
}
```

### Webhook signature verification

Mercado Libre signs each webhook delivery with an `x-signature` header using HMAC-SHA256 and your `client_secret`. AlgoVoi verifies this signature automatically. Payloads that fail verification are rejected.

---

## Order webhook payload

When an order event fires, AlgoVoi receives a notification:

```json
{
  "resource": "/orders/1234567890",
  "user_id": 123456789,
  "topic": "orders_v2",
  "application_id": 987654321,
  "attempts": 1,
  "sent": "2024-01-15T10:30:00.000Z",
  "received": "2024-01-15T10:30:00.100Z"
}
```

AlgoVoi then fetches the full order:

```http
GET https://api.mercadolibre.com/orders/1234567890
Authorization: Bearer <access_token>
```

---

## Troubleshooting

| Symptom | Likely cause |
|---------|-------------|
| `x-signature` mismatch | `client_secret` incorrect in credentials |
| HTTP 401 on API calls | Access token expired — AlgoVoi will refresh automatically |
| HTTP 403 on order fetch | OAuth token lacks required scopes — re-authorise |
| Webhooks not arriving | Subscription not created or topic incorrect — check Mercado Libre Developer Portal |
| HTTP 422 "No network config" | Network config missing for `preferred_network` |
| Wrong country auth URL | Use the country-specific auth domain (e.g. `auth.mercadolibre.com.br`) for the seller's country |

---

---

## Live test status

Confirmed end-to-end on **2026-04-01** against `api1.ilovechicken.co.uk`:

| Test | Network | Result |
|------|---------|--------|
| Webhook → checkout link | `algorand_mainnet` (USDC (ASA 31566704)) | Pass |

Signature verified and checkout link generated. Asset: USDC (ASA 31566704).

## Supported networks

| Network | Asset | Notes |
|---------|-------|-------|
| `algorand_mainnet` | USDC (ASA 31566704) | Requires ASA opt-in on payout wallet |
| Webhook → checkout link | `voi_mainnet` (WAD (ARC200 app ID 47138068)) | Pass | |
| `algorand_testnet` | Test USDC | For integration testing only |
| `voi_testnet` | Test aUSDC | For integration testing only |

## Supported countries

| Country | Auth domain |
|---------|------------|
| Argentina | `auth.mercadolibre.com.ar` |
| Brazil | `auth.mercadolibre.com.br` |
| Mexico | `auth.mercadolibre.com.mx` |
| Colombia | `auth.mercadolibre.com.co` |
| Chile | `auth.mercadolibre.cl` |
| Peru | `auth.mercadolibre.com.pe` |
| Other LATAM | See [Mercado Libre Developers](https://developers.mercadolibre.com) |
