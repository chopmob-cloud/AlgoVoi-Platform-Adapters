# OpenCart Integration — AlgoVoi Tenant Services

Accept **USDC on Algorand** and **aUSDC on VOI** as payment in your OpenCart 4 store via AlgoVoi.

Two payment methods are provided by the extension:

| Gateway | ID | Method |
|---------|----|--------|
| AlgoVoi Hosted Checkout | `algovoi` | Creates a payment link via `/v1/payment-links`, redirects customer to hosted checkout page |
| AlgoVoi Extension | `algovoi_ext` | In-page payment via the AlgoVoi browser extension — no redirect |

---

## How it works

### Hosted Checkout

```
Customer confirms order at checkout
            ↓
OpenCart calls POST /v1/payment-links with amount, currency, label
            ↓
AlgoVoi returns a checkout_url
            ↓
Customer redirected to hosted checkout page (QR code + wallet link)
            ↓
Customer pays on-chain
            ↓
AlgoVoi verifies transaction on-chain
            ↓
OpenCart order status updated to Complete with TX ID in order history
```

### Extension Payment

```
Customer confirms order at checkout (with AlgoVoi browser extension installed)
            ↓
OpenCart calls POST /v1/payment-links to get checkout_url
            ↓
Server scrapes checkout page for receiver address and memo
            ↓
Customer redirected to in-store pending page
            ↓
algosdk builds ASA transfer (USDC or aUSDC) in browser
            ↓
window.algorand.signAndSendTransactions() signs the transaction
            ↓
Signed bytes submitted directly to algod POST /v2/transactions
            ↓
Browser polls algod until confirmed-round > 0
            ↓
Browser POSTs tx_id to OpenCart verify endpoint
            ↓
OpenCart proxies to POST /checkout/{token}/verify on AlgoVoi API
            ↓
Order status updated to Complete — customer redirected to success page
```

---

## Prerequisites

- An active AlgoVoi tenant account with a valid **tenant API key** (prefix `algv_`)
- OpenCart **4.x** (tested on 4.1.0.3)
- PHP 8.x with `curl` extension enabled
- HTTPS on the storefront (required for browser extension `window.algorand` API)

---

## Step 1 — Configure your network

You need at least one network config with a payout address and your chosen stablecoin.

### USDC on Algorand mainnet

```http
POST /api/tenants/{tenant_id}/network-configs
Authorization: Bearer <admin-key>
Content-Type: application/json

{
  "network": "algorand_mainnet",
  "payout_address": "<your-algorand-address>",
  "preferred_asset_id": "31566704",
  "preferred_asset_decimals": 6
}
```

> ASA `31566704` is Circle's native USDC on Algorand mainnet.
> Your payout wallet must have opted into this ASA before receiving payments.

### aUSDC on VOI mainnet

```http
POST /api/tenants/{tenant_id}/network-configs
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

## Step 2 — Generate a tenant API key

The OpenCart extension authenticates directly against `/v1/payment-links` using a **tenant API key** (not the admin key).

```http
POST /api/tenants/{tenant_id}/api-keys
Authorization: Bearer <admin-key>
```

Response:

```json
{
  "key_id": "...",
  "plaintext": "algv_...",
  "created_at": "..."
}
```

> The plaintext key is shown once. Copy it before closing the response.

---

## Step 3 — Install the extensions

The integration consists of two separate OpenCart extensions. Each lives in its own subdirectory under `extension/`.

### Directory structure

```
extension/
├── algovoi/                          ← Hosted Checkout extension
│   ├── admin/
│   │   ├── controller/payment/algovoi.php
│   │   ├── language/en-gb/payment/algovoi.php
│   │   └── view/template/payment/algovoi.twig
│   └── catalog/
│       ├── controller/payment/algovoi.php
│       ├── model/payment/algovoi.php
│       ├── language/en-gb/payment/algovoi.php
│       └── view/template/payment/algovoi.twig
│
└── algovoi_ext/                      ← Extension Payment extension
    ├── admin/
    │   ├── controller/payment/algovoi_ext.php
    │   ├── language/en-gb/payment/algovoi_ext.php
    │   └── view/template/payment/algovoi_ext.twig
    └── catalog/
        ├── controller/payment/algovoi_ext.php
        ├── model/payment/algovoi_ext.php
        ├── language/en-gb/payment/algovoi_ext.php
        ├── view/template/payment/algovoi_ext.twig       ← checkout panel
        └── view/template/payment/algovoi_ext_pending.twig ← in-page payment UI
