# AlgoVoi Platform Adapters

Integration guides and drop-in payment plugins for connecting e-commerce platforms to **AlgoVoi Tenant Services** — enabling merchants to accept stablecoin payments settled on the Algorand, VOI, Hedera, Stellar, Base, and Solana blockchains.

---

## What is AlgoVoi?

AlgoVoi is a multi-tenant payment infrastructure layer built on the Algorand Virtual Machine (AVM) with Hedera, Stellar, Base (EVM), and Solana support. It allows merchants and developers to accept on-chain stablecoin payments through hosted checkout or browser extension flows, without managing wallets or blockchain integrations directly.

Supported settlement assets:

| Asset | Network | Details |
|-------|---------|---------|
| USDC  | Algorand mainnet | Native ASA (ASA ID 31566704), issued by Circle |
| aUSDC | VOI mainnet      | Native ASA (ASA ID 302190), Aramid-bridged USDC |
| USDC  | Hedera mainnet   | HTS token 0.0.456858, issued by Circle |
| USDC  | Stellar mainnet  | Credit asset issued by Circle (`GA5ZSEJYB37JRC5AVCIA5MOP4RHTM335X2KGX3IHOJAPP5RE34K4KZVN`); receiver must have a trust line before accepting |
| USDC  | Base mainnet     | ERC-20 token (`0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913`), issued by Circle |
| USDC  | Solana mainnet   | SPL token (`EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v`), issued by Circle |
| ALGO / VOI / HBAR / XLM / ETH / SOL | Any mainnet | Native coin payments also supported on every chain (6/6/8/7/18/9 decimals respectively) |

---

## What is this repository?

This repository contains **production-ready payment adapters** and **integration documentation** for connecting e-commerce platforms, custom applications, and AI agent services to AlgoVoi Tenant Services.

Included:
- **Drop-in plugins** for WooCommerce, OpenCart, PrestaShop, and Shopware (tested and deployed)
- **CMS payment gateways** for Drupal Commerce, Easy Digital Downloads (WordPress), and Ghost — all Comet-validated 2026-04-15
- **Native adapters** for PHP, Python, Go, and Rust (zero external dependencies) — all hardened to v1.1.0 on 2026-04-15
- **Agent protocol middleware** for MPP and AP2 (gate APIs behind payment challenges)
- **AI platform adapters** for OpenAI, Claude, Gemini, Bedrock, Cohere, xAI/Grok, and Mistral (MPP + AP2 + x402, all 6 chains)
- **AI agent framework adapters** for LangChain, LlamaIndex, CrewAI, Hugging Face, AutoGen, Semantic Kernel, Pydantic AI, DSPy, Vercel AI SDK, Google A2A, LangGraph, and Agno — gate LLM-agnostic pipelines, RAG chains, multi-agent crews, and autonomous agents (MPP + AP2 + x402, all 6 chains)
- **No-code / automation adapters** for Zapier, Make (Integromat), n8n, and **X (Twitter)** — drop-in Python classes that bridge AlgoVoi payment flows into any no-code workflow, with webhook verification, MPP + x402 + AP2 challenge generation, and all 24 networks; the X adapter auto-posts payment confirmations and checkout links to X via webhook (OAuth 1.0a, stdlib-only, 4-chain mainnet verified 2026-04-18)
- **MCP server** (`@algovoi/mcp-server` / `algovoi-mcp`) — exposes 13 AlgoVoi tools natively inside Claude Desktop, Claude Code, Cursor, and Windsurf via the Model Context Protocol
- **x402 embeddable widget** for any HTML page (Cloudflare Pages)
- **Integration guides and Python adapters for 45+ platforms** — all end-to-end tested on `api1.ilovechicken.co.uk` across all 6 chains

---

## AlgoVoi Cloud — No-Code Dashboard

