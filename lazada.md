# Lazada Integration — AlgoVoi Tenant Services

Accept **USDC on Algorand** and **aUSDC on VOI** for Lazada orders via AlgoVoi.

---

## Coverage

Lazada operates across **6 countries** in Southeast Asia: Malaysia, Thailand, Philippines, Singapore, Indonesia, and Vietnam. A single AlgoVoi integration covers all Lazada regional storefronts under the same seller account.

---

## Important: Lazada payment model

Lazada processes all consumer checkout payments internally. AlgoVoi's Lazada integration targets:

- **B2B / supplier invoicing** — receive order push notifications and issue a crypto payment request to a supplier or fulfilment partner
- **Seller-initiated settlement** — settle platform fees or inter-company invoices in USDC/aUSDC
- **Operator-initiated flows** — your own backend posts order data directly to AlgoVoi (bypass mode)

---

## How it works

```
Lazada order placed → Lazada Open Platform push notification fired
        ↓
AlgoVoi receives + verifies HMAC-SHA256 signature → parses order
        ↓
AlgoVoi creates a hosted checkout link (USDC or aUSDC)
        ↓
Counterparty pays on-chain
        ↓
AlgoVoi verifies transaction on-chain
        ↓
Lazada order status updated with AlgoVoi TX reference
```

---

## Prerequisites

- An active AlgoVoi tenant account
- A Lazada seller account
- A Lazada Open Platform app registered at [open.lazada.com](https://open.lazada.com)
- OAuth access token per seller (obtained via the Lazada OAuth flow)

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

## Step 2 — Get Lazada API credentials

1. Register an app at the [Lazada Open Platform developer portal](https://open.lazada.com)
2. Note your **App Key** and **App Secret** from the app detail page
3. Complete the OAuth flow to obtain an **Access Token** for your seller account:
   - Direct the seller to `https://auth.lazada.com/oauth/authorize?response_type=code&client_id=<app_key>&redirect_uri=<redirect_uri>`
   - Exchange the returned code at `https://auth.lazada.com/rest?method=lazada.seller.token.create` using your App Key and App Secret
4. Store the **Access Token** and **Refresh Token** — AlgoVoi handles token refresh automatically

> For regional storefronts, the base URL variant may differ (e.g. `https://api.lazada.com.my/rest` for Malaysia). AlgoVoi normalises all requests through `https://api.lazada.com/rest` by default. Contact support if you require a region-specific base URL override.

> All Lazada API requests are signed with **HMAC-SHA256** over the concatenated sorted parameters. AlgoVoi handles request signing automatically using your App Secret.

---

## Step 3 — Connect the integration

```http
POST /internal/integrations/{tenant_id}/lazada
Authorization: Bearer <admin-key>
Content-Type: application/json

{
  "credentials": {
    "app_key": "<lazada-app-key>",
    "app_secret": "<lazada-app-secret>",
    "access_token": "<oauth-access-token>"
  },
  "shop_identifier": "<your-lazada-seller-id>",
  "base_currency": "USD",
  "preferred_network": "algorand_mainnet"
}
```

**`preferred_network`** — which chain to settle payments on:

| Value | Settles in |
|-------|-----------|
| `algorand_mainnet` | USDC on Algorand |
| Webhook → checkout link | `voi_mainnet` (WAD (ARC200 app ID 47138068)) | Skip |

The response includes a `webhook_secret` and a `webhook_url`. Save both — the secret is shown once.

```json
{
  "webhook_url": "https://api.algovoi.com/webhooks/lazada/{tenant_id}",
  "webhook_secret": "...",
  "preferred_network": "algorand_mainnet"
}
```

---

## Step 4 — Register push notifications in Lazada Open Platform

1. Log in to the [Lazada Open Platform app console](https://open.lazada.com)
2. Open your app and navigate to **Push Notifications** (or **Event Subscription**)
3. Enter the `webhook_url` from Step 3 as the notification endpoint
4. Subscribe to the **Order** event type (covers new order creation)
5. Save the configuration

Lazada signs push notifications with HMAC-SHA256. The signature is included in the request headers and AlgoVoi verifies it automatically using the `webhook_secret` from Step 3.

> If the Lazada console asks for a verification token or challenge, use the `webhook_secret` from Step 3. AlgoVoi handles the challenge-response automatically.

### Option B — Direct operator POST (bypass mode)

POST order data directly from your backend with `Authorization: Bearer <webhook_secret>`.

---

## Payment flow

Once connected:

1. AlgoVoi receives the Lazada push notification for a new order
2. A hosted checkout link is created (valid 30 minutes)
3. Share the checkout URL with your supplier or fulfilment partner
4. Counterparty pays in USDC or aUSDC on-chain
5. AlgoVoi verifies the transaction and updates the Lazada order status with the AlgoVoi TX ID as the reference

---

## Troubleshooting

| Symptom | Likely cause |
|---------|-------------|
| HTTP 401 on webhook | Signature mismatch — reconnect the integration to rotate the secret |
| HTTP 422 "No network config" | Network config missing for `preferred_network` |
| Push notifications not arriving | Endpoint not saved correctly in the Lazada Open Platform console — re-register |
| OAuth token expired | Lazada access tokens expire — use the stored refresh token or reconnect the integration |
| Order status update failing | App Secret may have changed or access token lacks order write permissions |
| Payment link expired | Counterparty took longer than 30 minutes — re-trigger manually via operator POST |

---

---

## Live test status

Confirmed end-to-end on **2026-04-01** against `api1.ilovechicken.co.uk`:

| Test | Network | Result |
|------|---------|--------|
| Webhook → checkout link | `algorand_mainnet` (USDC (ASA 31566704)) | Skip |

Webhook signature verified on `algorand_mainnet`; full order-amount fetch requires real platform API credentials.

## Supported networks

| Network | Asset | Notes |
|---------|-------|-------|
| `algorand_mainnet` | USDC (ASA 31566704) | Requires ASA opt-in on payout wallet |
| Webhook → checkout link | `voi_mainnet` (WAD (ARC200 app ID 47138068)) | Skip | |
| `algorand_testnet` | Test USDC | For integration testing only |
| `voi_testnet` | Test aUSDC | For integration testing only |
