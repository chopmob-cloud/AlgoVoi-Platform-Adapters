# Wix eCommerce Integration — AlgoVoi Tenant Services

Accept **USDC on Algorand** and **aUSDC on VOI** as payment in your Wix store via AlgoVoi.

---

## How it works

```
Customer places a Wix order
            ↓
Wix sends a signed JWT webhook (RS256)
            ↓
AlgoVoi verifies JWT signature → parses order from payload
            ↓
AlgoVoi creates a hosted checkout link (USDC or aUSDC)
            ↓
Customer pays on-chain
            ↓
AlgoVoi verifies the transaction on-chain
            ↓
Wix order payment status set to PAID
```

> Wix webhooks are RS256-signed JWTs. AlgoVoi verifies them using the RSA
> public key from your Wix app dashboard.

---

## Prerequisites

- An active AlgoVoi tenant account
- A Wix site with eCommerce enabled
- A Wix app (created in the Wix Developer Console) with eCommerce permissions

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

## Step 2 — Create a Wix app and get credentials

1. Go to the [Wix Developer Console](https://dev.wix.com/) and create a new app
2. Under **OAuth → Permissions**, add:
   - `eCommerce - Manage orders`
3. Under **Webhooks**, note the **Public Key** (PEM format) — this is used to verify incoming webhooks
4. Install the app on your Wix site and complete OAuth to get an access token
5. Note your **Account ID** and **Site ID** from the Wix dashboard

---

## Step 3 — Connect the integration

```http
POST /internal/integrations/{tenant_id}/wix
Authorization: Bearer <admin-key>
Content-Type: application/json

{
  "credentials": {
    "public_key": "-----BEGIN PUBLIC KEY-----\n...\n-----END PUBLIC KEY-----",
    "access_token": "<wix-oauth-access-token>",
    "account_id": "<wix-account-id>",
    "site_id": "<wix-site-id>"
  },
  "shop_identifier": "mysite.wixsite.com",
  "base_currency": "USD",
  "preferred_network": "algorand_mainnet"
}
```

The response includes a `webhook_url`. Register this in your Wix app.

---

## Step 4 — Register the webhook in Wix

1. In the Wix Developer Console, go to your app → **Webhooks**
2. Add a new webhook subscription:
   - **Event**: `wix.ecom.v1.order` → `eCommerceOrderCreated`
   - **Callback URL**: the `webhook_url` from Step 3
3. Save — Wix will start sending signed JWTs to your endpoint

---

## Payment flow for your customers

Once connected, every new Wix order triggers AlgoVoi to:

1. Verify the JWT signature using your app's public key
2. Create a hosted checkout link valid for **30 minutes**
3. Display the amount in USDC (or aUSDC) with a QR code and wallet link
4. On successful on-chain confirmation:
   - Wix order `paymentStatus` set to **PAID** via the eCommerce Orders API

---

## Troubleshooting

| Symptom | Likely cause |
|---------|-------------|
| HTTP 401 on webhook | JWT verification failed — check that `public_key` matches your Wix app |
| HTTP 422 "No network config" | Network config missing for `preferred_network` |
| Order not updating | `access_token` expired or lacks eCommerce manage permission |
| JWT decode error | Ensure `public_key` is PEM format with correct line breaks |

---

## Supported networks

| Network | Asset | Notes |
|---------|-------|-------|
| Webhook → checkout link | Webhook → checkout link | Webhook → checkout link | Webhook → checkout link | `algorand_mainnet` (USDC (ASA 31566704)) | Skip | Requires ASA opt-in on payout wallet |
| Webhook → checkout link | Webhook → checkout link | `voi_mainnet` (WAD (ARC200 app ID 47138068)) | Skip | |
| `algorand_testnet` | Test USDC | For integration testing only |
| `voi_testnet` | Test aUSDC | For integration testing only |

---

## Live test status

Not yet live-tested -- Wix webhooks are RS256-signed JWTs requiring a real RSA keypair. Signature verification logic is implemented; functional test pending real Wix app credentials.
