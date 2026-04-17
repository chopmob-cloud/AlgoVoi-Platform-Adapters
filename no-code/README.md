# AlgoVoi No-Code / Automation Adapters

Integrates AlgoVoi crypto payments with the three leading workflow automation platforms.

| Adapter | Platform | Version | Tests |
|---------|----------|---------|-------|
| [zapier/](zapier/) | Zapier | 1.0.0 | 77 |
| [make/](make/) | Make (Integromat) | 1.0.0 | 71 |
| [n8n/](n8n/) | n8n | 1.0.0 | 77 |

**Total: 225 tests · 21/21 smoke checks · Phase 1 PASS**

## Quick start

Each adapter is a single Python file with zero extra dependencies (stdlib only for HTTP).

```bash
# Zapier
from zapier_algovoi import AlgoVoiZapier

handler = AlgoVoiZapier(
    algovoi_key="algv_...",
    tenant_id="...",
    payout_algorand="ADDR...",
    webhook_secret="whsec_...",      # optional
    zapier_hook_url="https://hooks.zapier.com/...",  # optional
)

# Make
from make_algovoi import AlgoVoiMake

handler = AlgoVoiMake(algovoi_key="algv_...", tenant_id="...", payout_algorand="ADDR...")

# n8n
from n8n_algovoi import AlgoVoiN8n

handler = AlgoVoiN8n(algovoi_key="algv_...", tenant_id="...", payout_algorand="ADDR...")
```

## Supported networks (16 total)

8 mainnet + 8 testnet across Algorand, VOI, Hedera, Stellar — USDC stablecoin and native coins.

## Protocols

All three adapters support **x402**, **MPP**, and **AP2** challenge generation and webhook verification.

Licensed under the Business Source License 1.1 — see [LICENSE](../LICENSE).
