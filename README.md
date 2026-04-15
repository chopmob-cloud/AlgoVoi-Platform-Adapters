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
- **CMS payment gateways** for Drupal Commerce, Easy Digital Downloads (WordPress), and Ghost — all Comet-validated 2026-04-15
- **Native adapters** for PHP, Python, Go, and Rust (zero external dependencies) — all hardened to v1.1.0 on 2026-04-15
- **Agent protocol middleware** for MPP and AP2 (gate APIs behind payment challenges)
- **AI platform adapters** for OpenAI, Claude, Gemini, Bedrock, Cohere, xAI/Grok, and Mistral (MPP + AP2 + x402, all 4 chains)
- **x402 embeddable widget** for any HTML page (Cloudflare Pages)
- **Integration guides and Python adapters for 45+ platforms** — all end-to-end tested on `api1.ilovechicken.co.uk` across all 4 chains

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
│   — Live-tested Python webhook adapters (4-chain verified 2026-04-14) —
├── allegro/              # Allegro marketplace (Poland / CEE)
├── bigcommerce/          # BigCommerce webhook adapter (partial — see note)
├── bolcom/               # Bol.com (Netherlands / Belgium)
├── cdiscount/            # Cdiscount (France / Belgium)
├── cex/                  # CeX (webstore operator bypass)
├── discord/              # Discord interactions payment adapter (Ed25519 — needs real app keypair)
├── ebay/                 # eBay Platform Notifications adapter
├── ecwid/                # Ecwid / Lightspeed E-Series adapter
├── etsy/                 # Etsy webhook adapter
├── faire/                # Faire B2B wholesale adapter (docs only — API approval required)
├── flipkart/             # Flipkart Seller API adapter (India)
├── freshbooks/           # FreshBooks invoice payment adapter
├── instagram-shops/      # Instagram & Facebook Shops adapter
├── jumia/                # Jumia seller adapter (docs only — no webhook endpoint)
├── lazada/               # Lazada open platform adapter (SE Asia)
├── mercadolibre/         # Mercado Libre adapter (Latin America)
├── myob/                 # MYOB AccountRight poll-based adapter
├── onbuy/                # OnBuy marketplace adapter (UK)
├── printful/             # Printful print-on-demand adapter
├── printify/             # Printify print-on-demand adapter (docs only — no webhook endpoint)
├── quickbooks-online/    # QuickBooks Online invoice adapter
├── rakuten/              # Rakuten marketplace adapter
├── sage-business-cloud/  # Sage Business Cloud invoice adapter
├── shopee/               # Shopee open platform adapter (SE Asia)
├── telegram/             # Telegram Bot payment adapter
├── tokopedia/            # Tokopedia seller adapter (Indonesia)
├── truelayer/            # TrueLayer open banking adapter (ES512 — needs real signing key)
├── walmart/              # Walmart Marketplace adapter
├── wave/                 # Wave Accounting invoice adapter
├── whatsapp/             # WhatsApp Business API adapter
├── wormhole/             # Wormhole cross-chain bridge adapter
├── x402-ai-agents/       # x402 autonomous AI agent payment adapter
├── ai-adapters/
│   ├── openai/           # Payment-gated OpenAI / compatible API wrappers (MPP + AP2 + x402)
│   ├── claude/           # Payment-gated Anthropic Claude wrappers (MPP + AP2 + x402)
│   ├── gemini/           # Payment-gated Google Gemini wrappers (MPP + AP2 + x402)
│   ├── bedrock/          # Payment-gated Amazon Bedrock Converse API wrappers (MPP + AP2 + x402)
│   ├── cohere/           # Payment-gated Cohere ClientV2 wrappers (MPP + AP2 + x402)
│   ├── xai/              # Payment-gated xAI Grok wrappers (MPP + AP2 + x402)
│   └── mistral/          # Payment-gated Mistral AI wrappers (MPP + AP2 + x402)
├── drupal-commerce/      # Drupal 10/11 + Commerce 2/3 payment gateway module
├── easy-digital-downloads/ # EDD 3.2+ WordPress plugin (digital downloads, licensing)
├── ghost/                # Ghost 5.x paid-membership grant-on-payment adapter
├── xero/                 # Xero invoice payment adapter
├── yapily/               # Yapily open banking adapter
├── zoho-books/           # Zoho Books invoice adapter
│
├── {platform}.md         # Integration guides (45+ platforms)
└── README.md
```

### Live-tested adapters

The following adapters have been end-to-end tested against a live AlgoVoi tenant on `algorand_mainnet`, `voi_mainnet`, `hedera_mainnet`, and `stellar_mainnet`:

| Platform | Demo store / notes | Hosted chains | Extension chains |
|----------|--------------------|---------------|-----------------|
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
| eBay | — (Platform Notifications webhook) | Algorand, VOI, Hedera, Stellar | — |
| Ecwid / Lightspeed E-Series | — (B2B webhook) | Algorand, VOI, Hedera, Stellar | — |
| Etsy | — (B2B webhook) | Algorand, VOI, Hedera, Stellar | — |
| Rakuten Ichiba | — (B2B webhook) | Algorand, VOI, Hedera, Stellar | — |
| OnBuy | — (B2B webhook) | Algorand, VOI, Hedera, Stellar | — |
| Yapily | — (open banking webhook) | Algorand, VOI, Hedera, Stellar | — |
| Walmart Marketplace | — (B2B webhook) | Algorand, VOI, Hedera, Stellar | — |
| CeX | — (operator bypass webhook) | Algorand, VOI, Hedera, Stellar | — |
| Printful | — (print-on-demand webhook) | Algorand, VOI, Hedera, Stellar | — |
| Wormhole | — (cross-chain bridge webhook) | Algorand, VOI, Hedera, Stellar | — |
| WhatsApp Business | — (Meta webhook) | Algorand, VOI, Hedera, Stellar | — |
| Instagram Shops | — (Meta webhook) | Algorand, VOI, Hedera, Stellar | — |
| Telegram | — (Bot API webhook) | Algorand, VOI, Hedera, Stellar | — |
| Allegro | — (marketplace webhook) | Algorand, VOI, Hedera, Stellar | — |
| Bol.com | — (marketplace webhook) | Algorand, VOI, Hedera, Stellar | — |
| Cdiscount | — (marketplace webhook) | Algorand, VOI, Hedera, Stellar | — |
| Flipkart | — (Seller API webhook) | Algorand, VOI, Hedera, Stellar | — |
| Lazada | — (open platform webhook) | Algorand, VOI, Hedera, Stellar | — |
| Mercado Libre | — (marketplace webhook) | Algorand, VOI, Hedera, Stellar | — |
| Shopee | — (open platform webhook) | Algorand, VOI, Hedera, Stellar | — |
| Tokopedia | — (marketplace webhook) | Algorand, VOI, Hedera, Stellar | — |
| x402 AI Agent adapter | — (x402 spec v1: `accepts` array, CAIP-2 networks, microunit amounts, `payload.signature` proof) | Algorand, VOI, Hedera, Stellar | — |
| MPP Gate | — (100% IETF `draft-ryan-httpauth-payment`: challenge echo, CAIP-2 routing, HMAC IDs, on-chain verification — v2.1.0, 153/153 tests, live smoke-tested all 4 chains 13 Apr 2026) | Algorand, VOI, Hedera, Stellar | — |
| AP2 Gate | — (payment request + local ed25519 verification) | Algorand, VOI | — |

**Last webhook test:** 14 April 2026 — all 39 testable adapters passed on all 4 chains (`algorand_mainnet`, `voi_mainnet`, `hedera_mainnet`, `stellar_mainnet`). Checkout pages validated live via Comet CDP. 6 adapters skipped: BigCommerce (partial — order-amount fetch needs real API credentials), Discord (Ed25519), TrueLayer (ES512), Faire/Jumia/Printify (docs only).

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
| BigCommerce | [bigcommerce.md](./bigcommerce.md) | [bigcommerce/](./bigcommerce/) | **Partial** — webhook sig verified; order-amount fetch requires real `store_hash` / `access_token` |
| **Wix eCommerce** | [wix.md](./wix.md) | [wix/](./wix/) | **Available — Payment Provider SPI (real checkout)** |
| **PrestaShop** | [prestashop.md](./prestashop.md) | [prestashop/](./prestashop/) | **Available — hosted + extension** |
| **Squarespace** | [squarespace.md](./squarespace.md) | [squarespace/](./squarespace/) | **Available — B2B webhook adapter** |
| **eBay** | [ebay.md](./ebay.md) | [ebay/](./ebay/) | **Available — Python webhook adapter** |
| **Walmart** | [walmart.md](./walmart.md) | [walmart/](./walmart/) | **Available — Python webhook adapter** |
| **Amazon SP-API** | [amazon.md](./amazon.md) | [amazon-mws/](./amazon-mws/) | **Available — B2B webhook adapter** |
| **CeX** | [cex.md](./cex.md) | [cex/](./cex/) | **Available — Python operator-bypass adapter** |
| **Ecwid / Lightspeed E-Series** | [ecwid.md](./ecwid.md) | [ecwid/](./ecwid/) | **Available — Python webhook adapter** |
| **OpenCart** | [opencart.md](./opencart.md) | [opencart/](./opencart/) | **Available — hosted + extension** |
| **Shopware** | [shopware.md](./shopware.md) | [shopware/](./shopware/) | **Available — hosted + extension** |
| **TikTok Shop** | [tiktok-shop.md](./tiktok-shop.md) | [tiktok-shop/](./tiktok-shop/) | **Available — B2B webhook adapter** |
| **Drupal Commerce** | [drupal-commerce/README.md](./drupal-commerce/README.md) | [drupal-commerce/](./drupal-commerce/) | **Available — Drupal 10/11 + Commerce 2/3 module (Comet-validated 2026-04-15)** |
| **Easy Digital Downloads** | [easy-digital-downloads/README.md](./easy-digital-downloads/README.md) | [easy-digital-downloads/](./easy-digital-downloads/) | **Available — EDD 3.2+ WordPress plugin (Comet-validated 2026-04-15)** |
| **Ghost** | [ghost/README.md](./ghost/README.md) | [ghost/](./ghost/) | **Available — Ghost 5.x paid-membership adapter (Comet-validated 2026-04-15)** |

## Regional & international marketplace integrations

All regional marketplace adapters have been end-to-end tested on **14 April 2026** across all 4 chains. Checkout pages validated live via Comet CDP.

| Platform | Guide | Region | Status |
|----------|-------|--------|--------|
| **Flipkart** | [flipkart.md](./flipkart.md) | India | **Available** — [flipkart/](./flipkart/) |
| **Etsy** | [etsy.md](./etsy.md) | Global | **Available** — [etsy/](./etsy/) |
| **Printful** | [printful.md](./printful.md) | Global (print-on-demand) | **Available** — [printful/](./printful/) |
| Printify | [printify.md](./printify.md) | Global (print-on-demand) | Docs only — no webhook endpoint |
| **Bol.com** | [bolcom.md](./bolcom.md) | Netherlands / Belgium | **Available** — [bolcom/](./bolcom/) |
| **Lazada** | [lazada.md](./lazada.md) | SE Asia (MY, TH, PH, SG, ID, VN) | **Available** — [lazada/](./lazada/) |
| **Tokopedia** | [tokopedia.md](./tokopedia.md) | Indonesia | **Available** — [tokopedia/](./tokopedia/) |
| **Rakuten** | [rakuten.md](./rakuten.md) | Japan / France / Germany | **Available** — [rakuten/](./rakuten/) |
| **Allegro** | [allegro.md](./allegro.md) | Poland / Central & Eastern Europe | **Available** — [allegro/](./allegro/) |
| **Shopee** | [shopee.md](./shopee.md) | SE Asia / Brazil | **Available** — [shopee/](./shopee/) |
| **Mercado Libre** | [mercadolibre.md](./mercadolibre.md) | Latin America | **Available** — [mercadolibre/](./mercadolibre/) |
| **OnBuy** | [onbuy.md](./onbuy.md) | United Kingdom | **Available** — [onbuy/](./onbuy/) |
| Jumia | [jumia.md](./jumia.md) | Africa (NG, KE, EG, GH + more) | Docs only — no webhook endpoint |
| **Cdiscount** | [cdiscount.md](./cdiscount.md) | France / Belgium | **Available** — [cdiscount/](./cdiscount/) |
| Faire | [faire.md](./faire.md) | Global (B2B wholesale) | Docs only — [faire/](./faire/) — requires Faire API approval |

## Accounting integrations

All 7 accounting adapters are end-to-end tested on **14 April 2026** against `api1.ilovechicken.co.uk` across all 4 chains (28/28 pass).

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
| **Telegram** | [telegram.md](./telegram.md) | **Available** — [telegram/](./telegram/) |
| Discord | [discord.md](./discord.md) | [discord/](./discord/) — Ed25519 signature; requires real Discord application keypair |
| **WhatsApp Business** | [whatsapp.md](./whatsapp.md) | **Available** — [whatsapp/](./whatsapp/) |
| **Instagram & Facebook Shops** | [instagram-shops.md](./instagram-shops.md) | **Available** — [instagram-shops/](./instagram-shops/) |

## Financial services integrations

| Platform | Guide | Status |
|----------|-------|--------|
| TrueLayer | [truelayer.md](./truelayer.md) | [truelayer/](./truelayer/) — ES512 JWK signature; requires real TrueLayer signing key |
| **Yapily** | [yapily.md](./yapily.md) | **Available** — [yapily/](./yapily/) |
| **Wormhole** | [wormhole.md](./wormhole.md) | **Available** — [wormhole/](./wormhole/) |

## AI agent & machine payment adapters

| Adapter | Files | Description | Status |
|---------|-------|-------------|--------|
| **x402** | [x402-ai-agents.md](./x402-ai-agents.md) / [x402-ai-agents/](./x402-ai-agents/) | Autonomous AI agent payments via the x402 protocol (spec v1 — `accepts` array, CAIP-2 IDs, microunit amounts, `payload.signature`) | **Production ready** — real payments smoke-tested on all 4 chains (Algorand, VOI, Stellar, Hedera), `x402/verify` confirmed on each. Adapter v2.0.0, 76/76 tests. |
| **MPP** | [mpp-adapter/mpp-adapter.md](./mpp-adapter/mpp-adapter.md) / [mpp-adapter/](./mpp-adapter/) | Machine Payments Protocol server middleware — 100% IETF `draft-ryan-httpauth-payment` compliant (challenge echo validation, CAIP-2 network routing, HMAC challenge IDs, on-chain verification, replay protection) | **Production ready** — 0.01 USDC live smoke-tested on all 4 chains (Algorand, VOI, Hedera, Stellar) 13 Apr 2026. Adapter v2.1.0, 153/153 tests. |
| **AP2** | [ap2-adapter/ap2-adapter.md](./ap2-adapter/ap2-adapter.md) / [ap2-adapter/](./ap2-adapter/) | AP2 v0.1 CartMandate/PaymentMandate server middleware with AlgoVoi crypto-algo extension. ed25519 mandate signing + on-chain tx verification across all 4 chains (Algorand, VOI, Hedera, Stellar). | **Production ready** — 0.01 USDC live smoke-tested on all 4 chains 13 Apr 2026. Real ed25519 sig verified. v2.0.0, 81/81 tests. |

## AI Platform Adapters

Drop-in payment gates for AI provider APIs. Each adapter wraps the AI call behind an on-chain payment check — the caller pays 0.01 USDC (or any configured amount) before the AI responds. All adapters accept OpenAI-format message lists and share a common interface: `check(headers, body)` → `result`, `complete(messages)` → `str`, `flask_guard()` convenience method.

| Platform | Class | SDK install | Protocol support | Files | Status |
|----------|-------|-------------|-----------------|-------|--------|
| **OpenAI** + compatible | `AlgoVoiMppAI` / `AlgoVoiAp2AI` / `AlgoVoiOpenAI` | `pip install openai` | MPP, AP2, x402 | [ai-adapters/openai/](./ai-adapters/openai/) | **Available** — 101/101 tests + smoke-tested all 4 chains 14 Apr 2026 |
| **Anthropic Claude** | `AlgoVoiClaude` | `pip install anthropic` | MPP, AP2, x402 | [ai-adapters/claude/](./ai-adapters/claude/) | **Available** — 76/76 tests + smoke-tested all 4 chains 14 Apr 2026 |
| **Google Gemini** | `AlgoVoiGemini` | `pip install google-genai` | MPP, AP2, x402 | [ai-adapters/gemini/](./ai-adapters/gemini/) | **Available** — 75/75 tests (Phase 2 pending billing-enabled key) |
| **Amazon Bedrock** | `AlgoVoiBedrock` | `pip install boto3` | MPP, AP2, x402 | [ai-adapters/bedrock/](./ai-adapters/bedrock/) | **Available** — 57/57 tests, Converse API (Nova / Claude / Llama / Titan models) |
| **Cohere** | `AlgoVoiCohere` | `pip install cohere` | MPP, AP2, x402 | [ai-adapters/cohere/](./ai-adapters/cohere/) | **Available** — Phase 1 + 1.5 + 2 PASS 4/4 chains 15 Apr 2026 |
| **xAI (Grok)** | `AlgoVoiXai` | `pip install xai-sdk` | MPP, AP2, x402 | [ai-adapters/xai/](./ai-adapters/xai/) | **Available** — 70/70 tests + Phase 1+2 PASS 4/4 chains 15 Apr 2026 (Comet-validated) |
| **Mistral** | `AlgoVoiMistral` | `pip install mistralai` | MPP, AP2, x402 | [ai-adapters/mistral/](./ai-adapters/mistral/) | **Available** — 70/70 tests + Phase 1 PASS 4/4 chains 15 Apr 2026 (Comet-validated) |

All adapters support all 4 chains (Algorand, VOI, Hedera, Stellar) and all 3 payment protocols (MPP, AP2, x402).

### OpenAI — MPP Quick start

```python
from mpp_algovoi import AlgoVoiMppAI

