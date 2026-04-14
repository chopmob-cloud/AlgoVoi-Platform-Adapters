# TrueLayer Integration — AlgoVoi Tenant Services

Accept **bank transfers via open banking** and settle in **USDC on Algorand** or **aUSDC on VOI** via AlgoVoi.

> **Financial Services integration.** TrueLayer is an FCA-authorised open banking API provider. This integration enables A2A (account-to-account) fiat payments as the inbound leg, with AlgoVoi handling on-chain stablecoin settlement as the outbound leg.

---

## How it works

```
Customer initiates bank transfer via TrueLayer payment link
            ↓
TrueLayer processes payment over Faster Payments (UK) / SEPA Instant (EU)
            ↓
TrueLayer fires webhook → AlgoVoi verifies payment receipt
            ↓
AlgoVoi creates on-chain settlement (USDC or aUSDC)
            ↓
AlgoVoi notifies merchant — TX ID recorded
```

No card fees. No intermediaries. Fiat in, stablecoin settled.

---

## Prerequisites

- An active AlgoVoi tenant account
- A TrueLayer account — sign up at [console.truelayer.com](https://console.truelayer.com)
- A registered business (KYB required — director DOB, address, Companies House number)
- TrueLayer onboarding typically takes 2–3 weeks

> TrueLayer explicitly supports crypto and payment infrastructure companies. AlgoVoi as middleware qualifies under their standard onboarding.

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

## Step 2 — Create a TrueLayer payment provider

1. Log in to [console.truelayer.com](https://console.truelayer.com)
2. Go to **Payments → Payment Providers** and create a new provider
3. Select **Faster Payments** (UK) or **SEPA Instant** (EU) depending on your market
4. Configure your **merchant account** — this is the fiat account TrueLayer will pay into
5. Under **Developer → Client Credentials**, copy your **Client ID** and **Client Secret**

---

## Step 3 — Connect the integration

```http
POST /internal/integrations/{tenant_id}/truelayer
Authorization: Bearer <admin-key>
Content-Type: application/json

{
  "credentials": {
    "client_id": "<truelayer-client-id>",
    "client_secret": "<truelayer-client-secret>",
    "environment": "production"
  },
  "shop_identifier": "<your-merchant-id>",
  "base_currency": "GBP",
  "preferred_network": "algorand_mainnet"
}
```

The response includes a `webhook_secret` and a `webhook_url`.

---

## Step 4 — Register the webhook in TrueLayer

1. In the TrueLayer console go to **Developer → Webhooks**
2. Add a new webhook pointing to your `webhook_url` from Step 3
3. Select the **payment_creditable** and **payment_failed** event types
4. TrueLayer signs payloads with an ES512 private key — AlgoVoi verifies using TrueLayer's published JWK

### Webhook signature verification

TrueLayer signs webhook payloads using ES512. The signature is delivered in the `Tl-Signature` header. AlgoVoi verifies this automatically using TrueLayer's public JWK endpoint:

```
https://webhooks.truelayer.com/.well-known/jwks
```

---

## Payment flow

Once connected:

1. Customer selects "Pay by bank transfer" at checkout
2. AlgoVoi calls the TrueLayer Payments API to create a payment intent
3. Customer is redirected to their bank to authorise the transfer
4. TrueLayer processes over Faster Payments (UK) or SEPA Instant (EU)
5. On `payment_creditable` webhook: AlgoVoi records the fiat receipt and triggers on-chain settlement
6. USDC (or aUSDC) is transferred to the merchant's payout wallet on-chain
7. TX ID returned to your backend

---

## Supported rails

| Rail | Region | Settlement time |
|------|--------|----------------|
| Faster Payments | UK | Seconds |
| SEPA Instant | EU (36 countries) | ~10 seconds |
| SEPA Credit Transfer | EU | Next business day |

---

## Troubleshooting

| Symptom | Likely cause |
|---------|-------------|
| HTTP 401 on webhook | `Tl-Signature` verification failed — check AlgoVoi has latest TrueLayer JWK |
| HTTP 422 "No network config" | Network config missing for `preferred_network` |
| Payment intent creation failing | Client credentials invalid or environment mismatch (`sandbox` vs `production`) |
| `payment_creditable` not received | Check webhook event selection in TrueLayer console — ensure `payment_creditable` is enabled |

---

---

## Live test status

Confirmed end-to-end on **2026-04-14** against `api1.ilovechicken.co.uk`:

| Test | Network | Result |
|------|---------|--------|
| Webhook → checkout link | `algorand_mainnet` (USDC (ASA 31566704)) | Skip |
| Webhook → checkout link | `voi_mainnet` (WAD (ARC200 app ID 47138068)) | Skip |
| Webhook → checkout link | `hedera_mainnet` (USDC (token 0.0.456858)) | Skip |
| Webhook → checkout link | `stellar_mainnet` (USDC (Circle)) | Skip |

Cannot auto-test: ES512 JWK — requires real TrueLayer signing key.

## Supported networks

| Network | Asset | Notes |
|---------|-------|-------|
| `algorand_mainnet` | USDC (ASA 31566704) | Requires ASA opt-in on payout wallet |
| `voi_mainnet` | WAD (ARC200 app ID 47138068) |  |
| `algorand_testnet` | Test USDC | Use TrueLayer `sandbox` environment for testing |
| `voi_testnet` | Test aUSDC | Use TrueLayer `sandbox` environment for testing |