```

### Copy files to server

```bash
# Hosted Checkout
scp -r opencart/algovoi/ root@<server-ip>:/var/www/html/opencart/extension/algovoi/

# Extension Payment
scp -r opencart/algovoi_ext/ root@<server-ip>:/var/www/html/opencart/extension/algovoi_ext/
```

### Important: autoloader path fix

OpenCart 4's autoloader maps `Opencart\Catalog\Model\*` to `catalog/model/`, not `extension/`. Both model files must also be placed at the path the autoloader expects:

```bash
# On the server:
mkdir -p /var/www/html/opencart/catalog/model/extension/algovoi/payment/
cp /var/www/html/opencart/extension/algovoi/catalog/model/payment/algovoi.php \
   /var/www/html/opencart/catalog/model/extension/algovoi/payment/algovoi.php

mkdir -p /var/www/html/opencart/catalog/model/extension/algovoi_ext/payment/
cp /var/www/html/opencart/extension/algovoi_ext/catalog/model/payment/algovoi_ext.php \
   /var/www/html/opencart/catalog/model/extension/algovoi_ext/payment/algovoi_ext.php
```

> This is required because OpenCart 4's `Factory::model()` generates class names under the `Opencart\Catalog\Model\` namespace, which the autoloader resolves to `DIR_APPLICATION` (`catalog/`), not `DIR_EXTENSION`. The extension directory copy is used by the framework for path registration; the `catalog/` copy is what PHP actually loads.

---

## Step 4 — Register in the database

Run the following SQL against your OpenCart database. Replace `@install_id` values if inserting manually.

### Hosted Checkout (`algovoi`)

```sql
-- Extension install record
INSERT INTO oc_extension_install (name, code, version, author, link, status, date_added)
VALUES ('AlgoVoi Hosted Checkout', 'algovoi', '1.0.0', 'AlgoVoi', '', 1, NOW());

SET @install_id = LAST_INSERT_ID();

-- Extension type registration
INSERT INTO oc_extension (extension, type, code)
VALUES ('algovoi', 'payment', 'algovoi');

-- File path registration
INSERT INTO oc_extension_path (extension_install_id, path) VALUES
(@install_id, 'extension/algovoi/catalog/controller/payment/algovoi.php'),
(@install_id, 'extension/algovoi/catalog/model/payment/algovoi.php'),
(@install_id, 'extension/algovoi/catalog/language/en-gb/payment/algovoi.php'),
(@install_id, 'extension/algovoi/catalog/view/template/payment/algovoi.twig'),
(@install_id, 'extension/algovoi/admin/controller/payment/algovoi.php'),
(@install_id, 'extension/algovoi/admin/language/en-gb/payment/algovoi.php'),
(@install_id, 'extension/algovoi/admin/view/template/payment/algovoi.twig');

-- Settings
INSERT INTO oc_setting (store_id, code, `key`, value, serialized) VALUES
(0, 'payment_algovoi', 'payment_algovoi_status',              '1',                                     0),
(0, 'payment_algovoi', 'payment_algovoi_api_base_url',        'https://api1.ilovechicken.co.uk',        0),
(0, 'payment_algovoi', 'payment_algovoi_tenant_id',           '<your-tenant-uuid>',                     0),
(0, 'payment_algovoi', 'payment_algovoi_admin_api_key',       'algv_<your-tenant-api-key>',             0),
(0, 'payment_algovoi', 'payment_algovoi_webhook_secret',      '<your-webhook-secret>',                  0),
(0, 'payment_algovoi', 'payment_algovoi_preferred_network',   'algorand_mainnet',                       0),
(0, 'payment_algovoi', 'payment_algovoi_pending_status_id',   '1',                                      0),
(0, 'payment_algovoi', 'payment_algovoi_complete_status_id',  '5',                                      0),
(0, 'payment_algovoi', 'payment_algovoi_sort_order',          '1',                                      0)
ON DUPLICATE KEY UPDATE value = VALUES(value);
```

### Extension Payment (`algovoi_ext`)

```sql
INSERT INTO oc_extension_install (name, code, version, author, link, status, date_added)
VALUES ('AlgoVoi Extension Payment', 'algovoi_ext', '1.0.0', 'AlgoVoi', '', 1, NOW());

SET @install_id = LAST_INSERT_ID();

INSERT INTO oc_extension (extension, type, code)
VALUES ('algovoi_ext', 'payment', 'algovoi_ext');