gate = AlgoVoiMppAI(
    openai_key        = "sk-...",
    algovoi_key       = "algv_...",
    tenant_id         = "your-tenant-uuid",
    payout_address    = "YOUR_ALGORAND_ADDRESS",
    networks          = ["algorand_mainnet"],   # or voi_mainnet / hedera_mainnet / stellar_mainnet
    amount_microunits = 10000,                  # 0.01 USDC per call
    resource_id       = "ai-chat",
)

@app.route("/ai/chat", methods=["POST"])
def chat():
    result = gate.check(dict(request.headers))
    if result.requires_payment:
        return result.as_flask_response()   # 402 + WWW-Authenticate: Payment challenge
    # result.receipt.payer, .tx_id, .amount available
    return jsonify({"content": gate.complete(request.json["messages"])})
```

Supports any OpenAI-compatible provider via `base_url`:

| Provider | base_url |
|----------|----------|
| OpenAI (default) | `https://api.openai.com/v1` |
| Mistral | `https://api.mistral.ai/v1` |
| Together AI | `https://api.together.xyz/v1` |
| Groq | `https://api.groq.com/openai/v1` |
| Perplexity | `https://api.perplexity.ai` |

### OpenAI — AP2 Quick start

```python
from ap2_algovoi import AlgoVoiAp2AI

gate = AlgoVoiAp2AI(
    openai_key        = "sk-...",
    algovoi_key       = "algv_...",
    tenant_id         = "your-tenant-uuid",
    payout_address    = "YOUR_ALGORAND_ADDRESS",
    networks          = ["algorand-mainnet", "voi-mainnet"],
    amount_microunits = 10000,                  # 0.01 USDC per call
)

@app.route("/ai/chat", methods=["POST"])
def chat():
    body   = request.get_json(silent=True) or {}
    result = gate.check(dict(request.headers), body)
    if result.requires_payment:
        return result.as_flask_response()   # 402 + X-AP2-Cart-Mandate header
    # result.mandate.payer_address, .network, .tx_id available
    return jsonify({"content": gate.complete(body["messages"])})
```

