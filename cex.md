# CeX (Computer Exchange) Integration — AlgoVoi Tenant Services

Accept **USDC on Algorand** and **aUSDC on VOI** for CeX Marketplace orders via AlgoVoi.

---

## Important: CeX Marketplace payment model

CeX (Computer Exchange) operates as a managed resale marketplace — CeX handles buyer payments internally. AlgoVoi's CeX integration targets:

- **Seller-initiated crypto invoicing** — receive a CeX order notification, AlgoVoi creates a payment link for B2B settlement or supplier payment
- **Operator-initiated flows** — your own backend posts order data directly to AlgoVoi (bypass mode)

---

## How it works

```
CeX order placed → CeX Seller API webhook fired
            ↓
AlgoVoi receives + verifies X-CeX-Signature HMAC → parses order
            ↓
AlgoVoi creates a hosted checkout link (USDC or aUSDC)
            ↓
Counterparty pays on-chain
            ↓
AlgoVoi verifies transaction on-chain
            ↓
CeX order updated with AlgoVoi TX reference
```

---

## Prerequisites

- An active AlgoVoi tenant account
- A CeX Marketplace seller account with API access
- A CeX API key and signing secret from the CeX Seller Hub

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
  "preferred_asset_id": "311051",
  "preferred_asset_decimals": 6
}
```

---

## Step 2 — Get CeX API credentials

1. Log in to the [CeX Seller Hub](https://sellers.cex.io)
2. Navigate to **Settings → API Access**
3. Generate an **API Key** and note the associated **Signing Secret**
4. Ensure the API key has order read and write permissions

---

## Step 3 — Connect the integration

```http
POST /internal/integrations/{tenant_id}/cex
Authorization: Bearer <admin-key>
Content-Type: application/json

{
  "credentials": {
    "api_key": "<cex-api-key>",
    "signing_secret": "<cex-signing-secret>"
  },
  "shop_identifier": "<your-cex-seller-id>",
  "base_currency": "GBP",
  "preferred_network": "algorand_mainnet"
}
```

The response includes a `webhook_secret` and a `webhook_url`.

---

## Step 4 — Register the webhook

Register your AlgoVoi webhook endpoint in the CeX Seller Hub:

1. Go to **Settings → Webhooks** in the CeX Seller Hub
2. Add a new webhook pointing to your `webhook_url` from Step 3
3. Select the **Order Created** event type
4. Save — CeX will begin signing requests with `X-CeX-Signature`

### Signature verification

CeX signs webhook payloads using HMAC-SHA256 with your `signing_secret`. The hex digest is delivered in the `X-CeX-Signature` header:

```
X-CeX-Signature: <hex(HMAC-SHA256(signing_secret, raw_body))>
```

AlgoVoi verifies this signature automatically on receipt.

### Option B — Direct operator POST (bypass mode)

POST order data directly from your backend with `Authorization: Bearer <webhook_secret>`.

---

## Webhook payload structure

AlgoVoi processes CeX order created events. Relevant fields:

```json
{
  "event": "order.created",
  "order": {
    "order_id": "CEX-123456",
    "created_at": "2026-03-01T12:00:00Z",
    "currency": "GBP",
    "total_amount": "49.99",
    "items": [
      {
        "box_id": "BX123456",
        "description": "Apple iPhone 13 128GB",
        "quantity": 1,
        "unit_price": "49.99"
      }
    ]
  }
}
```

---

## Payment flow

Once connected:

1. AlgoVoi receives the `order.created` webhook
2. A hosted checkout link is created (valid 30 minutes)
3. Share the checkout URL with the counterparty via CeX messaging or email
4. Counterparty pays in USDC or aUSDC on-chain
5. AlgoVoi verifies the transaction and records the TX ID against the CeX order

---

## Troubleshooting

| Symptom | Likely cause |
|---------|-------------|
| HTTP 401 on webhook | `X-CeX-Signature` mismatch — check signing secret or re-register |
| HTTP 422 "No network config" | Network config missing for `preferred_network` |
| Order not updating | API key lacks write permissions or has expired |

---

## Supported networks

| Network | Asset | Notes |
|---------|-------|-------|
| `algorand_mainnet` | USDC (ASA 31566704) | Requires ASA opt-in on payout wallet |
| `voi_mainnet` | aUSDC (ARC200 app ID 311051) | |
| `algorand_testnet` | Test USDC | For integration testing only |
| `voi_testnet` | Test aUSDC | For integration testing only |
