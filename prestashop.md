# PrestaShop — AlgoVoi Payment Modules

Two payment modules are provided for PrestaShop 8.x:

| Module | Folder | Flow |
|--------|--------|------|
| `algovoi` | `prestashop/algovoi/` | Hosted checkout — redirects buyer to AlgoVoi payment page (Algorand, VOI, Hedera, Stellar) |
| `algovoi_ext` | `prestashop/algovoi_ext/` | Wallet checkout — buyer signs in-browser via Pera / Defly / Lute (Algorand + VOI only; the AlgoVoi extension does not currently sign Hedera or Stellar transactions) |

Both modules were developed and tested against **PrestaShop 8.2.5** (not 9.x, which has no prebuilt installer as of early 2026) running on MariaDB.

---

## Overview

### algovoi (Hosted Checkout)

1. Buyer chooses "Pay with AlgoVoi (USDC on Algorand/Hedera/Stellar, aUSDC on VOI)" at checkout.
2. Buyer picks the network via a radio group — Algorand, VOI, Hedera, or Stellar.
3. PrestaShop creates an order in **Awaiting Payment** state and calls the AlgoVoi API to create a payment link (`/v1/payment-links`) with the selected `preferred_network`.
4. Buyer is redirected to the AlgoVoi hosted checkout page, which shows the correct ticker (USDC/aUSDC/HBAR/XLM) and memo format (`algovoi:{token}` on Algo/VOI/Hedera, or short-form `av:{token[:20]}` on Stellar to fit the 28-byte MEMO_TEXT limit).
5. On return, the `confirm` controller advances the order to **Payment Accepted**.
6. A webhook endpoint is available for server-side confirmation.

**Supported chains & assets for hosted checkout:**

| Chain | Network value | Native | Stablecoin |
|-------|---------------|--------|------------|
| Algorand | `algorand_mainnet` / `algorand_testnet` | ALGO (6 dp) | USDC (ASA 31566704) |
| VOI | `voi_mainnet` / `voi_testnet` | VOI (6 dp) | aUSDC (ARC200 app 302190) |
| Hedera | `hedera_mainnet` | HBAR (8 dp) | USDC (HTS 0.0.456858) |
| Stellar | `stellar_mainnet` / `stellar_testnet` | XLM (7 dp) | USDC (issuer `GA5ZSEJYB37JRC5AVCIA5MOP4RHTM335X2KGX3IHOJAPP5RE34K4KZVN`) |

> **Stellar USDC note:** The receiving Stellar account must have an established trust line to the Circle USDC asset (`USDC:GA5ZSEJYB37JRC5AVCIA5MOP4RHTM335X2KGX3IHOJAPP5RE34K4KZVN`) before it can accept USDC payments. Configure the trust line once in your Stellar wallet — similar to opting in to an Algorand ASA.

### algovoi_ext (Wallet Checkout)

1. Buyer chooses "Pay with AlgoVoi Wallet" at checkout.
2. PrestaShop calls the AlgoVoi API to create a payment request (`/v1/payment-requests`).
3. The buyer is shown an in-page signing UI. JavaScript calls `window.algorand.signAndSendTransactions()` via the browser wallet extension.
4. The signed transaction is submitted to algod, confirmed on-chain, then verified via the AlgoVoi API.
5. On confirmation the order is advanced to Payment Accepted and the buyer is redirected.
6. A webhook endpoint provides server-side settlement confirmation.

---

## Prerequisites

- PrestaShop 8.2.5 installed (use the official zip installer; 9.x has no prebuilt installer).
- PHP 8.1+ with `curl` and `json` extensions enabled.
- MySQL / MariaDB 10.x.
- An AlgoVoi account with a tenant ID, API key, and webhook secret.
- (For `algovoi_ext`) Buyers need Pera Wallet, Defly, or Lute browser extension installed.

---

## Installation

### 1. Copy module folders

```bash
cp -r prestashop/algovoi     /var/www/html/prestashop/modules/
cp -r prestashop/algovoi_ext /var/www/html/prestashop/modules/
chown -R www-data:www-data /var/www/html/prestashop/modules/algovoi
chown -R www-data:www-data /var/www/html/prestashop/modules/algovoi_ext
```

### 2. Install via CLI

```bash
cd /var/www/html/prestashop
php bin/console prestashop:module install algovoi
php bin/console prestashop:module install algovoi_ext
```

### 3. Required DB fixes for payment modules to appear at checkout

PrestaShop 8.x payment modules will silently not appear unless the following rows exist. Run these after install (replace `1`/`2` with the actual `id_module` values):

