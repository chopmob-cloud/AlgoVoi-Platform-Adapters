# Easy Digital Downloads — AlgoVoi Payment Gateway

Accept USDC on Algorand, VOI (aUSDC), Hedera, and Stellar in your **Easy Digital Downloads 3.2+** store. Non-custodial — funds settle to the merchant's configured wallet. Works with digital downloads, license keys, Software Licensing, and Recurring Payments.

**v1.0.0 — EDD 3.2+ / WordPress 6.4+ / PHP 8.0+**

Full integration guide: [easy-digital-downloads/](.)
https://github.com/chopmob-cloud/AlgoVoi-Platform-Adapters

---

## How it works

```
Customer reaches EDD checkout
        │
        ▼
Selects "Pay with Crypto (AlgoVoi)"
        │
        ▼
edd_gateway_algovoi action runs:
  • Creates a pending EDD payment record
  • POSTs to /v1/payment-links with order total + network
  • Stashes token + api_base + network in payment meta
        │
        ▼
Customer redirected to api1.ilovechicken.co.uk/checkout/{token}
        │
        ▼
Customer pays on-chain via wallet (Pera / Defly / HashPack / Freighter / …)
        │
        ▼
Return to EDD success page (with ?algovoi_payment_id=N)
        │
        ▼
template_redirect hook calls GET /checkout/{token} — cancel-bypass guard:
  payment only transitions to "publish" if status is paid / completed / confirmed.
        │
        ▼
(Out-of-band) Webhook hits /wp-json/algovoi-edd/v1/webhook
  • HMAC-SHA256 (base64) verified via webhook_secret
  • Gateway cross-checked again via GET /checkout/{token}
  • Idempotent: duplicate webhooks for same payment don't re-transition
```

---

## Install

1. Download the `algovoi-edd.php` file.
2. Upload it to `wp-content/plugins/algovoi-edd/algovoi-edd.php` (or zip + use the WP admin plugin uploader).
3. Activate **AlgoVoi for Easy Digital Downloads** under **Plugins**.
4. Configure at **Downloads → Settings → Payments → AlgoVoi**:
   - **API Base URL** — `https://api1.ilovechicken.co.uk`
   - **API Key** — your `algv_*` key from the [AlgoVoi dashboard](https://api1.ilovechicken.co.uk/dashboard)
   - **Tenant ID** — your tenant UUID
   - **Webhook Secret** — used for HMAC verification on incoming webhooks
   - **Default network** — Algorand / VOI / Hedera / Stellar
5. Enable AlgoVoi under **Downloads → Settings → Payments → General → Payment Gateways**.

---

## Files

| File | Description |
|------|-------------|
| `algovoi-edd.php` | Single-file plugin — gateway registration, settings, `edd_gateway_algovoi` handler, return handler, REST webhook, helpers |

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

```
POST /wp-json/algovoi-edd/v1/webhook
```

Register this URL in your AlgoVoi dashboard. Signed with HMAC-SHA256 (base64) in the `X-AlgoVoi-Signature` header.

---

## Security posture

Matches the April 2026 + pass-2 audit patterns applied to the WooCommerce / native-PHP adapters:

| Protection | Where |
|---|---|
| **Cancel-bypass guard** | `template_redirect` calls `algovoi_edd_verify_paid()` before flipping to `publish` |
| **HMAC empty-secret reject** | Webhook returns 500 if `webhook_secret` is empty |
| **Timing-safe HMAC compare** | `hash_equals()` on base64 HMAC-SHA256 |
| **Body size cap** | 64 KB before HMAC computation |
| **Empty signature reject** | Explicit check before HMAC computation |
| **https-only outbound** | `algovoi_edd_is_https()` gate on API base; refuses to send key over plaintext |
| **Token length cap** | 200-char cap on `rawurlencode`d token |
| **Amount sanity** | `is_finite() && > 0` before link creation |
| **Spoofed-webhook protection** | Webhook controller ALSO calls `algovoi_edd_verify_paid()` — HMAC-valid but payment-not-confirmed webhooks are rejected |
| **Idempotent transitions** | Status is only flipped if not already `publish`/`complete` |

---

## EDD Software Licensing integration

EDD's license-key generation and delivery happens automatically on `edd_update_payment_status($id, 'publish')`. No extra work needed — license keys are generated and emailed when the AlgoVoi webhook fires (or on customer return).

---

## Dependencies

```
easy-digital-downloads >= 3.2
PHP >= 8.0
WordPress >= 6.4
```

No composer / third-party libraries. Uses WP's built-in `wp_remote_post` / `wp_remote_get` for HTTP.

---

## Note on EDD 3.0 Orders API

This plugin uses the legacy `edd_insert_payment()` / `edd_update_payment_status()` / `edd_get_payment_meta()` function family. These are **fully supported backward-compat shims** on EDD 3.2 → 3.3.x (tested range), delegating internally to the new Orders API.

If EDD drops the compat layer in a future major release, this plugin will need to migrate to the Orders API (`edd_build_order()` + `edd_add_order_meta()` + `edd_update_order()`). The on-chain gateway interaction, HMAC, cancel-bypass guard, and webhook flow are unaffected — only the 6 EDD calls would change. A v1.1.0 release will follow if / when EDD signals that direction.

---

Licensed under the [Business Source License 1.1](../LICENSE).
