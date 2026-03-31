# WhatsApp Business Integration — AlgoVoi Tenant Services

Accept **USDC on Algorand** and **aUSDC on VOI** as payment via WhatsApp Business using AlgoVoi.

> **Social Commerce integration.** WhatsApp Business Cloud API supports product catalogues and order messages. When a customer sends an order via WhatsApp, AlgoVoi receives the webhook, creates a hosted checkout link, and your bot replies with a payment button — all within the WhatsApp conversation.

---

## How it works

```
Customer browses your WhatsApp catalogue and places an order
            ↓
WhatsApp fires order webhook → AlgoVoi parses product_items
            ↓
AlgoVoi creates a hosted checkout link (USDC or aUSDC)
            ↓
Your WhatsApp bot replies with a "Pay with USDC" CTA button
            ↓
Customer taps link → pays on-chain
            ↓
AlgoVoi verifies transaction on-chain
            ↓
AlgoVoi fires webhook → bot sends payment confirmation to customer
```

---

## Prerequisites

- An active AlgoVoi tenant account
- A Meta Business Account (business verification required)
- A WhatsApp Business Account (WABA) with Cloud API access
- A Meta App with `whatsapp_business_messaging` and `whatsapp_business_management` permissions
- A permanent System User access token from Meta Business Manager
- A publicly accessible HTTPS webhook endpoint

> Meta requires **business verification** before the WhatsApp Commerce/Orders API is fully accessible. Complete verification at [business.facebook.com/settings/security](https://business.facebook.com/settings/security).

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

## Step 2 — Set up WhatsApp Cloud API

1. Go to [developers.facebook.com](https://developers.facebook.com) and create a Meta App
2. Add the **WhatsApp** product to your app
3. In **WhatsApp → API Setup**, note your **Phone Number ID** and **WhatsApp Business Account ID (WABA ID)**
4. In Meta Business Manager, create a **System User** with `whatsapp_business_messaging` and `whatsapp_business_management` permissions
5. Generate a **permanent access token** for the System User

---

## Step 3 — Connect the integration

```http
POST /internal/integrations/{tenant_id}/whatsapp
Authorization: Bearer <admin-key>
Content-Type: application/json

{
  "credentials": {
    "access_token": "<meta-system-user-access-token>",
    "phone_number_id": "<whatsapp-phone-number-id>",
    "waba_id": "<whatsapp-business-account-id>",
    "app_secret": "<meta-app-secret>"
  },
  "shop_identifier": "<phone_number_id>",
  "base_currency": "GBP",
  "preferred_network": "algorand_mainnet"
}
```

The response includes a `webhook_secret` and a `webhook_url`.

---

## Step 4 — Register the webhook

1. In your Meta App go to **WhatsApp → Configuration → Webhooks**
2. Set the **Callback URL** to your `webhook_url` from Step 3
3. Set the **Verify Token** to your `webhook_secret`
4. Subscribe to the **messages** field on the `whatsapp_business_account` object
5. Click **Verify and Save**

### Webhook signature verification

Meta signs every webhook delivery with an `X-Hub-Signature-256` header:

```
X-Hub-Signature-256: sha256=<hex(HMAC-SHA256(app_secret, raw_body))>
```

AlgoVoi verifies this signature automatically on receipt.

---

## Order webhook payload

When a customer submits an order from your WhatsApp catalogue, AlgoVoi receives:

```json
{
  "object": "whatsapp_business_account",
  "entry": [{
    "changes": [{
      "field": "messages",
      "value": {
        "messages": [{
          "type": "order",
          "from": "<customer-whatsapp-number>",
          "order": {
            "catalog_id": "<catalog_id>",
            "product_items": [
              {
                "product_retailer_id": "SKU-001",
                "quantity": 2,
                "item_price": 24.99,
                "currency": "GBP"
              }
            ]
          }
        }]
      }
    }]
  }]
}
```

---

## Payment reply

AlgoVoi automatically replies to the customer with a CTA button linking to the checkout:

```http
POST https://graph.facebook.com/v18.0/{phone_number_id}/messages
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "messaging_product": "whatsapp",
  "to": "<customer-whatsapp-number>",
  "type": "interactive",
  "interactive": {
    "type": "cta_url",
    "body": {
      "text": "Your order total is £49.98. Pay in USDC on Algorand:"
    },
    "action": {
      "name": "cta_url",
      "parameters": {
        "display_text": "Pay with USDC",
        "url": "<algovoi-checkout-url>"
      }
    }
  }
}
```

---

## Troubleshooting

| Symptom | Likely cause |
|---------|-------------|
| Webhook verification failing | Verify Token mismatch — check `webhook_secret` |
| `X-Hub-Signature-256` mismatch | `app_secret` incorrect in credentials |
| Order messages not arriving | "messages" field not subscribed in webhook config |
| CTA button not rendering | WhatsApp template approval required for some message types in certain regions |
| HTTP 422 "No network config" | Network config missing for `preferred_network` |
| Access token expiring | Use a permanent System User token, not a short-lived user token |

---

## Supported networks

| Network | Asset | Notes |
|---------|-------|-------|
| `algorand_mainnet` | USDC (ASA 31566704) | Requires ASA opt-in on payout wallet |
| `voi_mainnet` | aUSDC (ARC200 app ID 311051) | |
| `algorand_testnet` | Test USDC | For development and testing |
| `voi_testnet` | Test aUSDC | For development and testing |