INSERT INTO oc_extension_path (extension_install_id, path) VALUES
(@install_id, 'extension/algovoi_ext/catalog/controller/payment/algovoi_ext.php'),
(@install_id, 'extension/algovoi_ext/catalog/model/payment/algovoi_ext.php'),
(@install_id, 'extension/algovoi_ext/catalog/language/en-gb/payment/algovoi_ext.php'),
(@install_id, 'extension/algovoi_ext/catalog/view/template/payment/algovoi_ext.twig'),
(@install_id, 'extension/algovoi_ext/catalog/view/template/payment/algovoi_ext_pending.twig'),
(@install_id, 'extension/algovoi_ext/admin/controller/payment/algovoi_ext.php'),
(@install_id, 'extension/algovoi_ext/admin/language/en-gb/payment/algovoi_ext.php'),
(@install_id, 'extension/algovoi_ext/admin/view/template/payment/algovoi_ext.twig');

INSERT INTO oc_setting (store_id, code, `key`, value, serialized) VALUES
(0, 'payment_algovoi_ext', 'payment_algovoi_ext_status',     '1', 0),
(0, 'payment_algovoi_ext', 'payment_algovoi_ext_sort_order', '2', 0)
ON DUPLICATE KEY UPDATE value = VALUES(value);
```

> `algovoi_ext` inherits API credentials from the `algovoi` settings (`payment_algovoi_tenant_id`, `payment_algovoi_admin_api_key`, `payment_algovoi_webhook_secret`, `payment_algovoi_preferred_network`). No separate credential settings are needed.

---

## Gateway 1: AlgoVoi Hosted Checkout

**OpenCart setting key:** `payment_algovoi`

| Setting key | Description |
|-------------|-------------|
| `payment_algovoi_status` | `1` = enabled |
| `payment_algovoi_api_base_url` | Base URL of the AlgoVoi API |
| `payment_algovoi_tenant_id` | Your AlgoVoi tenant UUID |
| `payment_algovoi_admin_api_key` | Tenant API key (`algv_...`) — used as Bearer token for `/v1/payment-links` |
| `payment_algovoi_webhook_secret` | HMAC-SHA256 secret for verifying inbound webhook callbacks |
| `payment_algovoi_preferred_network` | `algorand_mainnet` or `voi_mainnet` |
| `payment_algovoi_pending_status_id` | OpenCart order status ID for "awaiting payment" (default: 1 = Pending) |
| `payment_algovoi_complete_status_id` | OpenCart order status ID for "paid" (default: 5 = Complete) |

**Payment flow:**

1. Customer completes checkout, clicks **Confirm Order**
2. OpenCart AJAX calls `extension/algovoi/payment/algovoi.confirm`
3. Controller POSTs to `POST /v1/payment-links`:
   ```http
   POST https://api1.ilovechicken.co.uk/v1/payment-links
   Authorization: Bearer algv_...
   X-Tenant-Id: <tenant-uuid>
   Content-Type: application/json

   {
     "amount": 49.99,
     "currency": "USD",
     "label": "Order #123",
     "preferred_network": "algorand_mainnet",
     "redirect_url": "https://yourstore.com/index.php?route=checkout/success",
     "expires_in_seconds": 3600
   }
   ```
4. API returns HTTP **201** with `checkout_url`
5. Browser redirected to `checkout_url`
6. On payment, AlgoVoi calls the webhook to update the order status

> **Note:** The AlgoVoi `/v1/payment-links` endpoint returns **HTTP 201**, not 200. Check for both in your HTTP client code.

> **`amount`** is in **major currency units** (e.g. `49.99`), not microunits.

---

## Gateway 2: AlgoVoi Extension Payment

**OpenCart setting key:** `payment_algovoi_ext`

This gateway lets customers with the **AlgoVoi browser extension** pay directly from the store. No external redirect — the transaction is built, signed, and submitted entirely within the browser.

**Requirements:**
- Customer must have the AlgoVoi browser extension installed.
- `algosdk` is loaded from jsDelivr CDN on the pending payment page — no additional setup.
- Store must be served over HTTPS (required by `window.algorand`).

**On-chain payment flow:**

```
Customer selects "AlgoVoi - Pay via Extension" → Confirm Order
          ↓
confirm() POSTs to /v1/payment-links → gets checkout_url
          ↓
Server fetches checkout page HTML, scrapes:
  • receiver address  (id="addr" — 58-char Algorand base32 address)
  • memo              (id="memo" — format: "algovoi:{token}")
  • chain and asset details derived from link response
          ↓
Payment details stored in session, order set to Pending
          ↓