### Claude — Quick start

```python
from claude_algovoi import AlgoVoiClaude

gate = AlgoVoiClaude(
    anthropic_key     = "sk-ant-...",
    algovoi_key       = "algv_...",
    tenant_id         = "your-tenant-uuid",
    payout_address    = "YOUR_ALGORAND_ADDRESS",
    protocol          = "mpp",               # "mpp" | "ap2" | "x402"
    network           = "algorand-mainnet",
    amount_microunits = 10000,               # 0.01 USDC per call
)

@app.route("/ai/chat", methods=["POST"])
def chat():
    body   = request.get_json(silent=True) or {}
    result = gate.check(dict(request.headers), body)
    if result.requires_payment:
        return result.as_flask_response()
    return jsonify({"content": gate.complete(body["messages"])})
```

Models: `claude-opus-4-5` · `claude-sonnet-4-5` (default) · `claude-haiku-4-5`

### Gemini — Quick start

```python
from gemini_algovoi import AlgoVoiGemini

gate = AlgoVoiGemini(
    gemini_key        = "AIza...",
    algovoi_key       = "algv_...",
    tenant_id         = "your-tenant-uuid",
    payout_address    = "YOUR_ALGORAND_ADDRESS",
    protocol          = "mpp",               # "mpp" | "ap2" | "x402"
    network           = "algorand-mainnet",
    amount_microunits = 10000,               # 0.01 USDC per call
)

@app.route("/ai/chat", methods=["POST"])
def chat():
    body   = request.get_json(silent=True) or {}
    result = gate.check(dict(request.headers), body)
    if result.requires_payment:
        return result.as_flask_response()
    return jsonify({"content": gate.complete(body["messages"])})
```

