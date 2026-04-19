# @algovoi/mcp-server

MCP server for [AlgoVoi](https://github.com/chopmob-cloud/AlgoVoi-Platform-Adapters) — create crypto payment links, verify payments, and generate MPP / x402 challenges from any MCP client (Claude Desktop, Claude Code, Cursor, Windsurf).

Supports **all 16 AlgoVoi networks**: USDC on Algorand, VOI, Hedera, Stellar (mainnet + testnet) and native ALGO, VOI, HBAR, XLM (mainnet + testnet).

## Install

```bash
# Via npx (no global install)
npx -y @algovoi/mcp-server

# Or install globally
npm install -g @algovoi/mcp-server
algovoi-mcp-server
```

Requires Node ≥ 20.

## Configure

### Option A — AlgoVoi Cloud (recommended)

[AlgoVoi Cloud](https://dash.algovoi.co.uk) gives you a single `algvc_...` key that covers all your integrations (WooCommerce, Zapier, n8n, MCP). Every payment your AI assistant creates appears in the Cloud dashboard alongside payments from every other platform.

```json
{
  "mcpServers": {
    "algovoi": {
      "command": "npx",
      "args": ["-y", "@algovoi/mcp-server"],
      "env": {
        "ALGOVOI_API_KEY": "algvc_...",
        "ALGOVOI_API_BASE": "https://cloud.algovoi.co.uk"
      }
    }
  }
}
```

Sign up free at [dash.algovoi.co.uk](https://dash.algovoi.co.uk).

### Option B — AlgoVoi direct

Connect straight to the AlgoVoi API with your `algv_...` key:

```json
{
  "mcpServers": {
    "algovoi": {
      "command": "npx",
      "args": ["-y", "@algovoi/mcp-server"],
      "env": {
        "ALGOVOI_API_KEY": "algv_...",
        "ALGOVOI_TENANT_ID": "your-tenant-uuid",
        "ALGOVOI_PAYOUT_ADDRESS": "YOUR_WALLET_ADDRESS",
        "ALGOVOI_WEBHOOK_SECRET": "optional"
      }
    }
  }
}
```

Sign up at [algovoi.co.uk](https://www.algovoi.co.uk) to get your API key and tenant ID.

## Tools

| Tool | Purpose |
|------|---------|
| `create_payment_link` | Hosted-checkout URL for Algorand / VOI / Hedera / Stellar |
| `verify_payment` | Check if a checkout token settled (optional tx_id) |
| `prepare_extension_payment` | In-page wallet flow params (Algorand / VOI) |
| `verify_webhook` | HMAC-SHA256 AlgoVoi webhook verification |
| `list_networks` | Supported chains + asset IDs |
| `generate_mpp_challenge` | IETF MPP 402 `WWW-Authenticate` response |
| `verify_mpp_receipt` | Verify MPP on-chain receipt |
| `verify_x402_proof` | Verify x402 base64 proof |

## Example prompts

> "Create an AlgoVoi payment link for $5 USDC on Algorand, labeled 'Order #42'."

> "Verify payment token abc123."

> "Generate an MPP 402 challenge for my /premium route, $0.01 per call, on Algorand and VOI."

## Development

```bash
git clone https://github.com/chopmob-cloud/AlgoVoi-Platform-Adapters
cd AlgoVoi-Platform-Adapters/mcp-server/typescript
npm install
npm run build
npm test
```

Run the built server directly for debugging:

```bash
ALGOVOI_API_KEY=algv_... \
ALGOVOI_TENANT_ID=... \
ALGOVOI_PAYOUT_ADDRESS=... \
  node dist/index.js
```

## License

Business Source License 1.1 — see [LICENSE](../../LICENSE).
