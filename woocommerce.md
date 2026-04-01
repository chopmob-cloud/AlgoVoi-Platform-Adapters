# WooCommerce Integration — AlgoVoi Tenant Services

Accept **USDC on Algorand** and **aUSDC on VOI** as payment in your WooCommerce store via AlgoVoi.

---

## How it works

```
Customer places a WooCommerce order
            ↓
AlgoVoi receives webhook → verifies signature → parses order
            ↓
AlgoVoi creates a hosted checkout link (USDC or aUSDC)
            ↓
Customer pays on-chain
            ↓
AlgoVoi verifies the transaction on-chain
            ↓
WooCommerce order updated to 'processing' + TX ID added as order note
```

---

## Prerequisites

- An active AlgoVoi tenant account
- A WordPress site running WooCommerce
- WooCommerce REST API credentials (consumer key + secret) with `read/write` access to orders

---

## Step 1 — Configure your network

You need at least one network config with a payout address and your chosen stablecoin.

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

> ASA `31566704` is Circle's native USDC on Algorand mainnet.
> Your payout wallet must have opted into this ASA before receiving payments.

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

> ARC200 app ID `302190` is aUSDC on VOI mainnet.

---

## Step 2 — Generate WooCommerce REST API credentials

1. In your WordPress Admin go to **WooCommerce → Settings → Advanced → REST API**
2. Click **Add key**
3. Set **Description** (e.g. "AlgoVoi"), **User**, and **Permissions** to `Read/Write`
4. Click **Generate API key**
5. Copy the **Consumer key** (`ck_...`) and **Consumer secret** (`cs_...`) — these are shown once

> Your WooCommerce site must be served over **HTTPS**. Basic auth credentials are sent in plaintext over HTTP.

---

## Step 3 — Connect the integration

```http
POST /internal/integrations/{tenant_id}/woocommerce
Authorization: Bearer <admin-key>
Content-Type: application/json

{
  "credentials": {
    "site_url": "https://mystore.com",
    "consumer_key": "ck_xxxxxxxxxxxxxxxxxxxx",
    "consumer_secret": "cs_xxxxxxxxxxxxxxxxxxxx"
  },
  "shop_identifier": "mystore.com",
  "base_currency": "USD",
  "preferred_network": "algorand_mainnet"
}
```

**`preferred_network`** — which chain to settle payments on:

| Value | Settles in |
|-------|-----------|
| `algorand_mainnet` | USDC (ASA 31566704) |
| `voi_mainnet` | aUSDC (ARC200 app 302190) |

The response includes a `webhook_secret` and a `webhook_url`. Save both — the secret is shown once.

```json
{
  "webhook_url": "https://api.algovoi.com/webhooks/woocommerce/{tenant_id}",
  "webhook_secret": "...",
  "preferred_network": "algorand_mainnet"
}
```

---

## Step 4 — Register the webhook in WooCommerce

1. In your WordPress Admin go to **WooCommerce → Settings → Advanced → Webhooks**
2. Click **Add webhook**
3. Set:
   - **Name**: AlgoVoi
   - **Status**: Active
   - **Topic**: Order created
   - **Delivery URL**: the `webhook_url` from Step 3
   - **Secret**: the `webhook_secret` from Step 3
   - **API version**: WP REST API Integration v3
4. Click **Save webhook**

> AlgoVoi verifies every inbound webhook using HMAC-SHA256 against the `X-WC-Webhook-Signature` header. Mismatched secrets will be rejected with HTTP 401.

---

## Payment flow for your customers

Once connected, every new WooCommerce order triggers AlgoVoi to:

1. Create a hosted checkout link valid for **30 minutes**
2. Display the amount in USDC (or aUSDC) with a QR code and wallet link
3. On successful on-chain confirmation:
   - WooCommerce order status updated to **processing**
   - TX ID recorded as an internal order note

The customer is redirected back to the WooCommerce order received page after payment.

---

## Tenant limits to check

```http
PUT /internal/tenants/{tenant_id}/limits
Authorization: Bearer <admin-key>
Content-Type: application/json

{
  "allowed_networks": ["algorand_mainnet"],
  "allowed_assets": ["31566704"],
  "kill_switch": false
}
```

---

## Troubleshooting

| Symptom | Likely cause |
|---------|-------------|
| HTTP 401 on webhook | `webhook_secret` mismatch — reconnect the integration to rotate the secret |
| HTTP 422 "No network config" | Network config missing or no payout address set for `preferred_network` |
| Order status not updating | Consumer key/secret lacks `write` permission, or site not on HTTPS |
| Payment link expired | Customer took longer than 30 minutes — a new order webhook will create a fresh link |
| `Skipping order.updated` in logs | Normal — AlgoVoi only processes `pending` or `on-hold` orders from update events |