Models: `gemini-2.0-flash` (default) · `gemini-2.0-flash-lite` · `gemini-2.5-pro`

### Bedrock — Quick start

```python
from bedrock_algovoi import AlgoVoiBedrock

gate = AlgoVoiBedrock(
    aws_access_key_id     = "AKIA...",       # or set AWS_ACCESS_KEY_ID env var
    aws_secret_access_key = "wJal...",       # or set AWS_SECRET_ACCESS_KEY env var
    aws_region            = "us-east-1",
    algovoi_key           = "algv_...",
    tenant_id             = "your-tenant-uuid",
    payout_address        = "YOUR_ALGORAND_ADDRESS",
    protocol              = "mpp",               # "mpp" | "ap2" | "x402"
    network               = "algorand-mainnet",
    amount_microunits     = 10000,               # 0.01 USDC per call
    model                 = "amazon.nova-pro-v1:0",
)

@app.route("/ai/chat", methods=["POST"])
def chat():
    body   = request.get_json(silent=True) or {}
    result = gate.check(dict(request.headers), body)
    if result.requires_payment:
        return result.as_flask_response()
    return jsonify({"content": gate.complete(body["messages"])})
```

Models (any model exposed by Bedrock Converse in your AWS region/account):
`amazon.nova-pro-v1:0` (default) · `amazon.nova-lite-v1:0` · `anthropic.claude-3-5-sonnet-20241022-v2:0` · `meta.llama3-70b-instruct-v1:0` · `amazon.titan-text-premier-v1:0`

