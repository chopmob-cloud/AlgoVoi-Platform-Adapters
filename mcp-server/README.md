# AlgoVoi MCP Server

An [MCP (Model Context Protocol)](https://modelcontextprotocol.io/) server that exposes AlgoVoi's payment infrastructure as tools any MCP client can call — Claude Desktop, Claude Code, Cursor, Windsurf, or any other MCP-compatible assistant.

Ship as **two packages**:

| Package | Install | Command |
|---------|---------|---------|
| [**TypeScript**](./typescript) | `npm i -g @algovoi/mcp-server` | `npx -y @algovoi/mcp-server` |
| [**Python**](./python) | `pip install algovoi-mcp` | `uvx algovoi-mcp` or `algovoi-mcp` |

Both expose the **same 8 tools** and the same API surface — pick whichever runtime your client prefers.

---

## 8 tools

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

Supported networks: **Algorand**, **VOI**, **Hedera**, **Stellar** (USDC on all four).

---

## Configuration

Both packages read the same env vars:

| Var | Required | Purpose |
|-----|----------|---------|
| `ALGOVOI_API_KEY` | ✅ | `algv_...` API key |
| `ALGOVOI_TENANT_ID` | ✅ | Tenant UUID |
| `ALGOVOI_PAYOUT_ADDRESS` | ✅ | Default wallet for payouts |
| `ALGOVOI_WEBHOOK_SECRET` | — | For `verify_webhook` |
| `ALGOVOI_API_BASE` | — | Override the AlgoVoi API base URL (advanced) |

**Auth is env-var only.** Secrets never pass through tool arguments — the MCP client never sees the API key.

---

## Claude Desktop / Claude Code / Cursor — config snippet

```json
{
  "mcpServers": {
    "algovoi": {
      "command": "npx",
      "args": ["-y", "@algovoi/mcp-server"],
      "env": {
        "ALGOVOI_API_KEY": "algv_...",
        "ALGOVOI_TENANT_ID": "...",
        "ALGOVOI_PAYOUT_ADDRESS": "..."
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

# Stdio integration smoke — boots both servers and confirms all 8 tools list
python smoke_stdio.py
```

---

Licensed under the [Business Source License 1.1](../LICENSE).
