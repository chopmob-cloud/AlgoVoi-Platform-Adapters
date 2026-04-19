# MCP.so Submission — AlgoVoi

Fill the form at **https://mcp.so/submit** with these values. Copy-paste ready.

---

### Name
```
AlgoVoi MCP Server
```

### URL (GitHub repo)
```
https://github.com/chopmob-cloud/AlgoVoi-Platform-Adapters/tree/master/mcp-server
```

### Description (if the form has one)
```
Accept crypto payments on Algorand, VOI, Hedera & Stellar from any MCP client (Claude Desktop, Cursor, Windsurf). Create hosted checkout links, verify on-chain payments, generate MPP/x402/AP2 challenges. Supports all 16 AlgoVoi networks: USDC + native tokens on mainnet and testnet. Routes through AlgoVoi Cloud (managed payouts) or direct API.
```

### Category / Tags (if present)
```
payment, crypto, algorand, stellar, hedera, usdc, agent-commerce, x402, mpp, ap2
```

### Server Config (JSON — paste verbatim)

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

### Additional (if form asks)

| Field | Value |
|---|---|
| Author / Owner | chopmob-cloud |
| License | BUSL-1.1 |
| Transport | stdio |
| npm | https://www.npmjs.com/package/@algovoi/mcp-server |
| PyPI | https://pypi.org/project/algovoi-mcp/ |
| Official MCP Registry | `io.github.chopmob-cloud/algovoi-mcp-server` |
| Icon URL | https://github.com/chopmob-cloud/AlgoVoi-Platform-Adapters/raw/master/shared/logo/algovoi-mark-256.png |

---

## After submission

- MCP.so aggregates user submissions manually; listing typically appears within 24–72 hours
- No email confirmation — check https://mcp.so/server/algovoi or search for "algovoi" to verify
- If not indexed within a week, follow up via their [Discord](https://discord.gg/RsYPRrnyqg) or [Telegram](https://t.me/+N0gv4O9SXio2YWU1)
