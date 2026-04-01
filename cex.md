# CeX (Computer Exchange) Integration — AlgoVoi Tenant Services

Accept **USDC on Algorand** and **aUSDC on VOI** for CeX Marketplace orders via AlgoVoi.

---

## Important: CeX has no public Seller API

CeX (Computer Exchange) does not provide a public Seller API, webhook system,
or Seller Hub portal. The only public CeX API is a read-only catalogue API
(`wss2.cex.{cc}.webuy.io/v3`) for product lookups — it has no order management
or outbound events.

AlgoVoi's CeX integration operates in **bypass mode only**:

- Your backend (or a CeX trade notification email parser) POSTs order data
  directly to AlgoVoi with `Authorization: Bearer <tenant_token>`
- AlgoVoi creates a hosted checkout link which you share with the counterparty
  via CeX messaging or email

There is no automated webhook path.

---

## How it works

```
CeX order placed → you receive notification (email / polling)
            ↓
Your backend POSTs order data to AlgoVoi with Bearer token
            ↓
AlgoVoi creates a hosted checkout link (USDC or aUSDC)
            ↓
Counterparty pays on-chain
            ↓
AlgoVoi verifies transaction on-chain
            ↓
TX reference returned to your backend
```

---

## Prerequisites

- An active AlgoVoi tenant account
- A CeX Marketplace seller account

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

## Step 2 — Connect the integration

```http
POST /internal/integrations/{tenant_id}/cex
Authorization: Bearer <admin-key>
Content-Type: application/json

{
  "credentials": {},
  "shop_identifier": "<your-cex-seller-id>",
  "base_currency": "GBP",
  "preferred_network": "algorand_mainnet"
}
```

The response includes a `webhook_secret` and a `webhook_url`.

---

## Step 3 — POST order data (bypass mode)

Since CeX has no outbound webhook, your backend posts order data directly to AlgoVoi:

```http
POST <webhook_url>
Authorization: Bearer <webhook_secret>
Content-Type: application/json

{
  "event": "order.created",
  "order": {
    "order_id": "CEX-123456",
    "created_at": "2026-03-01T12:00:00Z",
    "currency": "GBP",
    "totalPrice": 49.99,
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

1. Your backend POSTs order data to AlgoVoi after receiving a CeX notification
2. A hosted checkout link is created (valid 30 minutes)
3. Share the checkout URL with the counterparty via CeX messaging or email
4. Counterparty pays in USDC or aUSDC on-chain
5. AlgoVoi verifies the transaction and returns the TX ID

---

## Troubleshooting

| Symptom | Likely cause |
|---------|-------------|
| HTTP 401 on POST | Bearer token mismatch — check `webhook_secret` |
| HTTP 422 "No network config" | Network config missing for `preferred_network` |

---

## Supported networks

| Network | Asset | Notes |
|---------|-------|-------|
| `algorand_mainnet` | USDC (ASA 31566704) | Requires ASA opt-in on payout wallet |
| `voi_mainnet` | aUSDC (ARC200 app ID 311051) | |
| `algorand_testnet` | Test USDC | For integration testing only |
| `voi_testnet` | Test aUSDC | For integration testing only |

---

## Live test status

Confirmed end-to-end on **2026-03-31** against `api1.ilovechicken.co.uk`:

| Test | Network | Result |
|------|---------|--------|
| Order webhook -> checkout link | `algorand_mainnet` (USDC ASA 31566704) | Pass |

Signature: `HMAC-SHA256` hex digest in `X-Cex-Signature`. Order amount must be in the `order.totalPrice` field.
