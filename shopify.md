# Shopify Integration — AlgoVoi Tenant Services

Accept **USDC on Algorand**, **aUSDC on VOI**, **USDC on Hedera**, and **USDC on Stellar** as payment in your Shopify store via AlgoVoi.

---

## How it works

```
Shopify order created
        ↓
AlgoVoi receives webhook → verifies HMAC signature → parses order
        ↓
AlgoVoi creates a hosted checkout link (customer selects chain)
        ↓
Customer pays on-chain (Algorand, VOI, Hedera, or Stellar)
        ↓
AlgoVoi verifies the transaction on-chain
        ↓
Shopify order marked as paid
```

No code changes needed in your Shopify store — AlgoVoi handles everything via webhooks.

---

## Prerequisites

- An active AlgoVoi tenant account ([start free trial](https://api1.ilovechicken.co.uk/signup))
- A Shopify store with Admin API access
- A Shopify Custom App with the `write_orders` and `read_orders` scopes

---

## Step 1 — Configure your networks

You need at least one network config with a payout address. Add as many chains as you want to accept.

### USDC on Algorand mainnet

```http
POST /internal/tenants/{tenant_id}/network-configs
Authorization: Bearer <admin-key>
Content-Type: application/json

{
  "network": "algorand_mainnet",
  "payout_address": "<your-algorand-address>"
}
```

Then set the stablecoin:

```http
PATCH /internal/tenants/{tenant_id}/network-configs/algorand_mainnet/stablecoin
Authorization: Bearer <admin-key>
Content-Type: application/json

{
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
  "payout_address": "<your-voi-address>"
}
```

```http
PATCH /internal/tenants/{tenant_id}/network-configs/voi_mainnet/stablecoin
Authorization: Bearer <admin-key>
Content-Type: application/json

{
  "preferred_asset_id": "302190",
  "preferred_asset_decimals": 6
}
```

> ASA `302190` is Aramid-bridged USDC (aUSDC) on VOI mainnet — a native ASA, not an ARC200 contract.

### USDC on Hedera mainnet

```http
POST /internal/tenants/{tenant_id}/network-configs
Authorization: Bearer <admin-key>
Content-Type: application/json

{
  "network": "hedera_mainnet",
  "payout_address": "<your-hedera-account-id>"
}
```

> Hedera account IDs look like `0.0.1234567`. The AlgoVoi platform handles HTS token configuration automatically.

### USDC on Stellar mainnet

```http
POST /internal/tenants/{tenant_id}/network-configs
Authorization: Bearer <admin-key>
Content-Type: application/json

{
  "network": "stellar_mainnet",
  "payout_address": "<your-stellar-address>"
}
```

```http
PATCH /internal/tenants/{tenant_id}/network-configs/stellar_mainnet/stablecoin
Authorization: Bearer <admin-key>
Content-Type: application/json

{
  "preferred_asset_id": "USDC:GA5ZSEJYB37JRC5AVCIA5MOP4RHTM335X2KGX3IHOJAPP5RE34K4KZVN",
  "preferred_asset_decimals": 7
}
```

> Stellar addresses start with `G`. Your payout account must have a trust line for Circle USDC before receiving payments.
> Stellar USDC uses 7 decimal places (not 6).

---

## Step 2 — Create a Shopify Custom App

1. In Shopify Admin go to **Settings → Apps and sales channels → Develop apps**
2. Click **Create an app** and give it a name (e.g. "AlgoVoi Payments")
3. Under **Configuration → Admin API scopes**, enable:
   - `read_orders`
   - `write_orders`
4. Click **Install app** and copy the **Admin API access token**

---

## Step 3 — Connect the integration

```http
POST /internal/integrations/{tenant_id}/shopify
Authorization: Bearer <admin-key>
Content-Type: application/json

{
  "credentials": {
    "shop_domain": "your-store.myshopify.com",
    "access_token": "<shopify-admin-api-access-token>"
  },
  "shop_identifier": "your-store.myshopify.com",
  "base_currency": "USD",
  "preferred_network": "algorand_mainnet"
}
```

**`preferred_network`** — which chain to default to for settlement:

| Value | Settles in |
|-------|-----------|
| `algorand_mainnet` | USDC (ASA 31566704) on Algorand |
| `voi_mainnet` | aUSDC (ASA 302190) on VOI |
| `hedera_mainnet` | USDC on Hedera |
| `stellar_mainnet` | USDC on Stellar |

The response includes a `webhook_secret` and a `webhook_url`. Save both — the secret is shown once.

```json
{
  "webhook_url": "https://api1.ilovechicken.co.uk/webhooks/shopify/{tenant_id}",
  "webhook_secret": "...",
  "preferred_network": "algorand_mainnet"
}
```

---

## Step 4 — Register the webhook in Shopify

1. In Shopify Admin go to **Settings → Notifications → Webhooks**
2. Click **Create webhook**
3. Set:
   - **Event**: Order creation
   - **URL**: the `webhook_url` from Step 3
   - **Format**: JSON
4. Copy the **Signing secret** Shopify shows — this must match the `webhook_secret` from Step 3

> AlgoVoi verifies every inbound webhook using HMAC-SHA256 against the `X-Shopify-Hmac-Sha256` header. Mismatched secrets will be rejected with HTTP 401.

---

## Payment flow for your customers

Once connected, every new Shopify order triggers AlgoVoi to:

1. Create a hosted checkout link valid for **30 minutes**
2. Display the amount in the configured stablecoin with a QR code and wallet link
3. Customer selects their preferred chain (Algorand, VOI, Hedera, or Stellar)
4. On successful on-chain confirmation, mark the Shopify order as **paid**

The customer is redirected back to the Shopify order status page after payment.

---

## Tenant limits to check

Ensure your tenant's limits allow the integration to function:

```http
PUT /internal/tenants/{tenant_id}/limits
Authorization: Bearer <admin-key>
Content-Type: application/json

{
  "allowed_networks": ["algorand_mainnet", "voi_mainnet", "hedera_mainnet", "stellar_mainnet"],
  "allowed_assets": ["31566704", "302190", "USDC:GA5ZSEJYB37JRC5AVCIA5MOP4RHTM335X2KGX3IHOJAPP5RE34K4KZVN"],
  "kill_switch": false
}
```

---

## Troubleshooting

| Symptom | Likely cause |
|---------|-------------|
| HTTP 401 on webhook | `webhook_secret` mismatch — reconnect the integration to rotate the secret |
| HTTP 422 "No network config" | Network config missing or no payout address set for `preferred_network` |
| Order not marked paid | Shopify Admin API token lacks `write_orders` scope |
| Payment link expired | Customer took longer than 30 minutes — a new order webhook will create a fresh link |
| Stellar checkout shows XLM | Stablecoin not configured — run the PATCH stablecoin endpoint for `stellar_mainnet` |

---

## Supported networks

| Network | Asset | Decimals | Notes |
|---------|-------|----------|-------|
| `algorand_mainnet` | USDC (ASA 31566704) | 6 | Requires ASA opt-in on payout wallet |
| `voi_mainnet` | aUSDC (ASA 302190) | 6 | Native ASA — Aramid-bridged USDC |
| `hedera_mainnet` | USDC (HTS) | 6 | Account ID format: `0.0.XXXXXXX` |
| `stellar_mainnet` | USDC (Circle issuer) | 7 | Requires trust line on payout account |
| `algorand_testnet` | Test USDC | 6 | For integration testing only |
| `voi_testnet` | Test aUSDC | 6 | For integration testing only |

---

## Security

All webhook and payment flows include:
- **HMAC-SHA256 webhook verification** — empty secrets rejected before HMAC check
- **Cancel-bypass prevention** — payment status verified via API before marking orders complete
- **TLS enforced** — all outbound API calls use SSL verification
- **Timing-safe comparisons** — `hash_equals` / `hmac.compare_digest` for all secret comparisons

---

## Live test status

Confirmed end-to-end on **2026-04-14** against `api1.ilovechicken.co.uk`:

| Test | Network | Result |
|------|---------|--------|
| Webhook → checkout link | `algorand_mainnet` (USDC (ASA 31566704)) | Pass |
| Webhook → checkout link | `voi_mainnet` (WAD (ARC200 app ID 47138068)) | Pass |
| Webhook → checkout link | `hedera_mainnet` (USDC (token 0.0.456858)) | Pass |
| Webhook → checkout link | `stellar_mainnet` (USDC (Circle)) | Pass |

Signature verification uses `HMAC-SHA256` over the raw request body. The webhook header is `X-Shopify-Hmac-Sha256`. The `webhook_secret` is auto-generated by AlgoVoi on integration creation — it is not the Shopify app secret.
