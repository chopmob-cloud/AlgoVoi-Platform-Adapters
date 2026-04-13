# Allegro Integration — AlgoVoi Tenant Services

Accept **USDC on Algorand** and **aUSDC on VOI** for Allegro orders via AlgoVoi.

> **Regional marketplace.** Allegro is the dominant e-commerce platform in Poland and operates across Central and Eastern Europe.

---

## How it works

Allegro does not support push webhooks. AlgoVoi polls the Allegro Order Events API to detect new orders.

```
AlgoVoi polls GET /order/events every N minutes
        ↓
New ORDER_CREATED event detected
        ↓
AlgoVoi fetches full order via GET /order/checkout-forms/{id}
        ↓
AlgoVoi creates a hosted checkout link (USDC or aUSDC)
        ↓
Checkout URL returned — share with buyer via Allegro messaging or email
        ↓
Buyer pays on-chain
        ↓
AlgoVoi verifies transaction on-chain
        ↓
AlgoVoi updates fulfillment status via PATCH /order/checkout-forms/{id}/fulfillment
```

---

## Prerequisites

- An active AlgoVoi tenant account
- An Allegro seller account
- An application registered at [apps.developer.allegro.pl](https://apps.developer.allegro.pl)
- OAuth2 scopes: `allegro:api:order:read allegro:api:order:write`

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

## Step 2 — Create an Allegro application

1. Go to [apps.developer.allegro.pl](https://apps.developer.allegro.pl) and sign in
2. Click **Create new application**
3. Select **Client Credentials** as the OAuth2 flow type
4. Request scopes: `allegro:api:order:read` and `allegro:api:order:write`
5. Copy the **Client ID** and **Client Secret**

---

## Step 3 — Connect the integration

```http
POST /internal/integrations/{tenant_id}/allegro
Authorization: Bearer <admin-key>
Content-Type: application/json

{
  "credentials": {
    "client_id": "<allegro-client-id>",
    "client_secret": "<allegro-client-secret>"
  },
  "shop_identifier": "<your-allegro-seller-id>",
  "base_currency": "PLN",
  "preferred_network": "algorand_mainnet"
}
```

**`preferred_network`** — which chain to settle payments on:

| Value | Settles in |
|-------|-----------|
| `algorand_mainnet` | USDC (ASA 31566704) |
| `voi_mainnet` | WAD (ARC200 app ID 47138068) |

AlgoVoi exchanges credentials for an access token automatically:

```http
POST https://allegro.pl/auth/oauth/token
Authorization: Basic <base64(client_id:client_secret)>
Content-Type: application/x-www-form-urlencoded

grant_type=client_credentials
```

---

## Step 4 — Order polling

AlgoVoi polls `GET /order/events` on your behalf using a cursor (`lastEventId`) to detect new orders:

```http
GET https://api.allegro.pl/order/events?type=ORDER_STATUS_CHANGED&from={last_event_id}
Authorization: Bearer <access_token>
Accept: application/vnd.allegro.public.v1+json
```

> The `Accept: application/vnd.allegro.public.v1+json` header is required for all Allegro API calls.

When a new order event is detected, AlgoVoi fetches the full order:

```http
GET https://api.allegro.pl/order/checkout-forms/{checkoutFormId}
Authorization: Bearer <access_token>
Accept: application/vnd.allegro.public.v1+json
```

The order response includes buyer details, line items, and total value. AlgoVoi uses this to generate a checkout link denominated in your `base_currency`.

> Allegro's order events API retains events for 24 hours and up to the last 1,000 events. AlgoVoi polls frequently enough to avoid missing events under normal load.

---

## Payment flow for your customers

Once AlgoVoi detects a new order:

1. A hosted checkout link is created (valid 30 minutes)
2. The checkout URL is returned — share it with your buyer via Allegro Messages or email
3. Buyer pays in USDC or aUSDC on-chain
4. AlgoVoi verifies the transaction on-chain
5. AlgoVoi updates the order fulfillment status:

```http
PATCH https://api.allegro.pl/order/checkout-forms/{checkoutFormId}/fulfillment
Authorization: Bearer <access_token>
Accept: application/vnd.allegro.public.v1+json
Content-Type: application/vnd.allegro.public.v1+json

{
  "status": "READY_FOR_PROCESSING",
  "shipmentSummary": {
    "lineItemsSent": "NONE"
  }
}
```

---

## Troubleshooting

| Symptom | Likely cause |
|---------|-------------|
| HTTP 401 on API calls | Access token expired — AlgoVoi will refresh automatically using client credentials |
| HTTP 403 on order fetch | `allegro:api:order:read` scope missing — re-register the application |
| HTTP 422 "No network config" | Network config missing for `preferred_network` |
| Orders not detected | Polling interval behind or event window exceeded — check AlgoVoi polling logs |
| Fulfillment update failing | `allegro:api:order:write` scope missing — re-register the application |
| Payment link expired | Buyer took longer than 30 minutes — share a new link via the AlgoVoi dashboard |
| Missing `Accept` header errors | Allegro requires `application/vnd.allegro.public.v1+json` on all requests |

---

---

## Live test status

Confirmed end-to-end on **2026-04-01** against `api1.ilovechicken.co.uk`:

| Test | Network | Result |
|------|---------|--------|
| Webhook → checkout link | `algorand_mainnet` (USDC (ASA 31566704)) | Pass |
| Webhook → checkout link | `voi_mainnet` (WAD (ARC200 app ID 47138068)) | Pass |
| Webhook → checkout link | `hedera_mainnet` (USDC (token 0.0.456858)) | Pass |
| Webhook → checkout link | `stellar_mainnet` (USDC (Circle)) | Pass |

Signature verified and checkout link generated. Asset: USDC (ASA 31566704).

## Supported networks

| Network | Asset | Notes |
|---------|-------|-------|
| `algorand_mainnet` | USDC (ASA 31566704) | Requires ASA opt-in on payout wallet |
| `voi_mainnet` | WAD (ARC200 app ID 47138068) |  |
| `algorand_testnet` | Test USDC | For integration testing only |
| `voi_testnet` | Test aUSDC | For integration testing only |
