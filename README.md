# AlgoVoi Platform Adapters

Integration guides and drop-in payment plugins for connecting e-commerce platforms to **AlgoVoi Tenant Services** — enabling merchants to accept stablecoin payments settled on the Algorand, VOI, and Hedera blockchains.

---

## What is AlgoVoi?

AlgoVoi is a multi-tenant payment infrastructure layer built on the Algorand Virtual Machine (AVM) with Hedera support. It allows merchants and developers to accept on-chain stablecoin payments through hosted checkout or browser extension flows, without managing wallets or blockchain integrations directly.

Supported settlement assets:

| Asset | Network | Details |
|-------|---------|---------|
| USDC | Algorand mainnet | Native ASA (ASA ID 31566704), issued by Circle |
| aUSDC | VOI mainnet | Native ASA (ASA ID 302190), Aramid-bridged USDC |
| USDC | Hedera mainnet | Via AlgoVoi hosted checkout |

---

## What is this repository?

This repository contains **public integration documentation** for connecting third-party e-commerce platforms to AlgoVoi Tenant Services.

Each guide covers:
- How the integration works end-to-end
- Prerequisites and setup steps
- Network and asset configuration
- Webhook registration
- Troubleshooting

Where a platform requires installable files (WordPress plugins, config templates, etc.) they are included in a subfolder alongside the guide.

> This repository contains documentation only. AlgoVoi platform source code is not published here.

---

## Repository structure

```
platform-adapters/
├── {adapter}.md          # Integration guide (one per platform)
└── {adapter}/            # Adapter-specific files where applicable
    ├── *.php             # PHP modules / plugins
    ├── theme/            # Theme CSS and templates (PrestaShop)
    ├── *.json            # Config templates
    └── ...
```

Integration guides (`.md`) are always at the root. Supporting files — plugins, config templates, deployment scripts — live in a matching subfolder named after the adapter.

### Live-tested adapters

The following adapters have been end-to-end tested against a live AlgoVoi tenant on `algorand_mainnet`, `voi_mainnet`, and `hedera_mainnet`:

| Platform | Demo store | Hosted chains | Extension chains |
|----------|-----------|---------------|-----------------|
| OpenCart 4 | opencart.ilovechicken.co.uk | Algorand, VOI, Hedera | Algorand, VOI |
| PrestaShop 8.2.5 | prestashop.ilovechicken.co.uk | Algorand, VOI, Hedera | Algorand, VOI |
| Shopware 6.7.8.2 | shopware.ilovechicken.co.uk | Algorand, VOI, Hedera | Algorand, VOI |
| WooCommerce 10.6.2 / WordPress 6.9.4 | woocommerce.ilovechicken.co.uk | Algorand, VOI, Hedera | Algorand, VOI |
| Native PHP | — | Algorand, VOI, Hedera | Algorand, VOI |
| Native Python | — | Algorand, VOI, Hedera | Algorand, VOI |
| Native Go | — | Algorand, VOI, Hedera | Algorand, VOI |
| Native Rust | — | Algorand, VOI, Hedera | Algorand, VOI |
| AlgoVoi 1.0 | api1.ilovechicken.co.uk/shop-demo | Algorand, VOI, Hedera | Algorand, VOI |

### Two payment flows

**Hosted checkout** — Customer is redirected to a secure AlgoVoi-hosted payment page. Supports Algorand, VOI, and Hedera. Works with any wallet. Payment confirmed via webhook or API status check.

**Extension payment** — Customer pays directly on the store page using the AlgoVoi browser extension and algosdk. Supports Algorand and VOI only (AVM chains). No redirect required.

---

## E-commerce integrations

| Platform | Guide | Files | Status |
|----------|-------|-------|--------|
| **Native PHP** | — | [native-php/](./native-php/) | **Available — drop-in, zero dependencies** |
| **Native Python** | — | [native-python/](./native-python/) | **Available — stdlib only, no pip install** |
| **Native Go** | — | [native-go/](./native-go/) | **Available — stdlib only, no go get** |
| **Native Rust** | — | [native-rust/](./native-rust/) | **Available — zero crates, pure stdlib** |
| Shopify | [shopify.md](./shopify.md) | — | Available |
| WooCommerce | [woocommerce.md](./woocommerce.md) | [woocommerce/](./woocommerce/) | Available |
| Magento 1 & 2 | [magento.md](./magento.md) | — | Available |
| BigCommerce | [bigcommerce.md](./bigcommerce.md) | — | Available |
| Wix eCommerce | [wix.md](./wix.md) | — | Available |
| PrestaShop | [prestashop.md](./prestashop.md) | [prestashop/](./prestashop/) | Available |
| Squarespace Commerce | [squarespace.md](./squarespace.md) | — | Available |
| eBay | [ebay.md](./ebay.md) | — | Available |
| Walmart | [walmart.md](./walmart.md) | — | Available |
| Amazon | [amazon.md](./amazon.md) | — | Available |
| CeX | [cex.md](./cex.md) | — | Available |
| Ecwid | [ecwid.md](./ecwid.md) | — | Available |
| OpenCart | [opencart.md](./opencart.md) | [opencart/](./opencart/) | Available |
| Shopware | [shopware.md](./shopware.md) | [shopware/](./shopware/) | Available |
| TikTok Shop | [tiktok-shop.md](./tiktok-shop.md) | — | Available |