Browser redirected to /extension/algovoi_ext/payment/algovoi_ext.pending
          ↓
Pending page renders extension payment UI:
  → algosdk loaded from CDN
  → window.algorand.enable() called with genesis hash (chain detection)
  → ASA transfer transaction built with suggestedParams from algod
  → window.algorand.signAndSendTransactions() signs the tx
  → Signed bytes submitted to algod POST /v2/transactions
  → algod pending tx polled until confirmed-round > 0 (up to 60 s)
  → 4 s pause for indexer catch-up
          ↓
Browser POSTs to extension/algovoi_ext/payment/algovoi_ext.verify:
  { "tx_id": "<algod-tx-id>" }
          ↓
Server proxies to POST /checkout/{token}/verify on AlgoVoi API
          ↓
On success: order → Complete, browser redirected to checkout/success
```

**Session data stored on `confirm()`:**

| Key | Contents |
|-----|----------|
| `algovoi_ext.token` | AlgoVoi checkout token (from `checkout_url`) |
| `algovoi_ext.checkout_url` | Full hosted checkout URL (fallback link) |
| `algovoi_ext.receiver` | On-chain receiver address (scraped from checkout page) |
| `algovoi_ext.memo` | Transaction note — `algovoi:{token}` |
| `algovoi_ext.amount_display` | Human-readable amount (e.g. `0.05`) |
| `algovoi_ext.ticker` | `USDC` or `aUSDC` |
| `algovoi_ext.asset_id` | Integer ASA ID (31566704 or 302190) |
| `algovoi_ext.amount_mu` | Amount in microunits (amount × 10⁶) |
| `algovoi_ext.algod_url` | Algod base URL for the chain |
| `algovoi_ext.chain` | `algorand-mainnet` or `voi-mainnet` |

**Algod configuration (hardcoded in controller):**

| Chain | Algod URL | Asset ID | Ticker |
|-------|-----------|----------|--------|
| `algorand-mainnet` | `https://mainnet-api.algonode.cloud` | 31566704 | USDC |
| `voi-mainnet` | `https://mainnet-api.voi.nodely.io` | 302190 | aUSDC |

**Verify endpoint:**

```
POST /index.php?route=extension/algovoi_ext/payment/algovoi_ext.verify
Content-Type: application/json

{ "tx_id": "<algod-tx-id>" }
```

- Requires active session with `algovoi_ext.token` set.
- Proxies to `POST https://api1.ilovechicken.co.uk/checkout/{token}/verify`.
- On success: order status updated to Complete with history comment `AlgoVoi extension payment confirmed. TX: {tx_id}`.
- Session `algovoi_ext` key cleared on success.

If the AlgoVoi extension is not detected (`window.algorand.isAlgoVoi` is falsy), a fallback link to the hosted checkout page is shown automatically.

---

## OpenCart 4 — Known Implementation Notes

### `getMethods()` requires customer session

OpenCart 4's `checkout/payment_method.getMethods` endpoint requires `session['customer']` to be set. Payment methods are loaded via AJAX **after** the customer completes the Account step (guest checkout or login). The payment option will not appear until the guest name/email form is submitted.

### HTTP 201 from `/v1/payment-links`

The AlgoVoi payment links API returns **HTTP 201 Created**, not 200. Any integration must check for both:

```php
if ($http_code === 200 || $http_code === 201) { ... }
```

### `amount` field is major units

`/v1/payment-links` expects `amount` as a decimal value in major currency units (e.g. `49.99` for $49.99), not microunits. The response `amount_microunits` field is in microunits — use this value when building the on-chain ASA transfer.

### Tenant API key, not admin key

`/v1/payment-links` requires a **tenant API key** (`algv_...`), not the admin key (`ak_...`). Create a tenant key via:

```http
POST /api/tenants/{tenant_id}/api-keys
Authorization: Bearer <admin-key>
```

New tenant keys have no expiry by default. The plaintext key is shown once at creation.

### Autoloader path

See Step 3 above. This is the most common cause of `Could not load model extension/algovoi/payment/algovoi` errors. Both the `extension/` path (for framework registration) and the `catalog/model/extension/` path (for PHP autoloading) must contain the model file.

---

## Troubleshooting