### Cohere — Quick start

```python
from cohere_algovoi import AlgoVoiCohere

gate = AlgoVoiCohere(
    cohere_key        = "...",                     # Cohere API key
    algovoi_key       = "algv_...",
    tenant_id         = "your-tenant-uuid",
    payout_address    = "YOUR_ALGORAND_ADDRESS",
    protocol          = "mpp",                     # "mpp" | "ap2" | "x402"
    network           = "algorand-mainnet",
    amount_microunits = 10000,                     # 0.01 USDC per call
    model             = "command-r-plus-08-2024",
)

@app.route("/ai/chat", methods=["POST"])
def chat():
    body   = request.get_json(silent=True) or {}
    result = gate.check(dict(request.headers), body)
    if result.requires_payment:
        return result.as_flask_response()
    return jsonify({"content": gate.complete(body["messages"])})
```

Models: `command-r-plus-08-2024` (default — most capable) · `command-r-08-2024` (balanced) · `command-r7b-12-2024` (fastest)

### xAI (Grok) — Quick start

```python
from xai_algovoi import AlgoVoiXai

gate = AlgoVoiXai(
    xai_key           = "xai-...",                  # xAI API key
    algovoi_key       = "algv_...",
    tenant_id         = "your-tenant-uuid",
    payout_address    = "YOUR_ALGORAND_ADDRESS",
    protocol          = "mpp",                      # "mpp" | "ap2" | "x402"
    network           = "algorand-mainnet",
    amount_microunits = 10000,                      # 0.01 USDC per call
    model             = "grok-4",
)

@app.route("/ai/chat", methods=["POST"])
def chat():
    body   = request.get_json(silent=True) or {}
    result = gate.check(dict(request.headers), body)
    if result.requires_payment:
        return result.as_flask_response()
    return jsonify({"content": gate.complete(body["messages"])})
```

