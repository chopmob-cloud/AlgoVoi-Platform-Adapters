# Shopware 6 Integration — AlgoVoi Tenant Services

Accept **USDC on Algorand** and **aUSDC on VOI** as payment in your Shopware 6 store via two installable plugins.

Live-tested on **Shopware 6.7.8.2 CE** against `api1.ilovechicken.co.uk` — 2026-04-02.

---

## What is included

| Item | Path | Description |
|------|------|-------------|
| Payment plugin | `shopware/AlgovoiPayment/` | Payment handlers, webhook controller, wallet pending controller |
| Theme plugin | `shopware/AlgovoiTheme/` | Dark theme CSS injection, branding overrides, search removal |
| Dark theme CSS | `shopware/algovoi.css` | Full dark theme stylesheet |
| Product import script | `shopware/import-products.php` | CLI script to seed demo digital products |
| nginx config | `nginx/shopware.conf` | Hardened virtual host with admin basic-auth and fail2ban config |

---

## Architecture

Two payment methods are registered by `AlgovoiPayment`:

| Technical name | Label | Flow |
|----------------|-------|------|
| `algovoi_hosted` | AlgoVoi Checkout (USDC / aUSDC) | Shopware redirects customer to AlgoVoi-hosted checkout page |
| `algovoi_wallet` | AlgoVoi Wallet (USDC / aUSDC) | In-store wallet signing page using Pera / Defly / Lute browser extension |

```
Customer places order → selects AlgoVoi payment method
            ↓
AlgovoiHostedPaymentHandler OR AlgovoiWalletPaymentHandler
            ↓
POST /v1/payment-links → AlgoVoi API creates checkout link
            ↓
[Hosted] Customer redirected to AlgoVoi checkout URL
[Wallet] Customer signs ASA transfer in browser extension
            ↓
AlgoVoi verifies on-chain transaction
            ↓
POST /algovoi/webhook → AlgovoiWebhookController
            ↓
OrderTransactionStateHandler marks transaction Paid
```

---

## Prerequisites

- Shopware 6.6+ (tested on 6.7.8.2 CE) — self-hosted
- PHP 8.2+, Composer
- An active AlgoVoi tenant account with API key and tenant ID
- The merchant wallet opted in to USDC (ASA 31566704) on Algorand and/or aUSDC (app ID 302190) on VOI

---

## Step 1 — Configure your AlgoVoi network

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

## Step 2 — Install the plugins

Copy both plugin directories into your Shopware installation:

```bash
cp -r AlgovoiPayment /var/www/html/shopware/custom/plugins/
cp -r AlgovoiTheme  /var/www/html/shopware/custom/plugins/

cd /var/www/html/shopware
sudo -u www-data php bin/console plugin:refresh
sudo -u www-data php bin/console plugin:install --activate AlgovoiPayment
sudo -u www-data php bin/console plugin:install --activate AlgovoiTheme
sudo -u www-data php bin/console cache:warmup
```

---

## Step 3 — Configure the payment plugin

In Shopware Admin go to **Extensions → My Extensions → AlgoVoi Payment → Configure** and set:

| Field | Value |
|-------|-------|
| API Base URL | `https://api1.ilovechicken.co.uk` (or your AlgoVoi instance) |
| API Key | Your tenant API key |
| Tenant ID | Your tenant UUID |
| Network | `algorand_mainnet` or `voi_mainnet` |
| Webhook Secret | Any random string — register the same value in AlgoVoi |

Alternatively set values directly in `system_config`:

```sql
INSERT INTO system_config (id, configuration_key, configuration_value, created_at)
VALUES
  (UNHEX(REPLACE(UUID(),'-','')), 'AlgovoiPayment.config.apiBaseUrl',    '{"_value":"https://api1.ilovechicken.co.uk"}', NOW()),
  (UNHEX(REPLACE(UUID(),'-','')), 'AlgovoiPayment.config.apiKey',         '{"_value":"<your-api-key>"}', NOW()),
  (UNHEX(REPLACE(UUID(),'-','')), 'AlgovoiPayment.config.tenantId',       '{"_value":"<your-tenant-id>"}', NOW()),
  (UNHEX(REPLACE(UUID(),'-','')), 'AlgovoiPayment.config.network',        '{"_value":"algorand_mainnet"}', NOW()),
  (UNHEX(REPLACE(UUID(),'-','')), 'AlgovoiPayment.config.webhookSecret',  '{"_value":"<your-webhook-secret>"}', NOW());
```

