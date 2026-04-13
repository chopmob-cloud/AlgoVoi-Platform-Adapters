# AlgoVoi Platform Adapters

Integration guides and drop-in payment plugins for connecting e-commerce platforms to **AlgoVoi Tenant Services** — enabling merchants to accept stablecoin payments settled on the Algorand, VOI, Hedera, and Stellar blockchains.

---

## What is AlgoVoi?

AlgoVoi is a multi-tenant payment infrastructure layer built on the Algorand Virtual Machine (AVM) with Hedera and Stellar support. It allows merchants and developers to accept on-chain stablecoin payments through hosted checkout or browser extension flows, without managing wallets or blockchain integrations directly.

Supported settlement assets:

| Asset | Network | Details |
|-------|---------|---------|
| USDC  | Algorand mainnet | Native ASA (ASA ID 31566704), issued by Circle |
| aUSDC | VOI mainnet      | Native ASA (ASA ID 302190), Aramid-bridged USDC |
| USDC  | Hedera mainnet   | HTS token 0.0.456858, issued by Circle |
| USDC  | Stellar mainnet  | Credit asset issued by Circle (`GA5ZSEJYB37JRC5AVCIA5MOP4RHTM335X2KGX3IHOJAPP5RE34K4KZVN`); receiver must have a trust line before accepting |
| ALGO / VOI / HBAR / XLM | Any mainnet | Native coin payments also supported on every chain (6/6/8/7 decimals respectively) |

---

## What is this repository?

This repository contains **production-ready payment adapters** and **integration documentation** for connecting e-commerce platforms, custom applications, and AI agent services to AlgoVoi Tenant Services.

