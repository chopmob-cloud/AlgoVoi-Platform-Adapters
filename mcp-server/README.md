# AlgoVoi MCP Server

An [MCP (Model Context Protocol)](https://modelcontextprotocol.io/) server that exposes AlgoVoi's payment infrastructure as tools any MCP client can call — Claude Desktop, Claude Code, Cursor, Windsurf, or any other MCP-compatible assistant.

Ships as **two packages**:

| Package | Install | Command |
|---------|---------|---------|
| [**TypeScript**](./typescript) | `npm i -g @algovoi/mcp-server` | `npx -y @algovoi/mcp-server` |
| [**Python**](./python) | `pip install algovoi-mcp` | `uvx algovoi-mcp` or `algovoi-mcp` |

Both expose the **same 13 tools** and the same API surface — pick whichever runtime your client prefers.

---

## 13 tools

### Payment tools

| # | Tool | What it does |
|---|------|-------------|
| 1 | `create_payment_link` | Hosted-checkout URL for a given amount + chain |
| 2 | `verify_payment` | Verify a checkout token (optionally with a tx_id) |
| 3 | `prepare_extension_payment` | In-page wallet-flow params (Algorand / VOI) |
| 4 | `verify_webhook` | HMAC-SHA256 signature check for AlgoVoi webhooks |
| 5 | `list_networks` | Supported chains + asset IDs (offline, no API call) |

### Protocol challenge tools

| # | Tool | What it does |
|---|------|-------------|
| 6 | `generate_mpp_challenge` | IETF MPP 402 `WWW-Authenticate` headers + challenge_id |
| 7 | `verify_mpp_receipt` | Verify an MPP on-chain receipt (direct indexer, no API call) |
| 8 | `verify_x402_proof` | Verify an x402 base64 payment proof (direct indexer) |
| 9 | `generate_x402_challenge` | x402 `X-Payment-Required` 402 headers + payload |
| 10 | `generate_ap2_mandate` | AP2 v0.1 `PaymentMandate` for AI agent payment flows |
| 11 | `verify_ap2_payment` | Verify an AP2 mandate payment receipt (direct indexer) |

### A2A agent tools *(new in v1.2.0)*

| # | Tool | What it does |
|---|------|-------------|
| 12 | `fetch_agent_card` | `GET {agent_url}/.well-known/agent.json` — discover an A2A agent's capabilities and payment requirements before calling it |
| 13 | `send_a2a_message` | `POST {agent_url}/message:send` — call a payment-gated A2A v1.0 agent; returns the task result on 200, or `challenge_headers` on 402 so Claude can pay and retry |

#### A2A pay-and-call flow

```
1. fetch_agent_card("https://agent.example.com")
   → see agent costs $0.01, accepts MPP on Algorand

2. send_a2a_message(agent_url, "What is the price of ALGO?")
   → payment_required: true, challenge_headers: {WWW-Authenticate: ...}

3. generate_mpp_challenge(...)   ← use tool #6
   → user pays on-chain

4. send_a2a_message(agent_url, text, payment_proof="<proof>")
   → task result returned
```

Supported networks: **Algorand**, **VOI**, **Hedera**, **Stellar** (USDC on all four + native ALGO/VOI/HBAR/XLM).

---

## Two ways to connect

### Option A — AlgoVoi Cloud (recommended)

[AlgoVoi Cloud](https://dash.algovoi.co.uk) is the control plane for all your integrations — WooCommerce, Zapier, n8n, and MCP all in one dashboard. Point `ALGOVOI_API_BASE` at `https://cloud.algovoi.co.uk` and your single `algv_...` API key covers every integration — no tenant ID or payout addresses needed (they're stored in the dashboard).

```json
{
  "mcpServers": {
    "algovoi": {
      "command": "npx",
      "args": ["-y", "@algovoi/mcp-server"],
      "env": {
        "ALGOVOI_API_KEY": "algv_...",
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
| `ALGOVOI_API_BASE` | — | Override the AlgoVoi API base URL (default: `https://cloud.algovoi.co.uk`) |

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
# TypeScript unit tests (77/77)
cd typescript && npm test

# Python unit tests (85/85)
cd python && pytest

# Stdio integration smoke — boots both servers and confirms all 13 tools list
python smoke_stdio.py
```

---

Licensed under the [Business Source License 1.1](../LICENSE).
