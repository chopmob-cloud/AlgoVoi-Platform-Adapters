# AlgoVoi Platform Adapters

Integration guides for connecting e-commerce platforms to **AlgoVoi Tenant Services** — enabling merchants to accept stablecoin payments settled on the Algorand and VOI blockchains.

---

## What is AlgoVoi?

AlgoVoi is a multi-tenant payment infrastructure layer built on the Algorand Virtual Machine (AVM). It allows merchants and developers to accept on-chain stablecoin payments through a hosted checkout experience, without managing wallets or blockchain integrations directly.

Supported settlement assets:

| Asset | Network | Details |
|-------|---------|---------|
| USDC | Algorand mainnet | Native ASA (ASA ID 31566704), issued by Circle |
| aUSDC | VOI mainnet | ARC200 token (app ID 311051) |

---

## What is this repository?

This repository contains **public integration documentation** for connecting third-party e-commerce platforms to AlgoVoi Tenant Services.

Each guide covers:
- How the integration works end-to-end
- Prerequisites and setup steps
- Network and asset configuration
- Webhook registration
- Troubleshooting

> This repository contains documentation only. AlgoVoi platform source code is not published here.

---

## E-commerce integrations

| Platform | Guide | Status |
|----------|-------|--------|
| Shopify | [shopify.md](./shopify.md) | Available |
| WooCommerce | [woocommerce.md](./woocommerce.md) | Available |
| Magento 1 & 2 | [magento.md](./magento.md) | Available |
| BigCommerce | [bigcommerce.md](./bigcommerce.md) | Available |
| Wix eCommerce | [wix.md](./wix.md) | Available |
| PrestaShop | [prestashop.md](./prestashop.md) | Available |
| Squarespace Commerce | [squarespace.md](./squarespace.md) | Available |
| eBay | [ebay.md](./ebay.md) | Available |
| Walmart | [walmart.md](./walmart.md) | Available |
| Amazon | [amazon.md](./amazon.md) | Available |
| CeX | [cex.md](./cex.md) | Available |

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