---

## Step 4 — Assign payment methods to your sales channel

The plugin registers the payment methods on install. Add them to your storefront sales channel via Admin:

**Sales Channels → Storefront → Payment and shipping → Payment methods → add AlgoVoi Checkout and AlgoVoi Wallet**

Or via SQL (replace `<sales_channel_id>` and `<payment_method_id>` with actual UUIDs):

```sql
INSERT IGNORE INTO sales_channel_payment_method (sales_channel_id, payment_method_id)
VALUES (UNHEX('<sales_channel_id>'), UNHEX('<payment_method_id>'));

-- Also update the denormalised ID column:
UPDATE sales_channel
SET payment_method_ids = JSON_ARRAY_APPEND(payment_method_ids, '$', '<payment_method_id_hex>')
WHERE id = UNHEX('<sales_channel_id>');
```

> **Important:** Shopware caches payment method IDs in a denormalised `payment_method_ids` JSON column on the `sales_channel` table. If you insert directly into the join table you must also update this column, or the checkout validator will block the methods.

---

## Step 5 — Register the AlgoVoi webhook

In your AlgoVoi Control Plane dashboard register:

```
https://yourstore.com/algovoi/webhook
```

Event: `payment.confirmed`

The webhook controller at `AlgovoiWebhookController.php` verifies the `X-AlgoVoi-Signature` HMAC-SHA256 header and matches the payment by the order label (`Order #XXXXX`).

---

## Step 6 — Deactivate default payment methods (optional)

To present only AlgoVoi methods at checkout, deactivate the built-in Shopware methods in Admin:

**Settings → Payment methods → Cash on delivery / Invoice / Paid in advance → toggle off**

---

## Wallet extension flow (AlgoVoi Wallet)

The `algovoi_wallet` payment method uses a Shopware-hosted signing page:

1. `AlgovoiWalletPaymentHandler` creates a payment link, scrapes the receiver address and memo, stores them in the order transaction `customFields`, and redirects to `/algovoi/wallet-pending/{txId}`
2. The pending page (`wallet-pending.html.twig`) loads algosdk v3 from CDN
3. The customer connects their Pera, Defly, or Lute wallet via the ARC-0027 `window.algorand` interface
4. An ASA transfer transaction is built using `algosdk.makeAssetTransferTxnWithSuggestedParamsFromObject`
5. Signed via `window.algorand.signTransactions([{ txn: b64Txn }])`
6. Submitted to the algod node, then `algosdk.waitForConfirmation` waits for on-chain confirmation
7. `POST /algovoi/verify` confirms with the AlgoVoi API and marks the Shopware transaction as Paid

Supported wallets: **Pera Wallet**, **Defly**, **Lute** (any ARC-0027-compliant browser extension).

---

## Theme plugin (AlgovoiTheme)

`AlgovoiTheme` applies a dark colour scheme to the Shopware Storefront and removes default Shopware branding:

| Override | Effect |
|----------|--------|
| `layout/meta.html.twig` | Injects `algovoi.css` into `<head>` on all page types |
| `layout/header/logo.html.twig` | Replaces Shopware logo image with **Algo**`Voi` text |
| `layout/header/header.html.twig` | Removes search bar from header |
| `layout/header/header-minimal.html.twig` | Removes contact block from minimal header |
| `layout/footer/footer.html.twig` | Removes "Service hotline" and "Realised with Shopware" blocks |

CSS palette: `#0f1117` background · `#e2e8f0` text · `#3b82f6` accent.

Copy `algovoi.css` to your Shopware `public/` directory:

```bash
cp algovoi.css /var/www/html/shopware/public/algovoi.css
```