---

## Supported networks

| Network | Asset | Notes |
|---------|-------|-------|
| `algorand_mainnet` | USDC (ASA 31566704) | Requires ASA opt-in on payout wallet |
| `voi_mainnet` | aUSDC (ARC200 app 302190) | |
| `algorand_testnet` | Test USDC | For integration testing only |
| `voi_testnet` | Test aUSDC | For integration testing only |

---

---

## WordPress Plugin — AlgoVoi Payment Gateway

The `algovoi-gateway.php` plugin provides two WooCommerce payment gateways. Both are contained in a single file and share the same plugin registration.

### Installation

1. On the server, create the plugin directory:
   ```bash
   mkdir -p /var/www/html/wordpress/wp-content/plugins/algovoi-gateway
   ```
2. Copy the plugin file:
   ```bash
   scp -i ~/.ssh/woocommerce_test algovoi-gateway.php \
     root@<server-ip>:/var/www/html/wordpress/wp-content/plugins/algovoi-gateway/algovoi-gateway.php
   ```
3. In WordPress Admin go to **Plugins → Installed Plugins**, find **AlgoVoi Payment Gateway**, click **Activate**.
4. Go to **WooCommerce → Settings → Payments** — both gateways will now appear.

---

### Gateway 1: AlgoVoi Hosted Checkout

**ID:** `algovoi`

This is the standard redirect gateway. On checkout the customer is redirected to the AlgoVoi hosted payment page where they pay via QR code or wallet link. On successful on-chain confirmation AlgoVoi calls back via the webhook registered in Step 4 above.

**Configuration (WooCommerce → Settings → Payments → AlgoVoi):**

| Field | Value |
|-------|-------|
| Enable/Disable | Check to enable |
| Title | Shown to customer at checkout (e.g. "Pay with Crypto (AlgoVoi)") |
| Description | Short description shown below payment method |
| API Base URL | Base URL of the AlgoVoi API (e.g. `https://api1.ilovechicken.co.uk`) |
| Tenant ID | Your AlgoVoi tenant UUID |
| Admin API Key | Bearer token for `/internal/` endpoints |
| Preferred Network | `algorand_mainnet` or `voi_mainnet` |
| Webhook Secret | Secret from Step 3 — used to verify inbound webhook signatures |

The gateway calls `POST /internal/checkout/{tenant_id}` server-side on order placement and redirects the customer to the returned `payment_url`.

---

### Gateway 2: AlgoVoi Extension (Pay via Browser Extension)

**ID:** `algovoi_extension`

This gateway lets customers who have the **AlgoVoi browser extension** installed pay directly from the checkout page. No external redirect occurs — the transaction is built, signed, and submitted to the chain entirely within the browser, then verified server-side via a WP REST endpoint.

**Requirements:**
- Customer must have the AlgoVoi browser extension installed and connected.
- `algosdk` is loaded automatically from the jsDelivr CDN on the thank-you page — no separate installation needed.

**Configuration (WooCommerce → Settings → Payments → AlgoVoi Extension):**

Same fields as Gateway 1 plus no additional settings. The gateway reads the network/asset configuration at payment time by fetching the AlgoVoi hosted checkout page server-side and parsing the receiver address, memo, and amount.

**On-chain payment flow:**

```
Customer clicks "Place Order"
          ↓
process_payment() fetches AlgoVoi checkout page server-side
  → extracts receiver address, memo (algovoi:{token}), amount, asset ID
  → stores all values as WooCommerce order meta
  → redirects to WooCommerce thank-you page
          ↓
Thank-you page renders the extension UI (dark AlgoVoi-branded panel)
  → algosdk loaded from CDN
  → window.algorand.enable() called with genesis hash for chain detection
  → Asset transfer transaction built with suggestedParams from algod
  → window.algorand.signAndSendTransactions() called — SIGNS ONLY, does not submit
  → Signed bytes (stxns[0]) submitted manually to algod POST /v2/transactions
  → Algod pending transaction polled until confirmed-round > 0 (up to 60 s)
  → 4 s pause for indexer catch-up
          ↓
Browser POSTs to /wp-json/algovoi/v1/orders/{id}/verify
  → WP verifies order_key, proxies to AlgoVoi POST /checkout/{token}/verify
  → On success: order status → processing, TX ID stored as order note
          ↓
Success message shown inline — no page redirect
```

**Receiver → asset mapping (hardcoded in plugin):**

| Receiver address prefix | Network | Asset | ASA / App ID |
|------------------------|---------|-------|-------------|
| `GHSRL2SAY…MADMWI` | Algorand mainnet | USDC | 31566704 (6 dp) |
| `THDLWTJ…EOQY` | VOI mainnet | aUSDC | 302190 (6 dp) |