```sql
-- Find module IDs
SELECT id_module, name FROM ps_module WHERE name IN ('algovoi', 'algovoi_ext');

-- ps_module_country: insert all active countries (id_currency must be real IDs, not 0)
INSERT IGNORE INTO ps_module_country (id_module, id_shop, id_country)
  SELECT 1, 1, id_country FROM ps_country WHERE active = 1;
INSERT IGNORE INTO ps_module_country (id_module, id_shop, id_country)
  SELECT 2, 1, id_country FROM ps_country WHERE active = 1;

-- ps_module_currency: must be -1 (all currencies), NOT 0
INSERT IGNORE INTO ps_module_currency (id_module, id_shop, id_currency) VALUES (1, 1, -1);
INSERT IGNORE INTO ps_module_currency (id_module, id_shop, id_currency) VALUES (2, 1, -1);

-- ps_module_carrier: must be empty for virtual/download products
-- DELETE FROM ps_module_carrier WHERE id_module IN (1, 2);
```

Clear cache after:

```bash
rm -rf /var/www/html/prestashop/var/cache/prod/smarty/compile/*
rm -rf /var/www/html/prestashop/var/cache/prod/smarty/cache/*
```

---

## Configuration

Go to **Back Office → Modules → Module Manager**, find each module, click **Configure**.

| Field | Value |
|-------|-------|
| API Base URL | `https://api1.ilovechicken.co.uk` |
| Tenant ID | Your AlgoVoi tenant ID |
| API Key | Your AlgoVoi API key |
| Preferred Network | Default network when customer makes no selection. One of: `algorand_mainnet`, `algorand_testnet`, `voi_mainnet`, `voi_testnet`, `hedera_mainnet`, `stellar_mainnet`, `stellar_testnet`. The hosted module also renders a chain picker so the buyer can override per order. |
| Webhook Secret | Your webhook HMAC secret |
| Pending Status ID | `1` (Awaiting Payment) |
| Complete Status ID | `5` (Payment Accepted) |

---

## Webhook Setup

Register these URLs in your AlgoVoi merchant dashboard:

| Module | Webhook URL |
|--------|-------------|
| algovoi | `https://yourshop.com/module/algovoi/webhook` |
| algovoi_ext | `https://yourshop.com/module/algovoi_ext/webhook` |

The webhook controller verifies `X-AlgoVoi-Signature` (HMAC-SHA256, base64-encoded). On a valid `payment.confirmed` event with `label` matching `Cart #N`, it advances the order to the complete status.

---

## Dark Theme

The demo store uses a full dark theme (`#0f1117` background, `#e2e8f0` text, `#3b82f6` accent). All theme overrides live in one file:

```
prestashop/theme/algovoi.css
```

Inject it from the theme's `head.tpl`:

```smarty
<link rel="stylesheet" href="{$urls.theme_assets}css/algovoi.css?v=18">
```

Copy to the server:

```bash
cp prestashop/theme/algovoi.css /var/www/html/prestashop/themes/classic/assets/css/
```

The layout template (`prestashop/theme/templates/layout-both-columns.tpl`) also contains two JS injections:
- **Placeholder image bust** — rewrites `en-default-*.jpg` to `-v2` variants to bypass Cloudflare cache.
- **Footer column cleanup** — removes "Products" and "Our Company" footer columns by heading text (Cloudflare HTML cache bypass).

---

## Nginx Hardening

Hardened nginx configs for all three storefronts are in `nginx/`:

| File | Site |
|------|------|
| `nginx/prestashop.conf` | prestashop.ilovechicken.co.uk |
| `nginx/opencart.conf` | opencart.ilovechicken.co.uk |
| `nginx/wordpress.conf` | 104.207.130.27 (WooCommerce) |

All three restrict admin access to a single whitelisted IP. Key rules:

- **PrestaShop**: `/admin` → `allow <IP>; deny all;` + rate limiting (20r/m admin, 5r/m login)
- **OpenCart**: `/admin` → `allow <IP>; deny all;` + rate limiting
- **WordPress**: `/wp-admin` + `/wp-login.php` + `/xmlrpc.php` → `allow <IP>; deny all;`

Sensitive paths blocked on all: `.env`, `*.log`, `*.sql`, `*.bak`, `vendor/`, `var/`, PHP in upload dirs.

Replace `YOUR_ADMIN_IP` in each file with your actual admin IP before deploying.

Deploy:

```bash
cp nginx/prestashop.conf /etc/nginx/sites-available/prestashop
cp nginx/opencart.conf   /etc/nginx/sites-available/opencart
cp nginx/wordpress.conf  /etc/nginx/sites-available/wordpress
nginx -t && nginx -s reload
```

---

## Currency Setup

Default currency is **USD**. EUR is also active.

To add USD if starting fresh:

```sql
-- Add USD
INSERT IGNORE INTO ps_currency
  (name, iso_code, numeric_iso_code, `precision`, conversion_rate, deleted, active, unofficial, modified)
VALUES ('US Dollar', 'USD', '840', 2, 1.08, 0, 1, 0, 0);

SET @usd = (SELECT id_currency FROM ps_currency WHERE iso_code='USD');

INSERT IGNORE INTO ps_currency_lang (id_currency, id_lang, name, symbol)
  SELECT @usd, id_lang, 'US Dollar', '$' FROM ps_lang;

INSERT IGNORE INTO ps_currency_shop (id_currency, id_shop, conversion_rate)
  SELECT @usd, id_shop, 1.08 FROM ps_shop;

-- Set as default
UPDATE ps_configuration SET value = @usd WHERE name = 'PS_CURRENCY_DEFAULT';

-- Fix EUR name if blank
UPDATE ps_currency SET name='Euro' WHERE iso_code='EUR';
UPDATE ps_currency_lang SET name='Euro', symbol='€'
  WHERE id_currency=(SELECT id_currency FROM ps_currency WHERE iso_code='EUR');
```

---

## UK Country & Postcode Fix

```sql
-- Enable United Kingdom
UPDATE ps_country SET active=1 WHERE iso_code='GB';

-- Fix UK postcode validation (default format rejects real UK postcodes)
UPDATE ps_country SET zip_code_format='' WHERE iso_code='GB';

-- Set store country to UK
INSERT INTO ps_configuration (name, value, date_add, date_upd)
VALUES ('PS_SHOP_COUNTRY_ID', 17, NOW(), NOW())
ON DUPLICATE KEY UPDATE value=17;
```

---

## Key Gotchas

### Payment module visibility requires correct DB state

Three tables must have correct rows or the module is silently skipped:

- **`ps_module_country`** — real country `id` values (not 0)
- **`ps_module_currency`** — `id_currency = -1` (not 0) meaning "all currencies"
- **`ps_module_carrier`** — must be **empty** for virtual/download products

### Smarty CSS/JS curly braces need `{literal}` blocks

```smarty
{literal}
<style>.my-class { color: #fff; }</style>
{/literal}
```

### `json_encode` Smarty modifier requires `nofilter`

```smarty
var data = {$myVar|json_encode nofilter};
```

Without `nofilter`, Smarty HTML-encodes the quotes and breaks the JSON.

### API key is visible in browser source (algovoi_ext)

`pending.tpl` passes the API key and tenant ID to the browser so the wallet signing JS can submit signed transactions. This is intentional — the key is needed client-side. Mitigate by using a scoped API key with submit-only permissions, or proxy the algod submit call through a server endpoint instead.

### AlgoVoi extension API — `signAndSendTransactions` call signature

```js
// Signs only — does NOT auto-submit to the network
var res = await window.algorand.signAndSendTransactions({
  txns: [{ txn: base64EncodedUnsignedTxnBytes }],
});
// res.stxns[0] = base64-encoded signed bytes — submit manually to algod
```

### PS 8.2.5, not 9.x

PrestaShop 9.x has no prebuilt zip installer as of early 2026. All work done on **8.2.5**.

---

## File Structure

```
prestashop/
  algovoi/
    algovoi.php
    controllers/front/
      payment.php         — creates payment link (/v1/payment-links), redirects buyer
      confirm.php         — return URL handler, advances order status
      webhook.php         — HMAC-verified server-side event handler
    views/templates/hook/
      payment_return.tpl

  algovoi_ext/
    algovoi_ext.php
    controllers/front/
      payment.php         — creates payment request (/v1/payment-requests), renders UI
      pending.php         — reads cookie, assigns Smarty vars for signing page
      verify.php          — proxies verify to AlgoVoi API, marks order complete
      webhook.php         — HMAC-verified server-side event handler
    views/templates/
      hook/payment_return.tpl
      front/pending.tpl   — in-page wallet signing UI (algosdk + window.algorand)

  theme/
    algovoi.css           — full dark theme override (v18)
    templates/
      layout-both-columns.tpl  — JS injections for image cache bust + footer cleanup
      head.tpl                 — algovoi.css link injection

nginx/
  prestashop.conf         — hardened nginx config, admin IP whitelist
  opencart.conf           — hardened nginx config, admin IP whitelist
  wordpress.conf          — hardened nginx config, wp-admin IP whitelist
```

---

## Live test status

Confirmed end-to-end on **2026-04-14** against `api1.ilovechicken.co.uk`:

| Test | Network | Result |
|------|---------|--------|
| Webhook → checkout link | `voi_mainnet` (WAD (ARC200 app ID 47138068)) | Pass |
| Webhook → checkout link | `hedera_mainnet` (USDC (token 0.0.456858)) | Pass |
| Webhook → checkout link | `stellar_mainnet` (USDC (Circle)) | Pass |
| Webhook → checkout link | `algorand_mainnet` (USDC (ASA 31566704)) | Pass |

Signature verified and checkout link generated. Asset: WAD (ARC200 app ID 47138068).
