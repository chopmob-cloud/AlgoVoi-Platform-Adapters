# AlgoVoi MCP Server

An [MCP (Model Context Protocol)](https://modelcontextprotocol.io/) server that exposes AlgoVoi's payment infrastructure as tools any MCP client can call — Claude Desktop, Claude Code, Cursor, Windsurf, or any other MCP-compatible assistant.

Ships as **two packages**:

| Package | Install | Command |
|---------|---------|---------|
| [**TypeScript**](./typescript) | `npm i -g @algovoi/mcp-server` | `npx -y @algovoi/mcp-server` |
| [**Python**](./python) | `pip install algovoi-mcp` | `uvx algovoi-mcp` or `algovoi-mcp` |

Both expose the **same 11 tools** and the same API surface — pick whichever runtime your client prefers.

---

## 11 tools

| # | Tool | What it does |
|---|------|-------------|
| 1 | `create_payment_link` | Hosted-checkout URL for a given amount + chain |
| 2 | `verify_payment` | Verify a checkout token (optionally with a tx_id) |
| 3 | `prepare_extension_payment` | In-page wallet-flow params (Algorand / VOI) |
| 4 | `verify_webhook` | HMAC-SHA256 signature check for AlgoVoi webhooks |
| 5 | `list_networks` | Supported chains + asset IDs (offline, no API call) |
| 6 | `generate_mpp_challenge` | IETF MPP 402 `WWW-Authenticate` headers + challenge_id |
| 7 | `verify_mpp_receipt` | Verify an MPP on-chain receipt |
| 8 | `verify_x402_proof` | Verify an x402 base64 payment proof |
| 9 | `generate_x402_challenge` | x402 `X-Payment-Required` 402 headers + payload |
| 10 | `generate_ap2_mandate` | AP2 v0.1 `PaymentMandate` for AI agent payment flows |
| 11 | `verify_ap2_payment` | Verify an AP2 mandate payment receipt |

Supported networks: **Algorand**, **VOI**, **Hedera**, **Stellar** (USDC on all four).

---

## Two ways to connect

### Option A — AlgoVoi Cloud (recommended)

[AlgoVoi Cloud](https://dash.algovoi.co.uk) is the control plane for all your integrations — WooCommerce, Zapier, n8n, and MCP all in one dashboard. Use a single `algvc_...` Cloud key; no tenant ID or payout addresses needed in your MCP config (they're stored in the dashboard).

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

Every payment Claude creates appears in your Cloud dashboard alongside payments from every other platform. One place to see everything.

Sign up free at [dash.algovoi.co.uk](https://dash.algovoi.co.uk).

---

### Option B — AlgoVoi direct

Connect straight to the AlgoVoi API with your `algv_...` key and tenant ID.

Both packages read the same env vars:

| Var | Required | Purpose |
|-----|----------|---------|
| `ALGOVOI_API_KEY` | ✅ | `algv_...` API key from the AlgoVoi dashboard |
| `ALGOVOI_TENANT_ID` | ✅ | Tenant UUID from the AlgoVoi dashboard |
| `ALGOVOI_PAYOUT_ALGORAND` | ✅* | Algorand payout wallet address |
| `ALGOVOI_PAYOUT_VOI` | ✅* | VOI payout wallet address |
| `ALGOVOI_PAYOUT_HEDERA` | ✅* | Hedera payout account (e.g. `0.0.123456`) |
| `ALGOVOI_PAYOUT_STELLAR` | ✅* | Stellar payout address (`G...`) |
| `ALGOVOI_PAYOUT_ADDRESS` | — | Universal fallback if per-chain vars are not set |
| `ALGOVOI_WEBHOOK_SECRET` | — | For `verify_webhook` |
| `ALGOVOI_API_BASE` | — | Override the AlgoVoi API base URL (default: `https://api1.ilovechicken.co.uk`) |

**\*** At least one per-chain address (or `ALGOVOI_PAYOUT_ADDRESS` as fallback) is required.

**Auth is env-var only.** Secrets never pass through tool arguments — the MCP client never sees the API key.

Sign up at [www.algovoi.co.uk](https://www.algovoi.co.uk) to get your API key and tenant ID.

```json
{
  "mcpServers": {
    "algovoi": {
      "command": "npx",
      "args": ["-y", "@algovoi/mcp-server"],
      "env": {
        "ALGOVOI_API_KEY": "algv_...",
        "ALGOVOI_TENANT_ID": "...",
        "ALGOVOI_PAYOUT_ALGORAND": "<your-algorand-address>",
        "ALGOVOI_PAYOUT_VOI":      "<your-voi-address>",
        "ALGOVOI_PAYOUT_HEDERA":   "0.0.<your-account>",
        "ALGOVOI_PAYOUT_STELLAR":  "G<your-stellar-address>"
      }
    }
  }
}
```

For the Python package, swap `"command": "uvx", "args": ["algovoi-mcp"]`.

Config file locations:
- **Claude Desktop**: `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS), `%APPDATA%\Claude\claude_desktop_config.json` (Windows)
- **Claude Code**: `~/.claude.json`
- **Cursor**: `~/.cursor/mcp.json`

---

## Testing

```bash
# TypeScript unit tests
cd typescript && npm test

# Python unit tests
cd python && pytest

# Stdio integration smoke — boots both servers and confirms all 11 tools list
python smoke_stdio.py
```

---

Licensed under the [Business Source License 1.1](../LICENSE).