Models: `grok-4` (default — latest, most capable) · `grok-3` · `grok-3-mini` (fast + cheap) · `grok-2-1212` · `grok-2-vision-1212`

### Mistral — Quick start

```python
from mistral_algovoi import AlgoVoiMistral

gate = AlgoVoiMistral(
    mistral_key       = "...",                        # Mistral API key
    algovoi_key       = "algv_...",
    tenant_id         = "your-tenant-uuid",
    payout_address    = "YOUR_ALGORAND_ADDRESS",
    protocol          = "mpp",                        # "mpp" | "ap2" | "x402"
    network           = "algorand-mainnet",
    amount_microunits = 10000,                        # 0.01 USDC per call
    model             = "mistral-large-latest",
)

@app.route("/ai/chat", methods=["POST"])
def chat():
    body   = request.get_json(silent=True) or {}
    result = gate.check(dict(request.headers), body)
    if result.requires_payment:
        return result.as_flask_response()
    return jsonify({"content": gate.complete(body["messages"])})
```

Models: `mistral-large-latest` (default — flagship) · `mistral-medium-latest` · `mistral-small-latest` · `codestral-latest` · `open-mistral-nemo` · `pixtral-large-latest`

OpenAI-format messages work across all seven platforms — system roles are extracted automatically where required (Claude, Bedrock), Gemini `assistant` roles are mapped to `model` internally, and Cohere, xAI, and Mistral all accept the system role natively via their respective SDKs.