Included:
- **Drop-in plugins** for WooCommerce, OpenCart, PrestaShop, and Shopware (tested and deployed)
- **Native adapters** for PHP, Python, Go, and Rust (zero external dependencies)
- **Agent protocol middleware** for MPP and AP2 (gate APIs behind payment challenges)
- **x402 embeddable widget** for any HTML page (Cloudflare Pages)
- **Integration guides** for 30+ platforms including Shopify, Magento, eBay, and more
- **27 provisional Python adapters** — see [Provisional adapters](#provisional-adapters) section below

> **Provisional adapters**: All adapters tagged `*(provisional)*` in the tables below contain Python implementations with full security hardening and unit tests, but have **not been end-to-end tested against a live platform environment**. API details are based on official documentation and community sources. Verify against your platform's current API before production use.

---

## Repository structure

```
platform-adapters/
├── woocommerce/          # WooCommerce plugin (single PHP file)
├── opencart/             # OpenCart 4 extensions (hosted + wallet)
├── prestashop/           # PrestaShop 8 modules (hosted + wallet)
├── shopware/             # Shopware 6 plugin (Symfony handlers)
├── native-php/           # Framework-free PHP adapter
├── native-python/        # Stdlib-only Python adapter
├── native-go/            # Stdlib-only Go package
├── native-rust/          # Zero-crate Rust library
├── magento2/             # Magento 2 / Adobe Commerce module (PHP)
├── amazon-mws/           # Amazon SP-API webhook adapter (Python)
├── tiktok-shop/          # TikTok Shop Open Platform adapter (Python)
├── squarespace/          # Squarespace Commerce webhook adapter (Python)
├── wix/                  # Wix Payment Provider SPI (Velo)
├── mpp-adapter/          # MPP server middleware (Python)
├── ap2-adapter/          # AP2 server middleware (Python)
├── shopify-app/          # Private — Shopify payment app (Cloudflare Pages, not distributed)
├── x402-widget/          # Embeddable payment widget (Web Component)
│
│   — Provisional Python adapters (security-hardened, docs-validated) —
├── allegro/              # [Provisional] Allegro marketplace (Poland / CEE)
├── bigcommerce/          # [Provisional] BigCommerce webhook adapter
├── bolcom/               # [Provisional] Bol.com (Netherlands / Belgium)
├── cdiscount/            # [Provisional] Cdiscount (France / Belgium)
├── cex/                  # [Provisional] CeX (webstore operator bypass)
├── discord/              # [Provisional] Discord interactions payment adapter
├── ebay/                 # [Provisional] eBay Platform Notifications adapter
├── ecwid/                # [Provisional] Ecwid / Lightspeed E-Series adapter
├── etsy/                 # [Provisional] Etsy webhook adapter
├── faire/                # [Provisional] Faire B2B wholesale adapter
├── flipkart/             # [Provisional] Flipkart Seller API adapter (India)
├── freshbooks/           # FreshBooks invoice payment adapter (production)
├── instagram-shops/      # [Provisional] Instagram & Facebook Shops adapter
├── jumia/                # [Provisional] Jumia seller adapter (Africa)
├── lazada/               # [Provisional] Lazada open platform adapter (SE Asia)
├── mercadolibre/         # [Provisional] Mercado Libre adapter (Latin America)
├── myob/                 # MYOB AccountRight poll-based adapter (production)
├── onbuy/                # [Provisional] OnBuy marketplace adapter (UK)
├── printful/             # [Provisional] Printful print-on-demand adapter
├── printify/             # [Provisional] Printify print-on-demand adapter
├── quickbooks-online/    # QuickBooks Online invoice adapter (production)
├── rakuten/              # [Provisional] Rakuten marketplace adapter
├── sage-business-cloud/  # Sage Business Cloud invoice adapter (production)
├── shopee/               # [Provisional] Shopee open platform adapter (SE Asia)
├── telegram/             # [Provisional] Telegram Bot payment adapter
├── tokopedia/            # [Provisional] Tokopedia seller adapter (Indonesia)
├── truelayer/            # [Provisional] TrueLayer open banking adapter
├── walmart/              # [Provisional] Walmart Marketplace adapter
├── wave/                 # Wave Accounting invoice adapter (production)
├── whatsapp/             # [Provisional] WhatsApp Business API adapter
├── wormhole/             # [Provisional] Wormhole cross-chain bridge adapter
├── x402-ai-agents/       # x402 autonomous AI agent payment adapter (live-tested)
├── xero/                 # Xero invoice payment adapter (production)
├── yapily/               # [Provisional] Yapily open banking adapter
├── zoho-books/           # Zoho Books invoice adapter (production)
│
├── {platform}.md         # Integration guides (30+ platforms)
└── README.md
```

### Live-tested adapters

The following adapters have been end-to-end tested against a live AlgoVoi tenant on `algorand_mainnet`, `voi_mainnet`, `hedera_mainnet`, and `stellar_mainnet`:

| Platform | Demo store | Hosted chains | Extension chains |
|----------|-----------|---------------|-----------------|
| OpenCart 4 | opencart.ilovechicken.co.uk | Algorand, VOI, Hedera, Stellar | Algorand, VOI |
| PrestaShop 8.2.5 | prestashop.ilovechicken.co.uk | Algorand, VOI, Hedera, Stellar | Algorand, VOI |
| Shopware 6.7.8.2 | shopware.ilovechicken.co.uk | Algorand, VOI, Hedera, Stellar | Algorand, VOI |
| WooCommerce 10.6.2 / WordPress 6.9.4 | woo.ilovechicken.co.uk | Algorand, VOI, Hedera, Stellar | Algorand, VOI |
| Shopify (Cloudflare Pages) | algovoi-3.myshopify.com | Algorand, VOI, Hedera, Stellar | — |
| Magento 2 / Adobe Commerce | — | Algorand, VOI, Hedera, Stellar | — |
| Amazon SP-API | — (B2B webhook) | Algorand, VOI, Hedera, Stellar | — |
| TikTok Shop | — (B2B webhook) | Algorand, VOI, Hedera, Stellar | — |
| Squarespace | — (B2B webhook) | Algorand, VOI, Hedera, Stellar | — |
| Wix eCommerce | — (SPI checkout) | Algorand, VOI, Hedera, Stellar | — |
| Native PHP | — | Algorand, VOI, Hedera, Stellar | Algorand, VOI |
| Native Python | — | Algorand, VOI, Hedera, Stellar | Algorand, VOI |
| Native Go | — | Algorand, VOI, Hedera, Stellar | Algorand, VOI |
| Native Rust | — | Algorand, VOI, Hedera, Stellar | Algorand, VOI |
| AlgoVoi 1.0 | api1.ilovechicken.co.uk/shop-demo | Algorand, VOI, Hedera, Stellar | Algorand, VOI |
| QuickBooks Online | — (B2B webhook) | Algorand, VOI, Hedera, Stellar | — |
| Xero | — (B2B webhook) | Algorand, VOI, Hedera, Stellar | — |
| FreshBooks | — (B2B webhook, form-urlencoded + fetch_order) | Algorand, VOI, Hedera, Stellar | — |
| Sage Business Cloud | — (polling, no push webhooks) | Algorand, VOI, Hedera, Stellar | — |
| Zoho Books | — (B2B webhook) | Algorand, VOI, Hedera, Stellar | — |
| Wave | — (B2B webhook) | Algorand, VOI, Hedera, Stellar | — |
| MYOB | — (polling, no push webhooks) | Algorand, VOI, Hedera, Stellar | — |
| x402 AI Agent adapter | — (x402 spec v1: `accepts` array, CAIP-2 networks, microunit amounts, `payload.signature` proof) | Algorand, VOI, Hedera, Stellar | — |
| MPP Gate | — (100% IETF `draft-ryan-httpauth-payment`: challenge echo, CAIP-2 routing, HMAC IDs, on-chain verification — v2.1.0, 153/153 tests, live smoke-tested all 4 chains 13 Apr 2026) | Algorand, VOI, Hedera, Stellar | — |
| AP2 Gate | — (payment request + local ed25519 verification) | Algorand, VOI | — |

**Last webhook test:** 11 April 2026 — 38 passed, 0 failed, 7 skipped (all 4 chains: `algorand_mainnet`, `voi_mainnet`, `hedera_mainnet`, `stellar_mainnet`)

**Accounting adapters end-to-end test:** 11 April 2026 — 28/28 passed (7 adapters × 4 chains) against `api1.ilovechicken.co.uk`

**Accounting adapters unit tests:** 339 passing, 0 failing (includes replay attack prevention coverage — commit `5025c4e`)

**AI agent adapters — production ready as of 13 April 2026:**
- x402: **spec v1 compliant** — `x402Version: 1`, `accepts` array, CAIP-2 network IDs, string microunit amounts, `payload.signature` proof format. Real payments smoke-tested on all 4 chains (Algorand, VOI, Stellar, Hedera mainnet), `x402/verify` confirmed `verified:true` on each. 76/76 unit tests passing. Adapter v2.0.0.
- MPP: **100% IETF spec compliant** (v2.1.0) — `id` (HMAC-SHA256), `method`, `intent="charge"`, `request=` (charge intent object), `expires`, challenge echo validation (Table 3), CAIP-2 network routing, replay protection, spec-compliant `Payment-Receipt`. On-chain verification smoke-tested on all 4 chains (Algorand, VOI, Hedera, Stellar) 13 Apr 2026 ×2. 153/153 unit tests.
- AP2: **production ready** (v2.0.0) — AP2 v0.1 CartMandate/PaymentMandate with AlgoVoi crypto-algo extension. CartMandate issues `PaymentMethodData` per extension schema (`network`, `receiver`, `amount_microunits`, `asset_id`, `min_confirmations`, `memo_required`). PaymentMandate accepts `payment_response.details.{network, tx_id, note_field}`. ed25519 sig + on-chain AVM verification. PyNaCl + cryptography fallback both confirmed. 81/81 tests.

### Two payment flows

**Hosted checkout** — Customer is redirected to a secure AlgoVoi-hosted payment page. Supports Algorand, VOI, Hedera, and Stellar. Works with any wallet (Pera, Defly, Lute, HashPack, Freighter, LOBSTR, …). Payment confirmed via webhook or API status check. Used by all platforms including Shopify.

**Extension payment** — Customer pays directly on the store page using the AlgoVoi browser extension and algosdk. Supports Algorand and VOI only (AVM chains). Buyers paying on Hedera or Stellar use hosted checkout with their chain-native wallet. No redirect required for extension flow. Available on WooCommerce, OpenCart, PrestaShop, and Shopware.

**Shopify checkout extension** — "Pay with Crypto →" link rendered on the thank-you page via Shopify Checkout UI Extension (Preact). Customer selects their chain on a dedicated pay page. Webhook automatically adds payment link to order notes.

---

## E-commerce integrations

| Platform | Guide | Files | Status |
|----------|-------|-------|--------|
| **Native PHP** | — | [native-php/](./native-php/) | **Available — drop-in, zero dependencies** |
| **Native Python** | — | [native-python/](./native-python/) | **Available — stdlib only, no pip install** |
| **Native Go** | — | [native-go/](./native-go/) | **Available — stdlib only, no go get** |
| **Native Rust** | — | [native-rust/](./native-rust/) | **Available — zero crates, pure stdlib** |
| **Shopify** | [shopify.md](./shopify.md) | Private (hosted service) | **Available — managed by AlgoVoi** |
| **WooCommerce** | [woocommerce.md](./woocommerce.md) | [woocommerce/](./woocommerce/) | **Available — hosted + extension** |
| **Magento 2 / Adobe Commerce** | [magento.md](./magento.md) | [magento2/](./magento2/) | **Available — hosted checkout, Knockout.js** |
| BigCommerce | [bigcommerce.md](./bigcommerce.md) | [bigcommerce/](./bigcommerce/) | *(provisional)* Python webhook adapter |
| **Wix eCommerce** | [wix.md](./wix.md) | [wix/](./wix/) | **Available — Payment Provider SPI (real checkout)** |
| **PrestaShop** | [prestashop.md](./prestashop.md) | [prestashop/](./prestashop/) | **Available — hosted + extension** |
| **Squarespace** | [squarespace.md](./squarespace.md) | [squarespace/](./squarespace/) | **Available — B2B webhook adapter** |
| eBay | [ebay.md](./ebay.md) | [ebay/](./ebay/) | *(provisional)* Python webhook adapter |
| Walmart | [walmart.md](./walmart.md) | [walmart/](./walmart/) | *(provisional)* Python webhook adapter |
| **Amazon SP-API** | [amazon.md](./amazon.md) | [amazon-mws/](./amazon-mws/) | **Available — B2B webhook adapter** |
| CeX | [cex.md](./cex.md) | [cex/](./cex/) | *(provisional)* Python operator-bypass adapter |
| Ecwid | [ecwid.md](./ecwid.md) | [ecwid/](./ecwid/) | *(provisional)* Python webhook adapter |
| **OpenCart** | [opencart.md](./opencart.md) | [opencart/](./opencart/) | **Available — hosted + extension** |
| **Shopware** | [shopware.md](./shopware.md) | [shopware/](./shopware/) | **Available — hosted + extension** |
| **TikTok Shop** | [tiktok-shop.md](./tiktok-shop.md) | [tiktok-shop/](./tiktok-shop/) | **Available — B2B webhook adapter** |

## Regional & international marketplace integrations

| Platform | Guide | Region | Status |
|----------|-------|--------|--------|
| Flipkart | [flipkart.md](./flipkart.md) | India | *(provisional)* [flipkart/](./flipkart/) |
| Etsy | [etsy.md](./etsy.md) | Global | *(provisional)* [etsy/](./etsy/) |
| Printful | [printful.md](./printful.md) | Global (print-on-demand) | *(provisional)* [printful/](./printful/) |
| Printify | [printify.md](./printify.md) | Global (print-on-demand) | *(provisional)* [printify/](./printify/) |
| Bol.com | [bolcom.md](./bolcom.md) | Netherlands / Belgium | *(provisional)* [bolcom/](./bolcom/) |
| Lazada | [lazada.md](./lazada.md) | SE Asia (MY, TH, PH, SG, ID, VN) | *(provisional)* [lazada/](./lazada/) |
| Tokopedia | [tokopedia.md](./tokopedia.md) | Indonesia | *(provisional)* [tokopedia/](./tokopedia/) |
| Rakuten | [rakuten.md](./rakuten.md) | Japan / France / Germany | *(provisional)* [rakuten/](./rakuten/) |
| Allegro | [allegro.md](./allegro.md) | Poland / Central & Eastern Europe | *(provisional)* [allegro/](./allegro/) |
| Shopee | [shopee.md](./shopee.md) | SE Asia / Brazil | *(provisional)* [shopee/](./shopee/) |
| Mercado Libre | [mercadolibre.md](./mercadolibre.md) | Latin America | *(provisional)* [mercadolibre/](./mercadolibre/) |
| OnBuy | [onbuy.md](./onbuy.md) | United Kingdom | *(provisional)* [onbuy/](./onbuy/) |
| Jumia | [jumia.md](./jumia.md) | Africa (NG, KE, EG, GH + more) | *(provisional)* [jumia/](./jumia/) |
| Cdiscount | [cdiscount.md](./cdiscount.md) | France / Belgium | *(provisional)* [cdiscount/](./cdiscount/) |
| Faire | [faire.md](./faire.md) | Global (B2B wholesale) | *(provisional)* [faire/](./faire/) — requires Faire API approval |

## Accounting integrations

All 7 accounting adapters were end-to-end tested on **11 April 2026** against `api1.ilovechicken.co.uk` across all 4 chains (28/28 pass).

> **Adapter source is not publicly distributed.** Integration guides are below. Download your adapter from the [AlgoVoi dashboard](https://api1.ilovechicken.co.uk/dashboard/downloads) after signing in with your API key.

| Platform | Guide | Status |
|----------|-------|--------|
| **QuickBooks Online** | [quickbooks-online.md](./quickbooks-online.md) | **Available** — private download |
| **Xero** | [xero.md](./xero.md) | **Available** — private download |
| **FreshBooks** | [freshbooks.md](./freshbooks.md) | **Available** — private download (form-urlencoded webhook + `fetch_order`) |
| **Sage Business Cloud** | [sage-business-cloud.md](./sage-business-cloud.md) | **Available** — private download (polling model, no push webhooks) |
| **Zoho Books** | [zoho-books.md](./zoho-books.md) | **Available** — private download (webhook body must include `${INVOICE.INVOICE_TOTAL}`) |
| **Wave** | [wave.md](./wave.md) | **Available** — private download |
| **MYOB** | [myob.md](./myob.md) | **Available** — private download (polling model, no push webhooks) |

## Social commerce integrations

| Platform | Guide | Status |
|----------|-------|--------|
| Telegram | [telegram.md](./telegram.md) | *(provisional)* [telegram/](./telegram/) |
| Discord | [discord.md](./discord.md) | *(provisional)* [discord/](./discord/) |
| WhatsApp Business | [whatsapp.md](./whatsapp.md) | *(provisional)* [whatsapp/](./whatsapp/) |
| Instagram & Facebook Shops | [instagram-shops.md](./instagram-shops.md) | *(provisional)* [instagram-shops/](./instagram-shops/) — requires Meta Tech Provider agreement |

## Financial services integrations

| Platform | Guide | Status |
|----------|-------|--------|
| TrueLayer | [truelayer.md](./truelayer.md) | *(provisional)* [truelayer/](./truelayer/) |
| Yapily | [yapily.md](./yapily.md) | *(provisional)* [yapily/](./yapily/) |
| Wormhole | [wormhole.md](./wormhole.md) | *(provisional)* [wormhole/](./wormhole/) |

## AI agent & machine payment adapters

| Adapter | Files | Description | Status |
|---------|-------|-------------|--------|
| **x402** | [x402-ai-agents.md](./x402-ai-agents.md) / [x402-ai-agents/](./x402-ai-agents/) | Autonomous AI agent payments via the x402 protocol (spec v1 — `accepts` array, CAIP-2 IDs, microunit amounts, `payload.signature`) | **Production ready** — real payments smoke-tested on all 4 chains (Algorand, VOI, Stellar, Hedera), `x402/verify` confirmed on each. Adapter v2.0.0, 76/76 tests. |
| **MPP** | [mpp-adapter/mpp-adapter.md](./mpp-adapter/mpp-adapter.md) / [mpp-adapter/](./mpp-adapter/) | Machine Payments Protocol server middleware — 100% IETF `draft-ryan-httpauth-payment` compliant (challenge echo validation, CAIP-2 network routing, HMAC challenge IDs, on-chain verification, replay protection) | **Production ready** — 0.01 USDC live smoke-tested on all 4 chains (Algorand, VOI, Hedera, Stellar) 13 Apr 2026. Adapter v2.1.0, 153/153 tests. |
| **AP2** | [ap2-adapter/ap2-adapter.md](./ap2-adapter/ap2-adapter.md) / [ap2-adapter/](./ap2-adapter/) | AP2 v0.1 CartMandate/PaymentMandate server middleware with AlgoVoi crypto-algo extension (`https://algovoi.io/ap2/extensions/crypto-algo/v1`). ed25519 mandate signing + on-chain AVM tx verification. | **Production ready** — CartMandate structure, real ed25519 smoke-tested 13 Apr 2026 (valid/tampered/wrong-key, both PyNaCl + cryptography paths). v2.0.0, 81/81 tests. |

## Charity Interfaces

Pre-built, self-contained donation pages powered by AlgoVoi and deployed to Cloudflare Pages. Zero external dependencies — drop the HTML file onto any server or share the URL directly.

| Page | URL | Cause | Amount | Chain |
|------|-----|-------|--------|-------|
| **Manndeshi Foundation** | [worker.ilovechicken.co.uk/manndeshi.html](https://worker.ilovechicken.co.uk/manndeshi.html) | Empowering rural women in India to become successful entrepreneurs | $2.75 USDC | Algorand |

Source: [x402-widget/manndeshi.html](./x402-widget/manndeshi.html) · [x402-widget/functions/api/manndeshi/donate.js](./x402-widget/functions/api/manndeshi/donate.js)

---

## x402 Embeddable Payment Widget

A drop-in Web Component for accepting x402 payments on any website. Deployed to Cloudflare Pages at `worker.ilovechicken.co.uk`. Full source and security guide: [x402-widget/](./x402-widget/)

```html
<script type="module" src="https://worker.ilovechicken.co.uk/widget.js"></script>
<algovoi-x402
  amount="29.99"
  chains="ALGO,VOI,XLM,HBAR"
  tenant-id="your-tenant-id"
  api-key="algv_your-api-key">
</algovoi-x402>
```

| Feature | Detail |
|---------|--------|
| Format | `<algovoi-x402>` Web Component — works in any HTML page |
| Chains | `ALGO` (Algorand), `VOI`, `XLM` (Stellar), `HBAR` (Hedera) |
| Backend | Cloudflare Pages Function proxying `POST /v1/payment-links` |
| Demo endpoint | `POST /api/x402/demo` — uses server-side env secrets (no client keys) |
| Pay endpoint | `POST /api/x402/pay` — uses client-supplied tenant-id + api-key |
| CORS | Enabled — embeddable from any origin |
| Security | See [x402-widget/README.md](./x402-widget/README.md) — server-side proxy recommended for production |

---

## Provisional adapters

The 27 adapters marked `*(provisional)*` above contain fully-functional Python implementations with:

- **Full security hardening** — HMAC-SHA256 timing-safe webhook verification (`hmac.compare_digest`), empty-secret rejection, SSL enforcement (`ssl.create_default_context`), tx_id/token length guards (> 200 chars rejected), `HOSTED_NETWORKS` whitelist, cancel-bypass prevention via `verify_payment`
- **Zero pip dependencies** — standard library only
- **Unit test coverage** — 30–57 Python unit tests per adapter (1,491 total for provisional adapters; 339 across the 7 accounting adapters), all passing
- **No hardcoded secrets** — all credentials passed via constructor

**Status**: API shapes validated against official documentation. Not yet end-to-end tested against a live platform sandbox or production environment. Before deploying a provisional adapter:

1. Review the adapter source and test file in its directory
2. Cross-check the webhook signature header and API endpoint against the platform's current developer docs
3. Test against the platform's sandbox environment
4. File an issue or PR with any corrections

---

## How payments work

```
Customer places order and selects chain (Algorand / VOI / Hedera / Stellar)
            ↓
Plugin creates payment link via POST /v1/payment-links
            ↓
Hosted: redirect to AlgoVoi checkout page
Extension: pay in-page via AlgoVoi browser wallet
            ↓
Customer pays on-chain
            ↓
AlgoVoi verifies the transaction on-chain
            ↓
Webhook fires → order marked as paid in your platform
```

Payments are verified directly on-chain — no intermediary holds funds. Settlement goes straight to the merchant's configured payout address.

### Security

Every adapter is hardened against real-world payment attack vectors. The full audit was performed in April 2026 across all four deployed stores and all native adapters.

#### Vulnerabilities found and fixed

| Vulnerability | Severity | Affected | Fix |
|---------------|----------|----------|-----|
| **Cancel-bypass** | Critical | Shopware, PrestaShop (hosted) | `finalize()` / `confirm.php` now call `GET /checkout/{token}` and only mark paid if status is `paid`/`completed`/`confirmed` |
| **Webhook empty-secret** | High | OpenCart, Shopware | Reject with HTTP 500 before HMAC check if `webhook_secret` is empty — prevents `hash_hmac('sha256', $body, '', true)` forgery |
| **Cookie-swap attack** | High | PrestaShop (extension) | `verify.php` cross-checks `id_customer` against logged-in customer before marking order as paid |
| **SSRF on checkout URL** | Medium | All platforms | `parse_url()` host comparison before any server-side fetch of checkout page |
| **Timing attack** | Medium | WooCommerce | `hash_equals()` for order_key comparison instead of `!==` |
| **Missing SSL verification** | Medium | OpenCart, PrestaShop | `CURLOPT_SSL_VERIFYPEER => true` and `CURLOPT_SSL_VERIFYHOST => 2` on all `curl` calls |
| **Input validation** | Low | All platforms | `tx_id` length guard (>200 chars rejected), network whitelist with strict `in_array()` |
| **Webhook replay attack** | Medium | Xero (accounting) | `is_replay()` checks `eventDateUtc` (with `firstRetryMoment` fallback) — webhooks older than 5 minutes rejected |

#### Security measures in every adapter

- **HMAC webhook verification** — `hash_equals` (PHP), `hmac.compare_digest` (Python), `hmac.Equal` (Go), `constant_time_eq` (Rust)
- **Empty secret rejection** — webhooks rejected before HMAC check if secret is not configured
- **SSRF protection** — checkout URL host validated against configured API base before server-side fetch
- **Cancel-bypass prevention** — hosted checkout returns verified via API status check before marking orders complete
- **Order ownership checks** — customer ID cross-referenced on verify endpoints (prevents cookie/session swap)
- **TLS enforced** — SSL verification on all outbound HTTP calls across every language
- **Input validation** — network whitelist, tx_id length guard, timing-safe comparisons
- **No hardcoded secrets** — all credentials read from platform admin config or environment variables
- **Replay attack prevention** — `is_replay()` method on all 7 accounting adapters; real implementation on Xero (`eventDateUtc` / `firstRetryMoment`, 5-minute window, fail-open); documented no-op on platforms with no signed timestamp in payload

---

## Getting started

1. **Sign up** — [Start a free trial](https://api1.ilovechicken.co.uk/signup) with just your wallet address (no email required)
2. **Get your API key** — Instant API access with testnet + capped mainnet (30-day trial)
3. **Configure networks** — Add payout addresses for Algorand, VOI, Hedera, and/or Stellar
4. **Install an adapter** — Drop the plugin into your store, or use a native adapter for custom apps
5. **Accept payments** — Customers select their chain and pay with stablecoins

---

## License

This repository is licensed under the [Business Source License 1.1](./LICENSE).

### Permitted

- Install plugins on your own store (WooCommerce, OpenCart, PrestaShop, Shopware)
- Use native adapters (PHP, Python, Go, Rust) in your own application
- Fork and modify the code for your own internal use
- Contribute improvements back via pull requests
- All usage requires a valid [AlgoVoi tenant account](https://api1.ilovechicken.co.uk/signup)

### Prohibited

- Operating the adapters (or derivatives) as a competing hosted payment service or payment gateway
- Reselling, sublicensing, or redistributing as a commercial product
- Processing payments without a valid AlgoVoi tenant account
- Removing or altering copyright, attribution, or license notices

### Not distributed

- **Shopify app** — proprietary hosted service operated by AlgoVoi. Merchants install via the Shopify App Store; source code is not publicly distributed.
- **Accounting adapters** (QuickBooks Online, Xero, FreshBooks, Sage Business Cloud, Zoho Books, Wave, MYOB) — source code is not publicly distributed. Integration guides are in this repository. Download your adapter from the [AlgoVoi dashboard](https://api1.ilovechicken.co.uk/dashboard/downloads) after signing in.

---

## Support

- Documentation: [github.com/chopmob-cloud/AlgoVoi-Platform-Adapters](https://github.com/chopmob-cloud/AlgoVoi-Platform-Adapters) (this repository)
- Open an issue in this repository
- Contact via [X (@AlgoVoi)](https://x.com/AlgoVoi)
- API: `api1.ilovechicken.co.uk`
