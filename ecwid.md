# Ecwid Integration — AlgoVoi Tenant Services

Accept **USDC on Algorand** and **aUSDC on VOI** as payment in your Ecwid store via AlgoVoi.

---

## How it works

```
Customer places an Ecwid order
            ↓
Ecwid fires a webhook (new_order event)
            ↓
AlgoVoi verifies HMAC-SHA256 signature → parses order
            ↓
AlgoVoi creates a hosted checkout link (USDC or aUSDC)
            ↓
Customer pays on-chain
            ↓
AlgoVoi verifies the transaction on-chain
            ↓
Ecwid order marked as paid with TX ID in order comments
```

---

## Prerequisites

- An active AlgoVoi tenant account
- An Ecwid store on **Business** plan or higher (required for the Ecwid REST API and webhooks)
- An Ecwid **Store ID** and **Secret Token** (from the Ecwid control panel)

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

## Step 2 — Get your Ecwid API credentials

1. In your Ecwid control panel go to **Apps → My Apps → Ecwid API**
2. Note your **Store ID**
3. Copy your **Secret Token** (used for both API calls and webhook signing)

> Alternatively, create a custom app at [developers.ecwid.com](https://developers.ecwid.com) and complete the OAuth flow to obtain a token with `read_store_profile read_orders update_orders` scopes.

---

## Step 3 — Connect the integration

```http
POST /internal/integrations/{tenant_id}/ecwid
Authorization: Bearer <admin-key>
Content-Type: application/json

{
  "credentials": {
    "store_id": "<ecwid-store-id>",
    "secret_token": "<ecwid-secret-token>"
  },
  "shop_identifier": "<ecwid-store-id>",
  "base_currency": "USD",
  "preferred_network": "algorand_mainnet"
}
```

The response includes a `webhook_secret` and a `webhook_url`.

---

## Step 4 — Register the webhook

Register your AlgoVoi endpoint via the Ecwid REST API:

```http
POST https://app.ecwid.com/api/v3/{store_id}/webhooks
Authorization: Bearer <secret_token>
Content-Type: application/json

{
  "url": "<webhook_url from Step 3>",
  "event": "order.created",
  "secret": "<webhook_secret from Step 3>"
}
```

Ecwid signs webhook requests with HMAC-SHA256. The signature is in the `X-Ecwid-Webhook-Signature` header (base64-encoded).

---

## Payment flow for your customers

Once connected, every new Ecwid order triggers AlgoVoi to:

1. Create a hosted checkout link valid for **30 minutes**
2. Display the USDC (or aUSDC) amount with a QR code and wallet link
3. On successful on-chain confirmation:
   - Ecwid order payment status set to **PAID**
   - TX ID added as a private order comment

---

## Troubleshooting

| Symptom | Likely cause |
|---------|-------------|
| HTTP 401 on webhook | Signature mismatch — check `webhook_secret` matches the secret used at registration |
| HTTP 422 "No network config" | Network config missing for `preferred_network` |
| Order not updating | Token lacks `update_orders` scope or has expired |
| Webhook not firing | Ecwid Business plan required; check app webhook registration |

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
| `order.created` webhook -> checkout link | `algorand_mainnet` (USDC (ASA 31566704)) | Pass |
| Webhook → checkout link | `voi_mainnet` (WAD (ARC200 app ID 47138068)) | Pass |
| Webhook → checkout link | `hedera_mainnet` (USDC (token 0.0.456858)) | Pass |
| Webhook → checkout link | `stellar_mainnet` (USDC (Circle)) | Pass |

Signature: `HMAC-SHA256` base64 in `X-Ecwid-Webhook-Signature`. Amount field: `data.total` (float, major units).