---

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

## Adapters with limited support

Six adapters have structural blockers that prevent full end-to-end testing:

| Adapter | Blocker |
|---------|---------|
| **BigCommerce** | Webhook signature verifies correctly, but `GET /v2/orders/{id}` for order amount requires a real `store_hash` and `access_token`. All other flow steps work. |
| **Discord** | Uses Ed25519 asymmetric signing — cannot sign test webhooks without a real Discord application keypair. |
| **TrueLayer** | Uses ES512 JWK signing — cannot sign test webhooks without a real TrueLayer private key. |
| **Faire** | Requires Faire API approval before any developer access. |
| **Jumia** | Documentation only — no webhook endpoint is publicly available. |
| **Printify** | Documentation only — no webhook endpoint is publicly available. |

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

Every adapter is hardened against real-world payment attack vectors. **Pass 1** (April 2026) covered cancel-bypass / empty-secret / cookie-swap / SSRF / timing attacks across all deployed stores and native adapters. **Pass 2** (15 April 2026) added defensive depth across the B2B webhook trio + native SDKs + a critical Rust compile fix.

#### Vulnerabilities found and fixed — Pass 1 (April 2026)

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

#### Vulnerabilities found and fixed — Pass 2 (15 April 2026)

Comet-validated audit across the B2B webhook trio and all 4 native SDKs. All seven adapters bumped from `1.0.0` to `1.1.0`.

