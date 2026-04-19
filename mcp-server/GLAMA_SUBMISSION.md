# Glama.ai Submission — AlgoVoi

Submit at **https://glama.ai/mcp/servers/add**. Copy-paste ready.

---

### GitHub repository URL
```
https://github.com/chopmob-cloud/AlgoVoi-Platform-Adapters
```

### Display name
```
AlgoVoi MCP Server
```

### Short description
```
Accept crypto payments on Algorand, VOI, Hedera & Stellar. Create hosted checkout links, verify on-chain payments, and generate MPP/x402/AP2 challenges from any MCP client. Supports all 16 AlgoVoi networks (USDC + native on mainnet + testnet).
```

### Category (if asked)
```
Payments / Finance
```

### Optional tags
```
payments, crypto, algorand, stellar, hedera, usdc, agent-commerce, x402, mpp, ap2
```

---

## What Glama will auto-detect

Glama runs license detection, security scan, and a health test during indexing. Ours should pass cleanly:

- **License**: BUSL-1.1 (documented in `LICENSE` at repo root)
- **Security**: no secrets in repo, `.gitignore` covers keys + env files, 158-commit history scrubbed of `cloud/` and `grants/`
- **Health test**: npm package `@algovoi/mcp-server` v1.1.1 has 65/65 passing tests

## After submission

- Glama's quality checks usually complete within minutes
- Listing appears at `https://glama.ai/mcp/servers/chopmob-cloud/algovoi-platform-adapters` (or similar auto-slug)
- Escalation via Discord if indexing stalls

## If Glama asks for a `glama.json`

Since our repo is a monorepo and the MCP server lives under `mcp-server/`, Glama may want disambiguation. If prompted, we can add `glama.json` at repo root pointing at the subdirectory. Hold off until asked — don't guess the schema without docs.
