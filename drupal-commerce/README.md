# Drupal Commerce — AlgoVoi Payment Gateway

Accept USDC on Algorand, VOI (aUSDC), Hedera, and Stellar in your Drupal Commerce store via the AlgoVoi hosted checkout flow. Non-custodial — funds settle directly to your configured wallet.

**v1.0.0 — Drupal 10 / 11, Commerce 2 / 3 compatible**

Full integration guide: [drupal-commerce/](.)
https://github.com/chopmob-cloud/AlgoVoi-Platform-Adapters

---

## How it works

```
Customer reaches Drupal Commerce checkout
        │
        ▼
Selects "Pay with Crypto (AlgoVoi)"
        │
        ▼
Drupal's OffsitePaymentGatewayBase builds a redirect form:
  • AlgoVoi::createPaymentLink() POSTs to /v1/payment-links
  • Returns a checkout URL + short token
  • Token + network stashed on the order as data fields
        │
        ▼
Customer redirected to api1.ilovechicken.co.uk/checkout/{token}
        │
        ▼
Customer pays on-chain via wallet (Pera / Defly / HashPack / Freighter / …)
        │
        ▼
Customer redirected back to Drupal "return" URL
        │
        ▼
AlgoVoi::onReturn() calls GET /checkout/{token} — cancel-bypass guard:
  order is only marked paid if status is paid / completed / confirmed.
  Creates a commerce_payment entity in the "completed" state.
        │
        ▼
(Optional, out-of-band) Webhook hits /payment/notify/algovoi/{gateway}
  • HMAC-SHA256 signature verified via webhook_secret
  • Gateway cross-checked again via GET /checkout/{token}
  • Idempotent: replayed webhooks don't duplicate payments
```

---

## Install

1. Drop this folder into your Drupal project at `web/modules/contrib/commerce_algovoi/` (or run `composer require chopmob/commerce_algovoi` once published).
2. Enable the module:
   ```bash
   drush en commerce_algovoi -y
   ```
3. Navigate to **Commerce → Configuration → Payment gateways** and click **+ Add payment gateway**.
4. Pick **AlgoVoi (USDC on Algorand / VOI / Hedera / Stellar)**, fill in:
   - **API base URL** — `https://api1.ilovechicken.co.uk`
   - **API Key** — your `algv_*` key
   - **Tenant ID** — your tenant UUID
   - **Webhook Secret** — used for HMAC verification on incoming webhooks
   - **Default network** — Algorand / VOI / Hedera / Stellar
5. Save. The gateway is now available at checkout.

---

## Files

| File | Description |
|------|-------------|
| `commerce_algovoi.info.yml` | Module metadata (Drupal 10/11, Commerce 2/3) |
| `commerce_algovoi.routing.yml` | Webhook route `/payment/notify/algovoi/{gateway}` |
| `src/Plugin/Commerce/PaymentGateway/AlgoVoi.php` | Main gateway — extends `OffsitePaymentGatewayBase`; config form, `createPaymentLink()`, `onReturn()`, `verifyWebhook()`, `verifyCheckoutPaid()` |
| `src/PluginForm/OffsiteRedirect/PaymentOffsiteForm.php` | Builds the redirect form (GET) to the checkout URL |
| `src/Controller/WebhookController.php` | Handles inbound webhook POSTs; HMAC + gateway cross-check |

---

## Supported chains

| Network key | Asset | Asset ID |
|-------------|-------|----------|
| `algorand_mainnet` | USDC | ASA 31566704 |
| `voi_mainnet` | aUSDC | ARC200 302190 |
| `hedera_mainnet` | USDC | HTS 0.0.456858 |
| `stellar_mainnet` | USDC | Circle |

---

## Webhook endpoint

Drupal automatically exposes:

```
POST /payment/notify/algovoi/{gateway_id}
```

where `{gateway_id}` is the machine name of the payment gateway you created in the admin UI (defaults to `algovoi_offsite` if you accept the suggested name).

Register this URL in your AlgoVoi dashboard as the webhook target.

---

## Security posture

The gateway enforces every applicable April 2026 hardening pattern:

| Protection | Where |
|---|---|
| **Cancel-bypass guard** | `AlgoVoi::onReturn()` calls `verifyCheckoutPaid()` before marking paid |
| **HMAC empty-secret reject** | `verifyWebhook()` returns `NULL` if `webhook_secret` is empty |
| **Timing-safe HMAC compare** | `hash_equals()` for base64 signature comparison |
| **Body size cap** | 64 KB cap before HMAC computation on webhook |
| **https-only outbound** | `startsWithHttps()` gate on every outbound call; refuses to send API key or token over plaintext |
| **Token length cap** | 200-char cap on `rawurlencode`d token in verify path |
| **Amount sanity** | `is_finite() && > 0` check before payment-link creation |
| **Webhook idempotency** | Duplicate `commerce_payment` loads skipped; replay-safe |
| **Double-check on webhook** | Even after HMAC verify, the webhook controller re-queries `verifyCheckoutPaid()` to prevent spoofed-but-HMAC-valid webhooks |

---

## Testing

```bash
# Typical test setup (from your Drupal root, with DDEV / Lando / local dev)
vendor/bin/phpunit -c core modules/contrib/commerce_algovoi/tests/
```

Phase 1 / Phase 2 live smoke is done via the standard AlgoVoi gateway test URL:

```bash
curl -s https://api1.ilovechicken.co.uk/health
# {"status":"ok","service":"gateway"}
```

The same 4-chain TX IDs used to smoke-test the Python / PHP / Go / Rust adapters work for Drupal once wired to a real merchant tenant.

---

## Dependencies

```
drupal/commerce ^2 || ^3   # Drupal Commerce 2.x / 3.x
drupal/commerce_payment     # bundled with commerce
```

Zero composer dependencies beyond Commerce itself. The HTTP client is Drupal's built-in `http_client` service (Guzzle).

---

Licensed under the [Business Source License 1.1](../LICENSE).
