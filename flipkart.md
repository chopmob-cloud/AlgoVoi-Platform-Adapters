# Flipkart Integration — AlgoVoi Tenant Services

Accept **USDC on Algorand** and **aUSDC on VOI** for Flipkart orders via AlgoVoi.

---

## Important: Flipkart payment model

Flipkart processes all consumer-facing payments internally via Super.money and FPay. AlgoVoi's Flipkart integration targets:

- **B2B / supplier invoicing** — receive order push notifications and issue a crypto payment request to a supplier or fulfilment partner
- **Seller-initiated settlement** — settle platform fees or inter-company invoices in USDC/aUSDC
- **Operator-initiated flows** — your own backend posts order data directly to AlgoVoi (bypass mode)

> This is not a replacement for Flipkart's native checkout. It is a supplementary settlement layer for sellers and suppliers who want on-chain stablecoin payments.

---

## How it works

```
Flipkart order placed → Order Management Notification Service push event
        ↓
AlgoVoi receives notification → verifies HMAC signature → parses order
        ↓
AlgoVoi creates a hosted checkout link (USDC or aUSDC)
        ↓
Counterparty pays on-chain
        ↓
AlgoVoi verifies transaction on-chain
        ↓
Flipkart shipment dispatched via API with AlgoVoi TX reference
```

---

## Prerequisites

- An active AlgoVoi tenant account
- A Flipkart seller account registered in the [Flipkart Seller Hub](https://seller.flipkart.com)
- A self-access app registered under **Manage Profile → Developer Access** (provides App ID and App Secret)
- Order Management Notification Service (OMNS) subscription configured in Seller Hub

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

## Step 2 — Get Flipkart API credentials

1. Log in to the [Flipkart Seller Hub](https://seller.flipkart.com)
2. Navigate to **Manage Profile → Developer Access**
3. Register a **self-access app** if you have not already done so
4. Copy the **App ID** and **App Secret** from the app detail page

To obtain an OAuth2 access token, POST to the token endpoint using Basic Auth with your App ID and App Secret (base64-encoded `appId:appSecret`):

```http
POST https://api.flipkart.net/oauth-service/oauth/token
Authorization: Basic <base64(appId:appSecret)>
Content-Type: application/x-www-form-urlencoded

grant_type=client_credentials&scope=Seller_Api
```

The response contains an `access_token` valid for approximately 60 days. AlgoVoi handles token refresh automatically once credentials are provided.

> The token endpoint uses the `client_credentials` grant. No user redirect is required for self-access apps.

---

## Step 3 — Connect the integration

```http
POST /internal/integrations/{tenant_id}/flipkart
Authorization: Bearer <admin-key>
Content-Type: application/json

{
  "credentials": {
    "app_id": "<flipkart-app-id>",
    "app_secret": "<flipkart-app-secret>"
  },
  "shop_identifier": "<your-flipkart-seller-id>",
  "base_currency": "INR",
  "preferred_network": "algorand_mainnet"
}
```

**`preferred_network`** — which chain to settle payments on:

| Value | Settles in |
|-------|-----------|
| `algorand_mainnet` | USDC (ASA 31566704) |
| `voi_mainnet` | WAD (ARC200 app ID 47138068) |

The response includes a `webhook_secret` and a `webhook_url`. Save both — the secret is shown once.

```json
{
  "webhook_url": "https://api.algovoi.com/webhooks/flipkart/{tenant_id}",
  "webhook_secret": "...",
  "preferred_network": "algorand_mainnet"
}
```

> AlgoVoi uses the App ID and App Secret to obtain and refresh OAuth2 tokens from Flipkart automatically.

---

## Step 4 — Subscribe to OMNS push notifications

Register the AlgoVoi webhook URL as the delivery endpoint in the Flipkart Order Management Notification Service:

1. Log in to the [Flipkart Seller Hub](https://seller.flipkart.com)
2. Navigate to **Orders → Order Notifications** (or OMNS settings)
3. Set the **Notification URL** to the `webhook_url` returned in Step 3
4. Subscribe to the **`shipment_created`** event to be notified when new orders are ready to process
5. Save the configuration

Flipkart signs push notifications — AlgoVoi verifies the signature automatically using the `webhook_secret` from Step 3.

### Option B — Direct operator POST (bypass mode)

POST order data directly from your backend with `Authorization: Bearer <webhook_secret>`.

---

## Payment flow

Once connected:

1. AlgoVoi receives the Flipkart OMNS push notification for a new shipment
2. Order details are fetched via `GET https://api.flipkart.net/sellers/v2/orders/` using the `orderItemIds` from the notification
3. A hosted checkout link is created (valid 30 minutes)
4. Share the checkout URL with your supplier or fulfilment partner
5. Counterparty pays in USDC or aUSDC on-chain
6. AlgoVoi verifies the transaction and dispatches the shipment via `POST https://api.flipkart.net/sellers/v3/shipments/dispatch` with the AlgoVoi TX ID as the reference

---

## Troubleshooting

| Symptom | Likely cause |
|---------|-------------|
| HTTP 401 on webhook | Signature mismatch — reconnect the integration to rotate the secret |
| HTTP 401 on token exchange | App ID or App Secret incorrect — re-check credentials in Seller Hub |
| HTTP 422 "No network config" | Network config missing for `preferred_network` |
| OMNS notifications not arriving | Notification URL not saved in Seller Hub, or OMNS subscription not active |
| Shipment dispatch failing | OAuth token may have expired — AlgoVoi will retry; reconnect if the error persists |
| Order fetch returning 404 | `orderItemIds` in the push payload are invalid or the order has been cancelled |
| Payment link expired | Counterparty took longer than 30 minutes — re-trigger manually via operator POST |

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
| `voi_mainnet` | WAD (ARC200 app ID 47138068) | | |
| `algorand_testnet` | Test USDC | For integration testing only |
| `voi_testnet` | Test aUSDC | For integration testing only |