| Symptom | Likely cause |
|---------|-------------|
| Payment method not shown at checkout | Guest/account step not completed — `session['customer']` not set |
| `Could not load model extension/algovoi/payment/algovoi` | Model file missing from `catalog/model/extension/algovoi/payment/` — see autoloader path fix |
| `Payment could not be initiated` | HTTP status check failing — API returns 201, not 200; or tenant API key has no DB record |
| HTTP 401 from `/v1/payment-links` | Using admin key instead of tenant API key, or tenant key not in `control_plane.api_keys` |
| `checkout_url` not returned | API key valid but tenant has no network config — run Step 1 |
| Extension payment page blank | Session expired or `algovoi_ext` session key cleared — customer must restart checkout |
| `window.algorand` undefined | AlgoVoi browser extension not installed, or store not on HTTPS |
| `Transaction not confirmed after timeout` | Network congestion — customer can retry; transaction may still confirm on-chain |

---

## Supported networks

| Network | Asset | Algod |
|---------|-------|-------|
| `algorand_mainnet` | USDC (ASA 31566704) | `mainnet-api.algonode.cloud` |
| `voi_mainnet` | aUSDC (ARC200 app 302190) | `mainnet-api.voi.nodely.io` |
| `algorand_testnet` | Test USDC | For integration testing only |
| `voi_testnet` | Test aUSDC | For integration testing only |

---

## Server hardening (nginx + fail2ban)

OpenCart is served by nginx. There is no `.htaccess` on nginx — all access control lives in the nginx site config.

### Rate limiting

Three limit zones are defined at the `http` level (outside `server {}`):

```nginx
limit_req_zone $binary_remote_addr zone=oc_admin:10m    rate=30r/m;
limit_req_zone $binary_remote_addr zone=oc_checkout:10m rate=20r/m;
limit_req_zone $binary_remote_addr zone=oc_login:10m    rate=5r/m;
```

Applied to:

| Location | Zone | Burst |
|----------|------|-------|
| `/admin` (all admin requests) | `oc_admin` | 10 |
| `/admin/index.php` (admin login) | `oc_login` | 3 |
| `index.php?route=checkout/*` | `oc_checkout` | 5 |
| `index.php?route=account/login` | `oc_login` | 3 |

All rate-limited locations return HTTP 429 on breach.

### Blocked paths

| Pattern | Reason |
|---------|--------|
| `/config.php`, `/admin/config.php` | Contains DB credentials |
| `/system/storage/` | Never publicly accessible |
| `/image/**.(php\|phtml\|...)` | Webshell prevention |
| `/download/**.(php\|...)` | Webshell prevention |
| `*.(engine\|inc\|sql\|bak\|log\|tpl)` | Sensitive file extensions |
| `readme.txt`, `CHANGELOG.md` etc. | Version disclosure |
| `/system/engine/`, `/system/library/` | Core PHP files |
| `/\.` (hidden files) | `.git`, `.env`, `.htaccess` etc. |

### Security headers

```
X-Frame-Options: SAMEORIGIN
X-Content-Type-Options: nosniff
X-XSS-Protection: 1; mode=block
Referrer-Policy: strict-origin-when-cross-origin
Permissions-Policy: camera=(), microphone=(), geolocation=(), payment=()
Strict-Transport-Security: max-age=31536000; includeSubDomains
```

PHP version is hidden via `fastcgi_hide_header X-Powered-By`.

### fail2ban

The `opencart-admin` jail watches `/var/log/nginx/error.log` using the built-in `nginx-limit-req` filter. An IP that triggers 10 rate-limit rejections within 60 seconds is banned for 10 minutes.

```ini
[opencart-admin]
enabled   = true
filter    = nginx-limit-req
logpath   = /var/log/nginx/error.log
maxretry  = 10
findtime  = 60
bantime   = 600
```

Check banned IPs: `fail2ban-client status opencart-admin`

---

## Live test status

Confirmed end-to-end on **2026-04-14** against `api1.ilovechicken.co.uk`, OpenCart 4.1.0.3 at `opencart.ilovechicken.co.uk`:

| Test | Network | Result |
|------|---------|--------|
| Webhook → checkout link | `algorand_mainnet` (USDC (ASA 31566704)) | Pass |
| Webhook → checkout link | `algorand_mainnet` (USDC (ASA 31566704)) | Pass |
| Webhook → checkout link | `algorand_mainnet` (USDC (ASA 31566704)) | Pass |
| Both payment methods visible at checkout after guest step | — | Pass |
| Webhook → checkout link | `voi_mainnet` (WAD (ARC200 app ID 47138068)) | Pass |
| Webhook → checkout link | `hedera_mainnet` (USDC (token 0.0.456858)) | Pass |
| Webhook → checkout link | `stellar_mainnet` (USDC (Circle)) | Pass |