| Vulnerability | Severity | Affected | Fix |
|---------------|----------|----------|-----|
| **Native Rust crate did not compile** | Critical | `native-rust` | `html_escape` referenced a non-existent `html::escape` module. Replaced with local implementation; crate now builds clean |
| **XSS via `</script>` break-out** | High | `native-python` | Caller-supplied `verify_url` / `success_url` were embedded into a `<script>` block via `json.dumps()`, which does not escape `</`. Added `_safe_url_for_script()` validator + belt-and-braces `</` → `<\/` neutralisation |
| **SSRF token-leak (caller-supplied URL)** | High | `amazon-mws` (`confirm_shipment`), `tiktok-shop` (`update_shipping`) | `marketplace_url` / `api_base` parameters now allowlisted to `*.amazon.com` / `*.tiktokglobalshop.com` only. SP-API access token cannot be sent to attacker-controlled hosts |
| **HMAC TypeError on bytes/None signature** | High | All Python adapters | `hmac.compare_digest` raises uncaught `TypeError` on type mismatch — surface as 500 instead of clean 401. Type guards added before the comparison |
| **`parse_order_webhook` `AttributeError` on null fields** | Medium | `tiktok-shop`, `squarespace` | `dict.get(k, default)` returns the literal `None` when the key exists but is JSON null. Added explicit `is None` checks + `AttributeError` to except tuple. Squarespace also dropped the flat-payload fallback that allowed unwrapped spoofs |
| **Plaintext API-key leak via `post()`** | High | `native-php`, `native-go`, `native-rust` | Internal `post()` helpers built request URLs from `api_base` with no scheme check. With misconfigured `http://`, the `Authorization: Bearer` header travelled in plaintext on every request. All three now refuse `http://` before any request is built |
| **Webhook body-size unbounded** | Low | All Python adapters | `verify_webhook` parsed bodies of any size, processing 1 MB+ inputs in full. Added 64 KB cap (`MAX_WEBHOOK_BODY_BYTES`) before the HMAC computation |
| **Amount sanity (`NaN` / `Inf` / negative / zero)** | Low | All adapters | `process_order` / `create_payment_link` accepted any `float`. Added `isfinite() && > 0` guard locally so the gateway round-trip is avoided |
| **`redirect_url` scheme unrestricted** | Low | All adapters | `file://`, `gopher://`, `javascript:` schemes were forwarded to the gateway verbatim. Now rejected with `https`-only allowlist |
| **`verify_payment` / `verify_hosted_return` no scheme guard** | Medium | All adapters | `_post()` had a guard but the `GET /checkout/{token}` path bypassed it. Plaintext `api_base` would leak the token in the URL. Explicit `startswith("https://")` check added on every read path |
| **`token` length cap missing** | Low | All adapters | Only `tx_id` had the 200-char cap; `token` was checked for emptiness only, allowing arbitrary-length payloads to be URL-encoded into the request path. Both inputs now length-capped |
| **Port-mismatch SSRF in `_scrape_checkout`** | Low | `native-php`, `native-go`, `native-rust` | Host comparison ignored port — same hostname on a different port slipped through. Now compares `host:port` |
| **Constructor signature drift in READMEs** | Low (docs) | 7 adapters | Quick-start examples documented args (`refresh_token`, `app_key`, `algovoi_api_key`, etc.) that did not exist on the actual classes — copy-pasting raised `AttributeError`. All 7 READMEs rewritten to match real signatures |

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