If the receiver address is not in this map the payment UI shows an "unsupported network" error.

**Order meta stored on placement:**

| Key | Contents |
|-----|----------|
| `_algovoi_token` | AlgoVoi checkout token |
| `_algovoi_checkout_url` | Full hosted checkout URL |
| `_algovoi_receiver` | On-chain receiver address |
| `_algovoi_memo` | Transaction note (`algovoi:{token}`) |
| `_algovoi_amount_display` | Human-readable amount with ticker |
| `_algovoi_ticker` | `USDC` or `aUSDC` |
| `_algovoi_asset_id` | Integer ASA / app ID |
| `_algovoi_microunits` | Amount in microunits (amount × 10⁶) |
| `_algovoi_algod` | Algod base URL for this chain |
| `_algovoi_chain` | `algorand_mainnet` or `voi_mainnet` |

---

### WP REST Verification Endpoint

The plugin registers a single REST endpoint used by the extension gateway JS:

```
POST /wp-json/algovoi/v1/orders/{id}/verify
Content-Type: application/json

{ "tx_id": "<algod-tx-id>", "order_key": "<wc-order-key>" }
```

- `order_key` is validated server-side against `$order->get_order_key()` — no WordPress authentication required.
- On success the plugin calls `$order->payment_complete($tx_id)` and returns `{"success": true}`.
- On failure it returns HTTP 400 with `{"error": "<reason>"}`.

The endpoint proxies to `POST /checkout/{token}/verify` on the AlgoVoi API. AlgoVoi uses the indexer to confirm the transaction, so the JS adds a 4 s indexer catch-up delay before calling this endpoint.

---

### Nginx Hardening

The following hardening was applied to the WordPress Nginx vhost alongside the plugin deployment. Rules are in `/etc/nginx/conf.d/wp-ratelimit.conf` and the main site block.

**Rate-limit zones** (`wp-ratelimit.conf`):

```nginx
limit_req_zone $binary_remote_addr zone=wp_login:10m  rate=5r/m;
limit_req_zone $binary_remote_addr zone=wp_admin:10m  rate=60r/m;
limit_req_zone $binary_remote_addr zone=wp_xmlrpc:1m  rate=1r/m;
```

**Protected locations** (all return 403):

| Path | Reason |
|------|--------|
| `wp-config.php` | Credentials exposure |
| `wp-config-sample.php` | Information disclosure |
| `readme.html`, `license.txt` | Version disclosure |
| `xmlrpc.php` | Brute-force / DDoS vector |
| `wp-content/debug.log` | Error log exposure |
| `wp-content/uploads/*.php` | Webshell prevention |
| `wp-includes/*.php` | Direct PHP execution |
| `wp-signup.php`, `wp-trackback.php` | Spam / unused endpoints |
| `/.` (hidden files) | `.env`, `.git`, etc. |
| `?author=[0-9]+` | Username enumeration |

**Rate-limited locations:**

| Location | Zone | Burst | Behaviour |
|----------|------|-------|-----------|
| `/wp-login.php` | `wp_login` (5 r/m) | 3, nodelay | Returns 429 when exceeded |
| `/wp-admin/` | `wp_admin` (60 r/m) | 20, nodelay | Returns 429 when exceeded |

**Security headers applied site-wide:**

```nginx
add_header X-Frame-Options "SAMEORIGIN";
add_header X-Content-Type-Options "nosniff";
add_header X-XSS-Protection "1; mode=block";
add_header Referrer-Policy "strict-origin-when-cross-origin";
add_header Permissions-Policy "geolocation=(), microphone=(), camera=()";
```

---

## Live test status

Confirmed end-to-end on **2026-04-01** against `api1.ilovechicken.co.uk`, real WooCommerce store at `104.207.130.27` running WooCommerce 10.6.2 / WordPress 6.9.4:

| Test | Network | Result |
|------|---------|--------|
| `order.created` webhook → checkout link created | `algorand_mainnet` | Pass |
| Extension gateway — sign, submit, confirm, verify end-to-end | `algorand_mainnet` | Pass |
| Extension gateway — sign, submit, confirm, verify end-to-end | `voi_mainnet` | Pass |
| Nginx hardening — blocked paths return 403 | — | Pass |
| Nginx hardening — `wp-login.php` rate limit (429 after burst) | — | Pass |

Signature verification uses `HMAC-SHA256` over the raw request body, base64-encoded, in the `X-WC-Webhook-Signature` header.

WooCommerce 10.x REST API requires a custom Basic Auth plugin (`wc-basic-auth.php`) since WC 9+ removed HTTP Basic Auth support. See [wc-basic-auth.php](wc-basic-auth.php) in this repo.