## Regional & international marketplace integrations

| Platform | Guide | Region | Status |
|----------|-------|--------|--------|
| Flipkart | [flipkart.md](./flipkart.md) | India | Available |
| Etsy | [etsy.md](./etsy.md) | Global | Available |
| Printful | [printful.md](./printful.md) | Global (print-on-demand) | Available |
| Printify | [printify.md](./printify.md) | Global (print-on-demand) | Available |
| Bol.com | [bolcom.md](./bolcom.md) | Netherlands / Belgium | Available |
| Lazada | [lazada.md](./lazada.md) | SE Asia (MY, TH, PH, SG, ID, VN) | Available |
| Tokopedia | [tokopedia.md](./tokopedia.md) | Indonesia | Available |
| Rakuten | [rakuten.md](./rakuten.md) | Japan / France / Germany | Available |
| Allegro | [allegro.md](./allegro.md) | Poland / Central & Eastern Europe | Available |
| Shopee | [shopee.md](./shopee.md) | SE Asia / Brazil | Available |
| Mercado Libre | [mercadolibre.md](./mercadolibre.md) | Latin America | Available |
| OnBuy | [onbuy.md](./onbuy.md) | United Kingdom | Available |
| Jumia | [jumia.md](./jumia.md) | Africa (NG, KE, EG, GH + more) | Available |
| Cdiscount | [cdiscount.md](./cdiscount.md) | France / Belgium | Available |
| Faire | [faire.md](./faire.md) | Global (B2B wholesale) | Requires Faire API approval |

## Accounting integrations

| Platform | Guide | Status |
|----------|-------|--------|
| QuickBooks Online | [quickbooks-online.md](./quickbooks-online.md) | Available |
| Xero | [xero.md](./xero.md) | Available |
| FreshBooks | [freshbooks.md](./freshbooks.md) | Available |
| Sage Business Cloud | [sage-business-cloud.md](./sage-business-cloud.md) | Available |
| Zoho Books | [zoho-books.md](./zoho-books.md) | Available |
| Wave | [wave.md](./wave.md) | Available |
| MYOB | [myob.md](./myob.md) | Available |

## Social commerce integrations

| Platform | Guide | Status |
|----------|-------|--------|
| Telegram | [telegram.md](./telegram.md) | Available |
| Discord | [discord.md](./discord.md) | Available |
| WhatsApp Business | [whatsapp.md](./whatsapp.md) | Available |
| Instagram & Facebook Shops | [instagram-shops.md](./instagram-shops.md) | Requires Meta Tech Provider agreement |

## Financial services integrations

| Platform | Guide | Status |
|----------|-------|--------|
| TrueLayer | [truelayer.md](./truelayer.md) | Available |
| Yapily | [yapily.md](./yapily.md) | Available |
| Wormhole | [wormhole.md](./wormhole.md) | Available |

## AI agent payments (x402)

| Guide | Description |
|-------|-------------|
| [x402-ai-agents.md](./x402-ai-agents.md) | Autonomous AI agent payments via the x402 protocol |

---

## How payments work

```
Customer places order and selects chain (Algorand / VOI / Hedera)
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

All adapters include:
- **HMAC webhook verification** with `hash_equals` — empty secrets rejected before HMAC check
- **SSRF protection** — checkout URL host validated against configured API base
- **Cancel-bypass prevention** — hosted checkout returns verified via API before marking orders complete
- **Order ownership checks** — customer ID cross-referenced on verify endpoints
- **TLS enforced** — SSL verification on all outbound HTTP calls
- **Input validation** — network whitelist, tx_id length guard, timing-safe comparisons

---

## Getting started

1. [Create an AlgoVoi tenant account](https://av.ilc-n.xyz)
2. Configure your network and payout address via the AlgoVoi Control Plane API
3. Follow the integration guide for your platform (see table above)

---

## Support

For questions about connecting your platform to AlgoVoi Tenant Services, open an issue in this repository or contact the AlgoVoi team.
