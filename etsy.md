# Etsy Integration — AlgoVoi Tenant Services

Accept **USDC on Algorand** and **aUSDC on VOI** for Etsy orders via AlgoVoi.

---

## Important: Etsy Payments and crypto settlement

Etsy Payments is required for most transactions on the platform. AlgoVoi's Etsy integration operates as an **additional payment option** for custom commissions and international orders where sellers have agreed to accept on-chain stablecoin payment outside the standard Etsy Payments checkout.

> AlgoVoi does not replace Etsy Payments. It is a supplementary flow — buyers settle via a hosted checkout link delivered after the order is placed.

---

## How it works

```
Etsy order placed → order.paid webhook fired
        ↓
AlgoVoi receives webhook → verifies HMAC-SHA256 signature → parses order
        ↓
AlgoVoi creates a hosted checkout link (USDC or aUSDC)
        ↓
Seller shares checkout link with buyer (Etsy message / email)
        ↓
Buyer pays on-chain
        ↓
AlgoVoi verifies transaction on-chain
        ↓
Etsy order updated with AlgoVoi TX reference via API
```

---

## Prerequisites

- An active AlgoVoi tenant account
- An Etsy seller account
- An app registered at [etsy.com/developers](https://www.etsy.com/developers) with OAuth2 configured
- OAuth2 scopes: `orders_r orders_w listings_r shops_r`

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
  "preferred_asset_id": "311051",
  "preferred_asset_decimals": 6
}
```

> ARC200 app ID `311051` is aUSDC on VOI mainnet.

---

## Step 2 — Get Etsy API credentials

1. Go to [etsy.com/developers](https://www.etsy.com/developers) and sign in
2. Click **Your Apps → Create a New App**
3. Fill in the app name and description, then copy the **Keystring** (this is your API key)
4. Configure the **Redirect URI** to your AlgoVoi callback URL (shown in your tenant dashboard)
5. Complete the **OAuth2 Authorization Code + PKCE** flow to obtain an access token:
   - Redirect the seller to `https://www.etsy.com/oauth/connect?response_type=code&client_id=<keystring>&redirect_uri=<redirect_uri>&scope=orders_r%20orders_w%20listings_r%20shops_r&state=<state>&code_challenge=<pkce_challenge>&code_challenge_method=S256`
   - Exchange the returned code at `https://openapi.etsy.com/v3/public/oauth/token` using your keystring and PKCE verifier
6. Copy the **access token** and **refresh token**

> AlgoVoi handles token refresh automatically once the initial access token and refresh token are stored.

---

## Step 3 — Connect the integration

```http
POST /internal/integrations/{tenant_id}/etsy
Authorization: Bearer <admin-key>
Content-Type: application/json

{
  "credentials": {
    "keystring": "<etsy-api-keystring>",
    "access_token": "<oauth2-access-token>",
    "refresh_token": "<oauth2-refresh-token>"
  },
  "shop_identifier": "<your-etsy-shop-id>",
  "base_currency": "USD",
  "preferred_network": "algorand_mainnet"
}
```

**`preferred_network`** — which chain to settle payments on:

| Value | Settles in |
|-------|-----------|
| `algorand_mainnet` | USDC on Algorand |
| `voi_mainnet` | aUSDC on VOI |

The response includes a `webhook_secret` and a `webhook_url`. Save both — the secret is shown once.

```json
{
  "webhook_url": "https://api.algovoi.com/webhooks/etsy/{tenant_id}",
  "webhook_secret": "...",
  "preferred_network": "algorand_mainnet"
}
```

---

## Step 4 — Register the webhook in Etsy

Register the AlgoVoi endpoint as the event delivery URL for your shop using the Etsy v3 API:

```http
POST https://openapi.etsy.com/v3/application/webhooks
Authorization: Bearer <access_token>
x-api-key: <keystring>
Content-Type: application/json

{
  "url": "<webhook_url from Step 3>",
  "event": "order.paid"
}
```

Etsy also supports `order.shipped` and `order.canceled` — subscribe to these if your integration needs to track fulfilment status.

Etsy signs webhook payloads using **HMAC-SHA256**. The signature is sent in the `webhook-signature` header alongside `webhook-id` and `webhook-timestamp`. AlgoVoi verifies this signature automatically using the `webhook_secret` from Step 3. Payloads that fail verification are rejected with HTTP 401.

> If you need to rotate the secret, reconnect the integration (Step 3) to generate a new `webhook_secret`, then re-register the webhook endpoint.

---

## Payment flow for your customers

Once connected:

1. AlgoVoi receives the `order.paid` webhook from Etsy
2. Full order detail is fetched via `GET https://openapi.etsy.com/v3/application/shops/{shopId}/receipts/{receiptId}`
3. A hosted checkout link is created (valid 30 minutes)
4. The checkout URL is returned in the webhook response — share it with your buyer via Etsy Messages or email
5. Buyer pays in USDC or aUSDC on-chain
6. AlgoVoi verifies the transaction on-chain and updates the order via the Etsy API with the AlgoVoi TX ID as a reference

> Etsy does not expose a direct payment update endpoint for third-party payment methods. AlgoVoi records the TX reference against the order using the available order notes or fulfilment fields.

---

## Troubleshooting

| Symptom | Likely cause |
|---------|-------------|
| HTTP 401 on webhook | `webhook-signature` mismatch — reconnect the integration to rotate the secret |
| HTTP 403 on order fetch | OAuth token lacks `orders_r` scope — re-authorise with the correct scopes |
| HTTP 422 "No network config" | Network config missing for `preferred_network` |
| Webhooks not received | Webhook not registered against your shop, or Etsy is retrying a failed delivery — check your AlgoVoi webhook logs |
| OAuth token rejected | Access token expired — AlgoVoi will attempt a refresh; reconnect if the error persists |
| Order update failing | OAuth token lacks `orders_w` scope — re-authorise with the correct scopes |
| Payment link expired | Buyer took longer than 30 minutes — share a new link manually via the AlgoVoi dashboard |

---

## Supported networks

| Network | Asset | Notes |
|---------|-------|-------|
| `algorand_mainnet` | USDC (ASA 31566704) | Requires ASA opt-in on payout wallet |
| `voi_mainnet` | aUSDC (ARC200 app ID 311051) | |
| `algorand_testnet` | Test USDC | For integration testing only |
| `voi_testnet` | Test aUSDC | For integration testing only |
