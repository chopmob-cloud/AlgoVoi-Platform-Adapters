# AlgoVoi Platform Adapters

Integration guides for connecting e-commerce platforms to **AlgoVoi Tenant Services** — enabling merchants to accept stablecoin payments settled on the Algorand and VOI blockchains.

---

## What is AlgoVoi?

AlgoVoi is a multi-tenant payment infrastructure layer built on the Algorand Virtual Machine (AVM). It allows merchants and developers to accept on-chain stablecoin payments through a hosted checkout experience, without managing wallets or blockchain integrations directly.

Supported settlement assets:

| Asset | Network | Details |
|-------|---------|---------|
| USDC | Algorand mainnet | Native ASA (ASA ID 31566704), issued by Circle |
| aUSDC | VOI mainnet | ARC200 token (app ID 302190) |

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

The following adapters have been end-to-end tested against a live AlgoVoi tenant on both `algorand_mainnet` and `voi_mainnet`:

| Platform | Demo store | Modules included |
|----------|-----------|-----------------|
| OpenCart 4 | opencart.ilovechicken.co.uk | Hosted checkout + wallet extension |
| PrestaShop 8.2.5 | prestashop.ilovechicken.co.uk | Hosted checkout + wallet extension |
| Shopware 6.7.8.2 | shopware.ilovechicken.co.uk | Hosted checkout + wallet extension |
| WooCommerce 10.6.2 / WordPress 6.9.4 | woocommerce.ilovechicken.co.uk | Hosted checkout + wallet extension |
| AlgoVoi 1.0 | api1.ilovechicken.co.uk/shop-demo | Hosted checkout + wallet extension |

---

## E-commerce integrations

| Platform | Guide | Files | Status |
|----------|-------|-------|--------|
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
Customer places order on your store
            ↓
AlgoVoi receives the order via webhook
            ↓
Hosted checkout link created (USDC or aUSDC)
            ↓
Customer pays on-chain (Algorand or VOI)
            ↓
AlgoVoi verifies the transaction on-chain
            ↓
Order marked as paid in your platform
```

Payments are verified directly on-chain — no intermediary holds funds. Settlement goes straight to the merchant's configured payout address.

---

## Getting started

1. [Create an AlgoVoi tenant account](https://av.ilc-n.xyz)
2. Configure your network and payout address via the AlgoVoi Control Plane API
3. Follow the integration guide for your platform (see table above)

---

## Support

For questions about connecting your platform to AlgoVoi Tenant Services, open an issue in this repository or contact the AlgoVoi team.