The fastest way to accept stablecoin payments — no server access or code required. **[dash.algovoi.co.uk](https://dash.algovoi.co.uk)** is the hosted SaaS version of AlgoVoi: sign up with your email, verify your identity, and connect your platforms through a guided dashboard wizard. Each wizard takes under 5 minutes.

### Sign up

1. Go to [dash.algovoi.co.uk/signup](https://dash.algovoi.co.uk/signup)
2. Enter your email and choose your account type (Individual, Sole Trader, or Company)
3. Your AlgoVoi API key is shown once on screen — copy it immediately
4. Complete KYC/KYB verification in the dashboard to unlock mainnet payments

Supported chains: Algorand, VOI, Hedera, Stellar, Base, Solana

### Connect a platform

After signing in, open **Connect** from the sidebar. Every integration has a setup badge:

| Badge | Meaning |
|-------|---------|
| ⚡ 1-click | Connect through an existing account — no downloads |
| 🔧 Upload | Download a zip and upload through your platform's admin UI |
| ⌨️ CLI | Requires shell access — run commands on your server |

#### E-commerce

| Platform | Setup | Notes |
|----------|-------|-------|
| **WooCommerce** | 🔧 Upload | WordPress + WooCommerce |
| **Magento 2** | ⌨️ CLI | Adobe Commerce / Magento Open Source |
| **PrestaShop** | 🔧 Upload | PrestaShop 8.x — hosted + wallet checkout |
| **OpenCart** | 🔧 Upload | OpenCart 4 payment extension |
| **Shopware** | 🔧 Upload | Shopware 6 payment plugin |
| **Gravity Forms** | 🔧 Upload | WordPress form builder with payments |
| **GiveWP** | 🔧 Upload | WordPress donation & fundraising plugin |
| Shopify | — | Coming soon (OAuth app install) |

#### Automation

| Platform | Setup | Notes |
|----------|-------|-------|
| **Zapier** | ⚡ 1-click | Connect 6,000+ apps via Zaps |
| **n8n** | ⚡ 1-click | Open-source workflow automation |
| **Make (Integromat)** | ⚡ 1-click | Visual automation platform |
| **Pabbly Connect** | ⚡ 1-click | Affordable automation for 1,000+ apps |
| **Activepieces** | ⚡ 1-click | Open-source automation (self-host or cloud) |
| **X (Twitter)** | ⌨️ CLI | Auto-post tweets on payment confirmation |

#### AI Assistants

| Platform | Setup | Notes |
|----------|-------|-------|
| **Claude / Cursor / Windsurf** | ⚡ 1-click | AlgoVoi MCP server — 13 payment tools inside your AI assistant |

### KYC / KYB verification

Before your first mainnet payment, upload the required documents through the **Onboarding** page:

| Account type | Required documents |
|-------------|-------------------|
| Individual | Government ID, Selfie, Proof of Address, Source of Funds |
| Sole Trader | Same as Individual |
| Company | Certificate of Incorporation, Director ID, Beneficial Owner Register, Memorandum of Association, plus director personal docs |

Accepted formats: PDF, JPEG, PNG, WebP — max 50 MB per file. The dashboard auto-advances to active status when all required documents are collected.

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
│   — Live-tested Python webhook adapters (4 original chains verified 2026-04-14; Base + Solana added 2026-04-22/23) —
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
├── ai-agent-frameworks/
│   ├── langchain/        # LangChain gate — any ChatModel, LCEL chain, RAG pipeline, or ReAct agent
│   ├── llamaindex/       # LlamaIndex gate — QueryEngine, ChatEngine, RAG pipeline, or ReAct agent
│   ├── crewai/           # CrewAI gate — crew.kickoff() + BaseTool for multi-agent crews
│   ├── huggingface/      # Hugging Face gate — InferenceClient, transformers pipeline, smolagents tool
│   ├── autogen/          # AutoGen gate — initiate_chat() + callable tool (0.2.x + 0.4.x)
│   ├── semantic-kernel/  # Semantic Kernel gate — chat completion, KernelFunction, SK plugin
│   ├── pydantic-ai/      # Pydantic AI gate — any Agent, deps injection, provider:model strings
│   ├── dspy/             # DSPy gate — any Predict / ChainOfThought / ReAct / compiled program
│   ├── vercel-ai-sdk/    # Vercel AI SDK gate — generateText, streamText, tool() — TypeScript
│   ├── a2a/              # Google A2A gate — A2A v1.0 REST (6 routes), agent card + extended card, task store
│   ├── langgraph/        # LangGraph gate — StateGraph invoke/stream, ToolNode, create_react_agent
│   └── agno/             # Agno gate — pre_hooks, ASGI middleware (AgentOS), run_agent + arun_agent
├── no-code/              # No-code / automation adapters (Zapier, Make, n8n, X) — v1.0.0, 225+ tests
│   ├── zapier/           #   AlgoVoiZapier — ZapierActionResult, webhook bridge, action handlers
│   ├── make/             #   AlgoVoiMake — Make bundle dict, module handlers
│   ├── n8n/              #   AlgoVoiN8n — n8n item dict, operation handlers
│   └── x/                #   AlgoVoiX — X (Twitter) webhook adapter; auto-posts payment confirmations &amp; checkout links via OAuth 1.0a
├── mcp-server/           # MCP server — 13 AlgoVoi tools for Claude Desktop / Claude Code / Cursor / Windsurf
│   ├── typescript/       #   @algovoi/mcp-server (npm) — `npx -y @algovoi/mcp-server`
│   └── python/           #   algovoi-mcp (PyPI) — `uvx algovoi-mcp`
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

The following adapters have been end-to-end tested against a live AlgoVoi tenant on `algorand_mainnet`, `voi_mainnet`, `hedera_mainnet`, `stellar_mainnet`, `base_mainnet`, and `solana_mainnet`:

| Platform | Demo store / notes | Hosted chains | Extension chains |
|----------|--------------------|---------------|-----------------|
| OpenCart 4 | opencart.ilovechicken.co.uk | Algorand, VOI, Hedera, Stellar, Base, Solana | Algorand, VOI |
| PrestaShop 8.2.5 | prestashop.ilovechicken.co.uk | Algorand, VOI, Hedera, Stellar, Base, Solana | Algorand, VOI |
| Shopware 6.7.8.2 | shopware.ilovechicken.co.uk | Algorand, VOI, Hedera, Stellar, Base, Solana | Algorand, VOI |
| WooCommerce 10.6.2 / WordPress 6.9.4 | woo.ilovechicken.co.uk | Algorand, VOI, Hedera, Stellar, Base, Solana | Algorand, VOI |
| Shopify (Cloudflare Pages) | algovoi-3.myshopify.com | Algorand, VOI, Hedera, Stellar, Base, Solana | — |
| Magento 2 / Adobe Commerce | — | Algorand, VOI, Hedera, Stellar, Base, Solana | — |
| Amazon SP-API | — (B2B webhook) | Algorand, VOI, Hedera, Stellar, Base, Solana | — |
| TikTok Shop | — (B2B webhook) | Algorand, VOI, Hedera, Stellar, Base, Solana | — |
| Squarespace | — (B2B webhook) | Algorand, VOI, Hedera, Stellar, Base, Solana | — |
| Wix eCommerce | — (SPI checkout) | Algorand, VOI, Hedera, Stellar, Base, Solana | — |
| Native PHP | — | Algorand, VOI, Hedera, Stellar, Base, Solana | Algorand, VOI |
| Native Python | — | Algorand, VOI, Hedera, Stellar, Base, Solana | Algorand, VOI |
| Native Go | — | Algorand, VOI, Hedera, Stellar, Base, Solana | Algorand, VOI |
| Native Rust | — | Algorand, VOI, Hedera, Stellar, Base, Solana | Algorand, VOI |
| AlgoVoi 1.0 | api1.ilovechicken.co.uk/shop-demo | Algorand, VOI, Hedera, Stellar, Base, Solana | Algorand, VOI |
| QuickBooks Online | — (B2B webhook) | Algorand, VOI, Hedera, Stellar, Base, Solana | — |
| Xero | — (B2B webhook) | Algorand, VOI, Hedera, Stellar, Base, Solana | — |
| FreshBooks | — (B2B webhook, form-urlencoded + fetch_order) | Algorand, VOI, Hedera, Stellar, Base, Solana | — |
| Sage Business Cloud | — (polling, no push webhooks) | Algorand, VOI, Hedera, Stellar, Base, Solana | — |
| Zoho Books | — (B2B webhook) | Algorand, VOI, Hedera, Stellar, Base, Solana | — |
| Wave | — (B2B webhook) | Algorand, VOI, Hedera, Stellar, Base, Solana | — |
| MYOB | — (polling, no push webhooks) | Algorand, VOI, Hedera, Stellar, Base, Solana | — |
| eBay | — (Platform Notifications webhook) | Algorand, VOI, Hedera, Stellar, Base, Solana | — |
| Ecwid / Lightspeed E-Series | — (B2B webhook) | Algorand, VOI, Hedera, Stellar, Base, Solana | — |
| Etsy | — (B2B webhook) | Algorand, VOI, Hedera, Stellar, Base, Solana | — |
| Rakuten Ichiba | — (B2B webhook) | Algorand, VOI, Hedera, Stellar, Base, Solana | — |
| OnBuy | — (B2B webhook) | Algorand, VOI, Hedera, Stellar, Base, Solana | — |
| Yapily | — (open banking webhook) | Algorand, VOI, Hedera, Stellar, Base, Solana | — |
| Walmart Marketplace | — (B2B webhook) | Algorand, VOI, Hedera, Stellar, Base, Solana | — |
| CeX | — (operator bypass webhook) | Algorand, VOI, Hedera, Stellar, Base, Solana | — |
| Printful | — (print-on-demand webhook) | Algorand, VOI, Hedera, Stellar, Base, Solana | — |
| Wormhole | — (cross-chain bridge webhook) | Algorand, VOI, Hedera, Stellar, Base, Solana | — |
| WhatsApp Business | — (Meta webhook) | Algorand, VOI, Hedera, Stellar, Base, Solana | — |
| Instagram Shops | — (Meta webhook) | Algorand, VOI, Hedera, Stellar, Base, Solana | — |
| Telegram | — (Bot API webhook) | Algorand, VOI, Hedera, Stellar, Base, Solana | — |
| Allegro | — (marketplace webhook) | Algorand, VOI, Hedera, Stellar, Base, Solana | — |
| Bol.com | — (marketplace webhook) | Algorand, VOI, Hedera, Stellar, Base, Solana | — |
| Cdiscount | — (marketplace webhook) | Algorand, VOI, Hedera, Stellar, Base, Solana | — |
| Flipkart | — (Seller API webhook) | Algorand, VOI, Hedera, Stellar, Base, Solana | — |
| Lazada | — (open platform webhook) | Algorand, VOI, Hedera, Stellar, Base, Solana | — |
| Mercado Libre | — (marketplace webhook) | Algorand, VOI, Hedera, Stellar, Base, Solana | — |
| Shopee | — (open platform webhook) | Algorand, VOI, Hedera, Stellar, Base, Solana | — |
| Tokopedia | — (marketplace webhook) | Algorand, VOI, Hedera, Stellar, Base, Solana | — |
| x402 AI Agent adapter | — (x402 spec v1: `accepts` array, CAIP-2 networks, microunit amounts, `payload.signature` proof) | Algorand, VOI, Hedera, Stellar, Base, Solana | — |
| MPP Gate | — (100% IETF `draft-ryan-httpauth-payment`: challenge echo, CAIP-2 routing, HMAC IDs, on-chain verification — v2.1.0, 153/153 tests, live smoke-tested all 4 original chains 13 Apr 2026; Base + Solana added 2026-04-22/23) | Algorand, VOI, Hedera, Stellar, Base, Solana | — |
| AP2 Gate | — (payment request + local ed25519 verification) | Algorand, VOI | — |
| LangChain (AI agent frameworks) | — (MPP + AP2 + x402; gates any ChatModel, LCEL chain, RAG pipeline, or ReAct agent tool — 76/77 tests, Phase 1+2 PASS 5/5 chains 16 Apr 2026, Comet-validated) | Algorand, VOI, Hedera, Stellar, Base, Solana | — |
| LlamaIndex (AI agent frameworks) | — (MPP + AP2 + x402; gates LlamaIndex LLM, QueryEngine, ChatEngine, or ReAct agent tool — 80/80 tests, Comet-validated 16 Apr 2026) | Algorand, VOI, Hedera, Stellar, Base, Solana | — |
| CrewAI (AI agent frameworks) | — (MPP + AP2 + x402; gates crew.kickoff() + BaseTool with PaymentToolInput args_schema — 68/68 tests, Comet-validated 16 Apr 2026) | Algorand, VOI, Hedera, Stellar, Base, Solana | — |
| Hugging Face (AI agent frameworks) | — (MPP + AP2 + x402; gates InferenceClient.chat_completion(), transformers pipeline, and smolagents Tool — 83/83 tests, 16 Apr 2026) | Algorand, VOI, Hedera, Stellar, Base, Solana | — |
| AutoGen (AI agent frameworks) | — (MPP + AP2 + x402; gates initiate_chat() + callable FunctionTool-compatible tool; llm_config property; 0.2.x + 0.4.x — 86/86 tests, 16 Apr 2026) | Algorand, VOI, Hedera, Stellar, Base, Solana | — |
| Semantic Kernel (AI agent frameworks) | — (MPP + AP2 + x402; gates chat completion, kernel.invoke(), and @kernel_function plugin; asyncio.run() sync wrappers — 76/76 tests, 16 Apr 2026) | Algorand, VOI, Hedera, Stellar, Base, Solana | — |
| Pydantic AI (AI agent frameworks) | — (MPP + AP2 + x402; gates any Agent with deps injection, all provider:model strings, pydantic_ai.tools.Tool-compatible — 77/77 tests, 16 Apr 2026) | Algorand, VOI, Hedera, Stellar, Base, Solana | — |
| DSPy (AI agent frameworks) | — (MPP + AP2 + x402; gates any Predict / ChainOfThought / ReAct / compiled program; dspy.context isolation, plain callable tool for ReAct — 78/78 tests, Phase 1 9/9 PASS 16 Apr 2026, Comet-validated) | Algorand, VOI, Hedera, Stellar, Base, Solana | — |
| Vercel AI SDK (AI agent frameworks) | — (MPP + AP2 + x402; TypeScript; generateText + streamText + tool() + nextHandler; any @ai-sdk/* provider — 79/79 tests, Phase 1 12/12 PASS 16 Apr 2026, Comet-validated) | Algorand, VOI, Hedera, Stellar, Base, Solana | — |
| Google A2A (AI agent frameworks) | — (MPP + AP2 + x402; A2A v1.0 REST server + client; 6 live endpoints: `/.well-known/agent.json`, `/extendedAgentCard`, `/message:send`, `/tasks`, `/tasks/{id}`, `/tasks/{id}:cancel`; extended agent card with payment auth metadata; legacy JSON-RPC 2.0 compat kept — 120/120 tests, Phase 1 12/12 PASS 16 Apr 2026, Comet-validated) | Algorand, VOI, Hedera, Stellar, Base, Solana | — |
| LangGraph (AI agent frameworks) | — (MPP + AP2 + x402; gates compiled StateGraph invoke/stream; AlgoVoiPaymentTool is BaseTool subclass, ToolNode-compatible, create_react_agent-compatible; flask_guard + flask_agent convenience wrappers — 77/77 tests, Phase 1 12/12 PASS 16 Apr 2026, Comet-validated) | Algorand, VOI, Hedera, Stellar, Base, Solana | — |
| Agno (AI agent frameworks) | — (MPP + AP2 + x402; gates any Agno Agent via pre_hooks, ASGI middleware for AgentOS, run_agent/arun_agent wrappers, flask_guard + flask_agent; AgnoPaymentRequired exception — 88/88 tests, Phase 1 13/13 PASS 16 Apr 2026, Comet-validated) | Algorand, VOI, Hedera, Stellar, Base, Solana | — |
| Zapier (no-code) | — (webhook bridge + action handlers: create_payment_link, verify_payment, list_networks, generate_challenge MPP/x402/AP2; ZapierActionResult return type — 77/77 tests, Phase 1+2 PASS 17 Apr 2026, Comet-validated) | 24 networks (12 mainnet + 12 testnet) | — |
| Make / Integromat (no-code) | — (module handlers: create_payment_link, verify_payment, list_networks, generate_challenge MPP/x402/AP2; Make bundle dict return type — 71/71 tests, Phase 1+2 PASS 17 Apr 2026, Comet-validated) | 24 networks (12 mainnet + 12 testnet) | — |
| n8n (no-code) | — (operation handlers: create_payment_link, verify_payment, list_networks, generate MPP/x402/AP2 challenges; n8n item dict return type — 77/77 tests, Phase 1+2 PASS 17 Apr 2026, Comet-validated) | 24 networks (12 mainnet + 12 testnet) | — |
| X / Twitter (no-code) | — (webhook adapter + OAuth 1.0a tweet posting; auto-posts payment confirmations &amp; checkout links when AlgoVoi fires a webhook; 62/62 unit tests; 4-chain mainnet e2e verified 18 Apr 2026; Base + Solana added 2026-04-22/23 — payments confirmed on-chain, tweets posted automatically) | Algorand, VOI, Hedera, Stellar, Base, Solana | — |

**Last webhook test:** 14 April 2026 — all 39 testable adapters passed on all 4 original chains (`algorand_mainnet`, `voi_mainnet`, `hedera_mainnet`, `stellar_mainnet`); Base and Solana added 2026-04-22/23. Checkout pages validated live via Comet CDP. 6 adapters skipped: BigCommerce (partial — order-amount fetch needs real API credentials), Discord (Ed25519), TrueLayer (ES512), Faire/Jumia/Printify (docs only).

**Accounting adapters unit tests:** 339 passing, 0 failing (includes replay attack prevention coverage — commit `5025c4e`)

**AI agent adapters — production ready as of 13 April 2026:**
- x402: **spec v1 compliant** — `x402Version: 1`, `accepts` array, CAIP-2 network IDs, string microunit amounts, `payload.signature` proof format. Real payments smoke-tested on all 4 original chains (Algorand, VOI, Stellar, Hedera mainnet); Base and Solana added 2026-04-22/23. `x402/verify` confirmed `verified:true` on each. 76/76 unit tests passing. Adapter v2.0.0.
- MPP: **100% IETF spec compliant** (v2.1.0) — `id` (HMAC-SHA256), `method`, `intent="charge"`, `request=` (charge intent object), `expires`, challenge echo validation (Table 3), CAIP-2 network routing, replay protection, spec-compliant `Payment-Receipt`. On-chain verification smoke-tested on all 4 original chains (Algorand, VOI, Hedera, Stellar) 13 Apr 2026 ×2; Base and Solana added 2026-04-22/23. 153/153 unit tests.
- AP2: **production ready** (v2.0.0) — AP2 v0.1 CartMandate/PaymentMandate with AlgoVoi crypto-algo extension. CartMandate issues `PaymentMethodData` per extension schema (`network`, `receiver`, `amount_microunits`, `asset_id`, `min_confirmations`, `memo_required`). PaymentMandate accepts `payment_response.details.{network, tx_id, note_field}`. ed25519 sig + on-chain AVM verification. PyNaCl + cryptography fallback both confirmed. 81/81 tests.

### Two payment flows

**Hosted checkout** — Customer is redirected to a secure AlgoVoi-hosted payment page. Supports Algorand, VOI, Hedera, Stellar, Base, and Solana. Works with any wallet (Pera, Defly, Lute, HashPack, Freighter, LOBSTR, MetaMask, Phantom, …). Payment confirmed via webhook or API status check. Used by all platforms including Shopify.

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

## CMS integrations

Drop-in payment gateways for major content-management and publishing platforms. All three were shipped together on **15 April 2026** and Comet-validated end-to-end. Each adapter applies the full April 2026 + pass-2 hardening set (cancel-bypass guard, empty-secret HMAC reject, timing-safe compare, 64 KB body cap, https-only outbound, amount sanity, scheme guards, token length caps, mandatory payment cross-check on webhooks).

| Platform | Guide | Files | Engine | Status |
|----------|-------|-------|--------|--------|
| **Drupal Commerce** | [drupal-commerce/README.md](./drupal-commerce/README.md) | [drupal-commerce/](./drupal-commerce/) | Drupal 10 / 11 + Commerce 2 / 3 | **Available — OffsitePaymentGatewayBase module, DI-driven, v1.0.0** |
| **Easy Digital Downloads** | [easy-digital-downloads/README.md](./easy-digital-downloads/README.md) | [easy-digital-downloads/](./easy-digital-downloads/) | EDD 3.2+ WordPress plugin | **Available — digital downloads + licensing + recurring, v1.0.0** |
| **Ghost** | [ghost/README.md](./ghost/README.md) | [ghost/](./ghost/) | Ghost 5.x (Python, Admin API / JWT) | **Available — grant-on-payment member upgrade, v1.0.0** |

Each adapter folder ships a `README.md` with a how-it-works diagram, quick-start, supported chains, webhook endpoint, security posture table, and dependency list.

## Regional & international marketplace integrations

All regional marketplace adapters have been end-to-end tested on **14 April 2026** across all 4 original chains; Base and Solana added 2026-04-22/23. Checkout pages validated live via Comet CDP.

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

All 7 accounting adapters are end-to-end tested on **14 April 2026** against `api1.ilovechicken.co.uk` across all 4 original chains (28/28 pass); Base and Solana added 2026-04-22/23.

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
| **x402** | [x402-ai-agents.md](./x402-ai-agents.md) / [x402-ai-agents/](./x402-ai-agents/) | Autonomous AI agent payments via the x402 protocol (spec v1 — `accepts` array, CAIP-2 IDs, microunit amounts, `payload.signature`) | **Production ready** — real payments smoke-tested on all 4 original chains (Algorand, VOI, Stellar, Hedera); Base and Solana added 2026-04-22/23, `x402/verify` confirmed on each. Adapter v2.0.0, 76/76 tests. |
| **MPP** | [mpp-adapter/mpp-adapter.md](./mpp-adapter/mpp-adapter.md) / [mpp-adapter/](./mpp-adapter/) | Machine Payments Protocol server middleware — 100% IETF `draft-ryan-httpauth-payment` compliant (challenge echo validation, CAIP-2 network routing, HMAC challenge IDs, on-chain verification, replay protection) | **Production ready** — 0.01 USDC live smoke-tested on all 4 original chains (Algorand, VOI, Hedera, Stellar) 13 Apr 2026; Base and Solana added 2026-04-22/23. Adapter v2.1.0, 153/153 tests. |
| **AP2** | [ap2-adapter/ap2-adapter.md](./ap2-adapter/ap2-adapter.md) / [ap2-adapter/](./ap2-adapter/) | AP2 v0.1 CartMandate/PaymentMandate server middleware with AlgoVoi crypto-algo extension. ed25519 mandate signing + on-chain tx verification across all 6 chains (Algorand, VOI, Hedera, Stellar, Base, Solana). | **Production ready** — 0.01 USDC live smoke-tested on all 4 original chains 13 Apr 2026; Base + Solana added 2026-04-22/23. Real ed25519 sig verified. v2.0.0, 81/81 tests. |

## AI Platform Adapters

Drop-in payment gates for AI provider APIs. Each adapter wraps the AI call behind an on-chain payment check — the caller pays 0.01 USDC (or any configured amount) before the AI responds. All adapters accept OpenAI-format message lists and share a common interface: `check(headers, body)` → `result`, `complete(messages)` → `str`, `flask_guard()` convenience method.

| Platform | Class | SDK install | Protocol support | Files | Status |
|----------|-------|-------------|-----------------|-------|--------|
| **OpenAI** + compatible | `AlgoVoiMppAI` / `AlgoVoiAp2AI` / `AlgoVoiOpenAI` | `pip install openai` | MPP, AP2, x402 | [ai-adapters/openai/](./ai-adapters/openai/) | **Available** — 101/101 tests + smoke-tested all 4 original chains 14 Apr 2026; Base + Solana added 2026-04-22/23 |
| **Anthropic Claude** | `AlgoVoiClaude` | `pip install anthropic` | MPP, AP2, x402 | [ai-adapters/claude/](./ai-adapters/claude/) | **Available** — 76/76 tests + smoke-tested all 4 original chains 14 Apr 2026; Base + Solana added 2026-04-22/23 |
| **Google Gemini** | `AlgoVoiGemini` | `pip install google-genai` | MPP, AP2, x402 | [ai-adapters/gemini/](./ai-adapters/gemini/) | **Available** — 75/75 tests (Phase 2 pending billing-enabled key) |
| **Amazon Bedrock** | `AlgoVoiBedrock` | `pip install boto3` | MPP, AP2, x402 | [ai-adapters/bedrock/](./ai-adapters/bedrock/) | **Available** — 57/57 tests, Converse API (Nova / Claude / Llama / Titan models) |
| **Cohere** | `AlgoVoiCohere` | `pip install cohere` | MPP, AP2, x402 | [ai-adapters/cohere/](./ai-adapters/cohere/) | **Available** — Phase 1 + 1.5 + 2 PASS 4/4 chains 15 Apr 2026 |
| **xAI (Grok)** | `AlgoVoiXai` | `pip install xai-sdk` | MPP, AP2, x402 | [ai-adapters/xai/](./ai-adapters/xai/) | **Available** — 70/70 tests + Phase 1+2 PASS 4/4 chains 15 Apr 2026 (Comet-validated) |
| **Mistral** | `AlgoVoiMistral` | `pip install mistralai` | MPP, AP2, x402 | [ai-adapters/mistral/](./ai-adapters/mistral/) | **Available** — 70/70 tests + Phase 1 PASS 4/4 chains 15 Apr 2026 (Comet-validated) |

All adapters support all 6 chains (Algorand, VOI, Hedera, Stellar, Base, Solana) and all 3 payment protocols (MPP, AP2, x402).

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

## AI Agent Framework Adapters

Gate entire orchestration frameworks behind on-chain payment — not just a single model provider. These adapters are LLM-agnostic: pass any pre-built ChatModel, LCEL chain, RAG pipeline, or ReAct agent and the payment check wraps the whole thing.

| Framework | Class | Install | Protocol support | Files | Status |
|-----------|-------|---------|-----------------|-------|--------|
| **LangChain** | `AlgoVoiLangChain` + `AlgoVoiPaymentTool` | `pip install langchain-core langchain-openai` | MPP, AP2, x402 | [ai-agent-frameworks/langchain/](./ai-agent-frameworks/langchain/) | **Available** — 76/77 tests + Phase 1+2 PASS 5/5 chains 16 Apr 2026 (Comet-validated) |
| **LlamaIndex** | `AlgoVoiLlamaIndex` + `AlgoVoiPaymentTool` | `pip install llama-index` | MPP, AP2, x402 | [ai-agent-frameworks/llamaindex/](./ai-agent-frameworks/llamaindex/) | **Available** — 80/80 tests, Comet-validated 16 Apr 2026 |
| **CrewAI** | `AlgoVoiCrewAI` + `AlgoVoiPaymentTool` | `pip install crewai` | MPP, AP2, x402 | [ai-agent-frameworks/crewai/](./ai-agent-frameworks/crewai/) | **Available** — 68/68 tests, Comet-validated 16 Apr 2026 |
| **Hugging Face** | `AlgoVoiHuggingFace` + `AlgoVoiPaymentTool` | `pip install huggingface-hub smolagents` | MPP, AP2, x402 | [ai-agent-frameworks/huggingface/](./ai-agent-frameworks/huggingface/) | **Available** — 83/83 tests, 16 Apr 2026 |
| **AutoGen** | `AlgoVoiAutoGen` + `AlgoVoiPaymentTool` | `pip install pyautogen` | MPP, AP2, x402 | [ai-agent-frameworks/autogen/](./ai-agent-frameworks/autogen/) | **Available** — 86/86 tests, 16 Apr 2026 |
| **Semantic Kernel** | `AlgoVoiSemanticKernel` + `AlgoVoiPaymentPlugin` | `pip install semantic-kernel` | MPP, AP2, x402 | [ai-agent-frameworks/semantic-kernel/](./ai-agent-frameworks/semantic-kernel/) | **Available** — 76/76 tests, 16 Apr 2026 |
| **Pydantic AI** | `AlgoVoiPydanticAI` + `AlgoVoiPaymentTool` | `pip install pydantic-ai` | MPP, AP2, x402 | [ai-agent-frameworks/pydantic-ai/](./ai-agent-frameworks/pydantic-ai/) | **Available** — 77/77 tests, 16 Apr 2026 |
| **DSPy** | `AlgoVoiDSPy` + `AlgoVoiPaymentTool` | `pip install dspy` | MPP, AP2, x402 | [ai-agent-frameworks/dspy/](./ai-agent-frameworks/dspy/) | **Available** — 78/78 tests, Phase 1 9/9 PASS 16 Apr 2026, Comet-validated |
| **Vercel AI SDK** | `AlgoVoiVercelAI` + `VercelAIResult` | `npm i ai zod` | MPP, AP2, x402 | [ai-agent-frameworks/vercel-ai-sdk/](./ai-agent-frameworks/vercel-ai-sdk/) | **Available** — 79/79 tests, Phase 1 12/12 PASS 16 Apr 2026, Comet-validated — **TypeScript** |
| **Google A2A** | `AlgoVoiA2A` + `AlgoVoiPaymentTool` | `pip install flask` | MPP, AP2, x402 | [ai-agent-frameworks/a2a/](./ai-agent-frameworks/a2a/) | **Available** — 84/84 tests, Phase 1 12/12 PASS 16 Apr 2026, Comet-validated |

### LangChain — Quick start

```python
from langchain_algovoi import AlgoVoiLangChain

gate = AlgoVoiLangChain(
    openai_key        = "sk-...",          # OpenAI key (or pass llm= to use any ChatModel)
    algovoi_key       = "algv_...",
    tenant_id         = "your-tenant-uuid",
    payout_address    = "YOUR_ALGORAND_ADDRESS",
    protocol          = "mpp",             # "mpp" | "ap2" | "x402"
    network           = "algorand-mainnet",
    amount_microunits = 10000,             # 0.01 USDC per call
)

@app.route("/ai/chat", methods=["POST"])
def chat():
    body   = request.get_json(silent=True) or {}
    result = gate.check(dict(request.headers), body)
    if result.requires_payment:
        return result.as_flask_response()
    return jsonify({"content": gate.complete(body["messages"])})
```

**Bring your own model** — pass any pre-built LangChain ChatModel instead of an OpenAI key:

```python
from langchain_anthropic import ChatAnthropic

gate = AlgoVoiLangChain(
    algovoi_key    = "algv_...",
    tenant_id      = "...",
    payout_address = "...",
    llm            = ChatAnthropic(model="claude-opus-4-5"),
)
```

**Gate any LCEL chain or RAG pipeline:**

```python
chain = ChatPromptTemplate.from_template("Answer: {question}") | ChatOpenAI() | StrOutputParser()

result = gate.check(headers, body)
if not result.requires_payment:
    output = gate.invoke_chain(chain, {"question": body["question"]})
```

**Drop into a ReAct agent as a `BaseTool`:**

```python
tool = gate.as_tool(resource_fn=lambda q: my_handler(q), tool_name="premium_kb")

from langchain.agents import create_react_agent, AgentExecutor
agent    = create_react_agent(llm, tools=[tool], prompt=prompt)
executor = AgentExecutor(agent=agent, tools=[tool])
```

The tool accepts `{"query": "...", "payment_proof": "<base64>"}`. Returns a challenge JSON dict if proof is absent or invalid; calls `resource_fn(query)` and returns the result if verified.

All 6 chains and all 3 protocols supported. Full reference: [ai-agent-frameworks/langchain/README.md](./ai-agent-frameworks/langchain/README.md)

### LlamaIndex — Quick start

```python
from llamaindex_algovoi import AlgoVoiLlamaIndex

gate = AlgoVoiLlamaIndex(
    openai_key        = "sk-...",
    algovoi_key       = "algv_...",
    tenant_id         = "your-tenant-uuid",
    payout_address    = "YOUR_ALGORAND_ADDRESS",
    protocol          = "mpp",
    network           = "algorand-mainnet",
    amount_microunits = 10000,
)

# Gate a LlamaIndex QueryEngine (RAG pipeline)
result = gate.check(headers, body)
if not result.requires_payment:
    answer = gate.query_engine_query(query_engine, body["query"])

# Gate a ChatEngine (multi-turn)
if not result.requires_payment:
    reply = gate.chat_engine_chat(chat_engine, body["message"])
```

**ReAct agent tool** — drop into any LlamaIndex agent:

```python
from llama_index.core.agent import ReActAgent

tool  = gate.as_tool(resource_fn=my_handler, tool_name="premium_kb")
agent = ReActAgent.from_tools([tool], llm=llm, verbose=True)
```

The tool accepts `{"query": "...", "payment_proof": "<base64>"}`. Returns a `ToolOutput` with `.content` (challenge JSON or resource result), `.tool_name`, `.raw_input`, `.raw_output`.

**Bring your own LlamaIndex LLM** (Anthropic, Google, Cohere, Bedrock, etc.):

```python
from llama_index.llms.anthropic import Anthropic

gate = AlgoVoiLlamaIndex(
    algovoi_key    = "algv_...",
    tenant_id      = "...",
    payout_address = "...",
    llm            = Anthropic(model="claude-opus-4-5"),
)
```

All 6 chains and all 3 protocols supported. Full reference: [ai-agent-frameworks/llamaindex/README.md](./ai-agent-frameworks/llamaindex/README.md)

### CrewAI — Quick start

```python
from crewai_algovoi import AlgoVoiCrewAI
from crewai import Agent, Task, Crew, LLM

gate = AlgoVoiCrewAI(
    openai_key        = "sk-...",
    algovoi_key       = "algv_...",
    tenant_id         = "your-tenant-uuid",
    payout_address    = "YOUR_ALGORAND_ADDRESS",
    protocol          = "mpp",
    network           = "algorand-mainnet",
    amount_microunits = 10000,
)

# Gate a crew.kickoff() call
result = gate.check(headers, body)
if not result.requires_payment:
    output = gate.crew_kickoff(my_crew, inputs={"topic": body["topic"]})

# Or use flask_guard with an inputs extractor
@app.route("/ai/research", methods=["POST"])
def research():
    return gate.flask_guard(my_crew, inputs_fn=lambda b: {"topic": b.get("topic", "")})
```

**Add AlgoVoiPaymentTool to any CrewAI agent:**

```python
tool = gate.as_tool(resource_fn=my_handler, tool_name="premium_kb")

researcher = Agent(
    role      = "Research Analyst",
    goal      = "Use premium_kb to answer questions.",
    backstory  = "Expert researcher.",
    tools     = [tool],
    llm       = LLM(model="openai/gpt-4o"),
)
```

The tool uses `PaymentToolInput` (Pydantic `args_schema`) — the agent generates `{"query": "...", "payment_proof": "<base64>"}`, CrewAI validates it, and `_run(query, payment_proof)` is called directly as kwargs. Any `crewai.LLM` provider (OpenAI, Anthropic, Gemini, Bedrock, Groq, Together AI, …) is supported via the LiteLLM router.

All 6 chains and all 3 protocols supported. Full reference: [ai-agent-frameworks/crewai/README.md](./ai-agent-frameworks/crewai/README.md)

### Hugging Face — Quick start

```python
from huggingface_algovoi import AlgoVoiHuggingFace

gate = AlgoVoiHuggingFace(
    hf_token          = "hf_...",
    algovoi_key       = "algv_...",
    tenant_id         = "your-tenant-uuid",
    payout_address    = "YOUR_ALGORAND_ADDRESS",
    protocol          = "mpp",
    network           = "algorand-mainnet",
    amount_microunits = 10000,
    model             = "meta-llama/Meta-Llama-3-8B-Instruct",
)

# Gate InferenceClient.chat_completion()
result = gate.check(headers, body)
if not result.requires_payment:
    reply = gate.complete(body["messages"])

# Gate a transformers pipeline
from transformers import pipeline
pipe = pipeline("text-generation", model="HuggingFaceH4/zephyr-7b-beta", token="hf_...")
if not result.requires_payment:
    answer = gate.inference_pipeline(pipe, body["messages"])
```

**Drop into a smolagents `ToolCallingAgent`:**

```python
from smolagents import ToolCallingAgent, InferenceClientModel

tool  = gate.as_tool(resource_fn=my_handler, tool_name="premium_kb")
model = InferenceClientModel(model_id="meta-llama/Meta-Llama-3-8B-Instruct")
agent = ToolCallingAgent(tools=[tool], model=model)
agent.run("Use premium_kb to answer my question.")
```

The tool accepts `query` and `payment_proof` (base64) as kwargs. Returns challenge JSON if proof absent/invalid; calls `resource_fn(query)` and returns the result if verified. Works with any `smolagents` agent type (`ToolCallingAgent`, `CodeAgent`, custom).

All 6 chains and all 3 protocols supported. Full reference: [ai-agent-frameworks/huggingface/README.md](./ai-agent-frameworks/huggingface/README.md)

### AutoGen — Quick start

```python
from autogen_algovoi import AlgoVoiAutoGen

gate = AlgoVoiAutoGen(
    openai_key        = "sk-...",
    algovoi_key       = "algv_...",
    tenant_id         = "your-tenant-uuid",
    payout_address    = "YOUR_ALGORAND_ADDRESS",
    protocol          = "mpp",
    network           = "algorand-mainnet",
    amount_microunits = 10000,
)

# Build agents from gate.llm_config
from autogen import AssistantAgent, UserProxyAgent
assistant  = AssistantAgent("assistant",  llm_config=gate.llm_config)
user_proxy = UserProxyAgent("user_proxy", human_input_mode="NEVER",
                             max_consecutive_auto_reply=3,
                             code_execution_config=False)

# Gate a conversation
result = gate.check(headers, body)
if not result.requires_payment:
    output = gate.initiate_chat(assistant, user_proxy, body["message"], max_turns=5)
```

**Callable tool — AutoGen 0.2.x:**

```python
tool = gate.as_tool(resource_fn=my_handler, tool_name="premium_kb")

@user_proxy.register_for_execution()
@assistant.register_for_llm(description=tool.description, name=tool.name)
def premium_kb(query: str, payment_proof: str = "") -> str:
    return tool(query=query, payment_proof=payment_proof)
```

**AutoGen 0.4.x `FunctionTool`:**

```python
from autogen_core.tools import FunctionTool
fn_tool = FunctionTool(tool, description=tool.description, name=tool.name)
```

All 6 chains and all 3 protocols supported. Full reference: [ai-agent-frameworks/autogen/README.md](./ai-agent-frameworks/autogen/README.md)

### Semantic Kernel — Quick start

```python
from semantic_kernel_algovoi import AlgoVoiSemanticKernel

gate = AlgoVoiSemanticKernel(
    openai_key        = "sk-...",
    algovoi_key       = "algv_...",
    tenant_id         = "your-tenant-uuid",
    payout_address    = "YOUR_ALGORAND_ADDRESS",
    protocol          = "mpp",
    network           = "algorand-mainnet",
    amount_microunits = 10000,
    model             = "gpt-4o",
)

# Gate SK chat completion (sync wrapper around async SK API)
result = gate.check(headers, body)
if not result.requires_payment:
    reply = gate.complete(body["messages"])

# Gate any KernelFunction
output = gate.invoke_function(kernel, summarise_fn, input=body["text"])
```

**Add as a `@kernel_function` plugin:**

```python
plugin = gate.as_plugin(resource_fn=my_handler, plugin_name="premium_kb")
kernel.add_plugin(plugin, plugin_name="premium_kb")
# The LLM can select plugin.gate() via function calling (auto-invocation)
```

The `gate` function accepts `query` and `payment_proof` (base64). Returns challenge JSON if proof absent/invalid; calls `resource_fn(query)` and returns the result if verified.

All 6 chains and all 3 protocols supported. Full reference: [ai-agent-frameworks/semantic-kernel/README.md](./ai-agent-frameworks/semantic-kernel/README.md)

### Pydantic AI — Quick start

```python
from pydanticai_algovoi import AlgoVoiPydanticAI

gate = AlgoVoiPydanticAI(
    openai_key        = "sk-...",
    algovoi_key       = "algv_...",
    tenant_id         = "your-tenant-uuid",
    payout_address    = "YOUR_ALGORAND_ADDRESS",
    protocol          = "mpp",
    network           = "algorand-mainnet",
    amount_microunits = 10000,
    model             = "openai:gpt-4o",     # any Pydantic AI provider:model string
)

# Gate chat completion
result = gate.check(headers, body)
if not result.requires_payment:
    reply = gate.complete(body["messages"])

# Gate any pre-built Agent (with optional dependency injection)
from pydantic_ai import Agent
my_agent = Agent("anthropic:claude-opus-4-5", system_prompt="Be concise.")
output   = gate.run_agent(my_agent, body["prompt"], deps=my_deps)
```

**Add as a `pydantic_ai.tools.Tool`:**

```python
from pydantic_ai.tools import Tool

tool  = gate.as_tool(resource_fn=my_handler, tool_name="premium_kb")
agent = Agent("openai:gpt-4o", tools=[Tool(tool, name=tool.name, description=tool.description)])
```

The tool accepts `query` and `payment_proof` (base64). Returns challenge JSON if proof absent/invalid; calls `resource_fn(query)` if verified. Supports all Pydantic AI providers — OpenAI, Anthropic, Google, Groq, Ollama, and any OpenAI-compatible endpoint via `base_url`.

All 6 chains and all 3 protocols supported. Full reference: [ai-agent-frameworks/pydantic-ai/README.md](./ai-agent-frameworks/pydantic-ai/README.md)

### DSPy — Quick start

```python
from dspy_algovoi import AlgoVoiDSPy

gate = AlgoVoiDSPy(
    openai_key        = "sk-...",
    algovoi_key       = "algv_...",
    tenant_id         = "your-tenant-uuid",
    payout_address    = "YOUR_ALGORAND_ADDRESS",
    protocol          = "mpp",
    network           = "algorand-mainnet",
    amount_microunits = 10000,
    model             = "openai/gpt-4o",   # DSPy provider/model string (slash, not colon)
)

# Gate any DSPy module
import dspy

class QA(dspy.Signature):
    """Answer the question."""
    question: str = dspy.InputField()
    answer:   str = dspy.OutputField()

result = gate.check(headers, body)
if not result.requires_payment:
    answer = gate.run_module(dspy.ChainOfThought(QA), question=body["question"])
```

**Gate a compiled DSPy program:**

```python
# Works with any compiled / optimised DSPy program (Predict, ChainOfThought, ReAct, MIPROv2…)
result = gate.run_module(my_compiled_program, question=body["question"])
```

**Drop into a ReAct agent as a plain callable tool:**

```python
tool  = gate.as_tool(resource_fn=my_handler, tool_name="premium_kb")
react = dspy.ReAct(QA, tools=[tool])

lm = gate._ensure_lm()
with dspy.context(lm=lm):
    out = react(question=body["question"])
```

All LLM calls use `dspy.context(lm=...)` — global `dspy.configure()` state is never modified. DSPy's `provider/model` string format is supported for OpenAI, Anthropic, Google, Cohere, Groq, Ollama, and Azure OpenAI.

All 6 chains and all 3 protocols supported. Full reference: [ai-agent-frameworks/dspy/README.md](./ai-agent-frameworks/dspy/README.md)

### Vercel AI SDK — Quick start

```typescript
import { openai } from "@ai-sdk/openai";
import { AlgoVoiVercelAI } from "./vercel_ai_algovoi";

const gate = new AlgoVoiVercelAI({
  algovoiKey:       "algv_...",
  tenantId:         "your-tenant-uuid",
  payoutAddress:    "YOUR_ALGORAND_ADDRESS",
  protocol:         "mpp",
  network:          "algorand-mainnet",
  amountMicrounits: 10_000,
  model:            openai("gpt-4o"),   // any @ai-sdk/* provider
});

// Next.js App Router — one-liner
export const POST = (req: Request) => gate.nextHandler(req);
```

**Streaming:**

```typescript
export async function POST(req: Request) {
  const body = await req.json();
  const result = await gate.check(req.headers, body);
  if (result.requiresPayment) return result.as402Response();
  return gate.streamText(body.messages).toDataStreamResponse();
}
```

**Payment tool for LLM function calling:**

```typescript
const tool = gate.asTool(
  async (query) => myPremiumHandler(query),
  { toolName: "premium_kb", toolDescription: "Access premium knowledge base." }
);
// Use in generateText({ tools: { premium_kb: tool } })
```

Supports any `@ai-sdk/*` provider — OpenAI, Anthropic, Google, Groq, Mistral, Cohere, Ollama, Azure. Uses `node:crypto` for MPP HMAC; requires Node.js runtime (not Edge) for MPP. x402 and AP2 work on Edge runtimes.

All 6 chains and all 3 protocols supported. Full reference: [ai-agent-frameworks/vercel-ai-sdk/README.md](./ai-agent-frameworks/vercel-ai-sdk/README.md)

---

### Google A2A — Quick start

```python
from a2a_algovoi import AlgoVoiA2A

gate = AlgoVoiA2A(
    algovoi_key="algv_...",
    tenant_id="your-tenant-uuid",
    payout_address="YOUR_ALGORAND_ADDRESS",
    protocol="mpp",
    network="algorand-mainnet",
    amount_microunits=10_000,
    agent_name="My AlgoVoi Agent",
)

# Flask A2A server
from flask import Flask, jsonify
app = Flask(__name__)

@app.route("/a2a", methods=["POST"])
def a2a_endpoint():
    return gate.flask_agent(lambda text: my_llm(text))

@app.route("/.well-known/agent-card.json")
def card():
    return jsonify(gate.agent_card("https://myhost.com/a2a"))

# A2A client — call another agent
response = gate.send_message("https://other-agent.example.com/a2a", "hello", payment_proof="proof")
task = response["result"]  # {"id": "...", "status": {"state": "completed"}, "artifacts": [...]}

# Payment tool for A2A pipelines
tool = gate.as_tool(lambda q: fetch_kb(q), tool_name="premium_kb")
```

All 6 chains and all 3 protocols supported. Full reference: [ai-agent-frameworks/a2a/README.md](./ai-agent-frameworks/a2a/README.md)

---

## No-Code / Automation Adapters

Drop-in Python classes that bridge AlgoVoi crypto payment flows into Zapier, Make (Integromat), and n8n — the three leading no-code / low-code automation platforms. Each adapter is a single file with zero external dependencies (stdlib HTTP only), mirrors the native Python adapter pattern, and applies the full April 2026 + pass-2 security hardening.

All three adapters were shipped on **17 April 2026** and are Comet-validated end-to-end.

| Platform | Class | Return format | Files | Tests | Status |
|----------|-------|---------------|-------|-------|--------|
| **Zapier** | `AlgoVoiZapier` | `ZapierActionResult` dataclass | [no-code/zapier/](./no-code/zapier/) | 77 | **Available** — Phase 1+2 PASS |
| **Make (Integromat)** | `AlgoVoiMake` | Make bundle dict | [no-code/make/](./no-code/make/) | 71 | **Available** — Phase 1+2 PASS |
| **n8n** | `AlgoVoiN8n` | n8n item dict | [no-code/n8n/](./no-code/n8n/) | 77 | **Available** — Phase 1+2 PASS |

**Total: 225/225 tests · 21/21 smoke checks (Phase 1) · 3/3 live create_payment_link + verify_payment (Phase 2)**

Supported across all 24 networks (12 mainnet + 12 testnet) on Algorand, VOI, Hedera, Stellar, Base, and Solana. All three adapters support MPP, x402, and AP2 challenge generation.

### Zapier — Quick start

```python
from zapier_algovoi import AlgoVoiZapier

handler = AlgoVoiZapier(
    algovoi_key    = "algv_...",
    tenant_id      = "your-tenant-uuid",
    payout_algorand= "YOUR_ALGORAND_ADDRESS",
    webhook_secret = "whsec_...",                          # optional
    zapier_hook_url= "https://hooks.zapier.com/hooks/catch/XXXX/YYYY/",  # optional
)

# Create a payment link (Zapier action)
result = handler.action_create_payment_link({
    "amount":   5.00,
    "currency": "USD",
    "label":    "Premium access",
    "network":  "algorand_mainnet",
})
# result.success, result.data["checkout_url"], result.data["token"]

# Verify payment status
result = handler.action_verify_payment({"token": "tok_..."})
# result.data["paid"] → True/False, result.data["status"] → "active"|"paid"|...

# Receive and forward an AlgoVoi webhook to a Zapier Catch Hook
result = handler.receive_and_forward(raw_body=..., signature=...)

# Generate MPP / x402 / AP2 challenge
result = handler.action_generate_challenge({
    "protocol":          "mpp",        # "mpp" | "x402" | "ap2"
    "resource_id":       "/api/premium",
    "amount_microunits": 10_000,
    "network":           "algorand_mainnet",
})
```

### Make (Integromat) — Quick start

```python
from make_algovoi import AlgoVoiMake

handler = AlgoVoiMake(
    algovoi_key     = "algv_...",
    tenant_id       = "your-tenant-uuid",
    payout_algorand = "YOUR_ALGORAND_ADDRESS",
    payout_stellar  = "G...",    # optional — add any chain
)

# Create a payment link (Make module)
bundle = handler.module_create_payment_link({
    "amount":   10.00,
    "currency": "USD",
    "label":    "API access — 30 days",
    "network":  "stellar_mainnet",
})
# bundle["data"]["checkout_url"], bundle["data"]["token"]
# on error: bundle["error"]["message"], bundle["error"]["code"]

# Verify payment
bundle = handler.module_verify_payment({"token": "tok_..."})
# bundle["data"]["paid"], bundle["data"]["status"]

# Generate challenge (MPP / x402 / AP2)
bundle = handler.module_generate_challenge({
    "protocol":          "x402",
    "resource_id":       "/api/v1/data",
    "amount_microunits": 500_000,
    "network":           "stellar_mainnet",
})

# Receive AlgoVoi webhook
bundle = handler.receive_webhook(raw_body=..., signature=...)
```

### n8n — Quick start

```python
from n8n_algovoi import AlgoVoiN8n

handler = AlgoVoiN8n(
    algovoi_key   = "algv_...",
    tenant_id     = "your-tenant-uuid",
    payout_hedera = "0.0.XXXXX",   # set whichever chains you support
)

# Create a payment link (n8n Code node operation)
item = handler.execute_create_payment_link({
    "amount":   2.50,
    "currency": "USD",
    "label":    "Agent service call",
    "network":  "hedera_mainnet",
})
# item["json"]["success"], item["json"]["checkout_url"], item["json"]["token"]

# Verify payment
item = handler.execute_verify_payment({"token": "tok_..."})
# item["json"]["paid"], item["json"]["status"]

# Generate challenges
item = handler.execute_generate_mpp_challenge({
    "resource_id": "/api/premium", "amount_microunits": 10_000, "network": "algorand_mainnet"
})
item = handler.execute_generate_x402_challenge({
    "resource_id": "/api/data",    "amount_microunits": 500_000, "network": "algorand_mainnet"
})
item = handler.execute_generate_ap2_mandate({
    "resource_id": "/service",     "amount_microunits": 2_000_000, "network": "voi_mainnet"
})

# Receive and verify an AlgoVoi webhook
item = handler.receive_webhook(raw_body=..., signature=...)
item = handler.execute_verify_webhook_signature({"raw_body": ..., "signature": ...})
```

Full reference: [no-code/README.md](./no-code/README.md)

---

## MCP Server

An [MCP (Model Context Protocol)](https://modelcontextprotocol.io/) server that exposes AlgoVoi's payment infrastructure as tools directly inside Claude Desktop, Claude Code, Cursor, Windsurf, and any other MCP-compatible AI assistant. Ships as two packages — pick whichever runtime your client supports:

| Package | Install | Command |
|---------|---------|---------|
| **`@algovoi/mcp-server`** (npm) | `npm i -g @algovoi/mcp-server` | `npx -y @algovoi/mcp-server` |
| **`algovoi-mcp`** (PyPI) | `pip install algovoi-mcp` | `uvx algovoi-mcp` |

### 13 built-in tools

| # | Tool | What it does |
|---|------|-------------|
| 1 | `create_payment_link` | Create a hosted-checkout URL for a given amount and chain |
| 2 | `verify_payment` | Verify a checkout token (optionally with a tx_id) |
| 3 | `prepare_extension_payment` | In-page wallet-flow params (Algorand / VOI) |
| 4 | `verify_webhook` | HMAC-SHA256 signature check for AlgoVoi webhooks |
| 5 | `list_networks` | Supported chains + asset IDs (offline, no API call) |
| 6 | `generate_mpp_challenge` | IETF MPP 402 `WWW-Authenticate` headers + challenge_id |
| 7 | `verify_mpp_receipt` | Verify an MPP on-chain receipt (direct indexer, no API call) |
| 8 | `verify_x402_proof` | Verify an x402 base64 payment proof (direct indexer) |
| 9 | `generate_x402_challenge` | x402 `X-Payment-Required` 402 headers + payload |
| 10 | `generate_ap2_mandate` | AP2 v0.1 `PaymentMandate` for AI agent payment flows |
| 11 | `verify_ap2_payment` | Verify an AP2 mandate payment receipt (direct indexer) |
| 12 | `fetch_agent_card` | `GET {agent_url}/.well-known/agent.json` — discover an A2A agent's capabilities and payment requirements |
| 13 | `send_a2a_message` | `POST {agent_url}/message:send` — call a payment-gated A2A v1.0 agent; returns task on 200, challenge headers on 402 for pay-and-retry |

### Quick start — Claude Desktop / Claude Code / Cursor

```json
{
  "mcpServers": {
    "algovoi": {
      "command": "npx",
      "args": ["-y", "@algovoi/mcp-server"],
      "env": {
        "ALGOVOI_API_KEY":         "algv_...",
        "ALGOVOI_TENANT_ID":       "...",
        "ALGOVOI_PAYOUT_ALGORAND": "<your-algorand-address>",
        "ALGOVOI_PAYOUT_VOI":      "<your-voi-address>",
        "ALGOVOI_PAYOUT_HEDERA":   "0.0.<your-account>",
        "ALGOVOI_PAYOUT_STELLAR":  "G<your-stellar-address>",
        "ALGOVOI_PAYOUT_BASE":     "0x<your-evm-address>",
        "ALGOVOI_PAYOUT_SOLANA":   "<your-solana-address>"
      }
    }
  }
}
```

Single-chain users only need to set the env var for their chain — the others are optional. For Base use `ALGOVOI_PAYOUT_BASE`; for Solana use `ALGOVOI_PAYOUT_SOLANA`. For the Python package, swap `"command": "uvx", "args": ["algovoi-mcp"]`.

Config file locations: **Claude Desktop** `%APPDATA%\Claude\claude_desktop_config.json` (Windows) / `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) · **Claude Code** `~/.claude.json` · **Cursor** `~/.cursor/mcp.json`

Full reference: [mcp-server/README.md](./mcp-server/README.md) · TypeScript source: [mcp-server/typescript/](./mcp-server/typescript/) · Python source: [mcp-server/python/](./mcp-server/python/)

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
  chains="ALGO,VOI,XLM,HBAR,ETH,SOL"
  tenant-id="your-tenant-id"
  api-key="algv_your-api-key">
</algovoi-x402>
```

| Feature | Detail |
|---------|--------|
| Format | `<algovoi-x402>` Web Component — works in any HTML page |
| Chains | `ALGO` (Algorand), `VOI`, `XLM` (Stellar), `HBAR` (Hedera), `ETH` (Base), `SOL` (Solana) |
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
Customer places order and selects chain (Algorand / VOI / Hedera / Stellar / Base / Solana)
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
3. **Configure networks** — Add payout addresses for Algorand, VOI, Hedera, Stellar, Base, and/or Solana
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