---

## Product import

`import-products.php` is a CLI script to seed demo digital products. Edit the `$products` array and the hardcoded IDs (`$currencyId`, `$salesChannelId`, `$taxId`, `$languageId`) for your instance, then run:

```bash
DATABASE_URL="mysql://user:pass@localhost:3306/shopware" \
  sudo -E -u www-data php import-products.php
```

---

## Server hardening

See `nginx/shopware.conf` for the production-ready nginx virtual host. Key features:

| Feature | Detail |
|---------|--------|
| Admin IP whitelist | Restricts `/admin` to a single IP |
| HTTP Basic Auth | Second factor on `/admin` via `auth_basic` |
| Rate limiting | 20 req/min on admin, 5 req/min on store-api login |
| `server_tokens off` | Hides nginx version |
| Security headers | HSTS preload, X-Frame-Options, CSP-ready Permissions-Policy |
| Blocked paths | `/vendor`, `/var`, `/config`, `/src`, dotfiles, `.log/.sql/.env` |
| PHP execution block | Prevents PHP execution in `/public/media/` |

Create the basic-auth credentials file:

```bash
htpasswd -bc /etc/nginx/.htpasswd_sw_admin <username> <password>
chmod 640 /etc/nginx/.htpasswd_sw_admin
chown root:www-data /etc/nginx/.htpasswd_sw_admin
```

**fail2ban jails** (create in `/etc/fail2ban/jail.d/shopware.conf`):

```ini
[shopware-admin]
enabled  = true
port     = http,https
filter   = shopware-admin
logpath  = /var/log/nginx/access.log
maxretry = 5
findtime = 300
bantime  = 3600

[shopware-login]
enabled  = true
port     = http,https
filter   = shopware-login
logpath  = /var/log/nginx/access.log
maxretry = 10
findtime = 300
bantime  = 1800
```

---

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| Payment method shows "blocked" | `payment_method_ids` JSON column not updated | Run `JSON_ARRAY_APPEND` UPDATE on `sales_channel` table and clear `cache.object` |
| "Unfortunately, something went wrong" on wallet page | `setTwig` called on controller | Remove `<call method="setTwig">` from `services.xml` — not present in SW 6.7 |
| "ARC27_SIGN_TXNS: txns must be an array" | Wrong `signTransactions` argument format | Pass array directly: `signTransactions([{ txn: b64 }])` not `signTransactions({ txns: [...] })` |
| "Transaction not found" on verify | Transaction not yet confirmed on-chain | Call `algosdk.waitForConfirmation(client, txHash, 10)` before calling `/algovoi/verify` |
| CSS not applied on product pages | `product-detail.html.twig` replaces `base_head` without `parent()` | Inject CSS via `layout/meta.html.twig` override instead of `base.html.twig` |
| Webhook 401 | HMAC mismatch | Check `webhookSecret` matches value registered in AlgoVoi dashboard |
| Plugin install "technicalName should not be blank" | Old `AlgovoiPayment.php` missing `technicalName` | Ensure `'technicalName' => 'algovoi_hosted'` is set in `onInstall` |

---

## Supported networks

| Network | Asset | ASA / App ID |
|---------|-------|-------------|
| `algorand_mainnet` | USDC | ASA 31566704 |
| `voi_mainnet` | aUSDC | App ID 302190 |

---

## Live test status

Tested end-to-end on **2026-04-02** — Shopware 6.7.8.2 CE — `shopware.ilovechicken.co.uk`

| Test | Network | Result |
|------|---------|--------|
| Hosted checkout — place order, pay, webhook confirms | `algorand_mainnet` | Pass |
| Wallet extension — sign ASA transfer in Pera, on-chain verify | `algorand_mainnet` | Pass |
| Webhook → checkout link | `voi_mainnet` (WAD (ARC200 app ID 47138068)) | Pass |
| Webhook → checkout link | `hedera_mainnet` (USDC (token 0.0.456858)) | Pass |
| Webhook → checkout link | `stellar_mainnet` (USDC (Circle)) | Pass |
