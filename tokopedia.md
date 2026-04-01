# Tokopedia Integration — AlgoVoi Tenant Services

Accept **USDC on Algorand** and **aUSDC on VOI** for Tokopedia orders via AlgoVoi.

---

## How it works

```
Tokopedia new order event → webhook pushed to AlgoVoi callback URL
        ↓
AlgoVoi verifies request → parses order from Fulfillment Service API
        ↓
AlgoVoi creates a hosted checkout link (USDC or aUSDC)
        ↓
Seller shares checkout link with buyer (Tokopedia chat / external channel)
        ↓
Buyer pays on-chain
        ↓
AlgoVoi verifies transaction on-chain
        ↓
Order status updated via Tokopedia Fulfillment Service API
```

No storefront code changes needed — AlgoVoi operates through the Tokopedia Fulfillment Service API and your registered callback URL.

---

## Prerequisites

- An active AlgoVoi tenant account
- A Tokopedia seller account registered as a Fulfillment Service partner
- A **Client ID**, **Client Secret**, and **FS ID** (Fulfillment Service ID) from the Tokopedia developer portal
- A publicly reachable HTTPS URL to use as your webhook callback

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

## Step 2 — Get Tokopedia API credentials

1. Log in to [developer.tokopedia.com](https://developer.tokopedia.com) or the [Tokopedia Partner Portal](https://partner.tokopedia.com)
2. Create or open your Fulfillment Service application
3. Copy your **Client ID** and **Client Secret** from the application detail page
4. Copy your **FS ID** (Fulfillment Service ID) — this is assigned when your fulfillment service is approved and is required on all order API calls

> The FS ID is distinct from your seller ID. If you have not yet registered a Fulfillment Service, contact Tokopedia Partner support to complete onboarding.

---

## Step 3 — Connect the integration

```http
POST /internal/integrations/{tenant_id}/tokopedia
Authorization: Bearer <admin-key>
Content-Type: application/json

{
  "credentials": {
    "client_id": "<tokopedia-client-id>",
    "client_secret": "<tokopedia-client-secret>",
    "fs_id": "<fulfillment-service-id>"
  },
  "shop_identifier": "<your-tokopedia-shop-id>",
  "base_currency": "IDR",
  "preferred_network": "algorand_mainnet"
}
```

**`preferred_network`** — which chain to settle payments on:

| Value | Settles in |
|-------|-----------|
| `algorand_mainnet` | USDC on Algorand |
| Webhook → checkout link | `voi_mainnet` (WAD (ARC200 app ID 47138068)) | Pass |

The response includes a `webhook_secret` and a `webhook_url`. Save both — the secret is shown once.

```json
{
  "webhook_url": "https://api.algovoi.com/webhooks/tokopedia/{tenant_id}",
  "webhook_secret": "...",
  "preferred_network": "algorand_mainnet"
}
```

> AlgoVoi uses the Client ID and Client Secret to obtain OAuth2 access tokens from
> `POST https://accounts.tokopedia.com/token` using the `client_credentials` grant.
> Tokens are refreshed automatically.

---

## Step 4 — Register the webhook callback in Tokopedia

Register the AlgoVoi webhook URL as the callback for new order events in the Tokopedia Fulfillment Service portal:

1. In the Tokopedia Partner Portal, open your Fulfillment Service application
2. Navigate to **Webhook / Callback Settings**
3. Set the **Callback URL** to the `webhook_url` returned in Step 3
4. Subscribe to the **`new_order`** event (or equivalent order notification event shown in your portal)
5. Save the configuration

Tokopedia will push a notification to the callback URL each time a new order is assigned to your Fulfillment Service. AlgoVoi processes the payload and fetches full order detail from the Fulfillment Service API using the FS ID.

---

## Payment flow for your customers

Once connected, every new order notification triggers AlgoVoi to:

1. Fetch the full order from `https://fs.tokopedia.net` using the FS ID
2. Create a hosted checkout link valid for **30 minutes**
3. Display the amount in USDC (or aUSDC) with a QR code and wallet link
4. On successful on-chain confirmation, update the order status via the Tokopedia Fulfillment Service API

> Tokopedia does not natively display external payment links to buyers in the checkout flow.
> Share the AlgoVoi checkout URL with your buyer via Tokopedia chat or your preferred channel.

---

## Troubleshooting

| Symptom | Likely cause |
|---------|-------------|
| HTTP 401 on token exchange | Client ID or Client Secret incorrect — check credentials in Step 2 |
| HTTP 422 "No network config" | Network config missing or no payout address set for `preferred_network` |
| Webhook not received | Callback URL not registered in Tokopedia partner portal, or FS ID not yet approved |
| Order fetch returning 403 | FS ID does not match the seller or the order is not assigned to your fulfillment service |
| Payment link expired | Customer took longer than 30 minutes — a new order webhook will create a fresh link |

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
