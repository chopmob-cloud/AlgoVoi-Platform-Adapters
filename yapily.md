# Yapily Integration — AlgoVoi Tenant Services

Accept **bank transfers via open banking** and settle in **USDC on Algorand** or **aUSDC on VOI** via AlgoVoi.

> **Financial Services integration.** Yapily is an FCA-authorised open banking API provider (FCA ref 827001). This integration enables A2A (account-to-account) fiat payments as the inbound leg, with AlgoVoi handling on-chain stablecoin settlement as the outbound leg. Yapily explicitly supports crypto and payment infrastructure companies.

---

## How it works

```
Customer initiates bank transfer via Yapily payment authorisation
            ↓
Yapily processes payment over Faster Payments (UK) / SEPA Instant (EU)
            ↓
Yapily fires webhook → AlgoVoi verifies payment receipt
            ↓
AlgoVoi creates on-chain settlement (USDC or aUSDC)
            ↓
AlgoVoi notifies merchant — TX ID recorded
```

Covers 2,000+ banks across 46+ countries with a single API.

---

## Prerequisites

- An active AlgoVoi tenant account
- A Yapily account — sign up at [yapily.com](https://yapily.com)
- A registered business (standard KYB — director details, Companies House number)
- ISO 27001 certification or equivalent data handling controls recommended

> Yapily is built to support high-volume and high-risk industries including crypto and iGaming. Payment infrastructure companies are a core use case.

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

## Step 2 — Create a Yapily application

1. Log in to the [Yapily Dashboard](https://dashboard.yapily.com)
2. Go to **Applications** and click **Create Application**
3. Give it a name (e.g. "AlgoVoi Payments")
4. Under **Payments**, enable **Single Immediate Payments**
5. Copy your **Application ID** (UUID) and **Application Secret**

---

## Step 3 — Connect the integration

```http
POST /internal/integrations/{tenant_id}/yapily
Authorization: Bearer <admin-key>
Content-Type: application/json

{
  "credentials": {
    "application_id": "<yapily-application-id>",
    "application_secret": "<yapily-application-secret>"
  },
  "shop_identifier": "<your-merchant-id>",
  "base_currency": "GBP",
  "preferred_network": "algorand_mainnet"
}
```

The response includes a `webhook_secret` and a `webhook_url`.

---

## Step 4 — Register the webhook in Yapily

1. In the Yapily Dashboard go to **Applications → [your app] → Webhooks**
2. Add a new webhook endpoint pointing to your `webhook_url` from Step 3
3. Select the **single_payment.status.completed** and **single_payment.status.updated** event types
4. Yapily signs payloads with HMAC-SHA256 — AlgoVoi verifies using your `webhook_secret`

### Webhook signature verification

Yapily includes a `webhook-signature` header on all webhook deliveries:

```
webhook-signature: <hex(HMAC-SHA256(webhook_secret, raw_body))>
```

AlgoVoi verifies this signature automatically on receipt.

### Webhook payload format

```json
{
  "type": "single_payment.status.completed",
  "event": {
    "id": "<payment-id>",
    "status": "COMPLETED",
    "amount": 100.00
  },
  "metadata": {
    "tracingId": "<tracing-id>"
  }
}
```

---

## Payment flow

Once connected:

1. Customer selects "Pay by bank transfer" at checkout
2. AlgoVoi calls the Yapily Payments API to create a payment authorisation request
3. Customer is redirected to their bank to authorise the transfer
4. Yapily processes over Faster Payments (UK) or SEPA Instant (EU)
5. On `single_payment.status.completed` webhook: AlgoVoi records the fiat receipt and triggers on-chain settlement
6. USDC (or aUSDC) is transferred to the merchant's payout wallet on-chain
7. TX ID returned to your backend

---

## Supported rails

| Rail | Region | Coverage | Settlement time |
|------|--------|----------|----------------|
| Faster Payments | UK | 40+ banks | Seconds |
| SEPA Instant | EU | 1,500+ banks | ~10 seconds |
| SEPA Credit Transfer | EU | 2,000+ banks | Next business day |
| Open Banking (other) | 46+ countries | Varies | Varies |

---

## Troubleshooting

| Symptom | Likely cause |
|---------|-------------|
| HTTP 401 on webhook | `webhook-signature` mismatch — check `webhook_secret` matches Yapily dashboard |
| HTTP 422 "No network config" | Network config missing for `preferred_network` |
| Payment authorisation rejected | Customer's bank not in Yapily's supported institution list |
| `single_payment.status.updated` with status `FAILED` | Customer abandoned bank auth or insufficient funds — no settlement triggered |
| Application credentials invalid | Application ID or secret rotated — reconnect via Step 3 |

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
| `algorand_testnet` | Test USDC | Use Yapily sandbox environment for testing |
| `voi_testnet` | Test aUSDC | Use Yapily sandbox environment for testing |
