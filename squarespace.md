# Squarespace Commerce Integration — AlgoVoi Tenant Services

Accept **USDC on Algorand** and **aUSDC on VOI** as payment in your Squarespace store via AlgoVoi.

---

## How it works

```
Customer places a Squarespace order
            ↓
Squarespace sends webhook with Squarespace-Signature header
            ↓
AlgoVoi verifies HMAC-SHA256 signature → parses order
            ↓
AlgoVoi creates a hosted checkout link (USDC or aUSDC)
            ↓
Customer pays on-chain
            ↓
AlgoVoi verifies the transaction on-chain
            ↓
Squarespace order marked as fulfilled with TX ID as tracking reference
```

> Squarespace Commerce API does not have a "mark as paid" endpoint. AlgoVoi
> marks the order as **fulfilled** upon payment confirmation, which closes the
> order and triggers the customer fulfilment notification.

---

## Prerequisites

- An active AlgoVoi tenant account
- A Squarespace site on a **Commerce** plan (Basic or Advanced)
- A Squarespace API key with Orders access

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

## Step 2 — Generate a Squarespace API key

1. In your Squarespace site go to **Settings → Developer Tools → API Keys**
2. Click **Generate Key**
3. Give it a name (e.g. "AlgoVoi") and enable:
   - **Orders**: `Read` and `Modify`
4. Copy the API key — it is shown once

---

## Step 3 — Connect the integration

```http
POST /internal/integrations/{tenant_id}/squarespace
Authorization: Bearer <admin-key>
Content-Type: application/json

{
  "credentials": {
    "api_key": "<squarespace-api-key>"
  },
  "shop_identifier": "mysite.squarespace.com",
  "base_currency": "USD",
  "preferred_network": "algorand_mainnet"
}
```

The response includes a `webhook_secret` and a `webhook_url`.

---

## Step 4 — Register the webhook in Squarespace

Squarespace webhooks are registered via the API:

```http
POST https://api.squarespace.com/1.0/webhook_subscriptions
Authorization: Bearer <api_key>
Content-Type: application/json

{
  "endpointUrl": "<webhook_url from Step 3>",
  "topics": ["order.create"]
}
```

Save the `secret` from the response — this is used to verify incoming webhooks. Pass it as the `webhook_secret` when connecting the integration.

> The Squarespace webhook secret is hex-encoded. AlgoVoi handles the hex
> decoding automatically during signature verification.

---

## Payment flow for your customers

Once connected, every new Squarespace order triggers AlgoVoi to:

1. Create a hosted checkout link valid for **30 minutes**
2. Display the amount in USDC (or aUSDC) with a QR code and wallet link
3. On successful on-chain confirmation:
   - Squarespace order marked as **Fulfilled**
   - TX ID recorded as the fulfilment tracking reference
   - Customer fulfilment notification sent by Squarespace

---

## Troubleshooting

| Symptom | Likely cause |
|---------|-------------|
| HTTP 401 on webhook | Signature mismatch — ensure `webhook_secret` is the hex secret from the subscription response |
| HTTP 422 "No network config" | Network config missing for `preferred_network` |
| Order not fulfilling | API key lacks Orders modify permission |
| Unexpected topic error | Only `order.create` events are processed — other topics are ignored |

---

## Supported networks

| Network | Asset | Notes |
|---------|-------|-------|
| `algorand_mainnet` | USDC (ASA 31566704) | Requires ASA opt-in on payout wallet |
| `voi_mainnet` | WAD (ARC200 app ID 47138068) |  |
| `algorand_testnet` | Test USDC | For integration testing only |
| `voi_testnet` | Test aUSDC | For integration testing only |

---

## Live test status

Confirmed end-to-end on **2026-03-31** against `api1.ilovechicken.co.uk`:

| Test | Network | Result |
|------|---------|--------|
| `order.create` webhook -> checkout link | `algorand_mainnet` (USDC (ASA 31566704)) | Pass |
| Webhook → checkout link | `voi_mainnet` (WAD (ARC200 app ID 47138068)) | Pass |
| Webhook → checkout link | `hedera_mainnet` (USDC (token 0.0.456858)) | Pass |
| Webhook → checkout link | `stellar_mainnet` (USDC (Circle)) | Pass |

Signature: `HMAC-SHA256` hex digest in `Squarespace-Signature`. Squarespace production provides a hex-encoded signing key; AlgoVoi accepts both hex-encoded and raw string secrets.
